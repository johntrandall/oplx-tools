"""Kitchen-sink: multi-resource project with groups, milestones,
mixed dep kinds, lead times, costs, notes, and constraints.

Catches: emergent interactions between features that individual
fixtures miss. If this opens cleanly and matches its golden, the
overall pipeline is healthy.

Note: user task ids start at `t2`, not `t1` — see f07 docstring for
the OmniPlan-reader collision rationale.
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
            Task(id="m1", title="Kickoff", type=TaskType.MILESTONE),
            Task(
                id="g1",
                title="Design phase",
                type=TaskType.GROUP,
                subtask_ids=["t2", "t3"],
            ),
            Task(
                id="t2",
                title="Architecture",
                effort=28800,
                priority=8,
                static_cost=Decimal("500.00"),
                note=Note(text="ADR template required."),
                prerequisites=[Dependency(idref="m1")],
                assignments=[Assignment(resource_idref="r2")],
            ),
            Task(
                id="t3",
                title="Schema review",
                effort=14400,
                prerequisites=[
                    Dependency(idref="t2", kind=DependencyKind.START_START,
                               lead_time=LeadTime(seconds=3600)),
                ],
                assignments=[Assignment(resource_idref="r3", units=Decimal("0.5"))],
            ),
            Task(
                id="g2",
                title="Build phase",
                type=TaskType.GROUP,
                subtask_ids=["t4", "t5"],
            ),
            Task(
                id="t4",
                title="Implementation",
                effort=57600,
                recalculate=Recalculate.EFFORT,
                prerequisites=[Dependency(idref="g1")],
                assignments=[
                    Assignment(resource_idref="r2"),
                    Assignment(resource_idref="r3"),
                    Assignment(resource_idref="r4"),
                ],
            ),
            Task(
                id="t5",
                title="Test pass",
                effort=14400,
                prerequisites=[
                    Dependency(idref="t4", kind=DependencyKind.FINISH_FINISH),
                ],
                start_no_earlier_than=utc(2026, 6, 20, 9, 0),
                assignments=[Assignment(resource_idref="r3")],
            ),
            Task(
                id="m2",
                title="Ship",
                type=TaskType.MILESTONE,
                prerequisites=[
                    Dependency(idref="t5"),
                    Dependency(idref="t4", kind=DependencyKind.FINISH_FINISH),
                ],
            ),
        ],
    )
    return Project(title="Kitchen-sink project", actual=actual)
