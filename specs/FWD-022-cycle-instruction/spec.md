# FWD-022 — Declared cycle, as instruction

size: S

Triage: surfaces 1 (instruction layer) · public · reversible · ~120 LOC →
score 1 + 1 = 2 → **S** (spec, impl, 1 full adversarial round; timebox 1 h).

Input: backlog item 9, successor of FWD-021 (paused, reverted). This is
the first slice ADR-0018 asks for: the smallest mechanism that solves the
reported problem. The owner reported that a round file declaring its done
criteria before execution visibly kept an agent on task. That file was
text. FWD-021 made it a git-history gate, and five review rounds attacked
the gate as a security boundary. This demand ships the text only.

## Problem

Long agent loops drift into side tasks. The owner asks for three things:

1. every cycle (one request, one or more demands) declares its objective,
   tasks and definition of done **before** execution;
2. anything discovered during execution is **not** acted on in the cycle;
   it goes to a list;
3. that list is presented at the close and is the next cycle's input.

## Requirements

- **R1** — AGENTS.md (and its template) carries a `## Cycle` section:
  before the first behavior change of a request, write and commit
  `cycles/C-<n>.md` with `objective:`, `demands:`, `## Tasks`,
  `## Done when`, `## Next cycle`.
- **R2** — `## Done when` is project-aware: it always lists
  declared-before, tests red-before/green-after, review budget spent with
  no blocker open, and residuals; it lists promotion only for M/L, and
  deploy/publish only when the project deploys or publishes.
- **R3** — during the cycle, a discovery outside `## Tasks` is appended to
  `## Next cycle` and is not fixed in-band (MNT-9). The only in-band
  exception is a defect that blocks a declared task, recorded as such.
- **R4** — at close: every done item is marked `[x]` (met) or `[-]` (not
  met, with the reason); the `## Next cycle` list is shown to the user
  verbatim; with `[scrum]` on, each item enters `backlog.md` with
  evidence `usage-data`.
- **R5** — the declaration is not edited after the first behavior commit
  except to add to `## Next cycle` or to mark done items. A changed scope
  is a new cycle.
- **R6** — no gate, no runtime change. `fde-scrum` and `fde-triage` point
  to the section; nothing else moves.

## Threat model

Contained: an honest agent that drifts into adjacent work, or forgets to
report what it found. Out of scope: an agent or owner deliberately
editing or deleting the cycle file, rewriting git history, or skipping
the section. The instruction assumes cooperation; a gate is a later
demand, only with usage-data that the instruction failed (ADR-0018).

## Boundaries

- Always: declare before code; list, don't fix, discoveries.
- Ask first: widening a cycle's tasks mid-run (it is a new cycle).
- Never: a mechanical check of cycle files in this demand.
