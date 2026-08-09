---
date: 2026-08-09
demand: FWD-002
---

# Acceptance — FWD-002 scrum mode

- `python3 bin/fde/verify.py --gate scrum` red on: missing/undated
  backlog goal, sprint without dated goal.md, non-latest sprint without
  retro.md; green on the kernel's own layout; silent no-op when `[scrum]`
  is absent — all covered by tests.
- `fde-scrum` skill exists (and is installed at `.claude/skills/`)
  defining capture, discover, plan, execute, close, review, retro, and
  the unplanned route.
- AGENTS.md template (and this repo's generated AGENTS.md) carry the
  scrum-mode section.
- ADR-0008 records the provenance ledger: canonical Scrum vs dual-track
  vs FORWARD-native vs dropped.
- The kernel runs the mode: `backlog.md` with dated product goal;
  `sprints/S-001/goal.md` dated, containing FWD-002.
- Suite green; `verify --all` green at the demand's closing commit; one
  isolated adversarial round recorded in `reviews/FWD-002/`.
