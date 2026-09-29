cycle: C-<n>
state: draft
date: YYYY-MM-DD
size: XS | S | M | L
objective: <one line: what is true when this cycle closes>
signed-off: <date and the owner's words; empty until sign-off>

<!-- kernel ADR-0019. Criteria and failure modes carry ids and are dated before
the first demand commit (I4). Decisions live in docs/adr/ and are cited
here by id, never restated. The plan is frozen at sign-off. At XS the plan
is minimal. States: draft (grouped) is written by fde-backlog; planned
(specified, awaiting sign-off) by fde-spec; running (with signed-off:),
closed and abandoned by the orchestrating agent, the only edits a frozen
plan takes. Rollback reverts the demand merges and the release commit,
never a range: a range would revert the cycle's own records. -->

## Items

- B-<n> <the backlog item this cycle groups; kept when the draft is specified>

## Threat model

Contained: <who or what the change must contain>.
Out of scope: <what the review may not block on>.

## Acceptance criteria

- **A1 — <name>.** <observable result, shown end to end>

## Failure modes

- **FM1:** <how it fails>. Detected by <check>. Meets A1.

## Demands

| id | layer | depends on | files | what | meets | follows |
|---|---|---|---|---|---|---|
| DEM-<n> | front / back / infra | — | <paths or globs it will touch> | <at most ~300 production lines, one layer> | A1 | ADR-<n> |
