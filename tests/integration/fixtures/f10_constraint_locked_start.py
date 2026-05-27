"""Task with a locked start date.

Catches: `<locked-start-date>` emit; positioned BEFORE `<recalculate>`
(element order matters); manual scheduling rendering.
"""

from oplx import Project, Scenario, Task

from ._builders import START, utc

NAME = "f10_constraint_locked_start"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Manually pinned",
                    effort=14400,
                    locked_start_date=utc(2026, 6, 8, 9, 0),
                ),
            ],
        )
    )
