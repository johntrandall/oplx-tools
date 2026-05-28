# Lint trigger decision: PostToolUse-on-edit, not pre-commit

> **Status:** decided 2026-05-27. Implementation in [`hooks/oplx-lint.sh`](../hooks/oplx-lint.sh) and the `PostToolUse` block of [`lash.json`](../lash.json).

## Decision

`oplx lint` runs as a **Claude Code `PostToolUse` hook on `Edit | Write | MultiEdit`**, not as a git pre-commit hook.

The hook fires on every agent write whose path touches an `.oplx` bundle (the hook resolves the bundle root by walking parents). Findings reach the calling agent via `hookSpecificOutput.additionalContext` — non-blocking, advisory.

## What the lint catches

Most codes mirror the silent-corruption catalog (`~/dev/oplx-format/spec/silent-corruption.md`) and inherit severity tiers from it. Bundle-structure codes (`MISSING-TOC`, `MISSING-ACTUAL`, `MISSING-CHANGELOG`, `MISSING-BASELINE-FILE`, `ROOT-TASK-MISSING`, `FILE-NOT-FOUND`) are local lint-impl assignments — the spec defines severities for content-level corruption, not for malformed bundle structure, so those tiers are chosen here in [`src/oplx/lint.py`](../src/oplx/lint.py).

| Code | Severity | OmniPlan behavior if it ships |
| --- | --- | --- |
| `TYPE-CASE` | CRITICAL | Document refuses to open. Silent. |
| `MISSING-TOC`, `MISSING-ACTUAL`, `MISSING-CHANGELOG` | CRITICAL | Document refuses to open (lint-impl assignment). |
| `FILE-NOT-FOUND` | CRITICAL | Path does not exist (lint-impl assignment). |
| `UNITS-ZERO` | HIGH | Assignment dropped on next save. |
| `ORPHANED-TASK` | HIGH | Task dropped on next save. |
| `ROOT-TASK-MISSING` | HIGH | Document structurally broken (lint-impl assignment). |
| `MISSING-BASELINE-FILE` | HIGH | `__TOC.xml` references a baseline file that isn't in the bundle (lint-impl assignment). |
| `DEP-MISSING` | HIGH | `<prerequisite-task idref="X"/>` points at a task that doesn't exist. OmniPlan silently drops the dep on load. |
| `T1-COLLISION` | HIGH | User task `t1` referenced from a non-root group's `<child-task>` list. OmniPlan drops it (collides with root `t-1` after hyphen strip). |
| `TASK-ID-NUMBERING` | HIGH | User task id doesn't match `^t[1-9]\d*$` (e.g. `m1`, `g1`, `gX`, `t0`). OmniPlan silently drops sibling tasks. |
| `DEP-KIND-CASE` | MEDIUM | Dependency degrades to Finish-Start. |
| `RECALCULATE-INVALID` | MEDIUM | Field normalizes to `duration`. |
| `TYPE-INVALID`, `RESOURCE-TYPE-INVALID` | MEDIUM | Field normalizes to default. |

Full prose in [`~/dev/oplx-format/spec/silent-corruption.md`](../../oplx-format/spec/silent-corruption.md).

## Why PostToolUse beats pre-commit for *this* catalog

The trade-off is real for most linters. It is **not balanced** here.

### PostToolUse (chosen)

- **Catches edits that never commit at all.** This is the strongest reason. A lot of real `.oplx` work is iterative scratch — generate, open in OmniPlan, tweak, re-open — that never reaches git. Test fixtures, throwaway scenarios, hand-built bundles to reproduce an OmniPlan bug. A pre-commit hook would see none of that. PostToolUse sees all of it.
- **Catches corruption in the working tree before it propagates.** The corruption catalog is dominated by patterns that the agent doesn't realize are wrong. If the agent edits an `.oplx`, runs OmniPlan against it, and OmniPlan silently rejects the file, the next edit may already be writing on top of broken state. Earlier detection wins.
- **Tightens the correction loop.** The agent sees the finding in the same turn as the Edit — the next iteration of the loop has the lint message already in context and can fix the value before producing a downstream Write. (Note: a commit-time hook could also surface findings to the same agent, just slower; the "agent has lost the thread" framing of this reason is the weakest of the three — don't lean on it.)
- **No additional dependency on git state.** The bundle on disk is sufficient — no need to interrogate the index for what's being committed.

### Pre-commit (rejected)

- Only fires on what's staged. Working-tree corruption that hasn't been staged yet is invisible.
- Many `.oplx` edits never reach git at all (test fixtures, throwaway scenarios, hand-built bundles for reproducing OmniPlan bugs).
- The corruption-to-feedback gap is N edits long, where N is however many edits the agent does before remembering to commit. With PostToolUse it's exactly one tool call.
- Pre-commit can still be added later as a defense-in-depth layer, but it cannot replace the edit-time signal — it can only supplement it.

## Why this argument doesn't generalize to all linters

This decision is **catalog-specific**. The corruption codes are mostly *file-level rejection* (CRITICAL) and *silent content drop* (HIGH). Those failure modes are invisible until OmniPlan refuses the file, by which point the agent has lost the thread. For a linter whose findings are style-only (line length, import order), edit-time noise would outweigh the catch-rate benefit and pre-commit would be the right place. For this linter, the failures are silent and downstream — edit-time is the only window where the agent still has the context to fix the cause.

## How agents see the findings

The hook emits a `PostToolUse` JSON envelope. `hookSpecificOutput.additionalContext` is appended to the conversation immediately after the tool result, marked as advisory. The Edit/Write is **not** reverted; the agent decides whether to follow up.

If `oplx lint` exits 0 (zero findings of any severity), the hook stays silent — no envelope, no noise on clean edits. Any finding — CRITICAL, HIGH, or MEDIUM — causes `oplx lint` to exit non-zero and the hook to emit the envelope; severities exist for prioritization, not for gating visibility.

## Pointers

- Hook script: [`hooks/oplx-lint.sh`](../hooks/oplx-lint.sh)
- Lint implementation: [`src/oplx/lint.py`](../src/oplx/lint.py)
- Manifest wiring: [`lash.json`](../lash.json) (`PostToolUse` entry under `hooks`, matcher `Edit|Write|MultiEdit`)
- Silent-corruption spec: `~/dev/oplx-format/spec/silent-corruption.md` (or the public mirror at github.com/johntrandall/oplx-format)
