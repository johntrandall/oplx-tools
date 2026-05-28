"""Lint coverage for the rest of the silent-corruption catalog.

test_roundtrip.py already covers TYPE-CASE; this file covers the remaining
codes: orphaned tasks, units="0", dep-kind case, recalculate-invalid,
missing-file, file-not-found, and the directory-bundle path.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from oplx.lint import LintFinding, lint

NS = "http://www.omnigroup.com/namespace/OmniPlan/v2"


def _toc(scenarios: list[tuple[str, str, str]] | None = None) -> bytes:
    """Build a __TOC.xml. scenarios is [(id, name, filename)]."""
    if scenarios is None:
        scenarios = [("test", "Actual", "Actual.xml")]
    sc_xml = "".join(
        f'<scenario id="{sid}" name="{name}" filename="{fn}"/>'
        for sid, name, fn in scenarios
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<omniplan xmlns="{NS}" file-format-version="3">
  <project>
    <next-task-id>2</next-task-id>
    <next-resource-id>2</next-resource-id>
    {sc_xml}
  </project>
</omniplan>
""".encode()


def _changelog() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<changelog xmlns="' + NS.encode() + b'">'
        b"<version>4.0</version></changelog>"
    )


def _scenario(
    root_children: str,
    tasks_xml: str,
    *,
    sid: str = "test",
    extra_resources: str = "",
) -> bytes:
    """Build a complete scenario XML.

    root_children: XML to place INSIDE <task id="t-1"> as additional children
        (always include the <child-task .../> entries for the sibling tasks).
    tasks_xml: XML for sibling <task> elements that appear after </task> closes t-1.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scenario xmlns="{NS}" id="{sid}">
  <start-date>2026-06-01T13:00:00.000Z</start-date>
  <top-resource idref="r-1"/>
  <resource id="r-1"><name>Project</name><type>Project</type></resource>{extra_resources}
  <top-task idref="t-1"/>
  <task id="t-1">
    <type>group</type>
    <recalculate>duration</recalculate>
    <static-cost>0</static-cost>
{root_children}
  </task>
{tasks_xml}
</scenario>
""".encode()


def _ok_task(tid: str, *, extras: str = "") -> str:
    """A minimal valid task element."""
    return (
        f'  <task id="{tid}"><title>{tid}</title>'
        '<recalculate>duration</recalculate>'
        f'<static-cost>0</static-cost>{extras}</task>\n'
    )


def _write_zip(
    tmp_path: Path,
    actual_bytes: bytes,
    *,
    name: str = "test.oplx",
    toc: bytes | None = None,
    omit: list[str] | None = None,
) -> Path:
    omit = omit or []
    out = tmp_path / name
    with zipfile.ZipFile(out, "w") as z:
        if "__TOC.xml" not in omit:
            z.writestr("__TOC.xml", toc or _toc())
        if "__changelog.xml" not in omit:
            z.writestr("__changelog.xml", _changelog())
        if "Actual.xml" not in omit:
            z.writestr("Actual.xml", actual_bytes)
    return out


def _simple_actual() -> bytes:
    return _scenario('    <child-task idref="t1"/>', _ok_task("t1"))


def _codes(findings: list[LintFinding]) -> list[str]:
    return [f.code for f in findings]


def test_file_not_found_returns_critical(tmp_path: Path) -> None:
    findings = lint(tmp_path / "does-not-exist.oplx")
    assert _codes(findings) == ["FILE-NOT-FOUND"]
    assert findings[0].severity == "CRITICAL"


def test_missing_toc(tmp_path: Path) -> None:
    out = tmp_path / "no-toc.oplx"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("__changelog.xml", _changelog())
        z.writestr("Actual.xml", _simple_actual())
    findings = lint(out)
    assert "MISSING-TOC" in _codes(findings)


def test_missing_changelog_and_actual(tmp_path: Path) -> None:
    out = tmp_path / "shell.oplx"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("__TOC.xml", _toc())
    findings = lint(out)
    codes = _codes(findings)
    assert "MISSING-CHANGELOG" in codes
    assert "MISSING-ACTUAL" in codes


def test_directory_bundle(tmp_path: Path) -> None:
    """Lint accepts a directory bundle, not just a zip."""
    bundle = tmp_path / "bundle.oplx"
    bundle.mkdir()
    (bundle / "__TOC.xml").write_bytes(_toc())
    (bundle / "__changelog.xml").write_bytes(_changelog())
    (bundle / "Actual.xml").write_bytes(_simple_actual())
    findings = lint(bundle)
    blockers = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
    assert blockers == []


def test_orphaned_task(tmp_path: Path) -> None:
    actual = _scenario(
        '    <child-task idref="t1"/>',
        _ok_task("t1") + _ok_task("t99"),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    orphans = [f for f in findings if f.code == "ORPHANED-TASK"]
    assert len(orphans) == 1
    assert "t99" in orphans[0].message
    assert orphans[0].severity == "HIGH"


def test_units_zero_flagged(tmp_path: Path) -> None:
    actual = _scenario(
        '    <child-task idref="t1"/>',
        _ok_task("t1", extras='<assignment idref="r1" units="0"/>'),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "UNITS-ZERO" and f.severity == "HIGH" for f in findings)


def test_dep_kind_lowercase_flagged(tmp_path: Path) -> None:
    actual = _scenario(
        '    <child-task idref="t1"/>\n    <child-task idref="t2"/>',
        _ok_task("t1") + _ok_task(
            "t2", extras='<prerequisite-task idref="t1" kind="ff"/>'
        ),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "DEP-KIND-CASE" for f in findings)


def test_recalculate_invalid_flagged(tmp_path: Path) -> None:
    # Build a task with a bad <recalculate> directly
    bad_task = (
        '  <task id="t1"><title>t1</title>'
        '<recalculate>none</recalculate>'
        '<static-cost>0</static-cost></task>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', bad_task)
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "RECALCULATE-INVALID" for f in findings)


def test_resource_type_lowercase_flagged(tmp_path: Path) -> None:
    extra = '\n  <resource id="r1"><name>Bob</name><type>staff</type></resource>'
    actual = _scenario(
        '    <child-task idref="t1"/>',
        _ok_task("t1"),
        extra_resources=extra,
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "RESOURCE-TYPE-INVALID" for f in findings)


def test_invalid_task_type_unknown_value(tmp_path: Path) -> None:
    bad_task = (
        '  <task id="t1"><title>t1</title>'
        '<type>chimera</type>'
        '<recalculate>duration</recalculate>'
        '<static-cost>0</static-cost></task>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', bad_task)
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "TYPE-INVALID" for f in findings)


def test_missing_baseline_file(tmp_path: Path) -> None:
    toc = _toc(
        scenarios=[
            ("act", "Actual", "Actual.xml"),
            ("bsl", "Baseline1", "Baseline1.xml"),
        ]
    )
    out = _write_zip(tmp_path, _simple_actual(), toc=toc)
    findings = lint(out)
    assert any(f.code == "MISSING-BASELINE-FILE" for f in findings)


def test_root_task_missing_idref_target(tmp_path: Path) -> None:
    """<top-task idref=missing-root/> but no matching <task id=missing-root/>."""
    actual = f"""<?xml version="1.0" encoding="UTF-8"?>
<scenario xmlns="{NS}" id="rtm">
  <start-date>2026-06-01T13:00:00.000Z</start-date>
  <top-resource idref="r-1"/>
  <resource id="r-1"><name>Project</name><type>Project</type></resource>
  <top-task idref="missing-root"/>
  <task id="t1"><title>x</title><recalculate>duration</recalculate><static-cost>0</static-cost></task>
</scenario>
""".encode()
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert any(f.code == "ROOT-TASK-MISSING" for f in findings)


def test_orphan_exemption_is_exact_not_prefix(tmp_path: Path) -> None:
    """The orphan-exemption sentinel must be {t-1, root_id} exactly — not a
    `startswith('t-')` prefix that would accidentally exempt user-authored
    ids like `t-foo` or `t-2`.
    """
    # Root group references only t-1 (the canonical root), not t-orphan.
    # t-orphan is a user-authored id starting with `t-` but should still be
    # caught as orphaned.
    body = (
        _ok_task("t1")
        + '  <task id="t-orphan"><title>tricky</title>'
        '<recalculate>duration</recalculate>'
        '<static-cost>0</static-cost></task>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', body)
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    orphans = [f for f in findings if f.code == "ORPHANED-TASK"]
    assert any("t-orphan" in f.message for f in orphans), (
        "User-authored ids starting with 't-' must still be orphan-checked"
    )


def test_t1_collision_flagged(tmp_path: Path) -> None:
    """User task with id='t1' that's a subtask of an explicit (non-root) group
    is silently dropped by OmniPlan. Lint should catch it HIGH.
    """
    body = (
        _ok_task("t1")
        + _ok_task("t2")
        + _ok_task("t3")
        + '  <task id="g1"><title>group</title><type>group</type>'
        '<recalculate>duration</recalculate><static-cost>0</static-cost>'
        '<child-task idref="t1"/><child-task idref="t2"/>'
        '<child-task idref="t3"/></task>\n'
    )
    actual = _scenario('    <child-task idref="g1"/>', body)
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    t1c = [f for f in findings if f.code == "T1-COLLISION"]
    assert len(t1c) == 1, f"expected one T1-COLLISION, got {len(t1c)}"
    assert t1c[0].severity == "HIGH"


def test_t1_as_direct_child_of_root_not_flagged(tmp_path: Path) -> None:
    """t1 as a direct child of the root t-1 is fine — that's how f02 works."""
    actual = _scenario(
        '    <child-task idref="t1"/>\n    <child-task idref="t2"/>',
        _ok_task("t1") + _ok_task("t2"),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert not any(f.code == "T1-COLLISION" for f in findings)


def test_dep_missing_flagged(tmp_path: Path) -> None:
    """A <prerequisite-task idref="X"/> pointing at a non-existent task X
    must be flagged HIGH — OmniPlan silently drops the dep on load and the
    successor schedules as if it had no predecessor.
    """
    # t1 has a prereq pointing at t-gone (which doesn't exist anywhere).
    body = (
        '  <task id="t1"><title>t1</title>'
        '<recalculate>duration</recalculate><static-cost>0</static-cost>'
        '<prerequisite-task idref="t-gone"/></task>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', body)
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    dep_missing = [f for f in findings if f.code == "DEP-MISSING"]
    assert len(dep_missing) == 1
    assert dep_missing[0].severity == "HIGH"
    assert "t-gone" in dep_missing[0].message


def test_dep_present_not_flagged(tmp_path: Path) -> None:
    """A prereq pointing at an existing task is clean."""
    body = (
        _ok_task("t1")
        + '  <task id="t2"><title>t2</title>'
        '<recalculate>duration</recalculate><static-cost>0</static-cost>'
        '<prerequisite-task idref="t1"/></task>\n'
    )
    actual = _scenario(
        '    <child-task idref="t1"/>\n    <child-task idref="t2"/>', body
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert not any(f.code == "DEP-MISSING" for f in findings)


def test_lint_finding_str_includes_location() -> None:
    f = LintFinding("CRITICAL", "TYPE-CASE", "boom", "Actual.xml")
    s = str(f)
    assert "CRITICAL" in s and "TYPE-CASE" in s and "Actual.xml" in s


def test_task_id_numbering_flags_non_t_id(tmp_path: Path) -> None:
    """A user task id that doesn't match `t<digits>` (e.g. `m1`, `g1`, `gX`)
    causes OmniPlan to silently drop sibling tasks. Lint should flag it HIGH.
    """
    body = (
        _ok_task("t2")
        + '  <task id="m1"><title>milestone</title><type>milestone</type>'
        '<recalculate>duration</recalculate><static-cost>0</static-cost></task>\n'
    )
    actual = _scenario(
        '    <child-task idref="t2"/>\n    <child-task idref="m1"/>',
        body,
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    ids = [f for f in findings if f.code == "TASK-ID-NUMBERING"]
    assert len(ids) == 1, f"expected one TASK-ID-NUMBERING, got {len(ids)}"
    assert ids[0].severity == "HIGH"
    assert "'m1'" in ids[0].message


def test_task_id_numbering_root_id_exempt(tmp_path: Path) -> None:
    """The root group's own id (`t-1`) does NOT match `t<digits>` but is
    by-design and must not be flagged.
    """
    actual = _scenario(
        '    <child-task idref="t2"/>',
        _ok_task("t2"),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert not any(f.code == "TASK-ID-NUMBERING" for f in findings)


def test_task_id_numbering_t_numbered_ids_not_flagged(tmp_path: Path) -> None:
    """All-t-numbered ids must not be flagged regardless of task type."""
    body = (
        _ok_task("t2")
        + '  <task id="t3"><title>group</title><type>group</type>'
        '<recalculate>duration</recalculate><static-cost>0</static-cost>'
        '<child-task idref="t4"/></task>\n'
        + _ok_task("t4")
    )
    actual = _scenario(
        '    <child-task idref="t2"/>\n    <child-task idref="t3"/>',
        body,
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    assert not any(f.code == "TASK-ID-NUMBERING" for f in findings)


def test_missing_window_flagged(tmp_path: Path) -> None:
    """A __TOC.xml without <window> renders blank gantt — lint MEDIUM."""
    bare_toc = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<omniplan xmlns="' + NS.encode() + b'" file-format-version="3">\n'
        b'  <project>\n'
        b'    <next-task-id>2</next-task-id>\n'
        b'    <next-resource-id>2</next-resource-id>\n'
        b'    <scenario id="t" name="Actual" filename="Actual.xml"/>\n'
        b'  </project>\n'
        b'</omniplan>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', _ok_task("t1"))
    out = _write_zip(tmp_path, actual, toc=bare_toc)
    findings = lint(out)
    mw = [f for f in findings if f.code == "MISSING-WINDOW"]
    assert len(mw) == 1, f"expected one MISSING-WINDOW, got {len(mw)}"
    assert mw[0].severity == "MEDIUM"


def test_window_scale_zero_flagged(tmp_path: Path) -> None:
    """A <window> with full-day-width=0 on any scale renders broken — MEDIUM."""
    bad_toc = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<omniplan xmlns="' + NS.encode() + b'" file-format-version="3">\n'
        b'  <window>\n'
        b'    <view>task</view>\n'
        b'    <task-view><gantt-view>\n'
        b'      <view-mode>actual</view-mode>\n'
        b'      <scale scale-name="Automatic" full-day-width="0"><selected/></scale>\n'
        b'    </gantt-view></task-view>\n'
        b'  </window>\n'
        b'  <project>\n'
        b'    <next-task-id>2</next-task-id>\n'
        b'    <next-resource-id>2</next-resource-id>\n'
        b'    <scenario id="t" name="Actual" filename="Actual.xml"/>\n'
        b'  </project>\n'
        b'</omniplan>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', _ok_task("t1"))
    out = _write_zip(tmp_path, actual, toc=bad_toc)
    findings = lint(out)
    ws = [f for f in findings if f.code == "WINDOW-SCALE-INVALID"]
    assert len(ws) == 1, f"expected one WINDOW-SCALE-INVALID, got {len(ws)}"
    assert ws[0].severity == "MEDIUM"
    assert "Automatic" in ws[0].message


def test_window_scale_negative_flagged(tmp_path: Path) -> None:
    """Negative full-day-width is also broken."""
    bad_toc = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<omniplan xmlns="' + NS.encode() + b'" file-format-version="3">\n'
        b'  <window>\n'
        b'    <task-view><gantt-view>\n'
        b'      <scale scale-name="Day" full-day-width="-5"/>\n'
        b'    </gantt-view></task-view>\n'
        b'  </window>\n'
        b'  <project><next-task-id>2</next-task-id>'
        b'<next-resource-id>2</next-resource-id>'
        b'<scenario id="t" name="Actual" filename="Actual.xml"/></project>\n'
        b'</omniplan>\n'
    )
    actual = _scenario('    <child-task idref="t1"/>', _ok_task("t1"))
    out = _write_zip(tmp_path, actual, toc=bad_toc)
    findings = lint(out)
    ws = [f for f in findings if f.code == "WINDOW-SCALE-INVALID"]
    assert len(ws) == 1


def test_window_present_no_finding(tmp_path: Path) -> None:
    """A generator-emitted file (with <window> + sane scales) passes clean."""
    from datetime import UTC, datetime as _dt

    from oplx import Project, Scenario, Task, generate

    proj = Project(actual=Scenario(
        id="ok-window", start_date=_dt(2026, 6, 1, 13, 0, tzinfo=UTC),
        tasks=[Task(id="t1", title="Solo", effort=14400)],
    ))
    out = tmp_path / "ok.oplx"
    generate(proj, out)
    findings = lint(out)
    assert not any(f.code == "MISSING-WINDOW" for f in findings)
    assert not any(f.code == "WINDOW-SCALE-INVALID" for f in findings)


def test_root_resource_auto_populates_child_resource(tmp_path: Path) -> None:
    """Without <child-resource> entries on r-1, OmniPlan silently drops every
    resource. Generator must auto-populate the root resource's subresource_ids
    with every top-level user resource. Verified 2026-05-28.
    """
    from datetime import UTC, datetime as _dt
    import zipfile as _zip

    from lxml import etree as _et

    from oplx import Project, Resource, Scenario, Task, generate
    from oplx.models import ResourceType

    proj = Project(actual=Scenario(
        id="r-test", start_date=_dt(2026, 6, 1, 13, 0, tzinfo=UTC),
        resources=[
            Resource(id="r1", name="Alice", type=ResourceType.STAFF),
            Resource(id="r2", name="Bob", type=ResourceType.STAFF),
        ],
        tasks=[Task(id="t1", title="Solo", effort=14400)],
    ))
    out = tmp_path / "with-resources.oplx"
    generate(proj, out)

    with _zip.ZipFile(out) as z:
        actual_xml = z.read("Actual.xml")
    root = _et.fromstring(actual_xml)
    r1_root = next(
        r for r in root.findall(f"{{{NS}}}resource") if r.get("id") == "r-1"
    )
    child_idrefs = {
        c.get("idref") for c in r1_root.findall(f"{{{NS}}}child-resource")
    }
    assert child_idrefs == {"r1", "r2"}, (
        f"r-1 should list both user resources as <child-resource>, got {child_idrefs}"
    )


def test_task_id_numbering_t0_flagged(tmp_path: Path) -> None:
    """`t0` is permitted by `^t\\d+$` but NOT by the tighter `^t[1-9]\\d*$`.
    Verified 2026-05-27 against OmniPlan 4.10.2: a `t0` sibling causes
    OmniPlan to silently drop other siblings (e.g. [t0, t1, t2] → only
    t0 + t2 visible; t1 dropped). So `t0` must be flagged.
    """
    actual = _scenario(
        '    <child-task idref="t0"/>',
        _ok_task("t0"),
    )
    out = _write_zip(tmp_path, actual)
    findings = lint(out)
    ids = [f for f in findings if f.code == "TASK-ID-NUMBERING"]
    assert len(ids) == 1, f"expected one TASK-ID-NUMBERING for t0, got {len(ids)}"
    assert "'t0'" in ids[0].message


def test_generator_emits_window_view_config(tmp_path: Path) -> None:
    """The generator must emit a <window> block in __TOC.xml so OmniPlan's
    gantt picks a usable zoom level. Without this, task bars render
    sub-pixel and the gantt area appears blank.
    """
    import zipfile as _zip
    from datetime import UTC, datetime

    from lxml import etree as _etree

    from oplx import Project, Scenario, Task, generate

    proj = Project(
        actual=Scenario(
            id="window-test",
            start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
            tasks=[Task(id="t1", title="Solo", effort=14400)],
        )
    )
    out = tmp_path / "window.oplx"
    generate(proj, out)

    with _zip.ZipFile(out) as z:
        toc_bytes = z.read("__TOC.xml")
    root = _etree.fromstring(toc_bytes)
    window = root.find(f"{{{NS}}}window")
    assert window is not None, "<window> missing — gantt bars will render blank"

    view = window.find(f"{{{NS}}}view")
    assert view is not None and view.text == "task"

    gantt = window.find(f"{{{NS}}}task-view/{{{NS}}}gantt-view")
    assert gantt is not None
    scales = gantt.findall(f"{{{NS}}}scale")
    scale_names = [s.get("scale-name") for s in scales]
    assert "Automatic" in scale_names
    assert "Day" in scale_names
    selected = [s for s in scales if s.find(f"{{{NS}}}selected") is not None]
    assert len(selected) == 1 and selected[0].get("scale-name") == "Automatic"
