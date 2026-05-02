"""Entry point for the `oplx` command."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .generate import from_yaml, generate
from .lint import lint
from .parse import parse


def cmd_generate(args: argparse.Namespace) -> int:
    yaml_text = Path(args.input).read_text()
    project = from_yaml(yaml_text)
    out = Path(args.out)
    generate(project, out, bundle=args.bundle)
    print(f"Wrote {out}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    findings = lint(args.input)
    if not findings:
        print(f"{args.input}: no findings")
        return 0
    for f in findings:
        print(f, file=sys.stderr)
    # Exit non-zero if any CRITICAL or HIGH
    has_blocker = any(f.severity in ("CRITICAL", "HIGH") for f in findings)
    return 1 if has_blocker else 0


def cmd_parse(args: argparse.Namespace) -> int:
    project = parse(args.input)
    if args.format == "json":
        # Convert dataclasses → dict, handling Decimal/datetime
        def default(o: object) -> object:
            if hasattr(o, "isoformat"):
                return o.isoformat()
            if hasattr(o, "value"):  # Enum
                return o.value
            return str(o)

        print(json.dumps(asdict(project), default=default, indent=2))
    else:
        # Human-readable summary
        print(f"Project: {project.actual.name} ({len(project.actual.tasks)} tasks, "
              f"{len(project.actual.resources)} resources, "
              f"{len(project.baselines)} baselines)")
        for t in project.actual.tasks:
            if t.id.startswith("t-"):
                continue  # skip prototypes/root
            prereqs = ", ".join(d.idref for d in t.prerequisites)
            print(
                f"  {t.id}: {t.title!r}"
                f" type={t.type.value}"
                f" effort={t.effort}s"
                f" rc={t.recalculate.value}"
                + (f" prereqs=[{prereqs}]" if prereqs else "")
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="oplx", description="OmniPlan .oplx tooling")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="Build an .oplx from YAML")
    p_gen.add_argument("input", help="Path to YAML description")
    p_gen.add_argument("--out", "-o", required=True, help="Output .oplx path")
    p_gen.add_argument(
        "--bundle", action="store_true", help="Produce directory bundle (default: zip variant)"
    )
    p_gen.set_defaults(func=cmd_generate)

    p_lint = sub.add_parser("lint", help="Validate an .oplx")
    p_lint.add_argument("input", help="Path to .oplx (zip or directory)")
    p_lint.set_defaults(func=cmd_lint)

    p_parse = sub.add_parser("parse", help="Parse an .oplx and emit JSON or summary")
    p_parse.add_argument("input", help="Path to .oplx (zip or directory)")
    p_parse.add_argument(
        "--format", "-f", choices=["json", "summary"], default="summary"
    )
    p_parse.set_defaults(func=cmd_parse)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
