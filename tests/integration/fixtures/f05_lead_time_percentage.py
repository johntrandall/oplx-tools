"""FS dependency with a percentage lead-time (fraction, NOT integer percent).

Catches: the percentage-fraction convention (0.25 = 25%, NOT the omniJS
integer-percent convention that bit us early on); `is-percentage="true"`
attribute emit.
"""

from decimal import Decimal

from oplx import Dependency, Project, Scenario, Task
from oplx.models import LeadTime

from ._builders import START

NAME = "f05_lead_time_percentage"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Predecessor (8h)", effort=28800),
                Task(
                    id="t2",
                    title="Successor after 25%",
                    effort=7200,
                    prerequisites=[
                        Dependency(
                            idref="t1", lead_time=LeadTime(fraction=Decimal("0.25"))
                        )
                    ],
                ),
            ],
        )
    )
