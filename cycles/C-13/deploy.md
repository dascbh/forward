cycle: C-13
date: 2026-09-29

1. **back**: FWD-036 merged, then release 0.21.0 pushed.
   - Verification: the suite and `verify.py --all` green; CI.
   - Rollback: `git revert --no-commit a9d37f8..<release sha>` and push.
   - Irreversible: no
