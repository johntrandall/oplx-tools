"""Lint an .oplx (zip or directory) against the format spec.

Catches silent-corruption patterns (uppercase <type>, lowercase kind=,
units="0", orphaned tasks, etc.) before they reach OmniPlan.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lxml import etree

NS = "http://www.omnigroup.com/namespace/OmniPlan/v2"
NSMAP = {"opns": NS}

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


@dataclass
class LintFinding:
    severity: Severity
    code: str
    message: str
    location: str | None = None  # e.g., "Actual.xml:123"

    def __str__(self) -> str:
        loc = f" [{self.location}]" if self.location else ""
        return f"{self.severity} {self.code}{loc}: {self.message}"


VALID_TASK_TYPES = {"task", "milestone", "group", "hammock"}
VALID_DEP_KINDS = {"FS", "FF", "SS", "SF"}  # FS is default-omitted; others must be uppercase
VALID_RECALCULATE = {"duration", "effort", "units"}
VALID_RESOURCE_TYPES_XML = {"Staff", "Equipment", "Material", "Group", "Project"}


def _read_xml(source: Path | zipfile.ZipFile, name: str) -> etree._Element | None:
    """Read an XML file from either a directory or a zip."""
    if isinstance(source, zipfile.ZipFile):
        try:
            with source.open(name) as f:
                return etree.parse(f).getroot()
        except KeyError:
            return None
    else:
        path = source / name
        if not path.exists():
            return None
        return etree.parse(str(path)).getroot()


def lint(oplx_path: str | Path) -> list[LintFinding]:
    """Lint an .oplx file (zip or directory bundle).

    Returns a list of LintFinding objects. Empty list = no issues.
    """
    p = Path(oplx_path)
    findings: list[LintFinding] = []

    # Open as zip or directory
    is_zip = p.is_file()
    source: zipfile.ZipFile | Path
    if is_zip:
        source = zipfile.ZipFile(p, "r")
    elif p.is_dir():
        source = p
    else:
        return [LintFinding("CRITICAL", "FILE-NOT-FOUND", f"Path does not exist: {p}")]

    try:
        # Required files
        toc = _read_xml(source, "__TOC.xml")
        changelog = _read_xml(source, "__changelog.xml")
        actual = _read_xml(source, "Actual.xml")

        if toc is None:
            findings.append(LintFinding("CRITICAL", "MISSING-TOC", "__TOC.xml is missing"))
        if changelog is None:
            findings.append(
                LintFinding("CRITICAL", "MISSING-CHANGELOG", "__changelog.xml is missing")
            )
        if actual is None:
            findings.append(
                LintFinding("CRITICAL", "MISSING-ACTUAL", "Actual.xml is missing")
            )

        if actual is not None:
            findings.extend(_lint_scenario(actual, "Actual.xml"))

        # Lint each baseline scenario
        if toc is not None:
            for sc_el in toc.findall(f".//{{{NS}}}scenario"):
                fn = sc_el.get("filename")
                if fn and fn != "Actual.xml":
                    bs = _read_xml(source, fn)
                    if bs is None:
                        findings.append(
                            LintFinding(
                                "HIGH",
                                "MISSING-BASELINE-FILE",
                                f"__TOC.xml references {fn} but it's not in the bundle",
                            )
                        )
                    else:
                        findings.extend(_lint_scenario(bs, fn))
    finally:
        if is_zip:
            assert isinstance(source, zipfile.ZipFile)
            source.close()

    return findings


def _lint_scenario(scenario: etree._Element, file_label: str) -> list[LintFinding]:
    findings: list[LintFinding] = []

    # Task type case-sensitivity
    for type_el in scenario.findall(f".//{{{NS}}}task/{{{NS}}}type"):
        v = (type_el.text or "").strip()
        if v and v not in VALID_TASK_TYPES:
            if v.lower() in VALID_TASK_TYPES:
                findings.append(
                    LintFinding(
                        "CRITICAL",
                        "TYPE-CASE",
                        f"<type>{v}</type> uses wrong case — must be lowercase. "
                        f"This causes the entire document to fail to open silently.",
                        f"{file_label}",
                    )
                )
            else:
                findings.append(
                    LintFinding(
                        "MEDIUM",
                        "TYPE-INVALID",
                        f"<type>{v}</type> is not a valid task type "
                        f"(expected one of {sorted(VALID_TASK_TYPES)})",
                        f"{file_label}",
                    )
                )

    # Resource type case-sensitivity
    for type_el in scenario.findall(f".//{{{NS}}}resource/{{{NS}}}type"):
        v = (type_el.text or "").strip()
        if v and v not in VALID_RESOURCE_TYPES_XML:
            findings.append(
                LintFinding(
                    "MEDIUM",
                    "RESOURCE-TYPE-INVALID",
                    f"<type>{v}</type> on resource — expected capitalized form like 'Staff'",
                    f"{file_label}",
                )
            )

    # Dependency kind case-sensitivity
    for prereq in scenario.findall(f".//{{{NS}}}prerequisite-task"):
        kind = prereq.get("kind")
        if kind is not None and kind not in VALID_DEP_KINDS:
            findings.append(
                LintFinding(
                    "MEDIUM",
                    "DEP-KIND-CASE",
                    f'kind="{kind}" — must be uppercase FS|FF|SS|SF. '
                    f"Lowercase or invalid values are silently stripped, "
                    f"defaulting the dependency to Finish-Start.",
                    f"{file_label}",
                )
            )

    # <recalculate> values
    for rc_el in scenario.findall(f".//{{{NS}}}recalculate"):
        v = (rc_el.text or "").strip()
        if v and v not in VALID_RECALCULATE:
            findings.append(
                LintFinding(
                    "MEDIUM",
                    "RECALCULATE-INVALID",
                    f"<recalculate>{v}</recalculate> — only "
                    f"{sorted(VALID_RECALCULATE)} are valid; others normalize to 'duration'",
                    f"{file_label}",
                )
            )

    # Assignment units="0"
    for assn in scenario.findall(f".//{{{NS}}}assignment"):
        units = assn.get("units")
        if units == "0" or units == "0.0":
            findings.append(
                LintFinding(
                    "HIGH",
                    "UNITS-ZERO",
                    f'<assignment units="0"/> — setting units to 0 REMOVES the assignment '
                    f"on save. Omit the assignment instead, or use a small positive value.",
                    f"{file_label}",
                )
            )

    # Orphaned task check (every <task id="tN"> must be reachable from <top-task>)
    findings.extend(_check_task_reachability(scenario, file_label))

    return findings


def _check_task_reachability(
    scenario: etree._Element, file_label: str
) -> list[LintFinding]:
    findings: list[LintFinding] = []

    top_task = scenario.find(f"{{{NS}}}top-task")
    if top_task is None:
        return findings  # not our problem here

    root_id = top_task.get("idref")
    if not root_id:
        return findings

    # Build map of task_id -> task element
    all_tasks: dict[str, etree._Element] = {}
    for t in scenario.findall(f"{{{NS}}}task"):
        tid = t.get("id")
        if tid:
            all_tasks[tid] = t

    if root_id not in all_tasks:
        findings.append(
            LintFinding(
                "HIGH",
                "ROOT-TASK-MISSING",
                f"<top-task idref={root_id}/> but no matching <task id={root_id}/>",
                file_label,
            )
        )
        return findings

    # BFS from root
    reachable: set[str] = set()
    queue = [root_id]
    while queue:
        tid = queue.pop()
        if tid in reachable:
            continue
        reachable.add(tid)
        task = all_tasks.get(tid)
        if task is None:
            continue
        for child in task.findall(f"{{{NS}}}child-task"):
            child_id = child.get("idref")
            if child_id:
                queue.append(child_id)

    # Tasks defined but not reachable (excluding negative-id prototype/root tasks)
    for tid in all_tasks:
        if tid not in reachable and not tid.startswith("t-"):
            findings.append(
                LintFinding(
                    "HIGH",
                    "ORPHANED-TASK",
                    f"Task {tid!r} is defined but not reachable from <top-task>. "
                    f"OmniPlan will silently drop it on save.",
                    file_label,
                )
            )

    return findings
