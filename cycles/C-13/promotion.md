cycle: C-13
date: 2026-09-29
decision: promote (A1-A5 met; A6 completes on the release push)
commit: fb453df

## Criteria

- A1 — AGENTS.md step 5, fde-review and fde-adversarial carry the code-review-default rule verbatim (pinned by TestReviewByWeight.test_the_rule_is_stated_verbatim_everywhere); reviews/FWD-036/findings.toml is `kind = "code"`; step 1 "only" removed (code F1 fixed, pinned) — met
- A2 — same pinned sentence sends sensitive/irreversible/over-~300-line demands to adversarial and M/L plans to plan review; the risk rule wins inside a plan (cycle F2 fixed, pinned by test_the_risk_rule_wins); plan review scheduled before sign-off in fde-triage and fde-spec (cycle F1 fixed, pinned by test_plan_review_is_scheduled_before_sign_off) — met
- A3 — code record passes I2/TRACE/I8 (TestCodeReviewRecordPassesTheGate, cycle review probe on a scratch fixture); findings template carries `kind` and `context_policy = "artifact_only"` (pinned); verify.py --all: I2 37 reports, I8 264 findings, all gates passed — met
- A4 — fde-adversarial and its installed copy pin the four modes and budgets (test_the_reviewer_knows_its_mode_and_budget); README names the four modes (cycle F4 fixed, pinned) — met
- A5 — AGENTS.md 1,599 words (<=1,600) and descriptions max 40, checked in the cycle review; pins in the suite — met
- A6 — suite 633 tests OK and `verify.py --all` green at fb453df; kernel_version is still 0.20.0 and nothing is pushed — pending deploy

Review budget: S, code review 1 round (4 findings, none blocking) and cycle review 1 round (4 findings, none blocking); none narrowed or declared. Cycle F3 (missing FWD-036 review record) is resolved: reviews/FWD-036/ exists. Code F2-F4 and cycle residuals are in backlog (B-50..B-52 and later), not conditions.

## Deploy

Bump `kernel_version` to 0.21.0 (fde.config.toml and the places the release checklist names), rerun the suite and `verify.py --all`, commit, push, confirm CI green.
Rollback (written before the push): `git revert --no-commit a9d37f83946b999fbe7c5f50b1cd0f9a8a1e9edd..<release sha>` then commit and push; time target under 10 minutes, no data or migration involved, reversible.
Numeric triggers do not apply (no running service); the trigger is CI red on main or a gate failing in a client install after sync, which means revert at once.

## Signals

- observability.toml declares 8 signals (I5 green); this change adds none, since it alters instruction text only.
- `kind` on every review record is the new field read by I2/I8/TRACE; a code review that fails the gate is the alert to watch.
- Usage-data to check after two cycles: share of demands reviewed as `code` vs `adversarial`, and any risky change that slipped through as code.

## What changes

- Make the release step mechanical so A6 is not left pending after promotion.
- Keep a pin per rule text that spans more than three files; the drift found here was placement, not wording.
- Backlog: who measures "production lines" at review time, and the front layer check when no wireframe exists.
