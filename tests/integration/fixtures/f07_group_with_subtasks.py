"""Group task containing three subtasks.

Catches: subtask-id emit on the group; group effort auto-omission; outline
hierarchy rendering; the orphan exemption (subtasks are reachable
through the group's `<child-task idref>`).
"""

from oplx import Project, Scenario, Task
from oplx.models import TaskType

from ._builders import START

NAME = "f07_group_with_subtasks"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="g1",
                    title="Implementation",
                    type=TaskType.GROUP,
                    subtask_ids=["t1", "t2", "t3"],
                ),
                Task(id="t1", title="Design", effort=14400),
                Task(id="t2", title="Code", effort=28800),
                Task(id="t3", title="Test", effort=14400),
            ],
        )
    )
