# FWD-003 — Triage inputs are judged per demand

Triage: surfaces 0 · public · reversible · ~250 LOC → score 1, torn → **S**.

## Problem

`sensitive` and `irreversible` are inherited wholesale from `[triage]`,
so in a personal+difficult project every demand starts at +4 and floors
at M — a one-line reversible UI flip paid financial-system ceremony in
the field (AGROMETA, DEM-reforma-prefetch). `surfaces` and `loc` are
already per-demand; the other two inputs are project-level proxies
applied at the wrong granularity.

## Requirements (EARS)

- R1: WHEN a demand is triaged, `sensitive` MUST mean "THIS demand
  touches data of the class declared in `[triage]`" — in a
  public/internal project it is always false; in personal/financial/
  health projects the agent judges the demand's paths; unsure → true.
- R2: WHEN a demand is triaged, `irreversible` MUST mean "THIS change is
  hard to undo once shipped" (migration, deletion, external side
  effect, published artifact) — `[triage].reversibility` sets the
  posture, and unsure → true.
- R3: WHEN the rule ships, the fde-triage skill and the demand-loop
  step 1 (template AND this repo's AGENTS.md, kept identical) MUST carry
  the per-demand wording and the strict tiebreaks, with drift detection
  in the suite.

## Failure modes

- FM-1: skill and AGENTS.md diverge on the rule (the I8-template drift
  class, again).
- FM-2: agents read the new rule as license to skip ceremony — the
  tiebreaks (unsure → true; torn → larger) must survive the rewrite.
