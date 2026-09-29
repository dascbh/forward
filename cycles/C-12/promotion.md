cycle: C-12
date: 2026-09-29
decision: promote, conditional on deploy step 2 (0.20.0 bumped and pushed); A1–A6 met, A7 pending deploy
commit: 14f42cc

<!-- kernel ADR-0019 rule 7. Promotion role, isolated worktree
agent-ae1573997ea3844e5 at 14f42cc: plan.md, deploy.md, board.md,
review.md, reviews/C-12, reviews/FWD-034, reviews/FWD-035, and the
suite, the gate and status.py run here (headlabs-platform read-only). -->

## Criteria

- A1 — review.md: `status.py --panel` prints Overview, Backlog, Cycles, Demands, Discarded; fde-backlog §1–2 runs it, shows it unchanged, lists actions as plain text, no question box; FM1 hostile-text fixture holds. At 14f42cc: exit 0, 160 lines, the same five `##` sections — met
- A2 — review.md: running cycle with progress, planned, drafts, warnings, next ids, counts; FM4 panel counts equal `--format json`. At 14f42cc the Overview also carries a `next:` line (C-12 F4) and warnings fold after 10 (C-12 F5, TestCycleReviewC12) — met
- A3 — C-12 F1 (high, blocking) fixed in 14f42cc: slugged `reviews/<id>-<slug>/` and `promotions/<id>-<slug>/` are read. Regression `test_f1_slugged_review_and_promotion_dirs_are_found` errors against b8aae62's runtime/status.py and passes at 14f42cc. On headlabs-platform the C-2 table shows DEM-035/036/037 reviewed and DEM-035/036 promoted; `--cycle` now shows review and promotion per demand (F3) — met
- A4 — review.md: 14 loose specs here, old layout in fixture (FM2). FWD-035 F1 (dangling cycle link unlisted) fixed. headlabs-platform `--format json`: 33 demands, 28 reviewed, 20 promoted (was 0/0 at the cycle review); its 23 loose DEM lines carry review and promotion status — met
- A5 — review.md: backlog by section with B-id and `→ C-n`; discarded with reason. At 14f42cc: Backlog (35) and Discarded (12) print as described — met
- A6 — review.md: `--demand FWD-029` prints spec, findings, promotion, ADRs; unknown id exits 2; skill maps "abre C-n"/"mostra <id>". FWD-034 F1 (empty id) fixed. At 14f42cc on headlabs, `--demand DEM-035` prints `reviews/DEM-035-kb-erase-source/findings.toml` with 5 findings and the promotion decision — met
- A7 — status.py exits 0 here and on headlabs-platform (empty stderr, read-only); 620 tests OK; `verify.py --all` all 15 gates green at 14f42cc; version still 0.19.0 and 13 commits unpushed (origin/main = 180a132) — pending deploy

Demand reviews: reviews/FWD-034 (3 low) and reviews/FWD-035 (1 medium, 2 low), 0 blocking; the two that broke A4/A6 fixed in-cycle, the rest in backlog.md (board.md). C-12 F2 (no demand review record) is stale: 9792715 recorded both before 14f42cc. C-12 F3–F5 fixed in 14f42cc.

Budget-spent or narrowed items (board.md): none. Declared limit carried by plan.md: the front demand's usability check is an isolated cold read of the printed panel, not a browser walkthrough (review.md `## Cold read`).

## Deploy

Rollback is written before the deploy. The kernel ships as a git tree;
no flag, no data to restore.

1. **back** (FWD-034) — merged at 30488e3 and reconciled at 14f42cc, behind the gate. Verified above (test_status both layouts; `--all` green; headlabs read-only). Rollback: part of step 2's range revert.
2. **front + release** — bump to 0.20.0 in every version file together (spec/invariants.toml, .fde/spec/invariants.toml, fde.config.toml, .claude-plugin/plugin.json, templates/fde.config.template.toml, spec/references/ui-patterns.toml and its .fde copy), one commit, push `main` from 180a132.
   - Verification: `python3 -m unittest discover -s tests` OK (≥ 620), `python3 bin/fde/verify.py --all` green (CFG-VER catches a partial bump), CI green on the pushed SHA, `status.py --panel` exit 0 here and on headlabs-platform.
   - Rollback (target: minutes, one push): `git revert --no-commit f7c9c06..<release sha>`, commit, push. Last pushed commit: 180a132 (`git log origin/main -1`). This range restores the 0.19.0 release tree exactly, including the four backlog-only commits 8200625..180a132 (backlog.md, cycles/C-6..C-11 drafts). To keep those, use `git revert --no-commit 180a132..<release sha>` (deploy.md's form).
   - Rollback triggers: CI red on the pushed SHA; any gate red at the release SHA; a test count below 620; `status.py` (any flag) exiting non-zero or printing a traceback on this repository or on headlabs-platform; a demand with a review directory reading "not reviewed".
3. Clients take it with `fde-sync`. Rollback: re-sync to 0.19.0 or revert the client's sync commit. Trigger: any gate red in a client that was green on 0.19.0.

First hour after step 2, recorded here when done: CI result on the SHA; `--all` on a fresh clone; `status.py --panel` with no new warning type; one manual pass of the critical flow (`/fde-backlog` → panel → "abre C-12" → "mostra FWD-035").

## Signals

What shows in use that the change works (I5):

- `python3 bin/fde/status.py --panel`: exit 0 and the five sections; the Overview counts equal `--format json` (FM4).
- `python3 bin/fde/status.py --format json`: `demands[]` with review path, findings, blocking and promotion per demand, in both layouts and in slugged directories (headlabs-platform: 33 / 28 reviewed / 20 promoted).
- `python3 bin/fde/status.py --demand <id>` / `--cycle C-n`: one demand's spec, findings, promotion, ADRs; exit 2 on an unknown id.
- `python3 bin/fde/verify.py --all`: CFG-VER on the 0.20.0 bump; I2/TRACE on the promoted demands. Repository-wide observability.toml (8 signals) stays the I5 source.

## What changes

- A reader of client artifacts must be proven on a real client before the cycle review: the slugged-directory layout was found only by running on headlabs-platform.
- A demand's review record should be committed before the cycle review starts, so the cycle review does not report a stale missing record (C-12 F2).
- The panel's promotion cell prints raw markdown (`\**promovido**`) from clients' decision lines (B-47); a status column needs a normalized value, not the first line.
