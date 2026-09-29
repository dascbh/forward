cycle: C-12
date: 2026-09-29
mode: cycle · round 1 of 1 (S) · full
commit: d05a4ad
mirror: reviews/C-12/findings.toml

<!-- Adversarial role, cycle mode. Judges the objective on the integrated
result; the demands' code is not re-reviewed. A cold read of the printed
panel replaces the browser walkthrough (declared limit in plan.md). -->

## Functioning

- **A1 — met here.** `status.py --panel` exits 0 on this repository (156 lines) and prints the five sections: Overview, Backlog, Cycles, Demands, Discarded. `skills/fde-backlog/SKILL.md` §1–2 runs it, shows the output unchanged, lists actions in plain text and forbids the question box. FM1 holds: in a fixture, pipes, `#`/`###` headings and `<script>` in the objective, items, section titles and a findings probe all come out escaped, and the demand table stays intact.
- **A2 — met.** The Overview shows running C-12 with 0/7 criteria, planned none, drafts C-6..C-11 and C-13, warnings none, next ids B-45 · C-14, and the counts. FM4 holds: the panel counts (backlog 32, discarded 12, cycles 13 = 1/0/7/5, demands 27 with 14 loose) equal the `--format json` data (backlog sections 3+1+1+6+21 = 32, plus 12 discarded).
- **A3 — not met on a client (F1).** Here, C-12 shows its objective, state, criteria, items, a demands table (layer, review, promotion) and its artifacts. On headlabs-platform, every demand shows "not reviewed" and "promotion —" although `reviews/DEM-035-kb-erase-source/findings.toml` exists. The drill-down for an ended cycle leaves out review and promotion (F3).
- **A4 — partly met (F1).** All 14 unlinked specs are listed here (13 linked + 14 loose = 27 spec dirs), and old-layout specs appear in the fixture (FM2 holds). On headlabs, the 23 loose demands all read "not reviewed · promotion —". Among them are `reviews/DEM-001-runtimes/` and `promotions/DEM-002-runtimes-wizard/decision.md`.
- **A5 — met.** Backlog items appear by section with their B-id and `→ C-n` mark. Discarded items carry a reason. In the fixture, a reason containing a pipe also got "— (no reason)" appended; see notes.
- **A6 — met here, wrong on a client (F1).** `--demand FWD-029` prints the cycle, layer, spec, 4 findings, the promotion and both ADRs. An unknown id exits 2, and a lowercase id resolves. The skill maps "abre C-n" to `--cycle` and "mostra <id>" to `--demand`. On headlabs, `--demand DEM-035` prints "review: none".
- **A7 — pending release.** 612 tests OK and `verify.py --all` is green. `kernel_version = "0.19.0"` and 7 commits are unpushed, as expected before the release step. The demand reviews are missing (F2).

## Cold read

I read `--panel` output on this repository as an owner new to the project.

**What it says the state is.** One cycle is running: C-12, a terminal backlog panel. None of its 7 criteria is met, and both of its demands (FWD-034 back, FWD-035 front) are "not reviewed". There are 32 open backlog items; almost all are already grouped into seven draft cycles (C-6..C-11, C-13). Five cycles are closed. There are 14 older demands with no cycle, many carrying blocking findings (FWD-001: "13 findings, 8 blocking"), and 12 discarded items.

**What I would do next.** I would finish C-12: its demands look built but unreviewed. The panel does not say so, though. It prints no action or next step (the actions come from the skill, after the panel). "0/7 met" and "not reviewed" are the only clues.

**Where I got confused** (what the output said, not a guess about users):
- "old" appears in every loose-demand line and is never explained. I could not tell whether "old" is a state to act on.
- "### (before any section)" reads like a parser artifact, not a heading I chose.
- The ended cycles say "criteria 10/10 met" (C-5) but "done 5/5 met" (C-1..C-4) for what looks like the same measure.
- "FWD-001 · old · 13 findings, 8 blocking · promotion —" looks alarming. I could not tell whether 8 blocking findings are open work or history; the panel gives no state for a loose demand.
- Clipped lines ("cycles with their demands an…") cut the running cycle's own objective mid-word, in the one line that says what the cycle is for.

## Readiness

- **Release**: suite and gate green; version still 0.19.0 (bump to 0.20.0 pending); 7 commits since `397a40f^` unpushed. The rollback in `deploy.md` step 2, `git revert --no-commit <last pushed sha>..<release sha>`, is the correct range form.
- **Review record**: neither `reviews/FWD-034/` nor `reviews/FWD-035/` exists. The board records FWD-034 as committed with no review line and has no line at all for FWD-035's commit (F2). The panel itself prints "not reviewed" for both.
- **README**: current. Lines 314–318 describe `fde-backlog` as the terminal panel with `--panel` and `--demand`. `skills/fde-status` documents both flags, and `.claude/skills/fde-backlog` mirrors `skills/fde-backlog`.
- **headlabs-platform (read-only)**: `--panel`, `--cycle C-2`, `--demand DEM-035` and `--format json` all exit 0, with no traceback and empty stderr. The content is wrong, though (F1).
- **FM3**: a fixture with 200 closed cycles, 401 loose specs and 500 long items prints 1,326 lines, the longest 141 characters. Clipping and folding apply, but the 200 warnings print unfolded at the top of the Overview (F5).

## Findings

- **F1 (high, blocking).** `status.py` reads reviews and promotions only from `reviews/<id>/` and `promotions/<id>/`. Slugged directories (`reviews/DEM-035-kb-erase-source/`) read as "not reviewed" and "promotion —". On headlabs-platform, all 33 demands read "not reviewed", although 29 review directories and 20 promotion directories exist. This breaks A3, A4 and A6.
- **F2 (medium).** C-12's demands carry no review artifact, and the board has no review or merge line for FWD-035. The plan declared "demand reviews 1 round each".
- **F3 (medium).** `--cycle C-n` (the "abre" drill-down) lists demands by layer only. For an ended cycle, whose demands the panel folds, review and promotion per demand are reachable only through N separate `--demand` calls.
- **F4 (medium).** The cold read found unexplained or inconsistent vocabulary: "old", "(before any section)", "done" vs "criteria", and no state for a loose demand with blocking findings.
- **F5 (low).** The folding rule does not cover warnings: 200 warnings print one line each above the backlog.
