---
date: 2026-08-09
demand: FWD-001
---

# Acceptance — FWD-001 self-install

- `python3 -m unittest discover -s tests` green, covering fde_lib
  validation, verify gates, guard, and spec/instruction integrity.
- `python3 bin/fde/verify.py --all` green at the demand's closing commit
  — the one that records the review and its accepted fixes. (Amended per
  finding F12: the review artifact necessarily post-dates the reviewed
  commit, so "green at the reviewed commit" was unsatisfiable by
  construction.)
- `.github/workflows/fde-gate.yml` runs tests + the full gate on every
  push and pull request.
- `[gate]` covers `runtime/`, `spec/`, `skills/`, `agents/`,
  `templates/`, `SETUP.md`; `[weights]` sums 100 with
  functional_correctness and maintainability blocking (≥ 15).
- One isolated adversarial review of this change recorded in
  `reviews/FWD-001/findings.toml`, every finding citing a probe or a
  principle (I8).
