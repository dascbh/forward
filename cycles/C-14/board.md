# C-14 board

- 2026-09-29 C-14 decided signed off by the owner ("aprovado"); wave 1: FWD-037, FWD-041, FWD-044, FWD-042
- 2026-09-29 FWD-037 claim AGENTS.md (+ template), cycles/C-14/inventory.md, skills/fde-triage, skills/fde-review, skills/fde-backlog, skills/fde-scrum, agents/fde-spec.md (+ copies), tests/test_instructions.py, tests/test_coherence.py
- 2026-09-29 FWD-041 claim runtime/verify.py, runtime/erosion.py, runtime/fde_lib.py, runtime/guard.py (+ bin/fde), tests/test_verify.py, tests/test_erosion.py, tests/test_fde_lib.py, tests/test_guard.py
- 2026-09-29 FWD-044 claim templates/fde-gate.yml, .github/workflows/fde-gate.yml, tests/test_install_sync.py (workflow pins)
- 2026-09-29 FWD-042 claim runtime/status.py (+ bin/fde), tests/test_status.py
- 2026-09-29 FWD-044 decided merged e3633e8; code review 2 low, none blocking (F1 → backlog B-54, F2 same as before the demand)
- 2026-09-29 FWD-042 decided merged c3a1216; code review 2 low, none blocking (→ backlog B-55)
- 2026-09-29 FWD-041 claim widened: runtime/triage.py (+ bin/fde) for B-28 message wording (ADR-0015 cited in two messages); tests/test_coherence.py one line, the guard LEGACY_NOTE pin (B-28), shared with FWD-037
- 2026-09-29 FWD-041 claim widened: skills/fde-erosion/SKILL.md (+ .claude copy), one sentence — whole-repo erosion now excludes cycles/ (B-20)
- 2026-09-29 FWD-041 claim widened: runtime/walkthrough.py (+ bin/fde), two message strings (B-28)
- 2026-09-29 FWD-037 claim widened: tests/test_scrum.py (TestBacklogInstructions pins the AGENTS.md ## Backlog sentences this demand moves; FWD-039 edits it after this merges)
- 2026-09-29 FWD-041 decided merged dbc2fe7; code review 3 low, none blocking (F1 moot — a demand has one layer; F2, F3 → B-58, B-59). FWD-037 merged; wave 2 starts: FWD-043, FWD-038, FWD-039
- 2026-09-29 FWD-043 claim skills/fde-review (budget/replan sentence only), skills/fde-triage, skills/fde-backlog, templates/cycle/plan.md, templates/cycle/deploy.md, AGENTS.md (MNT-9 and budget lines only) (+ copies), cycles/C-14/inventory.md must-stay table if an anchor changes
- 2026-09-29 FWD-038 claim agents/fde-promotion.md, templates/cycle/promotion.md, templates/findings.template.toml (+ .fde), skills/fde-review (merge-line and fixed_in sentences), runtime/verify.py gate_adversarial, runtime/status.py (fixed_in read) (+ bin/fde), tests/test_verify.py, tests/test_status.py
- 2026-09-29 FWD-039 claim fde.config.toml, templates/fde.config.template.toml, runtime/fde_lib.py validate, runtime/verify.py gate_scrum, skills/fde-scrum (rename), AGENTS.md ## Backlog lines (+ copies), tests/test_scrum.py
