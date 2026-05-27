# oplx-tools

**Python tooling for OmniPlan `.oplx` documents.** Generate, lint, and parse `.oplx` files **without OmniPlan running or installed**.

> **Naming note**: `oplx` is the file extension OmniPlan uses (`.oplx`). This project is **not** related to Yamaha OPL audio synthesis chips (OPL2/OPL3/OPL4) which share a similar string in some retro-audio communities.

## Ecosystem

This repo is one of three working together:

| Repo | What it is | When to use |
|---|---|---|
| 📖 [**oplx-format**](https://github.com/johntrandall/oplx-format) | The file-format **specification** (CC-BY-4.0) | Read this if you're writing any `.oplx` tool in any language |
| 🐍 [**oplx-tools**](https://github.com/johntrandall/oplx-tools) (this repo) | **Python implementation**: generate / lint / parse — **no OmniPlan needed** | Headless `.oplx` workflows: CI/CD, batch generation, ETL |
| 🤖 [**omniplan-mcp**](https://github.com/johntrandall/omniplan-mcp) | **MCP server** for live OmniPlan automation (requires OmniPlan running) | Conversational task management with Claude — "schedule a task tomorrow at 2pm" |
| 📦 [**lash**](https://github.com/johntrandall/lash) | The installer used to wire `oplx-tools`'s lint hook into Claude Code | One-shot setup for the agent integration |

**Picking between live MCP and headless oplx-tools:**

- Use [**omniplan-mcp**](https://github.com/johntrandall/omniplan-mcp) when you want conversational interaction with the running app (open documents, query/edit live tasks, schedule changes).
- Use **this repo** when you want to **read, create, or edit `.oplx` files without running OmniPlan at all** — agents on Linux, CI pipelines, batch generation from spreadsheets, headless tests, mass migration, etc. No GUI, no license, no Mac required.

## Prior art

- [**liyanage/omniplan-python**](https://github.com/liyanage/omniplan-python) — older Python library focused on read-side data access. Different scope from `oplx-tools` (this repo emphasizes from-scratch file generation, lint, and silent-corruption detection). Use both if you need both reading and writing.

PRs that improve interop with existing libraries are welcome.

## What's here

- **`oplx generate`** — build a minimum-viable `.oplx` from a YAML/JSON description (no OmniPlan required)
- **`oplx lint`** — validate a `.oplx` (zip or directory) against the [format spec](https://github.com/johntrandall/oplx-format); catch silent-corruption patterns before they bite
- **`oplx parse`** — extract tasks/resources/dependencies/assignments from an `.oplx` for downstream tools (BI, ETL, integrations)

The spec lives in a separate repo ([`oplx-format`](https://github.com/johntrandall/oplx-format)) so it can be referenced by tool authors in any language. This repo is the Python reference implementation.

## Use cases

These all work **without OmniPlan running or installed**:

### 1. Generate `.oplx` files from external sources

Drive OmniPlan's task tree from your existing data. Turn a CSV, JSON dataset, or YAML manifest into a valid `.oplx` your stakeholders can open in OmniPlan to review:

```bash
oplx generate roadmap.yaml --out roadmap.oplx
```

Useful for: project bootstrapping from templates, generating per-customer plans, converting Jira/Linear/GitHub issue exports into a Gantt chart your PMs can review and edit, weekly auto-regenerated baselines.

### 2. Headless lint in CI/CD

Run on Linux runners with no Mac, no OmniPlan license:

```yaml
# .github/workflows/oplx-lint.yml
- run: uv tool install oplx-tools
- run: oplx lint plans/*.oplx   # CRITICAL findings exit non-zero, fail the build
```

Catches silent-corruption patterns the moment they're committed (uppercase `<type>`, lowercase `kind=`, `units="0"`, orphaned tasks not reachable from `<top-task>`). See [silent-corruption catalog](https://github.com/johntrandall/oplx-format/blob/main/spec/silent-corruption.md).

### 3. Bulk-edit existing files without touching OmniPlan

Read in, mutate, write out:

```python
from oplx import parse, generate
from oplx.models import TaskType

doc = parse("project.oplx")
for task in doc.actual.tasks:
    if "[milestone]" in task.title:
        task.type = TaskType.MILESTONE
        task.title = task.title.replace("[milestone]", "").strip()
generate(doc, "project-fixed.oplx")
```

Works on a stack of files in a loop. No GUI thrash, no per-file dialog acceptance.

### 4. Parse for downstream BI / ETL

OmniPlan's CSV export is lossy (no dependency kinds, no constraint dates, no custom data types). The XML form preserves everything:

```python
from oplx import parse

doc = parse("project.oplx")
total_effort = sum(t.effort or 0 for t in doc.actual.tasks)
critical_path = [t for t in doc.actual.tasks if t.total_slack == 0]
```

Pipe into your warehouse, dashboard, or Slack digest.

### 5. Generate baselines programmatically

The OmniPlan UI's "Set Baseline" button has no API equivalent in OmniPlan's AppleScript dictionary or Omni Automation surface. `oplx generate` (with the `Project.baselines=` field) creates a multi-scenario doc directly — useful for capturing weekly snapshots automatically without UI clicking.

### 6. Agent-driven workflows

With the [Claude Code lint hook](#full-install-cli--claude-code-lint-hook) installed, agents can read/create/edit `.oplx` files freely; any silent-corruption pattern they introduce is immediately surfaced in their next turn so they self-correct. This composes naturally with [omniplan-mcp](https://github.com/johntrandall/omniplan-mcp) when the live app is also available — the MCP for runtime queries, this repo for file mutation.

## Status

- **Verified against**: OmniPlan 4.10.2
- **Spec version**: 0.1.0
- **Maturity**: alpha — works for the cases tested in the research repo (cycles 0011–0023). Not yet battle-tested in production.
- **Python**: 3.11+

## Install

### Quick install (CLI only)

**Homebrew (macOS):**

```bash
brew tap johntrandall/tap
brew install oplx-tools
```

**uv (Python tool, cross-platform):**

```bash
uv tool install oplx-tools
# Or from a local clone:
uv tool install ~/dev/oplx-tools
```

The CLI command is `oplx`. The full install path below adds the Claude Code lint hook on top of the CLI.

### Full install (CLI + Claude Code lint hook)

If you're using Claude Code (or any tool with the same `PostToolUse` hook surface) and you want **agents to be auto-corrected the moment they introduce a silent-corruption pattern**, install via [**lash**](https://github.com/johntrandall/lash) — a tiny manifest-driven installer.

`lash install` reads the `lash.json` manifest in this repo and:

1. Installs the `oplx` CLI (`uv tool install`).
2. Symlinks `hooks/oplx-lint.sh` → `~/.claude/hooks/oplx-lint.sh`.
3. Patches `~/.claude/settings.json` with a `PostToolUse` `Edit|Write|MultiEdit` block that runs the hook.

```bash
# One-time prerequisite — zero-dep installer (single Python script):
uv tool install lash-installer
# Or from a clone:  uv tool install git+https://github.com/johntrandall/lash

# Clone this repo and install:
git clone https://github.com/johntrandall/oplx-tools ~/dev/oplx-tools
cd ~/dev/oplx-tools
lash install                       # runs all 3 operations above
```

After install, **restart Claude Code** (or open `/hooks` once) so the settings watcher picks up the new entry.

`lash install` is idempotent — re-run safely after `git pull` to refresh. See [lash README](https://github.com/johntrandall/lash) for full manifest semantics.

```bash
lash status                        # see what's installed
lash uninstall                     # reverse all operations cleanly
```

### What the hook does

The `oplx-lint.sh` hook fires after `Edit`/`Write`/`MultiEdit` when the file path resolves to inside an `.oplx` directory bundle. It runs `oplx lint <bundle>` on that bundle and — if any findings are produced — emits a `PostToolUse` JSON envelope to stdout whose `hookSpecificOutput.additionalContext` is appended to the conversation as advisory. **Non-blocking** — the Edit is not reverted; the agent sees the findings in the same turn and decides whether to self-correct.

Severity tiers (from [silent-corruption.md](https://github.com/johntrandall/oplx-format/blob/main/spec/silent-corruption.md)):

- **CRITICAL** — file-level rejection (e.g., `<type>MILESTONE</type>` uppercase silently makes OmniPlan refuse to open the doc)
- **HIGH** — content silently dropped on save (e.g., orphaned tasks, `units="0"` deleting an assignment)
- **MEDIUM** — value normalized to default (e.g., `<recalculate>none</recalculate>` → `duration`)
- **LOW** — cosmetic / metadata

To disable the hook without uninstalling the CLI: `lash uninstall && uv tool install oplx-tools`.

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
