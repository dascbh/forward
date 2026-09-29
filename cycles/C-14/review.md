cycle: C-14
date: 2026-09-29
commit: 6b55ec0
round: 1 of 2 (M, full)
reviewer: fde-adversarial, cycle mode, agent-a6b2c2f2c37902119
record: reviews/C-14/findings.toml

## Functioning

- **A1 — met for a back cycle, not for a front one (F4).** AGENTS.md is 1,090 words. Read cold, a back cycle runs end to end: triage → fde-triage, plan and deploy → fde-spec, states and close → fde-backlog, review, merge and budget → fde-review, RULE → fde-triage, backlog → fde-backlog-format. The must-stay rules are present. For a front demand, no text in AGENTS.md or in any skill on the loop points to fde-design (and none points to fde-survey, B-60). Step 5's "The cycle review is unchanged" has no referent for a cold reader (note).
- **A2 — met.** B-29: fde-review Budget, "that pick is the replan", matching AGENTS.md `## Cycle`. B-11: fde-backlog *specify*, "fetch and read the log since the last known commit". B-48 and B-49: fde-review `## Before the cycle review`. B-40: templates/cycle/plan.md and deploy.md, "never a range". B-21: "(MNT-9 scope discipline)". B-25: fde-walkthrough, "compiled first, by the planner".
- **A3 — not yet (F3).** Declined in plan.md, but backlog.md:13 still routes B-1 "→ C-14". promotion.md does not exist yet.
- **A4 — met in mechanics, broken in practice (F1).** On a scratch clone: a blocker with `fixed_in = "0521ded"` reads "0 blocking, fixed in 0521ded" in `status --demand`, and I8 stays green. Removing `context_policy` from reviews/C-14/findings-plan.toml turns I2 red. The promotion template and agent know all four endings. But FWD-040 is on main with no review record and no merge line.
- **A5 — met.** On a scratch old-client clone, `[scrum]` in place of `[backlog]` is green under `--gate backlog` and `--gate scrum`. `goal: not set` is red. A top-level `scrum = true` or `backlog = "yes"` gives CFG BACKLOG-TABLE red, with no traceback. `.claude/skills/fde-scrum` is gone.
- **A6 — met as text, unreviewed (F1).** SETUP §7 step 6 and fde-sync copy the kernel `docs/adr/` to `.fde/adr/`, replaced whole, never into the project's `docs/adr/`. §8 step 5 removes installed `fde-` skills the kernel no longer has, and keeps other skills. fde-sync rewrites both old comment forms and keeps a live `[scrum]` header. It warns up front about the permissions write and auto mode. This repository's `.fde/adr/` holds 0001–0021.
- **A7 — met.** The runtime at 6b55ec0 runs `verify.py --all` from headlabs-platform: all gates passed, and the tree is clean afterwards. FWD-041 and FWD-044 carry their tests and the CI change, reviewed as code.
- **A8 — met.** On headlabs, the `--panel` promotion cell shows `**promovido**` unescaped and cuts at a word ("bloqueado por 3…"). One findings parse and the helpers were reviewed in FWD-042.
- **A9 — open, as expected before close (F3).** All 30 items still read "→ C-14". 29 are delivered by the merged demands, three of them (B-32, B-38, B-42) by the unreviewed FWD-040. B-1 is declined in the plan only. None is open in substance.

## Readiness

- Suite and gate: green. 705 tests OK; `verify.py --all` passes all gates (BACKLOG id, I2 over 46 records).
- Version: `kernel_version` is 0.21.0 in fde.config.toml and spec/invariants.toml. The bump to 0.22.0 is pending with the release.
- deploy.md rollback: correctly "never a range", but it names "the demand merge commits", and there are none. Demands landed as plain rebased commits (FWD-037 as two), and b77621c (reconcile) is a behavior commit that belongs to no demand. The list promotion.md carries must name every behavior commit (F2). Steps 1 and 3 are complete.
- README: current. It names fde-backlog-format and `[backlog]`, and describes no installed `.fde/` layout, so `.fde/adr/` is not missing from it.
- Demand review records: FWD-037, 038, 039, 041, 042, 043 and 044 have one. **FWD-040 has none** (F1).

## Findings

- **F1 — high, blocking (probe: `ls reviews/`, board).** FWD-040 is on main with no `reviews/FWD-040/` record and no merge line, which breaks A4 (B-39) and the B-49 precondition this cycle ships. The gate stays green because B-39 is text only. The fix: FWD-040's code review, committed, and its merge line on the board.
- **F2 — medium (REL-3).** The rollback lists "demand merge commits" that do not exist and omits the reconcile commit b77621c. Fix in promotion.md's release list.
- **F3 — medium (probe: backlog.md:13).** B-1 is not recorded as declined in the backlog. A9 closes at promotion.
- **F4 — medium (MNT-4).** No pointer to fde-design (or fde-survey) on the loop, so A1 fails for a front cycle in an AGENTS.md-only tool. One pointer fits in the 10-word headroom. Fix in-cycle (B-60 shows A1 unmet).
