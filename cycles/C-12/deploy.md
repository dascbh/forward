cycle: C-12
date: 2026-09-29

<!-- kernel ADR-0019 rule 5. No infra step: the kernel ships by release. -->

1. **back**: status.py JSON adds `demands` and per-cycle artifact paths
   (FWD-034), merged to main behind the gate.
   - Verification: test_status covers both layouts; the gate passes on
     this repository and read-only on headlabs-platform.
   - Rollback: revert the FWD-034 merge.
   - Irreversible: no
2. **front**: panel.py and the fde-backlog step (FWD-035), then release
   0.20.0 pushed.
   - Verification: design QA against the approved wireframe; the
     walkthrough at the cycle review; the suite and the gate green; CI.
   - Rollback: `git revert --no-commit <last pushed sha>..<release sha>`
     and push.
   - Irreversible: no
