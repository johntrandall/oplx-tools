# oplx-tools

**Python tooling for OmniPlan `.oplx` documents.** Companion to [`oplx-format`](https://github.com/USER/oplx-format) (the file-format specification).

> **Naming note**: `oplx` is the file extension OmniPlan uses (`.oplx`). This project is **not** related to Yamaha OPL audio synthesis chips (OPL2/OPL3/OPL4) which share a similar string in some retro-audio communities.

## Prior art

If you're looking for OmniPlan automation, you may also want to evaluate:

- [**liyanage/omniplan-python**](https://github.com/liyanage/omniplan-python) — older library focused on data access (read-side). Different scope from `oplx-tools` (this repo emphasizes from-scratch file generation, lint, and silent-corruption detection).

This repo is intended to complement, not replace, prior community work. PRs that improve interop with existing libraries are welcome.

## What's here

- **`oplx generate`** — build a minimum-viable `.oplx` from a YAML/JSON description (no OmniPlan required)
- **`oplx lint`** — validate a `.oplx` (zip or directory) against the format spec; catch silent-corruption patterns before they bite
- **`oplx parse`** — extract tasks/resources/dependencies/assignments from an `.oplx` for downstream tools (BI, ETL, integrations)

The spec lives in a separate repo (`oplx-format`) so it can be referenced by tool authors in any language. This repo is the Python reference implementation.

## Status

- **Verified against**: OmniPlan 4.10.2
- **Spec version**: 0.1.0
- **Maturity**: alpha — works for the cases tested in the research repo (cycles 0011–0023). Not yet battle-tested in production.
- **Python**: 3.11+

## Install

```bash
uv tool install oplx-tools
# or:
pipx install oplx-tools
```

(Not yet on PyPI — install from source for now.)

```bash
git clone https://github.com/USER/oplx-tools
cd oplx-tools
uv pip install -e .
```

## Quick examples

### Generate a minimal doc

```bash
cat > project.yaml <<'EOF'
title: My Project
start_date: 2026-06-01T13:00:00Z
tasks:
  - id: t1
    title: Plan
    effort: 14400         # 4 hours
  - id: t2
    title: Build
    effort: 28800
    depends_on: [t1]
  - id: t3
    title: Ship
    type: milestone
    depends_on: [t2]
EOF

oplx generate project.yaml --out project.oplx
open -a OmniPlan project.oplx
```

### Lint an existing doc

```bash
oplx lint project.oplx
# Checks for: orphaned tasks, uppercase <type>, lowercase kind=, units="0",
# unreachable child-task chains, etc.
```

### Parse for downstream use

```bash
oplx parse project.oplx --format json | jq '.tasks[].title'
```

```python
from oplx import parse

doc = parse("project.oplx")
for task in doc.actual.tasks:
    print(task.title, task.effort, [d.idref for d in task.prerequisites])
```

## Project layout

```
src/oplx/
├── __init__.py
├── cli.py              # Entry point: `oplx` command
├── models.py           # Dataclasses for Project, Scenario, Task, Resource, Dependency
├── generate.py         # YAML/dict → .oplx zip
├── lint.py             # .oplx → list of warnings/errors
├── parse.py            # .oplx → models
└── xml/                # Element-by-element serializers/deserializers
```

## Coverage vs spec

`oplx generate`:
- ✅ All 4 task types (with hammock via XML hand-write since omniJS rejects)
- ✅ All 4 dependency kinds with optional lead-time (duration or percentage)
- ✅ All 4 date constraints
- ✅ Multi-resource assignment with units
- ✅ Custom data (string values; other types not yet wired)
- ✅ Per-resource schedule overrides (basic)
- ✅ Multi-baseline scenarios
- ✅ Zip variant output (default) or directory bundle
- ⚠️ 3-pt estimation: emit `<min/expected/max-estimate>` and let OmniPlan PERT-compute `<effort>`
- ❌ Note rich-text formatting (bold/color/alignment) — plain text only
- ❌ `<filter>` saved-filter generation (would need NSPredicate bplist construction)

`oplx lint`:
- ✅ Silent-corruption catalog (all CRITICAL + HIGH tier patterns)
- ✅ Element-ordering rules
- ✅ Element-presence requirements (every task reachable from `t-1`)
- ⚠️ XML schema validation (loose; relies on examples not a formal XSD/Relax-NG)

`oplx parse`:
- ✅ Reads zip variant and directory bundle
- ✅ Resolves dependencies, assignments, schedules
- ✅ Handles multi-scenario docs (Actual + baselines)
- ⚠️ Note rich-text: returns concatenated `<lit>` text; structure preserved as raw XML if requested
- ❌ Filter bplist decode (use `plistlib` directly if needed)

## License

MIT (see [LICENSE](LICENSE)). The format itself is described in the [oplx-format](../oplx-format) repo under CC-BY-4.0.

## Contributing

This is alpha software. Expected places needing work:
- `src/oplx/xml/` — more thorough element handling (each element gets its own ser/de)
- `tests/` — round-trip tests against `oplx-format` examples
- `oplx lint` — additional silent-corruption patterns as they emerge
- Note rich-text formatting (bold/color/alignment) — currently plain-only

PRs welcome. Please include a fixture (`tests/fixtures/`) demonstrating the case.
