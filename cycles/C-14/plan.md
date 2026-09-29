# C-14

state: draft
objective: clear the backlog — every item still needed after 0.21.0, starting with AGENTS.md as a skeleton and the detailed rules in skills

## Items

- B-53 owner decision — AGENTS.md keeps only the loop's skeleton and a pointer per step; detailed rules (sizing table, RULE lane, review modes, cycle states, blocker path, deploy order, backlog format) move into their skills (fde-triage, fde-review, fde-backlog, fde-scrum), with their verbatim pins moving with them; target: AGENTS.md well under the cap so a new rule never forces trims (resolves B-51; owner, 2026-09-29)
- B-21 C-2#3 usage-data — the ## Cycle section cites MNT-9 by bare id; a client reading AGENTS.md alone cannot resolve it (review note)
- B-25 (C-5) usage-data — at XS/S the walkthrough's intended model is compiled by the architecture role, which those sizes do not otherwise plan in (RECON-TEXT note)
- B-29 (C-5) usage-data — a cycle review's blocker at budget spent goes to the owner (AGENTS.md, fde-review) while kernel ADR-0019 rules 1/7 say only a replan reaches the user; state that this IS a replan (reviews/C-5 delta F1)
- B-11 Resync before proposing
- B-48 (C-12) usage-data — prove a reader against a real client (headlabs) before the cycle review, not only against this repo's layout (C-12 F1 was invisible here)
- B-49 (C-12) usage-data — commit the demand reviews before the cycle review starts, so the cycle reviewer sees them (C-12 F2 was stale)
- B-40 (C-5) usage-data — the cycle plan template should give a range revert from the last pushed SHA as the rollback of a multi-commit release (reviews/C-5 F4)
- B-1 Per-demand `sensitive`/`irreversible` in triage
- B-30 (C-5) usage-data — the promotion template and fde-promotion say met / not met; status.py also settles `declined` and `limit` — align the template and the agent (reviews/C-5 delta F2)
- B-31 (C-5) usage-data — a blocker fixed inside its demand has no closing record: findings.toml keeps `blocking = true`; add a `fixed_in` / status field so "no blocking finding open" has evidence (reviews/C-5 delta F3)
- B-39 (C-5) usage-data — a demand can merge without its review; the board's merge line should require the review record (FWD-031 merged unreviewed, caught at promotion)
- B-50 (C-13) usage-data — the I2 gate reads only files named `findings.toml` (`gate_adversarial`, `rglob("findings.toml")`), so a plan review recorded in `reviews/C-<n>/findings-plan.toml` (kernel ADR-0021) is never checked for `context_policy = "artifact_only"` (FWD-036)
- B-13 C-1#3 usage-data — gate_scrum crashes when [scrum] is not a table
- B-34 (C-5) usage-data — `--gate scrum` accepts `goal: not set` and Goal/Date lines under a `##` section; read the header only, as fde_lib.header_lines does (reviews/FWD-031 F1)
- B-36 (C-5) usage-data — no test stops sprint instructions from returning in agents/ or other skills; widen the retirement pin to every instruction file (reviews/FWD-031 F3)
- B-37 (C-5) opinion — the `[scrum]` key, the fde-scrum skill and the gate ids no longer match what they do (backlog goal); rename to backlog (reviews/FWD-031 F4)
- B-32 (C-5) usage-data — clients read "kernel ADR-00NN" but never receive the kernel ADRs; ship them read-only or link them (reviews/C-5 F3 partial)
- B-38 (C-5) usage-data — clients keep the old config comment "backlog + sprints" across syncs (headlabs fde.config.toml:196) (reviews/FWD-031 F5)
- B-42 usage-data — under Claude Code auto mode, the classifier blocks the sync's permission merge (SETUP §8.4) and the sync stops half way (kernel_version and permissions left undone); fde-sync should say up front that it writes permissions and tell the user to leave auto mode if blocked (owner report, 2026-09-29)
- B-12 C-1#2 usage-data — I1's changed() lists files with git diff-tree --name-only without -z, so git-quoted paths (non-ASCII, tab) may miss behavior_paths
- B-14 C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite
- B-15 C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not keep full-history runs red (touches ADR-0016's pinned run line)
- B-16 C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client
- B-20 C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note)
- B-27 (C-5) usage-data — I1-REQS reads journey R# tokens only from per-demand acceptance.md; a front demand in the cycle layout (A# criteria in plan.md) is not traced to evals/journeys/ — needs a follow-up in verify.py (FWD-032 note)
- B-28 (C-5) usage-data — runtime messages still cite bare kernel ADR ids a client cannot resolve: guard.py LEGACY_NOTE "only for a cycle opened before ADR-0019" (pinned by tests/test_coherence.py); instruction texts now say "kernel ADR-00NN" (RECON-C5-TEXT, reviews/C-5 F3)
- B-45 (C-12) usage-data — `--demand` parses findings.toml twice (code review FWD-034 F3)
- B-46 (C-12) usage-data — nested `d and d[...]` expressions in status.py's panel helpers are hard to read (code review FWD-035 F2)
- B-47 (C-12) usage-data — the panel's promotion cell shows a bold decision as `\**promovido**` (the leading `*` escaped as a list marker) and cuts it at 40 characters mid-word (`--panel --root headlabs-platform`, DEM-002, DEM-013)
