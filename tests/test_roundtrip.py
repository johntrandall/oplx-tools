"""Round-trip tests: generate → parse → expect same data."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from oplx import (
    Assignment,
    Dependency,
    Project,
    Resource,
    Task,
    generate,
    lint,
    parse,
)
from oplx.models import (
    DependencyKind,
    LeadTime,
    Note,
    Recalculate,
    ResourceType,
    Scenario,
    TaskType,
)


def _build_simple_project() -> Project:
    actual = Scenario(
        id="test-001",
        start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
        tasks=[
            Task(id="t1", title="Plan", effort=14400),
            Task(
                id="t2",
                title="Build",
                effort=28800,
                prerequisites=[Dependency(idref="t1")],
            ),
            Task(
                id="t3",
                title="Ship",
                type=TaskType.MILESTONE,
                prerequisites=[Dependency(idref="t2")],
            ),
        ],
    )
    return Project(actual=actual)


def test_minimum_viable_roundtrip(tmp_path: Path) -> None:
    proj = _build_simple_project()
    out = tmp_path / "test.oplx"
    generate(proj, out)
    assert out.exists()
    assert out.is_file()  # zip variant by default

    # No lint findings on our own output
    findings = lint(out)
    blockers = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
    assert blockers == [], f"Generator produces blocker-level lint findings: {blockers}"

    # Round-trip: parse the generated file, verify task structure
    parsed = parse(out)
    assert len(parsed.actual.tasks) >= 3
    titles = {t.title for t in parsed.actual.tasks if not t.id.startswith("t-")}
    assert titles == {"Plan", "Build", "Ship"}


def test_dependency_kind_roundtrip(tmp_path: Path) -> None:
    proj = Project(
        actual=Scenario(
            id="dep-001",
            start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
            tasks=[
                Task(id="t1", title="Source", effort=3600),
                Task(
                    id="t2",
                    title="Target",
                    effort=3600,
                    prerequisites=[
                        Dependency(idref="t1", kind=DependencyKind.FINISH_FINISH),
                    ],
                ),
            ],
        )
    )
    out = tmp_path / "deps.oplx"
    generate(proj, out)

    parsed = parse(out)
    target = next(t for t in parsed.actual.tasks if t.title == "Target")
    assert len(target.prerequisites) == 1
    assert target.prerequisites[0].kind == DependencyKind.FINISH_FINISH


def test_lead_time_duration_roundtrip(tmp_path: Path) -> None:
    proj = Project(
        actual=Scenario(
            id="lt-001",
            start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
            tasks=[
                Task(id="t1", title="Source", effort=3600),
                Task(
                    id="t2",
                    title="Target",
                    effort=3600,
                    prerequisites=[
                        Dependency(idref="t1", lead_time=LeadTime(seconds=1800)),
                    ],
                ),
            ],
        )
    )
    out = tmp_path / "lt.oplx"
    generate(proj, out)

    parsed = parse(out)
    target = next(t for t in parsed.actual.tasks if t.title == "Target")
    assert target.prerequisites[0].lead_time is not None
    assert target.prerequisites[0].lead_time.seconds == 1800


def test_lead_time_percentage_uses_fraction(tmp_path: Path) -> None:
    """omniJS takes integer percent, but the XML form is fraction.

    Our model and YAML/dict input use fraction (matching XML). This test
    verifies we don't accidentally apply the omniJS convention here.
    """
    proj = Project(
        actual=Scenario(
            id="ltp-001",
            start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
            tasks=[
                Task(id="t1", title="Source", effort=3600),
                Task(
                    id="t2",
                    title="Target",
                    effort=3600,
                    prerequisites=[
                        Dependency(idref="t1", lead_time=LeadTime(fraction=Decimal("0.25"))),
                    ],
                ),
            ],
        )
    )
    out = tmp_path / "ltp.oplx"
    generate(proj, out)

    parsed = parse(out)
    target = next(t for t in parsed.actual.tasks if t.title == "Target")
    assert target.prerequisites[0].lead_time is not None
    assert target.prerequisites[0].lead_time.fraction == Decimal("0.25")


def test_lint_catches_uppercase_type() -> None:
    """Manually build an .oplx with <type>MILESTONE</type> and verify lint flags it."""
    import zipfile

    actual_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<scenario xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2" id="bad-001">
  <start-date>2026-06-01T13:00:00.000Z</start-date>
  <top-resource idref="r-1"/>
  <resource id="r-1"><name>Project</name><type>Project</type></resource>
  <top-task idref="t-1"/>
  <task id="t-1">
    <type>group</type>
    <recalculate>duration</recalculate>
    <static-cost>0</static-cost>
    <child-task idref="t1"/>
  </task>
  <task id="t1">
    <title>Bad uppercase milestone</title>
    <type>MILESTONE</type>
    <recalculate>duration</recalculate>
    <static-cost>0</static-cost>
  </task>
</scenario>
"""
    toc_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<omniplan xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2" file-format-version="3">
  <project>
    <next-task-id>2</next-task-id>
    <next-resource-id>2</next-resource-id>
    <scenario id="bad-001" name="Actual" filename="Actual.xml"/>
  </project>
</omniplan>
"""
    changelog_xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<changelog xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2">'
        b"<version>4.0</version></changelog>"
    )

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".oplx", delete=False) as tf:
        with zipfile.ZipFile(tf.name, "w") as z:
            z.writestr("__TOC.xml", toc_xml)
            z.writestr("__changelog.xml", changelog_xml)
            z.writestr("Actual.xml", actual_xml)

        findings = lint(tf.name)

    type_case_findings = [f for f in findings if f.code == "TYPE-CASE"]
    assert len(type_case_findings) == 1
    assert type_case_findings[0].severity == "CRITICAL"
