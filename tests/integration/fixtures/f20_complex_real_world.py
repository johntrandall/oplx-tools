"""Kitchen-sink: multi-resource project with groups, milestones,
mixed dep kinds, lead times, costs, notes, and constraints.

Catches: emergent interactions between features that individual
fixtures miss. If this opens cleanly and matches its golden, the
overall pipeline is healthy.

Note: user task ids start at `t2`, not `t1` — see f07 docstring for
the OmniPlan-reader collision rationale. All ids follow the t<digits>
convention required by lint code `TASK-ID-NUMBERING` (Verified
2026-05-27: non-conforming ids like `m1`/`g1` cause OmniPlan to
silently drop sibling tasks from the rendered tree).
"""

from decimal import Decimal

from oplx import (
    Assignment,
    Dependency,
    Project,
    Resource,
    Scenario,
    Task,
)
from oplx.models import (
    DependencyKind,
    LeadTime,
    Note,
    Recalculate,
    ResourceType,
    TaskType,
)

from ._builders import START, utc

NAME = "f20_complex_real_world"


def build() -> Project:
    alice = Resource(
        id="r2",
        name="Alice",
        type=ResourceType.STAFF,
        cost_per_hour=Decimal("125.00"),
        email="alice@example.com",
    )
    bob = Resource(
        id="r3",
        name="Bob",
        type=ResourceType.STAFF,
        cost_per_hour=Decimal("100.00"),
        email="bob@example.com",
    )
    aws = Resource(
        id="r4",
        name="AWS bill",
        type=ResourceType.MATERIAL,
        cost_per_use=Decimal("200.00"),
    )

    actual = Scenario(
        id="auto",
        start_date=START,
        end_date=utc(2026, 7, 1, 17, 0),
        resources=[alice, bob, aws],
        tasks=[
            Task(id="t2", title="Kickoff", type=TaskType.MILESTONE),
            Task(
                id="t3",
                title="Design phase",
                type=TaskType.GROUP,
                subtask_ids=["t4", "t5"],
            ),
            Task(
                id="t4",
                title="Architecture",
                effort=28800,
                priority=8,
                static_cost=Decimal("500.00"),
                note=Note(text="ADR template required."),
                prerequisites=[Dependency(idref="t2")],
                assignments=[Assignment(resource_idref="r2")],
            ),
            Task(
                id="t5",
                title="Schema review",
                effort=14400,
                prerequisites=[
                    Dependency(idref="t4", kind=DependencyKind.START_START,
                               lead_time=LeadTime(seconds=3600)),
                ],
                assignments=[Assignment(resource_idref="r3", units=Decimal("0.5"))],
            ),
            Task(
                id="t6",
                title="Build phase",
                type=TaskType.GROUP,
                subtask_ids=["t7", "t8"],
            ),
            Task(
                id="t7",
                title="Implementation",
                effort=57600,
                recalculate=Recalculate.EFFORT,
                prerequisites=[Dependency(idref="t3")],
                assignments=[
                    Assignment(resource_idref="r2"),
                    Assignment(resource_idref="r3"),
                    Assignment(resource_idref="r4"),
                ],
            ),
            Task(
                id="t8",
                title="Test pass",
                effort=14400,
                prerequisites=[
                    Dependency(idref="t7", kind=DependencyKind.FINISH_FINISH),
                ],
                start_no_earlier_than=utc(2026, 6, 20, 9, 0),
                assignments=[Assignment(resource_idref="r3")],
            ),
            Task(
                id="t9",
                title="Ship",
                type=TaskType.MILESTONE,
                prerequisites=[
                    Dependency(idref="t8"),
                    Dependency(idref="t7", kind=DependencyKind.FINISH_FINISH),
                ],
            ),
        ],
    )
    return Project(title="Kitchen-sink project", actual=actual)
