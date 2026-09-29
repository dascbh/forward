cycle: C-14
date: 2026-09-29
decision: promote — deploy done (8446fec)
commit: 5d791ca

Evidence: cycles/C-14/review.md (full round at 6b55ec0, delta round at b18199b), reviews/C-14/ (findings.toml, findings-delta.toml, findings-plan.toml), reviews/FWD-037..044, board.md, and `python3 bin/fde/verify.py --all` run once at 5d791ca: all gates passed (I1, I2 over 49 reports, I3, I8 over 295 findings, I4, I5, I6, I7, BACKLOG, TRACE, EROSION, DIVERGE, SURVEY). The suite at 5d791ca was recorded OK by the main thread and not rerun here.

## Criteria

- A1 — AGENTS.md is 1,098 words (cap 1,100); the inventory precedes the move and a script checked 75 sentences, no rule lost (board, FWD-037); the cycle review's F4 (no pointer to fde-design or fde-survey for a front cycle) is fixed in efb1839/5d791ca — met
- A2 — one text each for B-29, B-11, B-48/B-49, B-40, B-21 and B-25, located in the cycle review's A2 line and delivered by FWD-043 and the reconcile b77621c — met
- A3 — B-1 declined: the risk rule (kernel ADR-0021) already carries sensitivity per demand, and the cycle score keeps `sensitive` and `irreversible`; recorded in plan.md and in backlog.md:126 (review F3 fixed) — declined
- A4 — promotion template and agent know met / declined / limit / not met; `fixed_in` closes a blocker; the merge line names the review; I2 reads every record in reviews/ (probed in a scratch clone in the cycle review); FWD-038, FWD-040 review records all present (F1 fixed in 99852cc) — met
- A5 — `[backlog]` with `[scrum]` alias, `fde-backlog-format`, gate ids renamed, `goal: not set` rejected, no crash on a non-table, sprint-wording test; the old-client `[scrum]` fixture is green (cycle review A5, probed) — met
- A6 — kernel ADRs read-only at `.fde/adr/`, old config comment rewritten, permissions and auto-mode notice, removal of retired `fde-` skills (cycle review A6, FWD-040 review, 6b55ec0) — met
- A7 — B-12, B-14, B-16, B-20, B-27, B-28 have tests red before the fix (FWD-041 review); B-15 in the CI workflow (FWD-044, e3633e8); headlabs-platform green under the new runtime, read-only run in the cycle review — met
- A8 — findings parsed once, helpers without nested and-expressions, the promotion cell unescaped and cut at a word (cycle review A8 on headlabs; FWD-042 review) — met
- A9 — 30 items listed in plan.md: 29 delivered by the eight demands (each in its board line and review) and B-1 declined (A3). The backlog holds only what this cycle's reviews added, B-54 to B-68, none owned by a C-14 criterion — met
- A10 — released as 0.22.0 in 8446fec (7 version files) with 8b222e4 in the release, pushed 9f9f3a2..8446fec; suite and `verify.py --all` green before the push; CI not verified (gh 401) — met

Budget: the M cycle review (full plus delta) is spent. Blockers found: F1 (fixed), D1 (fixed by the split). None open, nothing narrowed, no declared limit.

## Release

The rollback is `git revert` of these commits plus the release commit, one by one, never a range (a range would also revert the cycle's own records: cycle review F2, delta D2). The demands landed as plain rebased commits; there are no merge commits.

- FWD-037: 7b274ad, ed6eb8f
- FWD-038: 0521ded
- FWD-039: 296e2be
- FWD-040: 6b55ec0
- FWD-041: dbc2fe7
- FWD-042: c3a1216
- FWD-043: 592be14
- FWD-044: e3633e8
- reconciles: b77621c, efb1839
- owner's direct commit 8b222e4 ("Lean process": direct lane, tests once per SHA, no clean delta, backlog ids on main, no sync mid-cycle): outside the plan, ships in the same release; revert it with the rest, and it touches AGENTS.md, so revert it in reverse order of landing.

Rollback order, newest first: release commit, efb1839, 8b222e4, 6b55ec0, b77621c, e3633e8, c3a1216, 296e2be, 0521ded, 592be14, dbc2fe7, ed6eb8f, 7b274ad. Time target: minutes (a local revert and push); clients re-sync from 0.21.0, and `.fde/adr/` and a `[backlog]` key are ignored by 0.21.0 (deploy.md step 3).

Rollout numeric triggers (kernel, no production traffic): the gate on main red on the release SHA, or a headlabs sync with `kernel_version` 0.22.0 whose `verify.py --all` is red where 0.21.0 was green. Either triggers the revert. First hour after the push: CI green on the release SHA, one manual sync pass on headlabs (`kernel_version` 0.22.0, `.fde/adr/` present, gate green).

## Signals

I5, the signals in observability.toml (unchanged, all eight attributes declared, I5 green):

- functional_correctness: the suite and `verify.py --all` on every push (fde-gate) — the release SHA's CI run.
- reliability_resilience: fde-gate history on main; a red run after the release is a broken release.
- usability_accessibility: field reports from the headlabs sync (the skeleton AGENTS.md read cold by a client).
- maintainability: the mirror, instruction-pin and inventory tests (FM1: every moved sentence is found verbatim in its skill).

## What changes

- Parallel demand start let FWD-040 land before its review record, so B-49 held only in text (F1); the next plan orders each demand's merge after its review, or the board rejects the line (B-39 as a gate is a backlog idea).
- deploy.md and plan.md named "merge commits" the direct lane never creates; the template should say "the demand's commits".
- Findings and behavior in one commit turned the gate red (D1); commit a review record alone, first.
