---
date: 2026-09-28
demand: FWD-022
---

# Acceptance — FWD-022 declared cycle, as instruction

1. AGENTS.md and templates/AGENTS.md.template carry an identical
   `## Cycle` section stating R1–R5; the mirror pair stays green.
2. The done list is conditional: promotion only for M/L, deploy/publish
   only when the project deploys or publishes.
3. `fde-triage` and `fde-scrum` reference the section in one line each.
4. `tests/test_instructions.py` has an eval per requirement R1–R4, red
   before the change and green after.
5. No file under `runtime/` or `bin/fde/` changes.
6. One isolated full adversarial round with no blocking finding open.
7. `cycles/C-2.md` declares this cycle before the first behavior commit
   and closes with its done items marked and its next-cycle list.
