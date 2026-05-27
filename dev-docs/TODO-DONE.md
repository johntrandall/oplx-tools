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

The pattern: any non-t-numbered sibling triggers silent drops; using
t-numbered IDs throughout makes all siblings visible.

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
