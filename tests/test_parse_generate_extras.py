"""Cover parse/generate features not exercised by the basic roundtrip.

Targets parse.py and generate.py branches: notes, resources, schedules,
constraint dates, custom data, baselines, milestone effort omission,
PERT estimates, recalculate=effort with fixed-duration, percentage
lead-time round-trip, naive-datetime rejection, etc.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from oplx.generate import _iso, from_yaml, generate
from oplx.models import (
    Assignment,
    CustomData,
    Dependency,
    DependencyKind,
    LeadTime,
    Note,
    Project,
    Recalculate,
    Resource,
    ResourceSchedule,
    ResourceType,
    Scenario,
    ScheduleDay,
    Task,
    TaskType,
    TimeSpan,
)
from oplx.parse import parse


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[arg-type]


def test_iso_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        _iso(datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001


def test_iso_converts_non_utc_to_utc() -> None:
    """A NYC 13:00 datetime must serialize as 18:00Z (EST) or 17:00Z (EDT),
    not 13:00Z. Without UTC normalization the dt.astimezone(dt.tzinfo) was a
    no-op and the file silently lied about the absolute instant.
    """
    from zoneinfo import ZoneInfo

    nyc = ZoneInfo("America/New_York")
    # June 1 is EDT (UTC-4), so 13:00 EDT = 17:00 UTC
    result = _iso(datetime(2026, 6, 1, 13, 0, tzinfo=nyc))
    assert result == "2026-06-01T17:00:00.000Z", result

    # Same wall-clock in UTC stays as 13:00Z
    result_utc = _iso(datetime(2026, 6, 1, 13, 0, tzinfo=UTC))
    assert result_utc == "2026-06-01T13:00:00.000Z", result_utc


def test_lead_time_rejects_both_seconds_and_fraction() -> None:
    with pytest.raises(ValueError):
        LeadTime(seconds=10, fraction=Decimal("0.1"))


def test_generate_rich_project_bundle_roundtrip(tmp_path: Path) -> None:
    """A scenario exercising notes, resources, assignments, custom data."""
    bob = Resource(
        id="r1",
        name="Bob",
        type=ResourceType.STAFF,
        note=Note(text="Hire date 2026-01-15\nLevel 5"),
        cost_per_hour=Decimal("125.50"),
        cost_per_use=Decimal("0"),
        units_available=Decimal("1"),
        efficiency=Decimal("0.9"),
        email="bob@example.com",
        schedule=ResourceSchedule(
            days=[
                ScheduleDay(
                    day_of_week="monday",
                    time_spans=[TimeSpan(start_seconds=32400, end_seconds=61200)],
                )
            ]
        ),
        custom_data=CustomData(values={"team": "alpha"}),
    )
    actual = Scenario(
        id="rich-001",
        start_date=_utc(2026, 6, 1, 13, 0),
        end_date=_utc(2026, 7, 1, 17, 0),
        fixed_end=True,
        granularity="hours",
        resources=[bob],
        tasks=[
            Task(
                id="t1",
                title="Plan",
                effort=14400,
                effort_done=3600,
                priority=5,
                note=Note(text="kickoff meeting required"),
                static_cost=Decimal("250.00"),
                locked_start_date=_utc(2026, 6, 1, 14, 0),
                start_no_earlier_than=_utc(2026, 6, 1, 13, 0),
                start_no_later_than=_utc(2026, 6, 2, 13, 0),
                end_no_earlier_than=_utc(2026, 6, 1, 17, 0),
                end_no_later_than=_utc(2026, 6, 3, 17, 0),
                assignments=[Assignment(resource_idref="r1", units=Decimal("0.5"))],
                custom_data=CustomData(values={"work_package": "WP-1"}),
            ),
            Task(
                id="t2",
                title="Estimate",
                effort=28800,
                min_estimate=14400,
                expected_estimate=28800,
                max_estimate=57600,
                recalculate=Recalculate.EFFORT,
                fixed_duration=86400,
                prerequisites=[
                    Dependency(
                        idref="t1",
                        kind=DependencyKind.START_START,
                        lead_time=LeadTime(fraction=Decimal("0.25")),
                    ),
                ],
                assignments=[
                    Assignment(resource_idref="r1"),  # default 1.0
                    Assignment(
                        resource_idref="r-skip", units=Decimal("0")
                    ),  # silently skipped
                ],
            ),
            Task(
                id="t3",
                title="Ship",
                type=TaskType.MILESTONE,
                effort=99999,  # should be omitted by generator
                prerequisites=[Dependency(idref="t2")],
            ),
        ],
    )
    baseline = Scenario(
        id="bsl-001",
        name="Baseline1",
        filename="Baseline1.xml",
        start_date=_utc(2026, 5, 1, 13, 0),
        tasks=[Task(id="t1", title="Plan", effort=14400)],
    )
    proj = Project(
        title="Rich",
        actual=actual,
        baselines=[baseline],
        custom_data_keys=["work_package", "team"],
        next_task_id=10,
        next_resource_id=5,
    )

    # Bundle variant exercises the directory-write branch
    out_dir = tmp_path / "rich.oplx"
    generate(proj, out_dir, bundle=True)
    assert (out_dir / "__TOC.xml").exists()
    assert (out_dir / "Actual.xml").exists()
    assert (out_dir / "Baseline1.xml").exists()

    parsed = parse(out_dir)
    assert parsed.actual.granularity == "hours"
    assert parsed.actual.end_date is not None
    assert parsed.actual.fixed_end is True
    assert len(parsed.baselines) == 1
    assert parsed.baselines[0].filename == "Baseline1.xml"

    # Bob roundtripped
    bob_p = next(r for r in parsed.actual.resources if r.name == "Bob")
    assert bob_p.type == ResourceType.STAFF
    assert bob_p.email == "bob@example.com"
    assert bob_p.cost_per_hour == Decimal("125.5")
    assert bob_p.efficiency == Decimal("0.9")
    assert bob_p.note is not None and "Hire date" in bob_p.note.text
    assert bob_p.custom_data.values == {"team": "alpha"}
    assert bob_p.schedule is not None
    assert bob_p.schedule.days[0].day_of_week == "monday"

    # t1 task fully roundtrips
    t1_p = next(t for t in parsed.actual.tasks if t.title == "Plan")
    assert t1_p.priority == 5
    assert t1_p.effort_done == 3600
    assert t1_p.note is not None and "kickoff" in t1_p.note.text
    assert t1_p.static_cost == Decimal("250")
    assert t1_p.locked_start_date is not None
    assert t1_p.start_no_earlier_than is not None
    assert t1_p.end_no_later_than is not None
    assert t1_p.custom_data.values == {"work_package": "WP-1"}
    assert t1_p.assignments[0].units == Decimal("0.5")

    # t2: 3-pt estimates, recalculate=effort with fixed-duration, SS dep with %
    t2_p = next(t for t in parsed.actual.tasks if t.title == "Estimate")
    assert t2_p.min_estimate == 14400
    assert t2_p.expected_estimate == 28800
    assert t2_p.max_estimate == 57600
    assert t2_p.recalculate == Recalculate.EFFORT
    assert t2_p.prerequisites[0].kind == DependencyKind.START_START
    assert t2_p.prerequisites[0].lead_time is not None
    assert t2_p.prerequisites[0].lead_time.fraction == Decimal("0.25")
    # units=0 assignment was dropped
    assert all(a.resource_idref != "r-skip" for a in t2_p.assignments)
    # default units=1.0 reads back
    assert any(a.resource_idref == "r1" and a.units == Decimal("1.0") for a in t2_p.assignments)

    # t3 milestone: effort omitted on write -> reads back as None
    t3_p = next(t for t in parsed.actual.tasks if t.title == "Ship")
    assert t3_p.type == TaskType.MILESTONE
    assert t3_p.effort is None


def test_from_yaml_accepts_iso_string() -> None:
    """When PyYAML doesn't auto-parse the date, the str branch runs."""
    proj = from_yaml(
        "title: y\nstart_date: '2026-06-01T13:00:00Z'\ntasks:\n  - id: t1\n    title: a\n    effort: 60\n"
    )
    assert proj.actual.start_date is not None
    assert proj.actual.start_date.tzinfo is not None


def test_from_yaml_naive_datetime_is_assumed_utc() -> None:
    """PyYAML returns a naive datetime for '2026-06-01T13:00:00' — we tz-add."""
    proj = from_yaml(
        "tasks: []\nstart_date: 2026-06-01T13:00:00\n"
    )
    assert proj.actual.start_date is not None
    assert proj.actual.start_date.tzinfo is not None


def test_parse_handles_negative_id_prototypes_passed_through(tmp_path: Path) -> None:
    """Tasks with ids like 't-1' are root/prototype — orphan check skips them."""
    proj = Project(
        actual=Scenario(
            id="proto",
            start_date=_utc(2026, 6, 1, 13, 0),
            tasks=[Task(id="t1", title="x", effort=60)],
        )
    )
    out = tmp_path / "p.oplx"
    generate(proj, out)
    parsed = parse(out)
    # Generator auto-creates root group t-1; parser must read it
    ids = {t.id for t in parsed.actual.tasks}
    assert "t-1" in ids
    assert "t1" in ids
