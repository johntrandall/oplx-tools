"""End-to-end tests for the `oplx` CLI entry points."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oplx.cli import main


def _yaml_fixture(tmp_path: Path) -> Path:
    yaml_path = tmp_path / "proj.yaml"
    yaml_path.write_text(
        """
title: CLI Test Project
start_date: 2026-06-01T13:00:00Z

tasks:
  - id: t1
    title: Plan
    effort: 14400
  - id: t2
    title: Build
    effort: 28800
    depends_on: [t1]
  - id: t3
    title: Ship
    type: milestone
    depends_on: [t2]
"""
    )
    return yaml_path


def test_cli_generate_writes_zip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    yaml_path = _yaml_fixture(tmp_path)
    out_path = tmp_path / "out.oplx"
    monkeypatch.setattr(
        "sys.argv", ["oplx", "generate", str(yaml_path), "--out", str(out_path)]
    )
    rc = main()
    assert rc == 0
    assert out_path.is_file()
    captured = capsys.readouterr()
    assert "Wrote" in captured.out


def test_cli_generate_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    yaml_path = _yaml_fixture(tmp_path)
    out_path = tmp_path / "bundle.oplx"
    monkeypatch.setattr(
        "sys.argv",
        ["oplx", "generate", str(yaml_path), "--out", str(out_path), "--bundle"],
    )
    rc = main()
    assert rc == 0
    assert out_path.is_dir()
    assert (out_path / "__TOC.xml").exists()
    assert (out_path / "Actual.xml").exists()


def test_cli_lint_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Generate first, then lint — clean roundtrip
    yaml_path = _yaml_fixture(tmp_path)
    out_path = tmp_path / "clean.oplx"
    monkeypatch.setattr(
        "sys.argv", ["oplx", "generate", str(yaml_path), "--out", str(out_path)]
    )
    assert main() == 0

    monkeypatch.setattr("sys.argv", ["oplx", "lint", str(out_path)])
    rc = main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "no findings" in captured.out


def test_cli_lint_blocker_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A CRITICAL finding (missing __TOC.xml) → exit 1."""
    empty_dir = tmp_path / "empty.oplx"
    empty_dir.mkdir()
    monkeypatch.setattr("sys.argv", ["oplx", "lint", str(empty_dir)])
    rc = main()
    assert rc == 1


def test_cli_parse_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    yaml_path = _yaml_fixture(tmp_path)
    out_path = tmp_path / "parse.oplx"
    monkeypatch.setattr(
        "sys.argv", ["oplx", "generate", str(yaml_path), "--out", str(out_path)]
    )
    assert main() == 0

    monkeypatch.setattr("sys.argv", ["oplx", "parse", str(out_path)])
    rc = main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "Project:" in captured.out
    assert "Plan" in captured.out
    assert "Build" in captured.out
    assert "Ship" in captured.out


def test_cli_parse_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    yaml_path = _yaml_fixture(tmp_path)
    out_path = tmp_path / "parse.oplx"
    monkeypatch.setattr(
        "sys.argv", ["oplx", "generate", str(yaml_path), "--out", str(out_path)]
    )
    assert main() == 0
    capsys.readouterr()  # drop the "Wrote ..." line

    monkeypatch.setattr(
        "sys.argv", ["oplx", "parse", str(out_path), "--format", "json"]
    )
    rc = main()
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "actual" in data
    titles = {t["title"] for t in data["actual"]["tasks"]}
    assert {"Plan", "Build", "Ship"}.issubset(titles)


def test_cli_missing_subcommand_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["oplx"])
    with pytest.raises(SystemExit):
        main()
