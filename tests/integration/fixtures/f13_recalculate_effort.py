"""Task with Recalculate.EFFORT (non-default).

Catches: non-default `<recalculate>` emit + the auto-derived
`<fixed-duration>` companion element that the generator writes alongside
non-DURATION recalculate modes.
"""

from oplx import Project, Scenario, Task
from oplx.models import Recalculate

from ._builders import START

NAME = "f13_recalculate_effort"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Effort-locked task",
                    effort=28800,
                    recalculate=Recalculate.EFFORT,
                ),
            ],
        )
    )
