"""Group task containing three subtasks.

Catches: subtask-id emit on the group; group effort auto-omission; outline
hierarchy rendering; the orphan exemption (subtasks are reachable
through the group's `<child-task idref>`).

Note: user task ids start at `t2`, not `t1`. OmniPlan's reader silently
drops a task whose id is `t1` when it's a subtask of an explicit group,
because it can't disambiguate it from the root `t-1` (likely strips the
hyphen internally). The spec allows `t1` for user tasks, but OmniPlan-
saved files start user numbering at `t2` (next-task-id defaults to 2)
and so do we. See SKILL.md pitfalls + the `T1-COLLISION` lint code.
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
                    subtask_ids=["t2", "t3", "t4"],
                ),
                Task(id="t2", title="Design", effort=14400),
                Task(id="t3", title="Code", effort=28800),
                Task(id="t4", title="Test", effort=14400),
            ],
        )
    )
