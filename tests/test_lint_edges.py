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


def test_lint_finding_str_includes_location() -> None:
    f = LintFinding("CRITICAL", "TYPE-CASE", "boom", "Actual.xml")
    s = str(f)
    assert "CRITICAL" in s and "TYPE-CASE" in s and "Actual.xml" in s
