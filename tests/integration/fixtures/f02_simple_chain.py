"""Three tasks linked Finish-Start (the README example).

Catches: basic FS dependency arithmetic; default kind omission in XML;
WBS numbering across a chain.
"""

from oplx import Dependency, Project, Scenario, Task

from ._builders import START

NAME = "f02_simple_chain"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(id="t1", title="Plan", effort=14400),
                Task(
                    id="t2",
                    title="Build",
                    effort=28800,
                    prerequisites=[Dependency(idref="t1")],
                ),
                Task(
                    id="t3",
                    title="Ship",
                    effort=7200,
                    prerequisites=[Dependency(idref="t2")],
                ),
            ],
        )
    )
