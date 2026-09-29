---
goal: The kernel develops itself end to end under its own mechanisms — install, demand loop, cadence — and every rule ships field-proven.
date: 2026-08-09
---

# Product backlog

Items ordered by value against the goal. Evidence ladder:
`opinion < usage-data < user-test < production`.

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| B-1 | Per-demand `sensitive`/`irreversible` in triage → C-10 | in sensitive+irreversible projects every demand floors at M, inflating ceremony for changes that touch neither (a one-line UI flip sized M in the field); per-demand judgment with strict tiebreaks would restore proportionality without relaxing criteria | usage-data (AGROMETA, DEM-reforma-prefetch) | M |
| B-2 | I1 bluntness on prose-only edits → C-10 | a comment or doc-only change inside a behavior root trips I1 and demands an eval touch; predicted as self-hosting friction in ADR-0007 — measure it here first, then decide (diff-content inspection vs accepting the over-approximation) | opinion (predicted, not yet felt) | S |
| B-3 | Role identity in the hook payload → C-10 | the guard's role branch only fires where the harness sends an agent identity (finding F3); an upstream feature request or a documented workaround would restore loop-tier scope enforcement | usage-data (F3, reproduced live) | S |

## Status

Items 1–5 selected into S-002 as FWD-003..FWD-007 (planning 2026-08-09);
sizes re-scored at selection with per-demand triage inputs. Items 6–8
below entered at the S-005 review; item 6 was selected into S-006 as
FWD-013.

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| B-6 | Verification discipline → C-10 | five factual errors about external sources shipped in two demands, each caught only by isolated review because the accompanying tests asserted a claim existed rather than that it was true; a catalog principle plus a gate on undated/expired claims would make the failure mode detectable by the suite | usage-data (S-005 reviews, 3 rounds) | M |

## Unplanned intake

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| B-11 | Resync before proposing → C-10 | a session negotiating FWD-021's finish proposed a plan already obsoleted by ADR-0018/FWD-022, landed on main from a parallel session; before proposing a plan for a paused or long-running demand, fetch and read the log since the last known commit | usage-data (FWD-021 retro) | XS |

## Captured from cycle C-1 (FWD-021, abandoned 2026-09-28)

FWD-021 is abandoned and its code is gone from main; the items that
described the cycle gate itself (C-1#1, #4, #5, #7–#13, #17, #19–#21)
went with it. What remains is pre-existing and independent of that gate.
Evidence for every line: usage-data (FWD-021 implementation and five isolated review rounds).

- B-12 C-1#2 usage-data — I1's changed() lists files with git diff-tree --name-only without -z, so git-quoted paths (non-ASCII, tab) may miss behavior_paths → C-9
- B-13 C-1#3 usage-data — gate_scrum crashes when [scrum] is not a table → C-8
- B-14 C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite → C-9
- B-15 C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not keep full-history runs red (touches ADR-0016's pinned run line) → C-9
- B-16 C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client → C-9
- B-17 C-1#16 usage-data — support for a project in a git subdirectory (I1 requires the git top level) → C-9

## Captured from cycle C-2 (FWD-022, closed 2026-09-28)

Evidence for every line: usage-data (FWD-022 implementation and its isolated review).

- B-20 C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note) → C-9
- B-21 C-2#3 usage-data — the ## Cycle section cites MNT-9 by bare id; a client reading AGENTS.md alone cannot resolve it (review note) → C-11
- B-25 (C-5) usage-data — at XS/S the walkthrough's intended model is compiled by the architecture role, which those sizes do not otherwise plan in (RECON-TEXT note) → C-11
- B-26 (C-5) usage-data — I5 stays repository-wide (observability.toml); reading the cycle's promotion.md ## Signals is not implemented (reviews/FWD-029 F4, declared limit) → C-11
- B-27 (C-5) usage-data — I1-REQS reads journey R# tokens only from per-demand acceptance.md; a front demand in the cycle layout (A# criteria in plan.md) is not traced to evals/journeys/ — needs a follow-up in verify.py (FWD-032 note) → C-9
- B-28 (C-5) usage-data — runtime messages still cite bare kernel ADR ids a client cannot resolve: guard.py LEGACY_NOTE "only for a cycle opened before ADR-0019" (pinned by tests/test_coherence.py); instruction texts now say "kernel ADR-00NN" (RECON-C5-TEXT, reviews/C-5 F3) → C-9
- B-29 (C-5) usage-data — a cycle review's blocker at budget spent goes to the owner (AGENTS.md, fde-review) while kernel ADR-0019 rules 1/7 say only a replan reaches the user; state that this IS a replan (reviews/C-5 delta F1) → C-6
- B-30 (C-5) usage-data — the promotion template and fde-promotion say met / not met; status.py also settles `declined` and `limit` — align the template and the agent (reviews/C-5 delta F2) → C-6
- B-31 (C-5) usage-data — a blocker fixed inside its demand has no closing record: findings.toml keeps `blocking = true`; add a `fixed_in` / status field so "no blocking finding open" has evidence (reviews/C-5 delta F3) → C-6
- B-32 (C-5) usage-data — clients read "kernel ADR-00NN" but never receive the kernel ADRs; ship them read-only or link them (reviews/C-5 F3 partial) → C-7
- B-33 (C-5) usage-data — sentences removed from AGENTS.md by the terse pass have no trace of where their rule went, beyond the ADR-0019 key-term test (reviews/FWD-033 F4 partial) → C-11
- B-34 (C-5) usage-data — `--gate scrum` accepts `goal: not set` and Goal/Date lines under a `##` section; read the header only, as fde_lib.header_lines does (reviews/FWD-031 F1) → C-8
- B-35 (C-5) usage-data — a client syncing with a sprint still open loses it from every view; fde-sync's migration should carry an open sprint's demands into backlog.md (reviews/FWD-031 F2) → C-7
- B-36 (C-5) usage-data — no test stops sprint instructions from returning in agents/ or other skills; widen the retirement pin to every instruction file (reviews/FWD-031 F3) → C-8
- B-37 (C-5) opinion — the `[scrum]` key, the fde-scrum skill and the gate ids no longer match what they do (backlog goal); rename to backlog (reviews/FWD-031 F4) → C-8
- B-38 (C-5) usage-data — clients keep the old config comment "backlog + sprints" across syncs (headlabs fde.config.toml:196) (reviews/FWD-031 F5) → C-7
- B-39 (C-5) usage-data — a demand can merge without its review; the board's merge line should require the review record (FWD-031 merged unreviewed, caught at promotion) → C-6
- B-40 (C-5) usage-data — the cycle plan template should give a range revert from the last pushed SHA as the rollback of a multi-commit release (reviews/C-5 F4) → C-11
- B-42 usage-data — under Claude Code auto mode, the classifier blocks the sync's permission merge (SETUP §8.4) and the sync stops half way (kernel_version and permissions left undone); fde-sync should say up front that it writes permissions and tell the user to leave auto mode if blocked (owner report, 2026-09-29) → C-7

- B-43 owner request — `/fde-backlog` opens a visual panel with sections/tabs showing everything: overview, backlog, cycles expandable to their demands, specs, reviews, ADRs, board, deploy and promotion, loose demands outside any cycle, and discarded items; actions stay in the conversation (owner, 2026-09-29) → C-12

## Discarded (2026-09-29)

Reviewed against 0.19.0 with the owner; ids stay retired.

- B-4 OTel wiring + guard audit trail — discarded: done — SETUP §8 writes the opt-in OTel block and guard.py appends every decision to .fde/guard-audit.jsonl (FWD-006)
- B-5 Execution provenance in demand artifacts — discarded: done — findings template carries agent_transcript (FWD-007)
- B-7 Split the reference base by kind — discarded: declined at the S-005 review; no growth since that would reopen it
- B-8 Collapse the parallel-copy defence — discarded: done — one mirror manifest, tests/mirror.toml (FWD-020, kernel ADR-0016)
- B-9 Declared cycle scope and a next-cycle list (FWD-021) — discarded: done — superseded by kernel ADR-0019 (backlog > cycle > demand), released in 0.19.0
- B-10 Report the timebox, don't just declare it — discarded: superseded — kernel ADR-0019: a timebox or size overrun is a board fact; reviews are 1 round per demand and budgeted per cycle
- B-18 C-1#18 usage-data — --no-replace-objects for the triage, erosion and I1 git spawn sites — discarded: outside the threat model — hardening against git replace refs belonged to FWD-021's hostile-actor model, abandoned
- B-19 C-2#1 usage-data — SETUP.md does not mention cycles/; a client learns the practice only from AGENTS.md (revie… — discarded: done — SETUP creates and installs cycles/ (FWD-032)
- B-22 C-2#4 usage-data — Voice asks for one status line while ## Cycle asks to show the next-cycle list verbatim; s… — discarded: obsolete — the ## Next cycle list no longer exists
- B-23 C-2#5 usage-data — measure whether the instruction holds: count cycles that close with in-band fixes before c… — discarded: obsolete — framed on the 0.16 next-cycle list and in-band fixes; the cycle model replaced it
- B-24 C-2#6 usage-data — kernel_version still 0.15.0 after ADR-0018 and FWD-022; bump on the next release — done in… — discarded: done — kernel_version moved with every release; now 0.19.0, and sync bumps it
- B-41 (C-5) usage-data — AGENTS.md sits at 1600/1600 words; the next cycle that adds a rule must remove text — discarded: not work — a standing constraint already enforced by TestTerse (AGENTS.md ≤ 1600 words)
