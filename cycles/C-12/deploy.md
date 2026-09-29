cycle: C-12
date: 2026-09-29

<!-- kernel ADR-0019 rule 5. No infra step: the kernel ships by release. -->

1. **back**: status.py JSON adds `demands`, per-cycle artifacts and
   `--demand` (FWD-034), merged behind the gate.
   - Verification: test_status covers both layouts; the gate passes here
     and read-only on headlabs-platform.
   - Rollback: revert the FWD-034 merge.
   - Irreversible: no
2. **front**: `--panel` and the fde-backlog procedure (FWD-035), then
   release 0.20.0 pushed.
   - Verification: an isolated cold read of the printed panel; the suite
     and the gate green; CI.
   - Rollback: `git revert --no-commit <last pushed sha>..<release sha>`
     and push.
   - Irreversible: no
