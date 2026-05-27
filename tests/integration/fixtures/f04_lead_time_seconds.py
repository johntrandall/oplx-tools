"""FS dependency with a positive lead-time duration (in seconds).

Catches: lead-time XML emit (`<lead-time is-percentage="false">N`); the
scheduler honoring the offset (successor starts N seconds after the
predecessor's finish).
"""

from oplx import Dependency, Project, Scenario, Task
from oplx.models import LeadTime

from ._builders import START

NAME = "f04_lead_time_seconds"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Predecessor", effort=14400),
                Task(
                    id="t2",
                    title="Lagged successor (+2h)",
                    effort=7200,
                    prerequisites=[
                        Dependency(idref="t1", lead_time=LeadTime(seconds=7200))
                    ],
                ),
            ],
        )
    )
