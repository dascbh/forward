---
goal: The kernel develops itself end to end under its own mechanisms — install, demand loop, cadence — and every rule ships field-proven.
date: 2026-08-09
---

# Product backlog

Items ordered by value against the goal. Evidence ladder:
`opinion < usage-data < user-test < production`.

| # | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| 1 | Per-demand `sensitive`/`irreversible` in triage | in sensitive+irreversible projects every demand floors at M, inflating ceremony for changes that touch neither (a one-line UI flip sized M in the field); per-demand judgment with strict tiebreaks would restore proportionality without relaxing criteria | usage-data (AGROMETA, DEM-reforma-prefetch) | M |
| 2 | I1 bluntness on prose-only edits | a comment or doc-only change inside a behavior root trips I1 and demands an eval touch; predicted as self-hosting friction in ADR-0007 — measure it here first, then decide (diff-content inspection vs accepting the over-approximation) | opinion (predicted, not yet felt) | S |
| 3 | Role identity in the hook payload | the guard's role branch only fires where the harness sends an agent identity (finding F3); an upstream feature request or a documented workaround would restore loop-tier scope enforcement | usage-data (F3, reproduced live) | S |
| 4 | OTel wiring + guard audit trail | SETUP optionally writes the Claude Code OTel env block (CLAUDE_CODE_ENABLE_TELEMETRY + OTLP endpoint) into the settings.json it already manages — operational audit out of the box; and the guard emits an allowed/blocked trail (today it blocks with exit 2 and leaves no record, which contradicts the spirit of I5) | opinion | S |
| 5 | Execution provenance in demand artifacts | findings.toml and decision.md record the reviewer's transcript id (agent-<id>) and session, optionally archiving the agent jsonl under reviews/<id>/ — today the forensic trail (full tool calls, probe scripts, outputs) is local and expires with harness retention, severing the link between the durable summary (probed) and the raw execution | opinion | S |

## Status

Items 1–5 selected into S-002 as FWD-003..FWD-007 (planning 2026-08-09);
sizes re-scored at selection with per-demand triage inputs. Items 6–8
below entered at the S-005 review; item 6 was selected into S-006 as
FWD-013.

| # | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| 6 | Verification discipline | five factual errors about external sources shipped in two demands, each caught only by isolated review because the accompanying tests asserted a claim existed rather than that it was true; a catalog principle plus a gate on undated/expired claims would make the failure mode detectable by the suite | usage-data (S-005 reviews, 3 rounds) | M |
| 7 | Split the reference base by kind | 55 entries across 5 node kinds in one 584-line TOML; the FWD-012 review asked whether one file is still the right container (MNT-1/MNT-2). Declined at the S-005 review — revisit if the base keeps growing | opinion | S |
| 8 | Collapse the parallel-copy defence | the graph mining the kernel's own review history ranks MNT-1 at 25.0 severity-weighted, 3x the next principle: source, installed mirror, template and generated surface each get a bespoke drift test. One mechanism could replace the case-by-case detectors | usage-data (graph --recurring) | M |

## Unplanned intake

| # | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| 9 | Declared cycle scope and a next-cycle list (FWD-021) | long agent loops drift into side tasks and burn tokens; declaring each cycle's tasks, objective and definition of done before execution, freezing scope during it (anything discovered goes to a list presented at close, which is the next cycle's input), and gating on a cycle file carrying the definition of done would keep loops on task. The kernel lacks: a DoD below S (acceptance.md starts at S), a scope-freeze rule outside [scrum], a mandatory next-cycle list at close. Owner chose gate enforcement on 2026-09-28 | usage-data (owner-reported: a round file with seven done criteria visibly improved agent behavior) | M — **abandoned 2026-09-28**: FWD-021 (gate) dropped by the owner; the need shipped as instruction in FWD-022 |
| 10 | Report the timebox, don't just declare it | ADR-0018 declares timeboxes but nothing makes the agent say one has run out; FWD-021 ran ~4.5 h on an M (3 h) and the owner learned the per-round cost only after the revert. At each round boundary the status line carries elapsed vs timebox and findings/blockers per round; at the timebox the agent stops and shows the trend before proposing. A choice between instruction and gate is offered with each option's estimated diff and rounds, instruction as default | usage-data (FWD-021 retro) | S |
| 11 | Resync before proposing | a session negotiating FWD-021's finish proposed a plan already obsoleted by ADR-0018/FWD-022, landed on main from a parallel session; before proposing a plan for a paused or long-running demand, fetch and read the log since the last known commit | usage-data (FWD-021 retro) | XS |

## Captured from cycle C-1 (FWD-021, abandoned 2026-09-28)

FWD-021 is abandoned and its code is gone from main; the items that
described the cycle gate itself (C-1#1, #4, #5, #7–#13, #17, #19–#21)
went with it. What remains is pre-existing and independent of that gate.
Evidence for every line: usage-data (FWD-021 implementation and five isolated review rounds).

- C-1#2 usage-data — I1's changed() lists files with git diff-tree --name-only without -z, so git-quoted paths (non-ASCII, tab) may miss behavior_paths
- C-1#3 usage-data — gate_scrum crashes when [scrum] is not a table
- C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite
- C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not keep full-history runs red (touches ADR-0016's pinned run line)
- C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client
- C-1#16 usage-data — support for a project in a git subdirectory (I1 requires the git top level)
- C-1#18 usage-data — --no-replace-objects for the triage, erosion and I1 git spawn sites

## Captured from cycle C-2 (FWD-022, closed 2026-09-28)

Evidence for every line: usage-data (FWD-022 implementation and its isolated review).

- C-2#1 usage-data — SETUP.md does not mention cycles/; a client learns the practice only from AGENTS.md (review note)
- C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note)
- C-2#3 usage-data — the ## Cycle section cites MNT-9 by bare id; a client reading AGENTS.md alone cannot resolve it (review note)
- C-2#4 usage-data — Voice asks for one status line while ## Cycle asks to show the next-cycle list verbatim; state that the list is the exception (review note)
- C-2#5 usage-data — measure whether the instruction holds: count cycles that close with in-band fixes before considering any cycle gate (ADR-0018)
- C-2#6 usage-data — kernel_version still 0.15.0 after ADR-0018 and FWD-022; bump on the next release — done in 0.16.0
- (C-5) usage-data — at XS/S the walkthrough's intended model is compiled by the architecture role, which those sizes do not otherwise plan in (RECON-TEXT note)
- (C-5) usage-data — I5 stays repository-wide (observability.toml); reading the cycle's promotion.md ## Signals is not implemented (reviews/FWD-029 F4, declared limit)
- (C-5) usage-data — I1-REQS reads journey R# tokens only from per-demand acceptance.md; a front demand in the cycle layout (A# criteria in plan.md) is not traced to evals/journeys/ — needs a follow-up in verify.py (FWD-032 note)
- (C-5) usage-data — runtime messages still cite bare kernel ADR ids a client cannot resolve: guard.py LEGACY_NOTE "only for a cycle opened before ADR-0019" (pinned by tests/test_coherence.py); instruction texts now say "kernel ADR-00NN" (RECON-C5-TEXT, reviews/C-5 F3)
- (C-5) usage-data — a cycle review's blocker at budget spent goes to the owner (AGENTS.md, fde-review) while kernel ADR-0019 rules 1/7 say only a replan reaches the user; state that this IS a replan (reviews/C-5 delta F1)
- (C-5) usage-data — the promotion template and fde-promotion say met / not met; status.py also settles `declined` and `limit` — align the template and the agent (reviews/C-5 delta F2)
- (C-5) usage-data — a blocker fixed inside its demand has no closing record: findings.toml keeps `blocking = true`; add a `fixed_in` / status field so "no blocking finding open" has evidence (reviews/C-5 delta F3)
- (C-5) usage-data — clients read "kernel ADR-00NN" but never receive the kernel ADRs; ship them read-only or link them (reviews/C-5 F3 partial)
- (C-5) usage-data — sentences removed from AGENTS.md by the terse pass have no trace of where their rule went, beyond the ADR-0019 key-term test (reviews/FWD-033 F4 partial)
