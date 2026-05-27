"""Two resources, each assigned to one task at 50%.

Catches: multi-assignment-per-task XML emit; fractional units (0.5);
resource list rendering.
"""

from decimal import Decimal

from oplx import Assignment, Project, Resource, Scenario, Task
from oplx.models import ResourceType

from ._builders import START

NAME = "f08_multi_resource"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            resources=[
                Resource(id="r1", name="Alice", type=ResourceType.STAFF),
                Resource(id="r2", name="Bob", type=ResourceType.STAFF),
            ],
            tasks=[
                Task(
                    id="t1",
                    title="Paired migration",
                    effort=14400,
                    assignments=[
                        Assignment(resource_idref="r1", units=Decimal("0.5")),
                        Assignment(resource_idref="r2", units=Decimal("0.5")),
                    ],
                ),
            ],
        )
    )
