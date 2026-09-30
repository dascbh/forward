---
goal: The kernel develops itself end to end under its own mechanisms — install, demand loop, cadence — and every rule ships field-proven.
date: 2026-08-09
---

# Product backlog

Items ordered by value against the goal. Evidence ladder:
`opinion < usage-data < user-test < production`.

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|

## Status

Items 1–5 selected into S-002 as FWD-003..FWD-007 (planning 2026-08-09);
sizes re-scored at selection with per-demand triage inputs. Items 6–8
below entered at the S-005 review; item 6 was selected into S-006 as
FWD-013.

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|

## Unplanned intake

| id | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|

## Captured from cycle C-1 (FWD-021, abandoned 2026-09-28)

FWD-021 is abandoned and its code is gone from main; the items that
described the cycle gate itself (C-1#1, #4, #5, #7–#13, #17, #19–#21)
went with it. What remains is pre-existing and independent of that gate.
Evidence for every line: usage-data (FWD-021 implementation and five isolated review rounds).


## Captured from cycle C-2 (FWD-022, closed 2026-09-28)

Evidence for every line: usage-data (FWD-022 implementation and its isolated review).








- B-54 (C-14) usage-data — the CI Range step writes the resolved base only to GITHUB_OUTPUT; echo it so a red run shows the range it diffed (code review FWD-044 F1)

- B-55 (C-14) usage-data — the promotion cell's 40-char cut can split a closing `**` (stray `*`), and inline mode repairs only `**`, not backticks or `_` (code review FWD-042 F1, F2)
- B-56 (C-14) usage-data — FWD-035 (closed C-12, layer `front`, meets A1–A6) is a terminal panel with no evals/journeys/; FWD-041's I1-REQS skips ended cycles, so it stays green, but a running cycle with a terminal-only `front` demand would need a journey manifest for text output — decide whether `front` means a UI surface only (FWD-041 build)

- B-58 (C-14) usage-data — I1-REQS criterion regex accepts FM# ids in a `meets` cell, which would demand a journey for a failure mode (code review FWD-041 F2)
- B-59 (C-14) opinion — erosion excludes a top-level cycles/ even when it holds real code and no [gate] roots are declared; no opt-back-in (code review FWD-041 F3)


- B-61 (C-14) opinion — AGENTS.md cites MNT-10 by bare id ("README and runbook change with how the system runs (MNT-10)"), the same unresolvable reference B-21 fixed for MNT-9 (FWD-043 build)

- B-62 (C-14) usage-data — status.py accepts any non-empty `fixed_in` as closing; no gate checks it names a real commit (code review FWD-038 F3)
- B-63 (C-14) usage-data — a config with both `[backlog]` and `[scrum]` fails BACKLOG-ALIAS at once, with no grace period (code review FWD-039 F2)
- B-64 (C-14) usage-data — the sprint-wording test matches exact phrases only; "mid-sprint" and fde-graph's "sprint" pass, and the allowlist excuses a whole line (code review FWD-039 F3)
- B-65 (C-14) usage-data — at XS/S nothing says who writes the flow/IA/wireframe inputs the planner's intended model needs (code review FWD-043 F2)
- B-66 (C-14) usage-data — "prove a reader against a real client" is text only; no artifact records what was proven where (code review FWD-043 F3)

- B-67 (C-14) usage-data — sync removes any `fde-*` skill the kernel does not ship, including a client's own `fde-<x>` skill; tell before, or keep a list of retired kernel names (code review FWD-040 F1)
- B-68 (C-14) usage-data — the 0.21.0 downgrade test skips silently when commit 5127c29 is absent (shallow CI clone) (code review FWD-040 F2)

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
- B-2 I1 bluntness on prose-only edits — discarded (2026-09-29, review against 0.21.0): predicted in ADR-0007, never felt in any cycle since
- B-3 Role identity in the hook payload — discarded (2026-09-29, review against 0.21.0): depends on the harness sending an agent identity; not actionable in the kernel
- B-6 Verification discipline — discarded (2026-09-29, review against 0.21.0): no recurrence since S-005; revisit only if the reference base grows
- B-17 C-1#16 usage-data — support for a project in a git subdirectory (I1 requires the git top level) — discarded (2026-09-29, review against 0.21.0): no client lives in a git subdirectory
- B-26 (C-5) usage-data — I5 stays repository-wide (observability.toml); reading the cycle's promotion.md ## Signals … — discarded (2026-09-29, review against 0.21.0): declared limit accepted: I5 stays repository-wide
- B-33 (C-5) usage-data — sentences removed from AGENTS.md by the terse pass have no trace of where their rule went, … — discarded (2026-09-29, review against 0.21.0): moot: B-53 moves the rules into skills and re-pins them there
- B-35 (C-5) usage-data — a client syncing with a sprint still open loses it from every view; fde-sync's migration sh… — discarded (2026-09-29, review against 0.21.0): no client runs sprints
- B-43 owner request — `/fde-backlog` shows everything in the terminal, in sections: overview, backlog, cycles with t… — discarded (2026-09-29, review against 0.21.0): done in C-12 (0.20.0)
- B-44 owner direction — review by weight: a coding demand (back, front or infra) inside a signed-off plan gets a cod… — discarded (2026-09-29, review against 0.21.0): done in C-13 (0.21.0)
- B-51 (C-13) usage-data — AGENTS.md is at 1,599 of 1,600 words after FWD-036; almost every sentence is pinned verbat… — discarded (2026-09-29, review against 0.21.0): merged into B-53
- B-52 (C-13) opinion — AGENTS.md step 1 says "Size sets only the planner's depth and the cycle review rounds", while… — discarded (2026-09-29, review against 0.21.0): fixed in the C-13 reconcile (fb453df)
- B-1 Per-demand `sensitive`/`irreversible` in triage — declined in C-14 (plan review F2): the risk rule (kernel ADR-0021) carries sensitivity per demand; the cycle score keeps it so a sensitive cycle keeps its plan review
- B-11 Resync before proposing — discarded: done in C-14 (0.22.0)
- B-12 C-1#2 usage-data — I1's changed() lists files with git diff-tree --name-only without -z, so git-quoted paths (… — discarded: done in C-14 (0.22.0)
- B-13 C-1#3 usage-data — gate_scrum crashes when [scrum] is not a table — discarded: done in C-14 (0.22.0)
- B-14 C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite — discarded: done in C-14 (0.22.0)
- B-15 C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not ke… — discarded: done in C-14 (0.22.0)
- B-16 C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client — discarded: done in C-14 (0.22.0)
- B-20 C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note) — discarded: done in C-14 (0.22.0)
- B-21 C-2#3 usage-data — the ## Cycle section cites MNT-9 by bare id; a client reading AGENTS.md alone cannot resolv… — discarded: done in C-14 (0.22.0)
- B-25 (C-5) usage-data — at XS/S the walkthrough's intended model is compiled by the architecture role, which those … — discarded: done in C-14 (0.22.0)
- B-27 (C-5) usage-data — I1-REQS reads journey R# tokens only from per-demand acceptance.md; a front demand in the c… — discarded: done in C-14 (0.22.0)
- B-28 (C-5) usage-data — runtime messages still cite bare kernel ADR ids a client cannot resolve: guard.py LEGACY_NO… — discarded: done in C-14 (0.22.0)
- B-29 (C-5) usage-data — a cycle review's blocker at budget spent goes to the owner (AGENTS.md, fde-review) while ke… — discarded: done in C-14 (0.22.0)
- B-30 (C-5) usage-data — the promotion template and fde-promotion say met / not met; status.py also settles `decline… — discarded: done in C-14 (0.22.0)
- B-31 (C-5) usage-data — a blocker fixed inside its demand has no closing record: findings.toml keeps `blocking = tr… — discarded: done in C-14 (0.22.0)
- B-32 (C-5) usage-data — clients read "kernel ADR-00NN" but never receive the kernel ADRs; ship them read-only or li… — discarded: done in C-14 (0.22.0)
- B-34 (C-5) usage-data — `--gate scrum` accepts `goal: not set` and Goal/Date lines under a `##` section; read the h… — discarded: done in C-14 (0.22.0)
- B-36 (C-5) usage-data — no test stops sprint instructions from returning in agents/ or other skills; widen the reti… — discarded: done in C-14 (0.22.0)
- B-37 (C-5) opinion — the `[scrum]` key, the fde-scrum skill and the gate ids no longer match what they do (backlog … — discarded: done in C-14 (0.22.0)
- B-38 (C-5) usage-data — clients keep the old config comment "backlog + sprints" across syncs (headlabs fde.config.t… — discarded: done in C-14 (0.22.0)
- B-39 (C-5) usage-data — a demand can merge without its review; the board's merge line should require the review rec… — discarded: done in C-14 (0.22.0)
- B-40 (C-5) usage-data — the cycle plan template should give a range revert from the last pushed SHA as the rollback… — discarded: done in C-14 (0.22.0)
- B-42 usage-data — under Claude Code auto mode, the classifier blocks the sync's permission merge (SETUP §8.4) and t… — discarded: done in C-14 (0.22.0)
- B-45 (C-12) usage-data — `--demand` parses findings.toml twice (code review FWD-034 F3) — discarded: done in C-14 (0.22.0)
- B-46 (C-12) usage-data — nested `d and d[...]` expressions in status.py's panel helpers are hard to read (code revi… — discarded: done in C-14 (0.22.0)
- B-47 (C-12) usage-data — the panel's promotion cell shows a bold decision as `\**promovido**` (the leading `*` esca… — discarded: done in C-14 (0.22.0)
- B-48 (C-12) usage-data — prove a reader against a real client (headlabs) before the cycle review, not only against … — discarded: done in C-14 (0.22.0)
- B-49 (C-12) usage-data — commit the demand reviews before the cycle review starts, so the cycle reviewer sees them … — discarded: done in C-14 (0.22.0)
- B-50 (C-13) usage-data — the I2 gate reads only files named `findings.toml` (`gate_adversarial`, `rglob("findings.t… — discarded: done in C-14 (0.22.0)
- B-53 owner decision — AGENTS.md keeps only the loop's skeleton and a pointer per step; detailed rules (sizing table… — discarded: done in C-14 (0.22.0)
- B-60 (C-14) usage-data — AGENTS.md no longer names fde-survey ("undocumented system: survey first") or fde-design; … — discarded: done in C-14 (cycle review F4, efb1839)
- B-57 (C-14) opinion — status.py parses the spec header `key: value · …` fields on its own (line ~644) while fde_lib.spec_fields now does the same for verify.py; one definition would do (MNT-11; FWD-041 build, status.py claimed by FWD-042) — discarded: done — status.py uses fde_lib's spec, table and id parsers (owner direction 2026-09-30, erosion budget)
