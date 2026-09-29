cycle: C-14
date: 2026-09-29

1. **infra**: FWD-044, the CI workflow change, merged behind the gate.
   - Verification: the workflow run on the pushed release SHA is green.
   - Rollback: `git revert` of FWD-044's merge commit alone.
   - Irreversible: no
2. **back**: FWD-037, 038, 039, 040, 041, 042 and 043 merged behind the
   gate, then release 0.22.0 pushed.
   - Verification:
     - the suite and `verify.py --all` are green;
     - headlabs-platform stays green under the new runtime, checked
       read-only;
     - a `[scrum]` old-client fixture is green;
     - CI is green.
   - Rollback:
     - `git revert` of the release commit and of the demand merge
       commits, listed in promotion.md at release;
     - never a range, which would also revert the cycle's own records.
   - Irreversible: no
3. **clients**: take it with the fde-sync skill.
   - Verification: after a headlabs sync, `kernel_version` is `0.22.0`,
     `.fde/adr/` is present, and the gate is green.
   - Rollback: re-sync from 0.21.0. The leftovers, `.fde/adr/` and any
     `[backlog]` key, are ignored by 0.21.0: its gate stays green,
     verified by a fixture in FWD-040.
   - Irreversible: no
