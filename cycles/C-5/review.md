cycle: C-5
date: 2026-09-29
round: 1 (full)

<!-- Cycle review (ADR-0019 rule 12), adversarial role, isolated worktree
agent-acf3d5bbf50cf3424 at 01b7c5b. No demand re-reviewed. Probes ran in
scratch copies under the session scratchpad: a full-history clone of this
repository and a clone of headlabs-platform. The live headlabs checkout
was only read. Findings are mirrored in reviews/C-5/findings.toml. -->

## Functioning

- A1 — met. On a clone, the fde-backlog §3 procedure assigned B-1..B-27: `#` cells became ids, bullets got `- B-<n>`, and `next.backlog_id` was B-28. §2 group: new `cycles/C-6/plan.md` (`state: draft`, `## Items` B-2, B-10, B-13) and a ` → C-6` mark on two table rows and one bullet. `status.py --format json` then gave: warnings [], C-6 draft with its 3 items, every grouped item's `cycle` = C-6, `next.cycle_id` C-7. `verify.py --all` was green before and after the commit. No spec was written.
- A2 — met, at the instruction and template level. Specifying C-6 from `.fde/templates/cycle/` gave a plan with a dated header, threat model, `A1`/`FM1` ids and a demand table (id, layer, depends on, meets, follows), plus a deploy.md ordered infra-expand → back → front → infra-contract, each step with verification and rollback. The gate was green. The planner's stop is stated in agents/fde-spec.md:48 and fde-backlog §2. Caveat (F2): who writes `planned`, and when, contradicts across texts. Note: the plan template has no `## Items`, so specifying a draft drops the draft's item list. The backlog's `→ C-n` marks survive.
- A3 — met. Text and JSON views show draft, running and closed states (C-1..C-4 as old files, C-5 and C-6 as directories); the backlog with ids and sections; `next` ids; and a "2 cycles open" warning. `state: closed` in plan.md reads as closed. JSON items carry full `text` and `cells`.
- A4 — met. specs/FWD-026..033 are each a lone `spec.md` of 57–101 words. Each cites C-5 and its A-ids, and none carries acceptance, failure modes, architecture or a promotion.
- A5 — met. AGENTS.md steps 4 and 6 (worktree per demand, board, rebase onto main, `--all` green) and board.md record eight demands in parallel with claims, blocked-on and rebased merges. The merge condition "no blocking finding open" hits F1.
- A6 — met. fde-review states demand and cycle mode, with walkthrough only for a `front` demand. The cycle review template matches. C-5 has no front demand, so no walkthrough runs here.
- A7 — met. The new runtime on the live headlabs-platform (read-only) gives all 12 gates green, and I4 reads 33 demands from old-layout acceptance.md. A headlabs clone with the new runtime, spec, templates and agents copied in is green once `kernel_version` is bumped. I2 fails when a cycle promotion.md covers an unreviewed demand, as it should. TRACE is green. SCRUM-GOAL/RETRO are gone. The old-layout fixture test is tests/test_verify.py:1469. Caveat (F5): a cycle closed with no promotion.md passes every gate.
- A8 — not met. A fresh read finds contradictions in the model: the blocking-finding path of a 1-round demand review (F1), and the `planned` state plus the backlog → draft step, which AGENTS.md never names (F2). The 15 discovery items were not re-audited one by one inside the budget.
- A9 — met. `wc -w AGENTS.md` = 1595 (≤ 1600). The longest skill or agent `description:` is 40 words (fde-verify), including the .claude copies. Caveat (F3): rationale moved to kernel ADRs that clients never receive.
- A10 — not yet done (release). Readiness is below.

## Readiness

- Suite: `python3 -m unittest discover -s tests` passes 563 tests, OK. `verify.py --all` on 01b7c5b: all gates passed.
- Version: 0.18.0 sits in spec/invariants.toml, .fde/spec/invariants.toml, fde.config.toml, .claude-plugin/plugin.json and templates/fde.config.template.toml (spec/references/ui-patterns.toml and its .fde copy also say 0.18.0). All of them move together, or CFG-VER goes red.
- Deploy step 1, rollback: not adequate as written (F4). 28 commits since origin/main (321e045) ship in one push. "git revert the release commit" undoes only the bump. `git revert --no-commit 321e045..HEAD` applies cleanly and leaves a tree identical to 321e045 (empty `git diff --cached 321e045`), so a real rollback exists.
- Deploy step 2 (client sync): SETUP §6.5 carries templates/cycle and findings.template.toml to .fde/templates/. fde-sync re-runs §6–8, and SETUP §8.4 plus fde-sync carry the permissions merge. ADR-0019 rule 15 (`## Next cycle` → backlog.md with B-ids) is in neither fde-sync nor SETUP (F3). fde-status only warns about it, and only for an open cycle. The sync also does not move the config's `kernel_version`: the simulated headlabs sync went CFG-VER red until it was bumped by hand. headlabs C-2 (old layout, 0.17.0) stays green after the simulated sync. The instructions it would read say only "a cycle opened before ADR-0019 finishes under its own rules", and ADR-0019 does not exist in headlabs (F3).
- Signals (I5): C-5 declares no production signal. I5 stays repository-wide (observability.toml, 8 signals), which is a declared limit on the board and in the backlog.
- README and runbook: README lists fde-backlog and fde-status, and describes fde-scrum as the backlog format. It still says "`fde-triage` — sizes the demand" (README.md:297), while AGENTS.md says size is set on the cycle, never on a demand. This repository has no runbook.

## Findings

1. **F1 — high, blocking.** A 1-round demand review has no fix-and-verify path for a blocking finding. AGENTS.md step 5 and fde-review §Budget send it to the owner (narrow, declare or pause). AGENTS.md ## Cycle ("the cycle owns ... its blocking findings") and ADR-0019 rule 7 ("the only thing that returns to the user is a replan") say otherwise. C-5's own board resolved about 20 blocking findings through unplanned fix demands (FWD-027-fix, RECON-TEXT, RECON-GATE, FWD-033 taking FWD-032 F1) without the owner. That path is written nowhere. Breaks A8; A5's merge condition depends on it.
2. **F2 — medium.** The draft → planned transition has no single owner and no place in AGENTS.md.
   - AGENTS.md:142 and templates/cycle/plan.md say fde-spec writes `state: planned`.
   - fde-backlog says the owner's sign-off sets it and the agent never does.
   - agents/fde-spec.md does not mention it.
   - ADR-0019 defines `planned` as "signed off", yet the planner stops before sign-off.

   AGENTS.md never names fde-backlog or the backlog → draft step. Breaks A8.
3. **F3 — medium.** ADR-0019 rule 15 and ADR-0019 itself do not reach clients.
   - fde-sync and SETUP have no migration step.
   - The client-facing texts cite kernel ADR ids: ADR-0019 ×11, plus ADR-0002, 0010, 0011, 0012, 0014, 0015 and 0018. In headlabs these resolve to nothing, or to unrelated ADRs such as ADR-0002 runtimes-internal-authorization. MNT-4.
4. **F4 — medium.** Deploy step 1's rollback ("git revert the release commit") does not undo the 28-commit release. The clean range revert is not the documented one.
5. **F5 — medium.** A cycle with `state: closed`, no promotion.md and 0/1 criteria met passes every gate. status.py shows it closed with no warning, so a cycle can skip promotion, and I2's promoted-without-review check with it.
