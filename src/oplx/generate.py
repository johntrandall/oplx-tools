"""Generate an .oplx file from a Project model (or a YAML/JSON description).

Produces the zip variant by default. Pass `bundle=True` to produce a directory bundle.

The generated XML matches the spec at https://github.com/johntrandall/oplx-format,
verified against OmniPlan 4.10.2.
"""

from __future__ import annotations

import secrets
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import yaml
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
    ResourceType,
    Scenario,
    Task,
    TaskType,
)

NS = "http://www.omnigroup.com/namespace/OmniPlan/v2"
NSMAP = {None: NS, "opns": NS}


def _scenario_id() -> str:
    """Generate an opaque scenario id, base64-style."""
    return secrets.token_urlsafe(8)


def _iso(dt: datetime) -> str:
    """Format a datetime in ISO-8601 UTC with milliseconds.

    Input must be tz-aware. Non-UTC inputs are converted to UTC before
    formatting — `datetime(13:00, tz=NYC)` serializes as `17:00Z`, not
    `13:00Z`. Naive datetimes are rejected (raise ValueError) so callers
    can't silently mis-stamp wall-clock-only times.
    """
    if dt.tzinfo is None:
        raise ValueError(f"datetime must be tz-aware, got naive: {dt}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _build_note_xml(parent: etree._Element, note: Note) -> None:
    """Build the <note>/<text>/<p>/<run>/<lit> rich-text structure."""
    note_el = etree.SubElement(parent, "note")
    text_el = etree.SubElement(note_el, "text")
    for line in note.text.split("\n"):
        p_el = etree.SubElement(text_el, "p")
        run_el = etree.SubElement(p_el, "run")
        lit_el = etree.SubElement(run_el, "lit")
        lit_el.text = line


def _build_user_data(parent: etree._Element, cd: CustomData) -> None:
    if not cd.values:
        return
    ud = etree.SubElement(parent, "user-data")
    for key, value in cd.values.items():
        k = etree.SubElement(ud, "key")
        k.text = key
        s = etree.SubElement(ud, "string")
        s.text = value


def _build_resource_schedule(parent: etree._Element, schedule: Any) -> None:
    sched = etree.SubElement(parent, "schedule")
    for day in schedule.days:
        d = etree.SubElement(sched, "schedule-day", attrib={"day-of-week": day.day_of_week})
        for span in day.time_spans:
            etree.SubElement(
                d,
                "time-span",
                attrib={
                    "start-time": str(span.start_seconds),
                    "end-time": str(span.end_seconds),
                },
            )
    # Auto-emit the two system calendars
    etree.SubElement(
        sched, "calendar", attrib={"name": "Overtime", "editable": "yes", "overtime": "yes"}
    )
    etree.SubElement(
        sched, "calendar", attrib={"name": "Time Off", "editable": "yes", "overtime": "no"}
    )


def _build_resource(parent: etree._Element, r: Resource) -> None:
    r_el = etree.SubElement(parent, "resource", attrib={"id": r.id})

    # name (always; may be empty self-closing)
    name_el = etree.SubElement(r_el, "name")
    if r.name:
        name_el.text = r.name

    # type
    type_el = etree.SubElement(r_el, "type")
    type_el.text = r.type.value

    # note (before cost block)
    if r.note:
        _build_note_xml(r_el, r.note)

    # cost-per-use, cost-per-hour
    if r.cost_per_use is not None:
        cpu = etree.SubElement(r_el, "cost-per-use")
        cpu.text = _decimal_str(r.cost_per_use)
    if r.cost_per_hour is not None:
        cph = etree.SubElement(r_el, "cost-per-hour")
        cph.text = _decimal_str(r.cost_per_hour)

    # units-available (always for Material when 0; omitted for others when 1)
    if r.units_available is not None:
        ua = etree.SubElement(r_el, "units-available")
        ua.text = _decimal_str(r.units_available)

    # efficiency (default 1.0 omitted)
    if r.efficiency is not None and r.efficiency != 1:
        eff = etree.SubElement(r_el, "efficiency")
        eff.text = _decimal_str(r.efficiency)

    # email-address (NOT <email>)
    if r.email:
        em = etree.SubElement(r_el, "email-address")
        em.text = r.email

    # schedule (per-resource override)
    if r.schedule:
        _build_resource_schedule(r_el, r.schedule)

    # subresources (groups and the root resource MUST list their members here,
    # or OmniPlan silently drops every resource from the doc tree). Verified
    # 2026-05-28 against OmniPlan 4.10.2 build 232.5.0.
    for sid in r.subresource_ids:
        etree.SubElement(r_el, "child-resource", attrib={"idref": sid})

    # custom data
    _build_user_data(r_el, r.custom_data)


def _decimal_str(d: Any) -> str:
    """Stringify Decimal values, stripping trailing zeros and unneeded decimal point."""
    s = str(d).rstrip("0").rstrip(".")
    return s if s else "0"


def _build_task(parent: etree._Element, t: Task) -> None:
    t_el = etree.SubElement(parent, "task", attrib={"id": t.id})

    # title (always; may be empty self-closing)
    title_el = etree.SubElement(t_el, "title")
    if t.title:
        title_el.text = t.title

    # type (omit for default 'task')
    if t.type != TaskType.TASK:
        type_el = etree.SubElement(t_el, "type")
        type_el.text = t.type.value

    # priority (default 0 omitted)
    if t.priority != 0:
        p_el = etree.SubElement(t_el, "priority")
        p_el.text = str(t.priority)

    # effort (omitted for milestones; PERT-computed when 3-pt set)
    if t.effort is not None and t.type != TaskType.MILESTONE and t.type != TaskType.GROUP:
        eff_el = etree.SubElement(t_el, "effort")
        eff_el.text = str(t.effort)

    # effort-done (default 0 omitted)
    if t.effort_done != 0:
        ed = etree.SubElement(t_el, "effort-done")
        ed.text = str(t.effort_done)

    # 3-pt estimation
    if t.min_estimate is not None:
        e = etree.SubElement(t_el, "min-estimate")
        e.text = str(t.min_estimate)
    if t.expected_estimate is not None:
        e = etree.SubElement(t_el, "expected-estimate")
        e.text = str(t.expected_estimate)
    if t.max_estimate is not None:
        e = etree.SubElement(t_el, "max-estimate")
        e.text = str(t.max_estimate)

    # locked-start-date (BEFORE recalculate)
    if t.locked_start_date:
        lsd = etree.SubElement(t_el, "locked-start-date")
        lsd.text = _iso(t.locked_start_date)

    # recalculate (always)
    rc = etree.SubElement(t_el, "recalculate")
    rc.text = t.recalculate.value

    # fixed-duration (alongside non-default recalculate)
    if t.recalculate != Recalculate.DURATION:
        # Auto-derive from effort if not explicitly set
        fd_value = t.fixed_duration if t.fixed_duration is not None else t.effort
        if fd_value is not None:
            fd = etree.SubElement(t_el, "fixed-duration")
            fd.text = str(fd_value)

    # static-cost (always)
    sc = etree.SubElement(t_el, "static-cost")
    sc.text = _decimal_str(t.static_cost)

    # subtasks (groups only)
    for sid in t.subtask_ids:
        etree.SubElement(t_el, "child-task", attrib={"idref": sid})

    # note (after value elements / subtasks)
    if t.note:
        _build_note_xml(t_el, t.note)

    # constraint dates (AFTER static-cost)
    if t.start_no_earlier_than:
        e = etree.SubElement(t_el, "start-no-earlier-than")
        e.text = _iso(t.start_no_earlier_than)
    if t.start_no_later_than:
        e = etree.SubElement(t_el, "start-no-later-than")
        e.text = _iso(t.start_no_later_than)
    if t.end_no_earlier_than:
        e = etree.SubElement(t_el, "end-no-earlier-than")
        e.text = _iso(t.end_no_earlier_than)
    if t.end_no_later_than:
        e = etree.SubElement(t_el, "end-no-later-than")
        e.text = _iso(t.end_no_later_than)

    # attachments (after static-cost / constraint dates, before prerequisites).
    # Spec: oplx-format spec/actual-xml.md § <attachment>. Verified 2026-05-28
    # against OmniPlan 4.10.2 build 232.5.0.
    for att in t.attachments:
        _build_attachment(t_el, att)

    # prerequisites
    for dep in t.prerequisites:
        _build_prerequisite(t_el, dep)

    # assignments
    for a in t.assignments:
        if a.units == 0:
            # Silent-corruption avoidance: don't emit units="0"
            continue
        attrib: dict[str, str] = {"idref": a.resource_idref}
        if a.units != 1:
            attrib["units"] = _decimal_str(a.units)
        etree.SubElement(t_el, "assignment", attrib=attrib)

    # custom data
    _build_user_data(t_el, t.custom_data)


def _build_attachment(t_el: etree._Element, att: Attachment) -> None:
    """Emit <attachment uri="..."><bookmarkData>...</bookmarkData></attachment>.

    Refuses to emit a file:// attachment without bookmark_data — that
    would produce a silently-ignored element in OmniPlan (the document
    opens but `count attachments of task` returns 0). Caller should
    populate bookmark_data via `oplx.bookmark.make_bookmark(path)`.
    HTTP/HTTPS URIs are emitted without <bookmarkData>.
    """
    if not att.uri:
        raise ValueError("Attachment.uri is required")
    if att.is_file_uri and not att.bookmark_data:
        raise ValueError(
            f"Attachment uri={att.uri!r} is file:// but bookmark_data is empty. "
            "OmniPlan silently ignores file:// attachments without <bookmarkData>. "
            "Generate one via oplx.bookmark.make_bookmark(abspath) (requires "
            "the [macos] extra)."
        )
    att_el = etree.SubElement(t_el, "attachment", attrib={"uri": att.uri})
    if att.bookmark_data:
        bm_el = etree.SubElement(att_el, "bookmarkData")
        bm_el.text = att.bookmark_data


def _build_prerequisite(t_el: etree._Element, dep: Dependency) -> None:
    attrib: dict[str, str] = {"idref": dep.idref}
    if dep.kind != DependencyKind.FINISH_START:
        attrib["kind"] = dep.kind.value

    if dep.lead_time is None:
        # Self-closing form
        etree.SubElement(t_el, "prerequisite-task", attrib=attrib)
        return

    # Non-empty form with <lead-time> child
    pr = etree.SubElement(t_el, "prerequisite-task", attrib=attrib)
    if dep.lead_time.seconds is not None:
        lt = etree.SubElement(pr, "lead-time", attrib={"is-percentage": "false"})
        lt.text = str(dep.lead_time.seconds)
    elif dep.lead_time.fraction is not None:
        lt = etree.SubElement(pr, "lead-time", attrib={"is-percentage": "true"})
        lt.text = _decimal_str(dep.lead_time.fraction)


def _build_scenario(scenario: Scenario) -> bytes:
    """Build a complete scenario XML file."""
    attrs: dict[str, str] = {"id": scenario.id}
    if scenario.fixed_end:
        attrs["fixed-end"] = "true"
    root = etree.Element("scenario", attrib=attrs, nsmap=NSMAP)

    if scenario.start_date:
        sd = etree.SubElement(root, "start-date")
        sd.text = _iso(scenario.start_date)
    if scenario.end_date and scenario.fixed_end:
        ed = etree.SubElement(root, "end-date")
        ed.text = _iso(scenario.end_date)
    if scenario.granularity != "exact":
        g = etree.SubElement(root, "granularity")
        g.text = scenario.granularity

    # rootResource
    etree.SubElement(root, "top-resource", attrib={"idref": scenario.root_resource_id})
    root_resource = next(
        (r for r in scenario.resources if r.id == scenario.root_resource_id), None
    )
    # Auto-populate the root resource's <child-resource> list with every
    # top-level user resource — i.e. every user resource that isn't already
    # a member of some other group resource's subresource_ids. Required:
    # without these, OmniPlan silently drops every user resource on load.
    explicitly_grouped = {
        sid for r in scenario.resources for sid in r.subresource_ids
    }
    top_level_resource_ids = [
        r.id for r in scenario.resources
        if r.id != scenario.root_resource_id and r.id not in explicitly_grouped
    ]
    if root_resource is None:
        # Auto-create
        root_resource = Resource(
            id=scenario.root_resource_id,
            name="Project",
            type=ResourceType.PROJECT,
            subresource_ids=top_level_resource_ids,
        )
        _build_resource(root, root_resource)
    else:
        # Respect an explicit list if the caller set one; otherwise auto-populate
        if not root_resource.subresource_ids:
            root_resource.subresource_ids = top_level_resource_ids
        _build_resource(root, root_resource)

    for r in scenario.resources:
        if r.id != scenario.root_resource_id:
            _build_resource(root, r)

    # rootTask
    etree.SubElement(root, "top-task", attrib={"idref": scenario.root_task_id})
    root_task = next((t for t in scenario.tasks if t.id == scenario.root_task_id), None)
    if root_task is None:
        # Auto-create root group containing all top-level tasks
        top_level_ids = [t.id for t in scenario.tasks if not _is_subtask_of_any(t.id, scenario)]
        root_task = Task(
            id=scenario.root_task_id, type=TaskType.GROUP, subtask_ids=top_level_ids
        )
        _build_task(root, root_task)
    else:
        _build_task(root, root_task)

    for t in scenario.tasks:
        if t.id != scenario.root_task_id:
            _build_task(root, t)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _is_subtask_of_any(task_id: str, scenario: Scenario) -> bool:
    return any(task_id in t.subtask_ids for t in scenario.tasks)


_GANTT_SCALES = (
    # (scale-name, full-day-width). Values copied from OmniPlan-saved files
    # (with-baseline.oplx etc.). Without these, OmniPlan's gantt zoom default
    # compresses the visible range so short task bars render sub-pixel.
    ("Automatic", "300"),
    ("Day", "1215"),
    ("Hour", "65880"),
    ("Minute", "64800"),
    ("Month", "34.5"),
    ("Quarter", "9.6"),
    ("Week", "162"),
    ("Year", "2.3625"),
)


def _build_window(root: etree._Element) -> None:
    """Emit a minimal <window> view-config so the gantt actually renders bars.

    Spec says <window> is optional. In practice OmniPlan's runtime fallback
    for gantt zoom (when <window> is absent) compresses the visible time
    range so much that hour/day-scale task bars become sub-pixel and the
    gantt area renders blank. Emitting <task-view><gantt-view><scale .../>>
    with the standard 8-scale table makes Automatic zoom pick a usable
    full-day-width. Verified 2026-05-27 against OmniPlan 4.10.2.
    """
    window = etree.SubElement(root, "window")
    etree.SubElement(window, "view").text = "task"
    task_view = etree.SubElement(window, "task-view")
    gantt_view = etree.SubElement(task_view, "gantt-view")
    etree.SubElement(gantt_view, "view-mode").text = "actual"
    for name, width in _GANTT_SCALES:
        scale = etree.SubElement(
            gantt_view,
            "scale",
            attrib={"scale-name": name, "full-day-width": width},
        )
        if name == "Automatic":
            etree.SubElement(scale, "selected")


def _build_toc(project: Project) -> bytes:
    root = etree.Element(
        "omniplan",
        attrib={"file-format-version": "3"},
        nsmap=NSMAP,
    )
    _build_window(root)
    proj = etree.SubElement(root, "project")
    etree.SubElement(proj, "next-task-id").text = str(project.next_task_id)
    etree.SubElement(proj, "next-resource-id").text = str(project.next_resource_id)

    etree.SubElement(
        proj,
        "scenario",
        attrib={
            "id": project.actual.id,
            "name": project.actual.name,
            "filename": project.actual.filename,
        },
    )
    for b in project.baselines:
        etree.SubElement(
            proj,
            "scenario",
            attrib={"id": b.id, "name": b.name, "filename": b.filename},
        )

    if project.custom_data_keys:
        keys = etree.SubElement(proj, "task-user-data-keys")
        ud = etree.SubElement(keys, "user-data")
        for k in project.custom_data_keys:
            ke = etree.SubElement(ud, "key")
            ke.text = k
            etree.SubElement(ud, "null")

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _build_changelog(project: Project) -> bytes:
    root = etree.Element("changelog", nsmap=NSMAP)
    etree.SubElement(root, "version").text = "4.0"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def generate(project: Project, out_path: str | Path, bundle: bool = False) -> Path:
    """Write `project` to an .oplx file at `out_path`.

    Args:
        project: The Project model.
        out_path: Output path (typically with `.oplx` extension).
        bundle: If True, produce a directory bundle. Default False (zip variant).

    Returns:
        The path written.
    """
    out_path = Path(out_path)

    # Auto-fill scenario id if it's still the placeholder
    if project.actual.id in ("auto", ""):
        project.actual.id = _scenario_id()

    actual_xml = _build_scenario(project.actual)
    toc_xml = _build_toc(project)
    changelog_xml = _build_changelog(project)
    baseline_files = {b.filename: _build_scenario(b) for b in project.baselines}

    if bundle:
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "__TOC.xml").write_bytes(toc_xml)
        (out_path / "__changelog.xml").write_bytes(changelog_xml)
        (out_path / project.actual.filename).write_bytes(actual_xml)
        for fname, data in baseline_files.items():
            (out_path / fname).write_bytes(data)
    else:
        # Zip variant — flat structure, no QuickLook/ subdir
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("__TOC.xml", toc_xml)
            z.writestr("__changelog.xml", changelog_xml)
            z.writestr(project.actual.filename, actual_xml)
            for fname, data in baseline_files.items():
                z.writestr(fname, data)

    return out_path


def from_yaml(yaml_text: str, base_dir: str | Path | None = None) -> Project:
    """Parse a YAML project description into a Project model.

    Schema (loose; see examples/ for full):

      title: My Project
      start_date: 2026-06-01T13:00:00Z
      tasks:
        - id: t1
          title: Plan
          effort: 14400
          attachments:
            - path: docs/plan-brief.pdf            # resolved against base_dir
            - uri: file:///absolute/path/file.txt  # used verbatim
            - uri: https://example.com/spec.html   # no bookmark needed
        - id: t2
          title: Build
          effort: 28800
          depends_on: [t1]

    Args:
        yaml_text: The YAML source.
        base_dir: Optional directory to resolve attachment ``path:`` entries
            against. When None, relative attachment paths are resolved against
            the current working directory. ``from_yaml_file()`` sets this to
            the YAML file's parent automatically.

    Attachment handling:
        - Items with ``path:`` are resolved (against ``base_dir`` if relative)
          and passed through ``oplx.bookmark.make_bookmark()`` to generate
          the ``file://`` URI + base64 bookmark data. This requires the
          ``[macos]`` extra; raises ``BookmarkUnavailableError`` otherwise.
        - Items with ``uri:`` are used verbatim. For ``file://`` URIs, the
          caller is responsible for supplying ``bookmark_data:`` (otherwise
          the generator will refuse to emit and the lint will fire
          ``ATTACH-NO-BOOKMARK``).
        - ``http://`` / ``https://`` URIs do not need ``bookmark_data``.
    """
    data = yaml.safe_load(StringIO(yaml_text))
    project = Project(title=data.get("title", ""))

    base = Path(base_dir) if base_dir is not None else Path.cwd()

    # Tasks
    for t_data in data.get("tasks", []):
        task = Task(
            id=t_data["id"],
            title=t_data.get("title", ""),
            type=TaskType(t_data.get("type", "task")),
            effort=t_data.get("effort"),
        )
        for prereq_id in t_data.get("depends_on", []):
            task.prerequisites.append(Dependency(idref=prereq_id))
        for att_data in t_data.get("attachments", []):
            task.attachments.append(_attachment_from_yaml(att_data, base))
        project.actual.tasks.append(task)

    # start_date — PyYAML may already have parsed it as a datetime
    sd = data.get("start_date")
    if isinstance(sd, datetime):
        from datetime import UTC

        project.actual.start_date = sd if sd.tzinfo else sd.replace(tzinfo=UTC)
    elif isinstance(sd, str):
        project.actual.start_date = datetime.fromisoformat(sd.replace("Z", "+00:00"))

    return project


def from_yaml_file(yaml_path: str | Path) -> Project:
    """Load a YAML project description from a file path.

    Sets ``base_dir`` to the file's parent so relative attachment paths
    (``attachments: [{path: docs/spec.pdf}]``) resolve against the YAML
    file's directory rather than the caller's CWD.
    """
    yaml_path = Path(yaml_path)
    return from_yaml(yaml_path.read_text(), base_dir=yaml_path.parent)


def _attachment_from_yaml(att_data: Any, base_dir: Path) -> "Attachment":
    """Build an Attachment from a YAML mapping.

    Supports two shapes::

        # path: relative or absolute filesystem path; bookmark generated
        - path: docs/spec.pdf

        # uri: raw URI; bookmark_data optional for http(s)://
        - uri: file:///abs/path/file.pdf
          bookmark_data: BASE64...

    """
    from .models import Attachment

    if not isinstance(att_data, dict):
        raise ValueError(
            f"attachment must be a mapping (got {type(att_data).__name__}): {att_data!r}"
        )

    if "path" in att_data:
        from .bookmark import make_bookmark

        raw = Path(att_data["path"])
        resolved = raw if raw.is_absolute() else (base_dir / raw).resolve()
        uri, b64 = make_bookmark(resolved)
        return Attachment(uri=uri, bookmark_data=b64)

    if "uri" in att_data:
        return Attachment(
            uri=att_data["uri"],
            bookmark_data=att_data.get("bookmark_data", ""),
        )

    raise ValueError(
        f"attachment entry must have either `path:` (filesystem path, "
        f"bookmark auto-generated) or `uri:` (raw URI). Got: {att_data!r}"
    )
