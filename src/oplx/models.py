"""Dataclasses for OmniPlan .oplx documents.

These are the in-memory representation of a parsed .oplx, and the input
to the generator. They map closely to the XML element grammar but are
not 1:1 — some elements (like the constraint-date single-field internal
representation) are denormalized into separate dataclass fields for
clarity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


class TaskType(str, Enum):
    """XML form is the value (lowercase). See spec/enums.md."""

    TASK = "task"
    MILESTONE = "milestone"
    GROUP = "group"
    HAMMOCK = "hammock"


class ResourceType(str, Enum):
    """XML form is the value (capitalized). See spec/enums.md."""

    STAFF = "Staff"
    EQUIPMENT = "Equipment"
    MATERIAL = "Material"
    GROUP = "Group"
    PROJECT = "Project"  # reserved for r-1


class DependencyKind(str, Enum):
    """XML kind= attribute value (uppercase). See spec/enums.md."""

    FINISH_START = "FS"  # default — XML attribute omitted
    FINISH_FINISH = "FF"
    START_START = "SS"
    START_FINISH = "SF"


class Recalculate(str, Enum):
    """XML form is the value. NOT 'assignments' or 'none' — see spec/enums.md."""

    DURATION = "duration"
    EFFORT = "effort"
    UNITS = "units"


Granularity = Literal["exact", "hours", "days"]


@dataclass
class LeadTime:
    """Lead-time on a dependency. EITHER duration OR percentage, not both."""

    seconds: int | None = None  # When set: <lead-time is-percentage="false">N</lead-time>
    fraction: Decimal | None = None  # When set: <lead-time is-percentage="true">F</lead-time> where F is the FRACTION (0.25 = 25%)

    def __post_init__(self) -> None:
        if self.seconds is not None and self.fraction is not None:
            raise ValueError("LeadTime: specify seconds OR fraction, not both")


@dataclass
class Dependency:
    """A prerequisite/dependent link.

    Stored on the Task (in `prerequisites`); the spec's <prerequisite-task>
    element is the XML form of this.
    """

    idref: str  # ID of the prerequisite task
    kind: DependencyKind = DependencyKind.FINISH_START
    lead_time: LeadTime | None = None


@dataclass
class Assignment:
    """A resource assignment to a task."""

    resource_idref: str  # e.g., "r5"
    units: Decimal = Decimal("1.0")  # default 1.0 omits the attribute; 0.0 is silent corruption


@dataclass
class CustomData:
    """Task or resource custom-data key/value map.

    Only string values are supported in 0.1.0 (other types not yet wired).
    """

    values: dict[str, str] = field(default_factory=dict)


@dataclass
class Note:
    """Rich-text note on a task or resource.

    Plain-text only in 0.1.0. Multi-line splits on \\n.
    """

    text: str = ""


@dataclass
class TimeSpan:
    """A working-hours range within a day."""

    start_seconds: int  # seconds from midnight (e.g., 28800 = 08:00)
    end_seconds: int  # seconds from midnight


@dataclass
class ScheduleDay:
    """Working hours for a specific weekday."""

    day_of_week: Literal[
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ]
    time_spans: list[TimeSpan] = field(default_factory=list)


@dataclass
class ResourceSchedule:
    """Per-resource calendar override.

    When present on a resource, <schedule-day> entries replace the default
    work hours for that weekday entirely (not deltas — the spec calls out
    that OmniPlan emits the FULL day's hours).
    """

    days: list[ScheduleDay] = field(default_factory=list)
    # Calendars (Overtime + Time Off) are auto-emitted by the generator;
    # not yet user-configurable in 0.1.0.


@dataclass
class Resource:
    """A resource in a scenario."""

    id: str  # e.g., "r1", "r-1" for root
    name: str = ""
    type: ResourceType = ResourceType.STAFF
    note: Note | None = None
    cost_per_hour: Decimal | None = None
    cost_per_use: Decimal | None = None
    units_available: Decimal | None = None
    efficiency: Decimal | None = None  # 0.0..1.0; default 1.0 omitted
    email: str | None = None  # XML element is <email-address>
    schedule: ResourceSchedule | None = None
    custom_data: CustomData = field(default_factory=CustomData)


@dataclass
class Task:
    """A task in a scenario."""

    id: str  # e.g., "t1"
    title: str = ""
    type: TaskType = TaskType.TASK
    priority: int = 0  # default 0 omitted
    effort: int | None = None  # seconds; omitted for milestones and groups
    effort_done: int = 0  # default 0 omitted
    min_estimate: int | None = None  # 3-pt PERT
    expected_estimate: int | None = None
    max_estimate: int | None = None
    recalculate: Recalculate = Recalculate.DURATION
    fixed_duration: int | None = None  # auto-emitted alongside non-default recalculate
    static_cost: Decimal = Decimal("0")
    note: Note | None = None
    locked_start_date: datetime | None = None  # for manual scheduling
    start_no_earlier_than: datetime | None = None
    start_no_later_than: datetime | None = None
    end_no_earlier_than: datetime | None = None
    end_no_later_than: datetime | None = None
    prerequisites: list[Dependency] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    subtask_ids: list[str] = field(default_factory=list)  # for groups
    custom_data: CustomData = field(default_factory=CustomData)


@dataclass
class Scenario:
    """A scenario file (Actual.xml or BaselineN.xml)."""

    id: str
    name: str = "Actual"
    filename: str = "Actual.xml"
    start_date: datetime | None = None
    end_date: datetime | None = None  # set + fixed_end=True → backward-from-end mode
    fixed_end: bool = False
    granularity: Granularity = "exact"
    has_generic_dates: bool = False
    root_task_id: str = "t-1"
    root_resource_id: str = "r-1"
    tasks: list[Task] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)


@dataclass
class Project:
    """The whole document."""

    title: str = ""
    actual: Scenario = field(default_factory=lambda: Scenario(id="auto"))
    baselines: list[Scenario] = field(default_factory=list)
    next_task_id: int = 2  # OmniPlan recomputes anyway; this is just a starting hint
    next_resource_id: int = 2
    custom_data_keys: list[str] = field(default_factory=list)  # registered in <task-user-data-keys>
    user_attribution: str = "oplx-tools"  # appears as user= on synthetic change-set
