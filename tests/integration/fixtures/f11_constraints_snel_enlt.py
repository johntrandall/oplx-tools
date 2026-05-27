"""Start-no-earlier-than + end-no-later-than constraints.

Catches: `<start-no-earlier-than>` and `<end-no-later-than>` emit
(positioned AFTER `<static-cost>`, per the spec); scheduler treating
them as soft bounds.
"""

from oplx import Project, Scenario, Task

from ._builders import START, utc

NAME = "f11_constraints_snel_enlt"


def build() -> Project:
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            tasks=[
                Task(
                    id="t1",
                    title="Bracketed task",
                    effort=14400,
                    start_no_earlier_than=utc(2026, 6, 3, 9, 0),
                    end_no_later_than=utc(2026, 6, 10, 17, 0),
                ),
            ],
        )
    )
