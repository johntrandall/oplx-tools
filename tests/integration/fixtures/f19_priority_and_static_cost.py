"""Task with non-default priority + static cost.

Catches: <priority> emit when != 0; <static-cost> emit; element order
(<priority> after <type>, <static-cost> after <recalculate>).
"""

from decimal import Decimal

from oplx import Project, Scenario, Task

from ._builders import START

NAME = "f19_priority_and_static_cost"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Expensive priority task",
                    effort=14400,
                    priority=8,
                    static_cost=Decimal("1500.00"),
                ),
            ],
        )
    )
