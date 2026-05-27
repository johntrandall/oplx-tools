"""3-point PERT estimation.

Catches: min/expected/max estimate emit; whether OmniPlan derives the
displayed effort from the PERT triple (it should, via the beta
distribution mean = (min + 4*expected + max) / 6).
"""

from oplx import Project, Scenario, Task

from ._builders import START

NAME = "f09_pert_estimates"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Uncertain task",
                    min_estimate=14400,  # 4h optimistic
                    expected_estimate=28800,  # 8h expected
                    max_estimate=57600,  # 16h pessimistic
                ),
            ],
        )
    )
