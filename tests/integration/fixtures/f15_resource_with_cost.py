"""Resource with cost-per-hour, cost-per-use, and efficiency.

Catches: cost element emit + element order (<cost-per-use> before
<cost-per-hour> per the spec); the efficiency != 1 emit (defaults are
omitted).
"""

from decimal import Decimal

from oplx import Assignment, Project, Resource, Scenario, Task
from oplx.models import ResourceType

from ._builders import START

NAME = "f15_resource_with_cost"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            resources=[
                Resource(
                    id="r1",
                    name="Senior consultant",
                    type=ResourceType.STAFF,
                    cost_per_hour=Decimal("250.00"),
                    cost_per_use=Decimal("500.00"),  # flat onboarding fee
                    efficiency=Decimal("0.8"),  # works at 80%
                ),
            ],
            tasks=[
                Task(
                    id="t1",
                    title="Consulting engagement",
                    effort=28800,  # 8h
                    assignments=[Assignment(resource_idref="r1")],
                ),
            ],
        )
    )
