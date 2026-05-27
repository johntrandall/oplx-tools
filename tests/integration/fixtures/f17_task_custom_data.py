"""Task with custom-data key/value pairs + the project-level key registry.

Catches: <user-data> emit on the task; <task-user-data-keys> emit in
__TOC.xml; the string-only constraint (only string values supported in
0.1.x).
"""

from oplx import Project, Scenario, Task
from oplx.models import CustomData

from ._builders import START

NAME = "f17_task_custom_data"


def build() -> Project:
    return Project(
        custom_data_keys=["work_package", "ticket_id"],
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Tagged task",
                    effort=14400,
                    custom_data=CustomData(
                        values={
                            "work_package": "WP-A",
                            "ticket_id": "TASK-42",
                        }
                    ),
                ),
            ],
        ),
    )
