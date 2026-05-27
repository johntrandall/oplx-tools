"""Five tasks, one each of every DependencyKind (FS / FF / SS / SF).

Catches: enum-case writing for `kind=` (must be uppercase — DEP-KIND-CASE
lint covers this at structure level; here we verify OmniPlan actually
USES the kind to drive scheduling).
"""

from oplx import Dependency, Project, Scenario, Task
from oplx.models import DependencyKind

from ._builders import START

NAME = "f03_all_dep_kinds"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Anchor", effort=14400),
                Task(
                    id="t2",
                    title="FS-after-Anchor",
                    effort=7200,
                    prerequisites=[Dependency(idref="t1")],  # default FS
                ),
                Task(
                    id="t3",
                    title="SS-with-Anchor",
                    effort=7200,
                    prerequisites=[
                        Dependency(idref="t1", kind=DependencyKind.START_START)
                    ],
                ),
                Task(
                    id="t4",
                    title="FF-with-Anchor",
                    effort=7200,
                    prerequisites=[
                        Dependency(idref="t1", kind=DependencyKind.FINISH_FINISH)
                    ],
                ),
                Task(
                    id="t5",
                    title="SF-with-Anchor",
                    effort=7200,
                    prerequisites=[
                        Dependency(idref="t1", kind=DependencyKind.START_FINISH)
                    ],
                ),
            ],
        )
    )
