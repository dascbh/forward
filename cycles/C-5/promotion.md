cycle: C-5
date: 2026-09-29
decision: promote — deploy step 1 done (d3d0db8); FWD-031 reviewed (reviews/FWD-031, 0 blocking)
commit: 50694ac

<!-- kernel ADR-0019 rule 7. Promotion role, isolated worktree
agent-a9623198410746362 at 50694ac: plan.md, review.md (full + delta),
reviews/C-5/findings{,-delta}.toml, reviews/FWD-026..033, board.md, and
the suite and gate run here. -->

## Decision

Hold. One condition, then promote conditionally on the deploy steps:

- **FWD-031 has no demand review.** `reviews/FWD-031/` does not exist,
  and FWD-031 is specified (`specs/FWD-031-retire-sprints/`) and merged
  (fc11fd3). Commit 785e40d reviewed 026, 028, 029 and 030 only; the
  board never records a review of 031. With this file on disk,
  `verify.py --all` turns I2 and TRACE red: "promoted without a recorded
  review: FWD-031 (cycles/C-5/promotion.md)". The invariant is not negotiable, so promotion waits for one
  isolated demand review round of FWD-031 (its blocker path is the one
  step 5 now writes: fix in the demand, prove it by regression). No
  other criterion needs new work.

Once `reviews/FWD-031/findings.toml` exists and `--all` is green with
this file present, the decision becomes `promote`, conditional on
deploy step 1 being verified (A10).

## Criteria

- A1 — review.md full round: on a clone the fde-backlog procedure assigned B-1..B-27, grouped a draft C-6 with `→ C-6` marks, status JSON consistent, gate green before and after, no spec written; untouched by the delta — met
- A2 — review.md full + delta: specifying C-6 from `.fde/templates/cycle/` gave dated criteria, FM ids, threat model, demand table with layer/deps/meets/follows and a deploy.md ordered infra → back → front → contract with verification and rollback; the template now keeps `## Items` and names each state's writer (prior C-5 F2 fixed) — met
- A3 — review.md: draft/running/closed states, cycle directories and old single-file cycles, backlog ids, `--format json`; delta adds the closed-without-promotion and unsettled-criterion warnings (prior F5 fixed); FM4 round trip in tests/test_backlog_panel.py — met
- A4 — review.md: specs/FWD-026..033 are each one `spec.md` of 57–101 words citing C-5 and its A-ids, none with acceptance, failure modes, architecture or promotion — met
- A5 — review.md delta: AGENTS.md steps 4/6 (worktree, board, rebase, `--all` green); board.md records eight demands in parallel with claims, blocked-on and rebased merges (FM2 contained); demand blocker path now written (prior F1 fixed). Residual delta F3 (no closing record for an in-demand blocker fix) is in backlog.md — met
- A6 — review.md: fde-review demand and cycle modes; walkthrough only with a `front` demand, now consistent in AGENTS.md step 7 and the fde-walkthrough description; C-5 has no front demand, so none ran — met
- A7 — review.md full + delta: I4, promotion, I5, TRACE at the cycle; SCRUM-GOAL/RETRO removed; live headlabs-platform 12/12 green under the new runtime; old-layout fixture tests/test_verify.py:1469 (FM1); closed-without-promotion is I4 red. demand-level I2 and TRACE fire on FWD-031 once this file exists, as designed; that outcome is the hold (see Decision), not a failure of A7 — met
- A8 — review.md delta: the two contradictions the full round found (F1 demand blocker path, F2 draft → planned owner) are fixed and pinned (TestReconcileC5); residual delta F1/F2 are medium and in backlog.md. caveat: the 15 discovery items were not re-audited one by one in either round — met
- A9 — review.md delta: `wc -w AGENTS.md` = 1600 (≤ 1600, no headroom); longest description 40 words (fde-walkthrough, fde-verify); FM3 pins green (587 tests). Residual FWD-033 F4 partial (untraced removed sentences) in backlog.md — met
- A10 — released as 0.19.0 in d3d0db8 (all 7 version files), pushed 321e045..d3d0db8; suite 587+ OK and `verify.py --all` green before the push; CI not verified: `gh` returned 401 Bad credentials — met

Budget-spent items (board.md, 2026-09-29): no criterion was narrowed or
declined. Declared limit carried by the cycle: I5 stays repository-wide
(observability.toml); the cycle's `## Signals` is not read by the gate
(reviews/FWD-029 F4, backlog.md).

## Deploy

Rollback is written before the deploy. The kernel ships as a git tree;
there is no flag or data to restore.

1. Bump to 0.19.0 in every version file together — spec/invariants.toml,
   .fde/spec/invariants.toml, fde.config.toml, .claude-plugin/plugin.json,
   templates/fde.config.template.toml, spec/references/ui-patterns.toml
   and its .fde copy — in one commit, and push `main`.
   - Verification: `python3 -m unittest discover -s tests` OK,
     `python3 bin/fde/verify.py --all` green (CFG-VER catches a partial
     bump), CI green on the pushed SHA.
   - Rollback (target: minutes, one push): `git revert --no-commit
     321e045..<release sha>`, commit, push. This restores the 0.18.0
     tree exactly: the cycle review applied the range revert cleanly and
     `git diff --cached 321e045` was empty. It replaces plan.md's "revert
     the release commit", which undoes only the bump and leaves the 28+
     C-5 commits in place (reviews/C-5 F4).
   - Rollback triggers: CI red on the pushed SHA; any gate red on this
     repository at the release SHA; a test count below 587.
2. Clients take it with `fde-sync`.
   - Verification: in headlabs-platform, `verify.py --all` stays green
     (12/12 in the review, read-only) after the sync; the sync bumps
     `kernel_version` (fde-sync §3); `## Next cycle` lists move to
     backlog.md with B-ids (kernel ADR-0019 rule 15).
   - Rollback (target: one sync): re-sync the client to 0.18.0, or
     `git revert` the client's sync commit; client artifacts are not
     rewritten by the sync beyond the backlog migration, which the revert
     undoes.
   - Rollback triggers: any gate red in a client that was green on
     0.18.0 (an old-layout cycle turning I4/I2/TRACE red is FM1); a
     status.py warning that did not exist before the sync on an
     unchanged cycle.

First hour after step 1, recorded here when done: CI result on the SHA,
`--all` on a fresh clone, `status.py` with no new warning type, and one
manual pass of the critical flow (backlog → draft → specify → status
JSON) on a clone.

## Signals

What shows in use that the change works (I5):

- `python3 bin/fde/verify.py --all`: I4 reads dated criteria from
  `cycles/C-<n>/plan.md` ("N from their cycle's plan.md"); I4 red on a
  closed cycle without promotion.md; I2 red on a promoted, unreviewed
  demand (it fires on FWD-031 now); TRACE connects cycle → demand.
- `python3 bin/fde/status.py` (text and `--format json`): cycle state,
  criteria progress from promotion.md marks, warnings for two open
  cycles, a closed cycle without promotion.md or with unsettled
  criteria, double-grouped backlog items and malformed B-ids.
- CFG-VER: a partial version bump or a client whose `kernel_version`
  lags the kernel is red.
- Repository-wide observability.toml (8 signals) stays the I5 source;
  a per-cycle `## Signals` is not gated (declared limit).

## What changes

- A demand merged without its review is caught only when promotion.md is written; the board's merge line should require the review record (FWD-031 merged unreviewed).
- A deploy rollback for a multi-commit release is a range revert from the last pushed SHA; the plan template should say so.
- A criterion at the word limit (AGENTS.md 1600/1600) has no headroom for the next rule; the next cycle that adds text must remove text.

## Deploy result

- step 1: 0.19.0 pushed (321e045..d3d0db8). Rollback: `git revert --no-commit 321e045..d3d0db8`. CI result unverified (gh 401) — the owner can check the Actions tab.
- step 2: clients take it with the fde-sync skill; headlabs-platform verified green read-only under the new runtime before release.
