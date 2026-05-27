# oplx-tools TODO

Open loops from the 2026-05-27 integration-suite build session
(`claude --resume d2514584-47cc-4816-9f71-8befedfed2e4` for the full
history). Both blockers were surfaced by the integration suite; neither
prevents the suite from running.

---

## TODO-1 (HIGH) — Empty gantt bars in OmniPlan exports + on-screen view

**Status:** surfaced 2026-05-27; not investigated.

**Symptom:** generated `.oplx` opens in OmniPlan, scheduler computes
correct dates (visible in CSV export and inspector pane), but the
**gantt area renders blank** — no task bars, no dependency arrows.
Observed both on-screen in the live OmniPlan window (via VNC) and in
PDF/PNG exports across every integration fixture. Outline + effort
labels + date headers render fine.

**Why it matters:** the original visual-verification ask was "do
dependency lines actually draw?" — currently we can't tell, because
no bars draw at all. The PNG file-size diff catches *gross* changes
but with empty gantt areas, that's a weak signal.

**Suspected causes** (one of these, possibly more):

- Generator omits `<window>` view-config in `__TOC.xml` — the spec
  (`~/dev/oplx-format/spec/toc-xml.md`) shows `<window>` containing
  `<view>task|resource</view>`, `<task-view>...</task-view>`,
  `<resource-view>`, `<network-view>`, etc. Our `_build_toc` writes
  none of it. OmniPlan may be falling back to a degenerate view-state
  per-document that doesn't draw bars.
- Date zoom-level mismatch: our default scenario `start_date` is
  in mid-2026 but OmniPlan's gantt default zoom may show
  current-quarter, so the bars are off-screen to the left or right.
- Missing `<schedule>` or `<scheduled-start-date>` per-task elements
  that OmniPlan needs for the renderer (different from the scheduler's
  computed dates — could be a serialization gap).
- A `<scenario>` attribute we're not setting that's required for the
  gantt renderer to engage.

**Next steps:**

1. Open a known-good OmniPlan-saved `.oplx` (have John save a simple
   3-task project in OmniPlan, then `unzip -p Actual.xml`) and diff
   against our generator's output. The delta is the likely fix.
2. Add `<window><view>task</view><task-view>...</task-view></window>`
   to `_build_toc`. Start with whatever OmniPlan emits by default.
3. Once bars render, re-baseline all 20 integration goldens. PNG sizes
   should jump significantly (we'd be capturing real visual content).

---

## TODO-2 (MEDIUM) — f20 under-reporting: OmniPlan reader bug with heterogeneous root-group children

**Status:** surfaced 2026-05-27; isolated but not fixed. Documented as
a known limitation in `tests/integration/README.md`.

**Symptom:** when the auto-created root group `t-1` has heterogeneous
children (e.g. a `<task type="milestone">` sibling to a `<task type="group">`,
or a milestone interleaved between tasks/groups), OmniPlan silently
processes only a subset of the children. Patterns observed against
OmniPlan 4.10.2 build 232.5.0:

- root children `[milestone, group(tasks)]` → only the milestone visible
- root children `[group(tasks), milestone]` → only the group's subtree
- root children `[milestone, task, milestone]` → only the first 2 visible
- 3 flat siblings of the same type → all 3 visible ✓ (control)

Minimal reproducer code is in the session transcript; effectively any
test fixture mixing milestone + group at the top level reproduces it.

**Suspected cause:** OmniPlan's reader appears to have type-coherence
expectations for a group's `<child-task>` list that aren't documented
in the spec. Could be:
- Group child-task lists must be uniform-type
- Milestones must not be direct children of groups (must be in their
  own dedicated sibling structure)
- Could be related to the `<window>` view-config omission (TODO-1) —
  fixing that might make this go away too

**Next steps:**

1. Same as TODO-1 step 1 — diff our XML against an OmniPlan-saved
   .oplx that has a similar heterogeneous structure (milestone +
   group siblings).
2. If the spec/OmniPlan does forbid this, add a new lint code
   `HETEROGENEOUS-GROUP-CHILDREN` (MEDIUM or HIGH) that flags
   `<task type="group">` whose `<child-task>` list mixes types.
3. Either generator-side rewrites (wrap milestone siblings in their
   own group) or doc-only pitfall.

Re-baseline f20 after fix.

---

## TODO-3 (LOW) — Generator should emit `<window>` view config

Sub-issue of TODO-1. The spec describes `<window>` element in
`__TOC.xml` with per-view configuration. Our generator omits it
entirely. Adding it will probably fix TODO-1 and may fix TODO-2.

Start small: emit `<window><view>task</view></window>` and re-test.
Add full per-view blocks only if needed.

---

## TODO-4 (LOW, deferred) — Rebuild VM with agent-account license

`oplx-tools-integration-test` VM inherited a personal-account license
from its `macos-15.7-l3-omniplan` parent (anti-pattern per `omni-licensing`
skill / ADR-001). Rebuild from `macos-15.7-l2-dev` + install OmniPlan
+ sign in with `john+omni-development@johnrandall.com` per agent-account
convention. Not blocking; existing VM works.
