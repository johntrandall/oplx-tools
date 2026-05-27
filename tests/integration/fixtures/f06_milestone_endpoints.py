"""Milestones at both ends of a chain.

Catches: milestone diamond rendering; effort auto-omission for
milestones; milestone scheduling (zero duration, single instant).
"""

from oplx import Dependency, Project, Scenario, Task
from oplx.models import TaskType

from ._builders import START

NAME = "f06_milestone_endpoints"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Kickoff", type=TaskType.MILESTONE),
                Task(
                    id="t2",
                    title="Phase 1",
                    effort=14400,
                    prerequisites=[Dependency(idref="t1")],
                ),
                Task(
                    id="t3",
                    title="Phase 2",
                    effort=14400,
                    prerequisites=[Dependency(idref="t2")],
                ),
                Task(
                    id="t4",
                    title="Ship",
                    type=TaskType.MILESTONE,
                    prerequisites=[Dependency(idref="t3")],
                ),
            ],
        )
    )
