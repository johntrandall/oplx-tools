"""Parse an .oplx file into a Project model.

Handles both the directory bundle and zip variant.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from lxml import etree

from .models import (
    Assignment,
    Attachment,
    CustomData,
    Dependency,
    DependencyKind,
    LeadTime,
    Note,
    Project,
    Recalculate,
    Resource,
    ResourceSchedule,
    ResourceType,
    Scenario,
    ScheduleDay,
    Task,
    TaskType,
    TimeSpan,
)

NS = "http://www.omnigroup.com/namespace/OmniPlan/v2"


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _read_xml(source: Path | zipfile.ZipFile, name: str) -> etree._Element | None:
    if isinstance(source, zipfile.ZipFile):
        try:
            with source.open(name) as f:
                return etree.parse(f).getroot()
        except KeyError:
            return None
    else:
        path = source / name
        return etree.parse(str(path)).getroot() if path.exists() else None


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_note(el: etree._Element) -> Note:
    """Parse a <note>/<text>/<p>/<run>/<lit> structure into plain text."""
    lines: list[str] = []
    text_el = el.find(_q("text"))
    if text_el is None:
        return Note(text="")
    for p in text_el.findall(_q("p")):
        line_parts: list[str] = []
        for run in p.findall(_q("run")):
            for lit in run.findall(_q("lit")):
                if lit.text:
                    line_parts.append(lit.text)
        lines.append("".join(line_parts))
    return Note(text="\n".join(lines))


def _parse_user_data(el: etree._Element) -> CustomData:
    cd = CustomData()
    ud = el.find(_q("user-data"))
    if ud is None:
        return cd
    children = list(ud)
    for i in range(0, len(children) - 1, 2):
        k = children[i]
        v = children[i + 1]
        if k.tag == _q("key") and v.tag == _q("string") and k.text and v.text is not None:
            cd.values[k.text] = v.text
    return cd


def _parse_resource(r: etree._Element) -> Resource:
    rid = r.get("id") or ""
    name_el = r.find(_q("name"))
    name = (name_el.text or "") if name_el is not None else ""
    type_el = r.find(_q("type"))
    type_str = (type_el.text or "Staff").strip() if type_el is not None else "Staff"
    try:
        rtype = ResourceType(type_str)
    except ValueError:
        rtype = ResourceType.STAFF

    def _opt_decimal(tag: str) -> Decimal | None:
        e = r.find(_q(tag))
        return Decimal(e.text) if e is not None and e.text else None

    schedule: ResourceSchedule | None = None
    sched_el = r.find(_q("schedule"))
    if sched_el is not None:
        days: list[ScheduleDay] = []
        for d_el in sched_el.findall(_q("schedule-day")):
            dow = d_el.get("day-of-week", "")
            spans: list[TimeSpan] = [
                TimeSpan(
                    start_seconds=int(s.get("start-time") or 0),
                    end_seconds=int(s.get("end-time") or 0),
                )
                for s in d_el.findall(_q("time-span"))
            ]
            days.append(ScheduleDay(day_of_week=dow, time_spans=spans))  # type: ignore[arg-type]
        schedule = ResourceSchedule(days=days)

    note_el = r.find(_q("note"))
    note = _parse_note(note_el) if note_el is not None else None

    email_el = r.find(_q("email-address"))

    return Resource(
        id=rid,
        name=name,
        type=rtype,
        note=note,
        cost_per_hour=_opt_decimal("cost-per-hour"),
        cost_per_use=_opt_decimal("cost-per-use"),
        units_available=_opt_decimal("units-available"),
        efficiency=_opt_decimal("efficiency"),
        email=email_el.text if email_el is not None else None,
        schedule=schedule,
        custom_data=_parse_user_data(r),
    )


def _parse_task(t: etree._Element) -> Task:
    tid = t.get("id") or ""
    title_el = t.find(_q("title"))
    title = (title_el.text or "") if title_el is not None else ""

    type_el = t.find(_q("type"))
    type_str = type_el.text.strip() if (type_el is not None and type_el.text) else "task"
    try:
        ttype = TaskType(type_str)
    except ValueError:
        ttype = TaskType.TASK

    def _opt_int(tag: str) -> int | None:
        e = t.find(_q(tag))
        return int(e.text) if e is not None and e.text else None

    def _opt_dt(tag: str) -> datetime | None:
        e = t.find(_q(tag))
        return _parse_iso(e.text) if e is not None and e.text else None

    rc_el = t.find(_q("recalculate"))
    rc_str = (rc_el.text or "duration").strip() if rc_el is not None else "duration"
    try:
        recalculate = Recalculate(rc_str)
    except ValueError:
        recalculate = Recalculate.DURATION

    sc_el = t.find(_q("static-cost"))
    static_cost = Decimal(sc_el.text or "0") if sc_el is not None else Decimal("0")

    # Prereqs
    prereqs: list[Dependency] = []
    for pr in t.findall(_q("prerequisite-task")):
        idref = pr.get("idref") or ""
        kind_str = pr.get("kind", "FS")
        try:
            kind = DependencyKind(kind_str)
        except ValueError:
            kind = DependencyKind.FINISH_START

        lt: LeadTime | None = None
        lt_el = pr.find(_q("lead-time"))
        if lt_el is not None and lt_el.text:
            is_pct = lt_el.get("is-percentage") == "true"
            if is_pct:
                lt = LeadTime(fraction=Decimal(lt_el.text))
            else:
                lt = LeadTime(seconds=int(lt_el.text))

        prereqs.append(Dependency(idref=idref, kind=kind, lead_time=lt))

    # Attachments
    attachments: list[Attachment] = []
    for att_el in t.findall(_q("attachment")):
        uri = att_el.get("uri") or ""
        bm_el = att_el.find(_q("bookmarkData"))
        bookmark_data = (bm_el.text or "").strip() if bm_el is not None else ""
        attachments.append(Attachment(uri=uri, bookmark_data=bookmark_data))

    # Assignments
    assignments: list[Assignment] = []
    for assn in t.findall(_q("assignment")):
        idref = assn.get("idref") or ""
        units_str = assn.get("units")
        units = Decimal(units_str) if units_str else Decimal("1.0")
        assignments.append(Assignment(resource_idref=idref, units=units))

    # Subtasks
    subtask_ids = [
        ct.get("idref") for ct in t.findall(_q("child-task")) if ct.get("idref")
    ]

    note_el = t.find(_q("note"))
    note = _parse_note(note_el) if note_el is not None else None

    priority_el = t.find(_q("priority"))
    priority = int(priority_el.text or "0") if priority_el is not None else 0

    effort_done_el = t.find(_q("effort-done"))
    effort_done = int(effort_done_el.text or "0") if effort_done_el is not None else 0

    return Task(
        id=tid,
        title=title,
        type=ttype,
        priority=priority,
        effort=_opt_int("effort"),
        effort_done=effort_done,
        min_estimate=_opt_int("min-estimate"),
        expected_estimate=_opt_int("expected-estimate"),
        max_estimate=_opt_int("max-estimate"),
        recalculate=recalculate,
        fixed_duration=_opt_int("fixed-duration"),
        static_cost=static_cost,
        note=note,
        locked_start_date=_opt_dt("locked-start-date"),
        start_no_earlier_than=_opt_dt("start-no-earlier-than"),
        start_no_later_than=_opt_dt("start-no-later-than"),
        end_no_earlier_than=_opt_dt("end-no-earlier-than"),
        end_no_later_than=_opt_dt("end-no-later-than"),
        attachments=attachments,
        prerequisites=prereqs,
        assignments=assignments,
        subtask_ids=[s for s in subtask_ids if s],
        custom_data=_parse_user_data(t),
    )


def _parse_scenario(scenario_el: etree._Element, name: str, filename: str) -> Scenario:
    sid = scenario_el.get("id") or "auto"
    fixed_end = scenario_el.get("fixed-end") == "true"

    sd_el = scenario_el.find(_q("start-date"))
    start_date = _parse_iso(sd_el.text) if sd_el is not None and sd_el.text else None

    ed_el = scenario_el.find(_q("end-date"))
    end_date = _parse_iso(ed_el.text) if ed_el is not None and ed_el.text else None

    g_el = scenario_el.find(_q("granularity"))
    granularity = (g_el.text or "exact").strip() if g_el is not None else "exact"

    top_task = scenario_el.find(_q("top-task"))
    root_task_id = top_task.get("idref", "t-1") if top_task is not None else "t-1"

    top_resource = scenario_el.find(_q("top-resource"))
    root_resource_id = (
        top_resource.get("idref", "r-1") if top_resource is not None else "r-1"
    )

    tasks = [_parse_task(t) for t in scenario_el.findall(_q("task"))]
    resources = [_parse_resource(r) for r in scenario_el.findall(_q("resource"))]

    return Scenario(
        id=sid,
        name=name,
        filename=filename,
        start_date=start_date,
        end_date=end_date,
        fixed_end=fixed_end,
        granularity=granularity,  # type: ignore[arg-type]
        root_task_id=root_task_id,
        root_resource_id=root_resource_id,
        tasks=tasks,
        resources=resources,
    )


def parse(oplx_path: str | Path) -> Project:
    """Parse an .oplx (zip or directory) into a Project model."""
    p = Path(oplx_path)
    is_zip = p.is_file()
    source: zipfile.ZipFile | Path
    if is_zip:
        source = zipfile.ZipFile(p, "r")
    else:
        source = p

    try:
        toc = _read_xml(source, "__TOC.xml")
        if toc is None:
            raise ValueError(f"{p}: __TOC.xml missing")

        actual_xml = _read_xml(source, "Actual.xml")
        if actual_xml is None:
            raise ValueError(f"{p}: Actual.xml missing")

        actual = _parse_scenario(actual_xml, name="Actual", filename="Actual.xml")

        # Baselines
        baselines: list[Scenario] = []
        for sc_el in toc.findall(f".//{_q('scenario')}"):
            fname = sc_el.get("filename")
            sname = sc_el.get("name") or ""
            if fname and fname != "Actual.xml":
                bs_xml = _read_xml(source, fname)
                if bs_xml is not None:
                    baselines.append(_parse_scenario(bs_xml, name=sname, filename=fname))

        next_task_id_el = toc.find(f".//{_q('next-task-id')}")
        next_resource_id_el = toc.find(f".//{_q('next-resource-id')}")
        next_task_id = (
            int(next_task_id_el.text or "2") if next_task_id_el is not None else 2
        )
        next_resource_id = (
            int(next_resource_id_el.text or "2")
            if next_resource_id_el is not None
            else 2
        )

        return Project(
            actual=actual,
            baselines=baselines,
            next_task_id=next_task_id,
            next_resource_id=next_resource_id,
        )
    finally:
        if is_zip:
            assert isinstance(source, zipfile.ZipFile)
            source.close()
