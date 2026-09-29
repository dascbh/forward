cycle: C-14
date: 2026-09-29

1. **back**: FWD-037..042 merged behind the gate, then release 0.22.0 pushed.
   - Verification: the suite and `verify.py --all` green; headlabs-platform read-only green under the new runtime; an old-client fixture with `[scrum]` stays green; CI.
   - Rollback: `git revert --no-commit 9f9f3a2..<release sha>` and push.
   - Irreversible: no
2. **clients**: take it with the fde-sync skill.
   - Verification: headlabs sync leaves `kernel_version = "0.22.0"`, `.fde/adr/` present, the gate green.
   - Rollback: re-sync from 0.21.0.
   - Irreversible: no
