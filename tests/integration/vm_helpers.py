"""Talks to the oplx-tools-integration-test Tart VM.

Encapsulates the open-export-pull pipeline proven in Phase A:

    1. scp the .oplx to /tmp/ in the VM
    2. AppleScript: close all docs, open the new one
    3. AppleScript via System Events: click View → Gantt View (image exports
       fail otherwise — see vm_helpers.SWITCH_VIEW_AS for details)
    4. AppleScript: export to CSV, PDF, PNG
    5. scp the artifacts back

Requires the VM to be running with these one-time TCC grants:
    Screen Recording  → /usr/sbin/screencapture
                      → /usr/libexec/sshd-keygen-wrapper
                      → python3.x
    Accessibility     → /usr/libexec/sshd-keygen-wrapper
Plus the runtime "bypass screen-capture private window picker" dialog
must have been accepted once per binary. And a VNC client must be
attached during runs (Screen Sharing.app on the host) — without an
observer, the WindowServer leaves document windows uncomposited and
image exports fail. See tests/integration/README.md for the full
setup procedure.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


VM_NAME = "oplx-tools-integration-test"
VM_USER = "admin"
VM_TMP = "/tmp"
SSH_KEY = Path.home() / ".ssh" / "tart_vm_key"


@dataclass(frozen=True)
class OmniPlanVersion:
    """Bakes into golden-file paths so a version bump doesn't silently
    invalidate the test suite."""

    short_version: str  # e.g. "4.10.2"
    bundle_version: str  # e.g. "232.5.0"
    macos_version: str  # e.g. "15.7.3"

    @property
    def golden_subdir(self) -> str:
        """Filesystem-safe slug for the golden/ subdirectory."""
        return f"omniplan-{self.short_version}-build-{self.bundle_version}"


@dataclass
class ExportArtifacts:
    """Paths to the artifacts pulled back from the VM after one fixture run."""

    csv: Path
    pdf: Path
    png: Path


# AppleScript to switch the front OmniPlan window to Gantt View. Required
# before image exports (PDF/PNG/TIFF/JPEG) — image-type exports otherwise
# fail with: "Exporting image types of this view is unsupported. (6)".
# Uses System Events menu click rather than a keystroke because keystrokes
# require the document's outline area to have key focus, which isn't
# guaranteed after an AppleScript `open`.
SWITCH_VIEW_AS = (
    'tell application "OmniPlan" to activate\n'
    "delay 1\n"
    'tell application "System Events" to tell process "OmniPlan" to '
    'click menu item "Gantt View" of menu "View" of menu bar 1'
)


def _ssh_target() -> str:
    """admin@<vm-ip> for scp/ssh."""
    ip = subprocess.check_output(
        ["tart-vm", "ip", VM_NAME], text=True
    ).strip()
    return f"{VM_USER}@{ip}"


def _ssh(cmd: str, *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a shell command in the VM via tart-vm ssh."""
    return subprocess.run(
        ["tart-vm", "ssh", VM_NAME, cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _scp_to_vm(local: Path, vm_path: str) -> None:
    target = _ssh_target()
    subprocess.run(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-q",
            str(local),
            f"{target}:{vm_path}",
        ],
        check=True,
        timeout=30,
    )


def _scp_from_vm(vm_path: str, local: Path) -> None:
    target = _ssh_target()
    subprocess.run(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-q",
            f"{target}:{vm_path}",
            str(local),
        ],
        check=True,
        timeout=30,
    )


def _osascript(script: str, *, timeout: int = 30) -> str:
    """Run AppleScript in the VM. Returns stdout, raises on stderr."""
    quoted = shlex.quote(script)
    proc = _ssh(f"osascript -e {quoted}", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"AppleScript failed: {proc.stderr.strip()}\nscript:\n{script}"
        )
    return proc.stdout


def detect_omniplan_version() -> OmniPlanVersion:
    """Read OmniPlan + macOS versions from the running VM."""
    short = _ssh(
        "defaults read /Applications/OmniPlan.app/Contents/Info "
        "CFBundleShortVersionString"
    ).stdout.strip()
    build = _ssh(
        "defaults read /Applications/OmniPlan.app/Contents/Info CFBundleVersion"
    ).stdout.strip()
    macos = _ssh("sw_vers -productVersion").stdout.strip()
    if not (short and build and macos):
        raise RuntimeError(
            f"could not read versions from VM (short={short!r}, "
            f"build={build!r}, macos={macos!r})"
        )
    return OmniPlanVersion(
        short_version=short, bundle_version=build, macos_version=macos
    )


def reset_omniplan() -> None:
    """Close every open document — fresh state per fixture."""
    _osascript('tell application "OmniPlan" to close every document saving no')


def open_document(vm_path: str) -> None:
    """Open `.oplx` at `vm_path` in OmniPlan and wait for it to settle."""
    _osascript(f'tell application "OmniPlan" to open POSIX file "{vm_path}"')
    _ssh("sleep 4")  # let the doc finish opening + compositor catch up


def switch_to_gantt_view() -> None:
    """Click View → Gantt View. Required before image-type exports."""
    _osascript(SWITCH_VIEW_AS, timeout=20)
    _ssh("sleep 2")


def export_document(*, vm_path: str, fmt: str, properties: str = "") -> None:
    """Export front document. fmt is one of: PDF, PNG, TIFF, JPEG, CSV, MSPDI,
    "HTML Task List", "HTML Resource List", "HTML Full Report", OmniGraffle.
    `properties` is a raw AppleScript record body (e.g. `{views to include:both
    views}`) — empty for formats that don't need it."""
    props = f" with properties {properties}" if properties else ""
    _osascript(
        f'tell application "OmniPlan" to export front document '
        f'to POSIX file "{vm_path}" as "{fmt}"{props}',
        timeout=30,
    )


def run_fixture(name: str, local_oplx: Path, *, work_dir: Path) -> ExportArtifacts:
    """End-to-end: push, open, switch view, export all 3 formats, pull.

    `work_dir` is where artifacts are written on the host (tests/integration/
    artifacts/<run-id>/<name>/).
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    vm_oplx = f"{VM_TMP}/{name}.oplx"
    vm_csv = f"{VM_TMP}/{name}.csv"
    vm_pdf = f"{VM_TMP}/{name}.pdf"
    vm_png = f"{VM_TMP}/{name}.png"

    # Clean leftover state from a previous run on the VM
    _ssh(f"rm -f {vm_oplx} {vm_csv} {vm_pdf} {vm_png}")

    _scp_to_vm(local_oplx, vm_oplx)
    reset_omniplan()
    open_document(vm_oplx)
    switch_to_gantt_view()

    # CSV first — independent of view state, validates the scheduler ran
    export_document(vm_path=vm_csv, fmt="CSV", properties="{show all rows:true}")
    # PDF + PNG — view-dependent
    export_document(
        vm_path=vm_pdf, fmt="PDF", properties="{views to include:both views}"
    )
    export_document(
        vm_path=vm_png, fmt="PNG", properties="{views to include:both views}"
    )

    artifacts = ExportArtifacts(
        csv=work_dir / f"{name}.csv",
        pdf=work_dir / f"{name}.pdf",
        png=work_dir / f"{name}.png",
    )
    _scp_from_vm(vm_csv, artifacts.csv)
    _scp_from_vm(vm_pdf, artifacts.pdf)
    _scp_from_vm(vm_png, artifacts.png)
    return artifacts


def pdf_to_text(pdf: Path) -> str:
    """Extract text content from a PDF for diff-based assertions.

    Uses `pdftotext` (poppler) on the host. Output is OS-independent
    once normalized — strips whitespace runs and trims edges.
    """
    out = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
    # Normalize: collapse runs of whitespace, trim per-line
    return "\n".join(re.sub(r"\s+", " ", line).strip() for line in out.splitlines())


def normalize_csv(csv: Path) -> str:
    """Read a CSV and return a normalized, line-sorted-by-WBS string.

    OmniPlan's CSV export embeds locale-dependent date formatting and may
    reorder columns trivially — normalizing here gives stable diffs.
    """
    text = csv.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
