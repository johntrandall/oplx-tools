"""Actual + one Baseline scenario.

Catches: baseline scenario filename + id emit in __TOC.xml; per-baseline
.xml file generation; comparison view if the renderer supports it.
"""

from oplx import Dependency, Project, Scenario, Task

from ._builders import START, utc

NAME = "f12_with_baseline"


def build() -> Project:
    actual = Scenario(
        id="auto",
        start_date=START,
        tasks=[
            Task(id="t1", title="Plan", effort=14400),
            Task(
                id="t2",
                title="Build",
                effort=43200,  # 12h — slipped from baseline's 8h
                prerequisites=[Dependency(idref="t1")],
            ),
        ],
    )
    baseline = Scenario(
        id="baseline-001",
        name="Baseline1",
        filename="Baseline1.xml",
        start_date=utc(2026, 5, 25, 13, 0),
        tasks=[
            Task(id="t1", title="Plan", effort=14400),
            Task(
                id="t2",
                title="Build",
                effort=28800,  # 8h original estimate
                prerequisites=[Dependency(idref="t1")],
            ),
        ],
    )
    return Project(actual=actual, baselines=[baseline])
