# C-6

state: abandoned
abandoned: 2026-09-29 — owner: backlog cleanup, items merged into C-14
objective: review flow closes cleanly: a demand blocker leaves a closing record, a merge requires its review, and promotion settles declined/limit criteria

## Moved to C-14

- B-29 (C-5) usage-data — a cycle review's blocker at budget spent goes to the owner (AGENTS.md, fde-review) while kernel ADR-0019 rules 1/7 say only a replan reaches the user; state that this IS a replan (reviews/C-5 delta F1)
- B-30 (C-5) usage-data — the promotion template and fde-promotion say met / not met; status.py also settles `declined` and `limit` — align the template and the agent (reviews/C-5 delta F2)
- B-31 (C-5) usage-data — a blocker fixed inside its demand has no closing record: findings.toml keeps `blocking = true`; add a `fixed_in` / status field so "no blocking finding open" has evidence (reviews/C-5 delta F3)
- B-39 (C-5) usage-data — a demand can merge without its review; the board's merge line should require the review record (FWD-031 merged unreviewed, caught at promotion)
