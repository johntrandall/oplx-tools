"""Resource with a per-resource work-hours schedule.

Catches: <schedule>/<schedule-day>/<time-span> emit; the two auto-emitted
calendars (Overtime, Time Off); whether OmniPlan honors a partial week
(here: Tuesday/Thursday only).
"""

from oplx import Project, Resource, Scenario, Task
from oplx.models import ResourceSchedule, ResourceType, ScheduleDay, TimeSpan

from ._builders import START

NAME = "f14_resource_with_schedule"


def build() -> Project:
    bob = Resource(
        id="r1",
        name="Part-time Bob",
        type=ResourceType.STAFF,
        schedule=ResourceSchedule(
            days=[
                ScheduleDay(
                    day_of_week="tuesday",
                    time_spans=[TimeSpan(start_seconds=32400, end_seconds=61200)],
                ),
                ScheduleDay(
                    day_of_week="thursday",
                    time_spans=[TimeSpan(start_seconds=32400, end_seconds=61200)],
                ),
            ]
        ),
    )
    return Project(
        actual=Scenario(
            id="auto",
            start_date=START,
            resources=[bob],
            tasks=[Task(id="t1", title="Bob's work", effort=14400)],
        )
    )
