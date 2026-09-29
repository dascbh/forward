cycle: C-<n>
date: YYYY-MM-DD
round: 1 (full) | 2 (delta)

<!-- kernel ADR-0019 rule 12. Judges the objective against plan.md; never
re-reviews a demand. Checks come from the touched layers: integration
for back, usability (walkthrough) for front, live checks for infra. -->

## Functioning

- A1 — <evidence on the integrated result> — met | not met

## Readiness

- Deploy plan: <each step's verification and rollback exercised, or why not>
- Signals (I5): <the signals the criteria declare, and where they are emitted>
- Runbook and README: <they match how the system now runs>

## Findings

<!-- only blocking findings are the cycle's; the rest go to backlog.md -->
