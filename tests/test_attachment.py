"""Tests for <attachment> emit, parse, lint, and YAML loading.

Wire form (verified 2026-05-28 against OmniPlan 4.10.2 build 232.5.0):

    <attachment uri="file:///abs/path/file.ext">
      <bookmarkData>BASE64_NSURL_BOOKMARK</bookmarkData>
    </attachment>

Silent-corruption gotcha: a file:// attachment without <bookmarkData>
opens cleanly but `count attachments of task` returns 0 (lint code
ATTACH-NO-BOOKMARK).
"""

from __future__ import annotations

import base64
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from oplx import Attachment, Project, Task, from_yaml, generate, lint, parse
from oplx.models import Scenario


def _bookmark_b64(n_bytes: int = 64) -> str:
    """Return a deterministic base64 blob that looks plausible as a bookmark."""
    return base64.b64encode(b"\x00" * n_bytes).decode("ascii")


def _scenario_with_attachments(*attachments: Attachment) -> Scenario:
    return Scenario(
        id="att-test",
        start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
        tasks=[Task(id="t1", title="Task with attachment", effort=3600,
                    attachments=list(attachments))],
    )


def test_attachment_emit_and_parse_roundtrip(tmp_path: Path) -> None:
    """Generator emits <attachment uri=... ><bookmarkData/></attachment>;
    parser recovers both fields verbatim.
    """
    bm = _bookmark_b64()
    proj = Project(actual=_scenario_with_attachments(
        Attachment(uri="file:///tmp/test.txt", bookmark_data=bm),
    ))
    out = tmp_path / "with-att.oplx"
    generate(proj, out)

    # Inspect raw XML for the structural assertions
    with zipfile.ZipFile(out) as z:
        xml = z.read("Actual.xml").decode()
    assert '<attachment uri="file:///tmp/test.txt">' in xml
    assert f"<bookmarkData>{bm}</bookmarkData>" in xml

    # Round-trip via parse
    parsed = parse(out)
    t1 = next(t for t in parsed.actual.tasks if t.id == "t1")
    assert len(t1.attachments) == 1
    assert t1.attachments[0].uri == "file:///tmp/test.txt"
    assert t1.attachments[0].bookmark_data == bm


def test_attachment_multiple_per_task_roundtrip(tmp_path: Path) -> None:
    bm1, bm2 = _bookmark_b64(64), _bookmark_b64(128)
    proj = Project(actual=_scenario_with_attachments(
        Attachment(uri="file:///tmp/a.txt", bookmark_data=bm1),
        Attachment(uri="file:///tmp/b.txt", bookmark_data=bm2),
    ))
    out = tmp_path / "two-att.oplx"
    generate(proj, out)

    parsed = parse(out)
    t1 = next(t for t in parsed.actual.tasks if t.id == "t1")
    assert len(t1.attachments) == 2
    assert [a.uri for a in t1.attachments] == [
        "file:///tmp/a.txt", "file:///tmp/b.txt",
    ]
    assert [a.bookmark_data for a in t1.attachments] == [bm1, bm2]


def test_attachment_emit_refuses_file_uri_without_bookmark(tmp_path: Path) -> None:
    """Generator refuses to silently produce ATTACH-NO-BOOKMARK output."""
    proj = Project(actual=_scenario_with_attachments(
        Attachment(uri="file:///tmp/no-bookmark.txt"),
    ))
    out = tmp_path / "bad.oplx"
    with pytest.raises(ValueError, match="bookmark_data"):
        generate(proj, out)


def test_attachment_http_uri_emits_without_bookmark(tmp_path: Path) -> None:
    """http:// URIs do not need <bookmarkData>; the generator emits them bare."""
    proj = Project(actual=_scenario_with_attachments(
        Attachment(uri="https://example.com/spec.html"),
    ))
    out = tmp_path / "http-att.oplx"
    generate(proj, out)

    with zipfile.ZipFile(out) as z:
        xml = z.read("Actual.xml").decode()
    assert 'uri="https://example.com/spec.html"' in xml
    assert "<bookmarkData>" not in xml  # none emitted for http(s)://


def test_attachment_element_order_after_static_cost(tmp_path: Path) -> None:
    """<attachment> appears after <static-cost> and before <prerequisite-task>.

    Spec § actual-xml.md `<attachment>` element. Verified 2026-05-28 against
    OmniPlan 4.10.2 build 232.5.0.
    """
    from oplx.models import Dependency

    bm = _bookmark_b64()
    proj = Project(actual=Scenario(
        id="order-test",
        start_date=datetime(2026, 6, 1, 13, 0, tzinfo=UTC),
        tasks=[
            Task(id="t1", title="Source", effort=3600),
            Task(
                id="t2",
                title="Target with attachment",
                effort=3600,
                attachments=[Attachment(uri="file:///tmp/x", bookmark_data=bm)],
                prerequisites=[Dependency(idref="t1")],
            ),
        ],
    ))
    out = tmp_path / "order.oplx"
    generate(proj, out)

    with zipfile.ZipFile(out) as z:
        xml = z.read("Actual.xml").decode()

    # Find the t2 <task> element span
    t2_start = xml.find('<task id="t2">')
    t2_end = xml.find("</task>", t2_start)
    t2_body = xml[t2_start:t2_end]
    sc = t2_body.find("<static-cost>")
    att = t2_body.find("<attachment ")
    prereq = t2_body.find("<prerequisite-task")
    assert sc < att < prereq, (
        f"element order wrong: static-cost={sc}, attachment={att}, "
        f"prerequisite-task={prereq}"
    )


def _bundle_oplx(tmp_path: Path, attachment_xml: str) -> Path:
    """Build a 2-file .oplx with a single task carrying the given attachment XML."""
    out = tmp_path / "fixture.oplx"
    actual = f"""<?xml version="1.0" encoding="UTF-8"?>
<scenario xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2" id="lint-att">
  <start-date>2026-06-01T13:00:00.000Z</start-date>
  <top-resource idref="r-1"/>
  <resource id="r-1"><name>Project</name><type>Project</type></resource>
  <top-task idref="t-1"/>
  <task id="t-1">
    <type>group</type><recalculate>duration</recalculate><static-cost>0</static-cost>
    <child-task idref="t1"/>
  </task>
  <task id="t1">
    <title>T</title><effort>3600</effort>
    <recalculate>duration</recalculate><static-cost>0</static-cost>
    {attachment_xml}
  </task>
</scenario>
"""
    toc = """<?xml version="1.0" encoding="UTF-8"?>
<omniplan xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2" file-format-version="3">
  <project>
    <next-task-id>2</next-task-id>
    <next-resource-id>2</next-resource-id>
    <scenario id="lint-att" name="Actual" filename="Actual.xml"/>
    <window><view>task</view><task-view><gantt-view><view-mode>actual</view-mode>
      <scale scale-name="Automatic" full-day-width="300"><selected/></scale>
    </gantt-view></task-view></window>
  </project>
</omniplan>
"""
    changelog = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<changelog xmlns="http://www.omnigroup.com/namespace/OmniPlan/v2">'
        "<version>4.0</version></changelog>"
    )
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("__TOC.xml", toc)
        z.writestr("__changelog.xml", changelog)
        z.writestr("Actual.xml", actual)
    return out


def test_lint_attach_no_bookmark_self_closing(tmp_path: Path) -> None:
    out = _bundle_oplx(tmp_path, '<attachment uri="file:///tmp/nope.txt"/>')
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-BOOKMARK"]
    assert len(matched) == 1
    assert matched[0].severity == "HIGH"


def test_lint_attach_no_bookmark_empty_child(tmp_path: Path) -> None:
    out = _bundle_oplx(
        tmp_path,
        '<attachment uri="file:///tmp/nope.txt"><bookmarkData></bookmarkData></attachment>',
    )
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-BOOKMARK"]
    assert len(matched) == 1


def test_lint_attach_no_bookmark_passes_with_bookmark(tmp_path: Path) -> None:
    bm = _bookmark_b64()
    out = _bundle_oplx(
        tmp_path,
        f'<attachment uri="file:///tmp/ok.txt"><bookmarkData>{bm}</bookmarkData></attachment>',
    )
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-BOOKMARK"]
    assert matched == []


def test_lint_attach_no_bookmark_skipped_for_http(tmp_path: Path) -> None:
    """http(s):// URIs are network-resolved; no bookmark needed."""
    out = _bundle_oplx(tmp_path, '<attachment uri="https://example.com/x"/>')
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-BOOKMARK"]
    assert matched == []


def test_lint_attach_no_file_flags_missing(tmp_path: Path) -> None:
    bm = _bookmark_b64()
    missing = "/tmp/this-path-definitely-does-not-exist-xyz123abc"
    out = _bundle_oplx(
        tmp_path,
        f'<attachment uri="file://{missing}"><bookmarkData>{bm}</bookmarkData></attachment>',
    )
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-FILE"]
    assert len(matched) == 1
    assert matched[0].severity == "MEDIUM"


def test_lint_attach_no_file_passes_when_exists(tmp_path: Path) -> None:
    target = tmp_path / "exists.txt"
    target.write_text("hi")
    bm = _bookmark_b64()
    out = _bundle_oplx(
        tmp_path,
        f'<attachment uri="file://{target}"><bookmarkData>{bm}</bookmarkData></attachment>',
    )
    findings = lint(out)
    matched = [f for f in findings if f.code == "ATTACH-NO-FILE"]
    assert matched == []


def test_yaml_attachment_uri_passthrough() -> None:
    yaml_text = """
title: With attachment
tasks:
  - id: t1
    title: Task
    effort: 3600
    attachments:
      - uri: https://example.com/spec.html
"""
    proj = from_yaml(yaml_text)
    t1 = next(t for t in proj.actual.tasks if t.id == "t1")
    assert len(t1.attachments) == 1
    assert t1.attachments[0].uri == "https://example.com/spec.html"
    assert t1.attachments[0].bookmark_data == ""


def test_yaml_attachment_path_requires_bookmark_extra(tmp_path: Path) -> None:
    """The ``path:`` form calls make_bookmark, which raises on non-Mac /
    without PyObjC. On a Mac with PyObjC available, it succeeds.
    """
    target = tmp_path / "target.txt"
    target.write_text("hi")
    yaml_text = f"""
tasks:
  - id: t1
    title: T
    effort: 3600
    attachments:
      - path: {target}
"""
    if sys.platform != "darwin":
        from oplx.bookmark import BookmarkUnavailableError
        with pytest.raises(BookmarkUnavailableError):
            from_yaml(yaml_text)
        return

    try:
        proj = from_yaml(yaml_text)
    except Exception as exc:
        from oplx.bookmark import BookmarkUnavailableError
        if isinstance(exc, BookmarkUnavailableError):
            pytest.skip("PyObjC not installed in test env")
        raise

    t1 = next(t for t in proj.actual.tasks if t.id == "t1")
    assert len(t1.attachments) == 1
    assert t1.attachments[0].uri.startswith("file://")
    assert t1.attachments[0].uri.endswith("/target.txt")
    assert t1.attachments[0].bookmark_data  # non-empty base64
