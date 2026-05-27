"""Pytest configuration for the integration suite.

These tests require the `oplx-tools-integration-test` Tart VM running, with
OmniPlan installed + TCC granted + a VNC client attached. See README.md.

Marked `integration` and SKIPPED by default — `uv run pytest` runs only the
unit tests. To run the integration suite:

    uv run pytest -m integration

To regenerate goldens (after intentional rendering / output changes):

    UPDATE_GOLDENS=1 uv run pytest -m integration
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from . import vm_helpers


INTEGRATION_DIR = Path(__file__).parent
GOLDEN_BASE = INTEGRATION_DIR / "golden"
ARTIFACTS_BASE = INTEGRATION_DIR / "artifacts"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless explicitly requested via -m integration."""
    if config.getoption("-m") and "integration" in config.getoption("-m"):
        return
    skip = pytest.mark.skip(reason="integration tests require VM — run with `-m integration`")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def omniplan_version() -> vm_helpers.OmniPlanVersion:
    """Detect OmniPlan + macOS versions once per pytest session.

    The version is baked into the golden path so a version bump
    doesn't silently invalidate the suite — it just makes the new
    version's goldens not exist yet, prompting a re-baseline.
    """
    return vm_helpers.detect_omniplan_version()


@pytest.fixture(scope="session")
def golden_dir(omniplan_version: vm_helpers.OmniPlanVersion) -> Path:
    """Per-OmniPlan-version golden directory."""
    p = GOLDEN_BASE / omniplan_version.golden_subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(scope="session")
def run_dir(omniplan_version: vm_helpers.OmniPlanVersion) -> Path:
    """Per-run artifacts directory. Persisted on test failure for inspection;
    cleaned on every fresh `-m integration` run."""
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    p = ARTIFACTS_BASE / f"{omniplan_version.golden_subdir}_{stamp}"
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture(scope="session")
def update_goldens() -> bool:
    return os.environ.get("UPDATE_GOLDENS") == "1"


@pytest.fixture(scope="session", autouse=True)
def vm_session_setup(omniplan_version: vm_helpers.OmniPlanVersion) -> None:
    """Once per session: log the VM identity and the OmniPlan version so
    test reports carry the lineage."""
    print(
        f"\n[integration] VM={vm_helpers.VM_NAME} "
        f"OmniPlan={omniplan_version.short_version} "
        f"(build {omniplan_version.bundle_version}) "
        f"macOS={omniplan_version.macos_version}"
    )
