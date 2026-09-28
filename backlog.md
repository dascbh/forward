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
| 9 | Declared cycle scope and a next-cycle list (FWD-021) | long agent loops drift into side tasks and burn tokens; declaring each cycle's tasks, objective and definition of done before execution, freezing scope during it (anything discovered goes to a list presented at close, which is the next cycle's input), and gating on a cycle file carrying the definition of done would keep loops on task. The kernel lacks: a DoD below S (acceptance.md starts at S), a scope-freeze rule outside [scrum], a mandatory next-cycle list at close. Owner chose gate enforcement on 2026-09-28 | usage-data (owner-reported: a round file with seven done criteria visibly improved agent behavior) | M |

## Captured from cycle C-1 (FWD-021, paused unpromoted 2026-09-28)

Evidence for every line: usage-data (FWD-021 implementation and five isolated review rounds).

- C-1#1 usage-data — an untracked file under cycles/ (e.g. .DS_Store) is a C2 stray entry and turns the local gate red; ignoring gitignored entries needs a decision
- C-1#2 usage-data — C1/C4 file lists use git diff-tree --name-only without -z, so git-quoted paths (non-ASCII, tab) may miss behavior_paths; I1's changed() shares the limit
- C-1#3 usage-data — gate_scrum crashes when [scrum] is not a table (pre-existing)
- C-1#4 usage-data — spec_size cannot read a Triage line whose bold size wraps to the next line, so FWD-021's own size-agreement check imposes nothing
- C-1#5 usage-data — C2 does not forbid [x]/[-] marks on done items at the moment an open cycle is added; the contract is silent
- C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite (pre-existing)
- C-1#7 usage-data — the unit suite went from 19 s to 44 s; test_cycle alone takes 12 s
- C-1#8 usage-data — a size or form error on an open cycle is reported twice (working tree + adding commit); collapse when the adding commit is in range and the file is unchanged
- C-1#9 usage-data — the explicit report's "behavior commits since added" count uses working-tree behavior_paths, not the parent-config paths the gate uses
- C-1#10 usage-data — the F9 merge check only sees cycle files in the merge's own -c list; a cycle file added on a side branch is judged on its side commit — correct but undocumented
- C-1#11 usage-data — test_cycle cost is dominated by fixture git commits; a shared pre-built history per class with --since slices would cut it further
- C-1#12 usage-data — the explicit report runs one git log per closed cycle to find its closing commit; batch it
- C-1#13 usage-data — every C6 message from an opening commit repeats the same way-out clause per item; emit it once
- C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not keep full-history runs red (touches ADR-0016's pinned run line)
- C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client
- C-1#16 usage-data — support for a project in a git subdirectory (the cycle gate requires the git top level; I1 shares the limit)
- C-1#17 usage-data — _p1_state's name still says P1 although it reads the single parent under linear history (name only)
- C-1#18 usage-data — --no-replace-objects for the triage, erosion and I1 git spawn sites (the cycle gate already passes it)
- C-1#19 usage-data — review-rounds: F47 and F48 remain blocking after round 5; the gate is reverted from main until a new demand closes them
- C-1#20 usage-data — promotion: FWD-021 was not promoted; a successor demand needs its own promotion
- C-1#21 usage-data — specs/FWD-021-cycle-scope/acceptance.md: its criteria are unmet on F47/F48; the successor re-declares or inherits them

## Captured from cycle C-2 (FWD-022, closed 2026-09-28)

Evidence for every line: usage-data (FWD-022 implementation and its isolated review).

- C-2#1 usage-data — SETUP.md does not mention cycles/; a client learns the practice only from AGENTS.md (review note)
- C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note)
- C-2#3 usage-data — the ## Cycle section cites MNT-9 by bare id; a client reading AGENTS.md alone cannot resolve it (review note)
- C-2#4 usage-data — Voice asks for one status line while ## Cycle asks to show the next-cycle list verbatim; state that the list is the exception (review note)
- C-2#5 usage-data — measure whether the instruction holds: count cycles that close with in-band fixes before considering any cycle gate (ADR-0018)
- C-2#6 usage-data — kernel_version still 0.15.0 after ADR-0018 and FWD-022; bump on the next release
