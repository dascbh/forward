---
date: 2026-08-09
demand: FWD-015
---

# Acceptance — FWD-015

- `fde-survey` skill exists and is installed, defining the seven sections
  R1 requires, the three evidence labels, the order of work, and the
  explicit instruction to compose `erosion.py` and `graph.py` rather than
  reimplement them.
- `runtime/survey.py` parses `discovery/survey.md` and reports: missing
  required sections, claims with no evidence label, and the recorded
  commit and date. Pure cores unit-tested without a repository.
- `bin/fde/verify.py --gate survey`: silent when there is no survey and
  no `[survey]` budget; red when a survey exists with a missing required
  section or an unlabeled claim; red when the recorded commit has drifted
  past a declared `max_drift_commits`. `--gate survey --staged` names the
  tier conflict.
- The demand loop (template AND this repo's AGENTS.md, kept identical)
  states the brownfield rule from R5.
- The kernel dogfoods it: `discovery/survey.md` surveying this repository,
  passing its own gate.
- Full suite and `verify --all` green at the demand's closing commit; two
  isolated adversarial rounds in `reviews/FWD-015/`;
  `promotions/FWD-015/decision.md` confronts this list.
