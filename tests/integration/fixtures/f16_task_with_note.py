"""Task with a multi-line plain-text note.

Catches: <note>/<text>/<p>/<run>/<lit> structure emit; multi-line splitting
on \\n; that OmniPlan preserves the lines on round-trip (within the
plain-text lossiness documented in the SKILL pitfalls).
"""

from oplx import Project, Scenario, Task
from oplx.models import Note

from ._builders import START

NAME = "f16_task_with_note"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Annotated task",
                    effort=14400,
                    note=Note(
                        text=(
                            "Requirements:\n"
                            "  1. validate input\n"
                            "  2. write output\n"
                            "  3. cleanup\n"
                            "See ticket TASK-42 for context."
                        )
                    ),
                ),
            ],
        )
    )
