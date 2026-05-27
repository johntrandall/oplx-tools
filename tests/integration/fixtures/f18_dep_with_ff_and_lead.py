"""FF dependency combined with a percentage lead-time.

Catches: kind + lead-time combo; the longer XML form of
<prerequisite-task> (with a child <lead-time> element rather than the
self-closing form).
"""

from decimal import Decimal

from oplx import Dependency, Project, Scenario, Task
from oplx.models import DependencyKind, LeadTime

from ._builders import START

NAME = "f18_dep_with_ff_and_lead"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Anchor", effort=28800),
                Task(
                    id="t2",
                    title="Finishes 25% before anchor finishes",
                    effort=14400,
                    prerequisites=[
                        Dependency(
                            idref="t1",
                            kind=DependencyKind.FINISH_FINISH,
                            lead_time=LeadTime(fraction=Decimal("0.25")),
                        ),
                    ],
                ),
            ],
        )
    )
