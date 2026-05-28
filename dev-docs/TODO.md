# oplx-tools TODO

Open loops. Closed items live in `TODO-DONE.md`.

---

## TODO-4 (LOW, deferred) — Rebuild VM with agent-account license

`oplx-tools-integration-test` VM inherited a personal-account license
from its `macos-15.7-l3-omniplan` parent (anti-pattern per `omni-licensing`
skill / ADR-001). Rebuild from `macos-15.7-l2-dev` + install OmniPlan
+ sign in with `john+omni-development@johnrandall.com` per agent-account
convention. Not blocking; existing VM works.
