"""Smallest possible Project: one task, no deps, no resources.

Catches: whether OmniPlan opens our most-minimal output at all; whether
the root group (`t-1`) and root resource (`r-1`) auto-creation produces
a file OmniPlan accepts.
"""

from oplx import Project, Scenario, Task

from ._builders import START

NAME = "f01_minimal"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[Task(id="t1", title="Solo task", effort=14400)],  # 4h
        )
    )
