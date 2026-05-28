# oplx-tools TODO — closed loops

Closed work items, retained for history. Open items live in `TODO.md`.

---

## TODO-1 (HIGH) — Empty gantt bars in OmniPlan exports + on-screen view

**Closed:** 2026-05-27 (session `cb58d211-dabd-4c5b-a20f-88156d7d0a02`).

**Root cause (Verified):** when `__TOC.xml` omits the `<window>` view-config
block, OmniPlan's runtime fallback for gantt zoom compresses the visible
range so much that hour- and day-scale task bars become sub-pixel. The
spec correctly says `<window>` is *optional* (OmniPlan opens the file
without it) — but the default Auto-zoom that fires when it's absent
makes bars invisible.

**Fix:** generator now emits a minimal `<window>` block in `__TOC.xml`
containing a `<task-view><gantt-view>` with the standard 8-scale table
(values copied from OmniPlan-saved `with-baseline.oplx`). The Automatic
scale is selected with `full-day-width="300"`.

**Verification:**
- Manually patched a generator output and confirmed bars render in the
  host OmniPlan window.
- Re-baselined integration goldens — `f01_minimal.png` now shows a
  visible blue bar; `f20_complex_real_world.png` shows all 4 top-level
  bars plus dependency arrows.
- New unit test `test_generator_emits_window_view_config` asserts the
  `<window>` structure.

---

## TODO-2 (MEDIUM) — f20 under-reporting: heterogeneous root-group children

**Closed:** 2026-05-27 (session `cb58d211-dabd-4c5b-a20f-88156d7d0a02`).

**Root cause (Verified):** the original framing — "heterogeneous root-group
children" — was a coincidence. Isolation against OmniPlan 4.10.2 build
232.5.0 narrowed it to **task IDs that don't match `t<digits>`**.
When any sibling task carries an id like `m1`, `g1`, or `gX`, OmniPlan's
reader silently drops subsequent siblings from the rendered tree. The
f20 fixture happened to use `m1`/`g1`/`m2`/`g2` IDs, which is why the
bug looked like a heterogeneity issue.

Isolation matrix (root-group children):

| Children                    | Result          |
|-----------------------------|-----------------|
| `[mA, mB]` (non-t)          | only mA visible |
| `[xA, xB]` (non-t)          | only xA visible |
| `[t1, mX, t3]` (mixed)      | all visible     |
| `[mX, t2(grp), t3(sub)]`    | all 3 visible   |
| `[t1(mile), gX(grp), t2]`   | t1+gX visible, t2 (sub) dropped |
| `[m1, g1(t2)]` (all non-t)  | only m1 visible |
| `[t1, t2(grp), t3(sub)]`    | all 3 visible   |
| `[t0]` solo                 | t0 visible (degenerate) |
| `[t0, t1, t2]`              | t0+t2 visible, t1 DROPPED |
| `[t0, t1(grp), t2(sub)]`    | only t0 visible |

The pattern: any non-t-numbered sibling triggers silent drops; using
t-numbered IDs starting at `t1` makes all siblings visible. **`t0` is
also broken** — verified 2026-05-28 in a verifier-driven follow-up
probe. Lint regex tightened from `^t\d+$` to `^t[1-9]\d*$`.

**Fix:**
- Added lint code `TASK-ID-NUMBERING` (HIGH) that flags any user task
  id (i.e. not the root `t-1`) that doesn't match `^t\d+$`.
- Renamed f20 fixture IDs (`m1`→`t2`, `g1`→`t3`, `t2`→`t4`, `t3`→`t5`,
  `g2`→`t6`, `t4`→`t7`, `t5`→`t8`, `m2`→`t9`).
- Re-baselined f20 — CSV now lists all 9 tasks (Kickoff, Design phase,
  Architecture, Schema review, Build phase, Implementation, Test pass,
  Ship), PNG shows all 4 top-level bars + 2 milestones + arrows.

**Verification:**
- New unit tests `test_task_id_numbering_flags_non_t_id`,
  `test_task_id_numbering_root_id_exempt`, and
  `test_task_id_numbering_t_numbered_ids_not_flagged` cover the lint
  code.
- Integration test `f20_complex_real_world` now passes against the
  rebaselined goldens.

---

## TODO-3 (LOW) — Generator should emit `<window>` view config

Closed together with TODO-1 — this was the sub-issue that named the
concrete code change. See TODO-1 closing notes above.

---

## TODO-5 (LOW) — Probe related OmniPlan-reader hypotheses

**Closed:** 2026-05-28 (session `cb58d211-dabd-4c5b-a20f-88156d7d0a02`).
All 6 items resolved in one probe session.

### #1 — Resource IDs ❌ MAJOR BUG FOUND

Hypothesis: non-conforming `r<id>` causes sibling resource drops.
**Actual finding:** the hypothesis was wrong but uncovered a worse bug —
**OmniPlan silently drops EVERY resource when the root resource `r-1`
has no `<child-resource>` entries**. Our generator was emitting `r-1`
without any `<child-resource>` references to user resources, so f08,
f14, f15, and f20 were all silently shipping with empty resource lists
and empty assignment columns. The integration test PASSED because the
goldens were baselined while the bug was active.

**Fix landed:**
- New `subresource_ids: list[str]` field on `Resource` model
- `_build_resource` now emits `<child-resource idref="..."/>` per id
- `_build_scenario` auto-populates the root resource's `subresource_ids`
  with every top-level user resource that isn't already a member of
  some other group resource
- Re-baselined f08, f14, f15, f20 integration goldens — `Assigned`
  column now correctly shows resource names; `Resources Cost` and
  `Total Task Cost` now correctly aggregate per-task

Resource id format (`rX` vs `r1`) turns out to be irrelevant — once
`<child-resource>` is emitted, any reasonable id works. Unlike tasks,
there's no `RESOURCE-ID-NUMBERING` lint code needed.

### #2 — `t-2` style ids on USER tasks ✓ NO BUG

Probed: `[t-2, t1, t3]`, `[t-2 first, t1 second]`, `[t-2, t1(group),
t3(sub)]`. All cases show every task. `t-2` as a user task id does NOT
trigger drops. Lint regex `^t[1-9]\d*$` over-rejects (it disallows
`t-2`), but the rejection is safe — `t-2` would be confusing for users
anyway. **Decision:** keep the strict regex; document outcome.

### #3 — Non-conforming id as `<prerequisite-task idref>` target ✓ NO NEW BUG

Probed: `[m1 (mile, non-t), t10 (depends on m1)]`. Both tasks visible
in OmniPlan; dependency wires correctly (predecessor m1, successor t10,
kind FS). TASK-ID-NUMBERING already flags `m1` directly, so no new lint
code needed.

### #4 — Degenerate `<window>` scale values ❌ BUG CONFIRMED

Probed: hand-edit `__TOC.xml` to set `full-day-width="0"` on the
Automatic scale. Result: gantt area renders completely broken (no
date headers, no bars, no outline content despite data being intact).
**Fix landed:** new lint code `WINDOW-SCALE-INVALID` (MEDIUM) flags
any `<scale>` with `full-day-width <= 0` or non-numeric value.

### #5 — `t1` as direct child of root regression test ✓ ALREADY COVERED

Investigation: f02_simple_chain already exercises this scenario —
`[t1, t2, t3]` as direct children of the auto-root, all visible. If a
future OmniPlan version tightens the T1-COLLISION exemption, f02's
golden CSV will diff and surface the regression. No new fixture needed.

### #6 — Lint doesn't enforce `<window>` presence ❌ CODE GAP

**Fix landed:** new lint code `MISSING-WINDOW` (MEDIUM) checks
`__TOC.xml` for the `<window>` element. A hand-edited file with
`<window>` stripped now produces a MEDIUM finding instead of silently
rendering blank bars in OmniPlan.

### Verification

- 48 unit tests pass (was 43; +5: missing-window, scale-zero,
  scale-negative, generator-emits-window-clean, root-resource-auto-populates)
- 20 integration tests pass against rebaselined goldens
- f08, f14, f15, f20 CSV goldens now show actual resource assignments
  + costs (previously blank)
