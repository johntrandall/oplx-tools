# oplx-tools TODO

Open loops. Closed items live in `TODO-DONE.md`.

---

## TODO-4 (LOW, deferred) — Rebuild VM with agent-account license

`oplx-tools-integration-test` VM inherited a personal-account license
from its `macos-15.7-l3-omniplan` parent (anti-pattern per `omni-licensing`
skill / ADR-001). Rebuild from `macos-15.7-l2-dev` + install OmniPlan
+ sign in with `john+omni-development@johnrandall.com` per agent-account
convention. Not blocking; existing VM works.

---

## TODO-5 (LOW) — Probe related OmniPlan-reader hypotheses

The TASK-ID-NUMBERING fix (TODO-2) was isolated against task ids. The
following hypotheses were surfaced by the bug-coverage verifier
(session `cb58d211-dabd-4c5b-a20f-88156d7d0a02`) but NOT tested. Each
needs ~5 minutes of host-OmniPlan MCP probing to confirm or rule out:

1. **Resource ids** — does `Resource(id="rX")` cause sibling resources
   to drop, parallel to the task-id bug? All current fixtures use
   `r1`/`r2`/`r3`/`r4` (conforming), so the bug — if it exists — is
   silent. Probe by building a project with `[Resource(id="rX"),
   Resource(id="rY")]` and querying via `mcp__omniplan-local__list_resources`.
   If reproduced, add a sibling lint code `RESOURCE-ID-NUMBERING`.

2. **`t-2` style ids** — OmniPlan-saved files use `t-2`, `t-3` as
   `<prototype-task>` ids. Lint rejects them (regex `^t[1-9]\d*$`
   doesn't match the hyphen). Whether OmniPlan would actually drop
   siblings on a `t-2` *user* task id (not a prototype) is untested.
   The lint rejection is the safe call regardless, but verify.

3. **Non-conforming id as `<prerequisite-task idref>` target** —
   matrix tested sibling drops at the task-tree level only. If a
   conforming task depends on a non-conforming task (e.g. `t10` depends
   on `m1`), does the scheduler still wire the dep correctly? Or does
   OmniPlan drop the prereq?

4. **`<window>` present but with degenerate scale values** —
   the gantt-bars fix (TODO-1) emits `<window>` when absent. If a
   parsed file already has `<window>` with `full-day-width="0"` on
   Automatic, generator pass-through preserves the bad value and
   bars stay invisible. Either lint the scale values or normalize
   them on parse.

5. **`t1` as direct child of root in newer OmniPlan versions** —
   `T1-COLLISION` exempts direct children of the root group. If
   OmniPlan tightens its reader in a future version, the exemption
   would silently miss the case. Adding a regression test fixture
   with `t1` as a direct root-group child would catch this on the
   next OmniPlan version bump.

Bundle these into one investigation session; they all need the same
setup (host OmniPlan + MCP).
