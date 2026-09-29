cycle: C-<n>
date: YYYY-MM-DD

<!-- kernel ADR-0019 rule 5. Order: infra-expand → back → front → infra-contract.
Drop a step the cycle does not touch. An irreversible step is never
bundled with a reversible one. A failed verification rolls the step back
and stops the cycle. Rollback reverts the demand merges and the release
commit, never a range: a range would revert the cycle's own records. -->

1. **infra-expand** — <backward-compatible infra change>
   - Verification: <plan diff, live check>
   - Rollback: <how>
   - Irreversible: no
2. **back** — <API, domain, data access>
   - Verification: <contract + integration tests>
   - Rollback: <how>
   - Irreversible: no
3. **front** — <screens, flows, text>
   - Verification: <design QA, walkthrough>
   - Rollback: <how>
   - Irreversible: no
4. **infra-contract** — <removal of what step 1 kept compatible, if any>
   - Verification: <live check>
   - Rollback: <how>
   - Irreversible: <yes: why | no>
