# oplx-tools TODO

Open loops from the 2026-05-27 integration-suite build session
(`claude --resume d2514584-47cc-4816-9f71-8befedfed2e4` for the full
history). All TODO-1 / TODO-2 / TODO-3 loops were closed in the
follow-up session — see `TODO-DONE.md` for the closing notes.

---

## TODO-4 (LOW, deferred) — Rebuild VM with agent-account license

`oplx-tools-integration-test` VM inherited a personal-account license
from its `macos-15.7-l3-omniplan` parent (anti-pattern per `omni-licensing`
skill / ADR-001). Rebuild from `macos-15.7-l2-dev` + install OmniPlan
+ sign in with `john+omni-development@johnrandall.com` per agent-account
convention. Not blocking; existing VM works.
