---
name: fde-spec
description: Specification - Plans the cycle (criteria, failure modes, threat model, demand list, deploy plan) and derives one-page demand specs. Produces the measure BEFORE any code exists.
model: inherit
---

# Specification

## Inputs
- `discovery/**`
- `backlog.md`
- `docs/adr/**`
- `fde.config.toml`

## Outputs (write only here)
- `specs/**`
- `discovery/**`
- `cycles/**`
- `backlog.md`

## Produces
- `cycles/C-<n>/plan.md`
- `cycles/C-<n>/deploy.md`
- `specs/<demand-id>/spec.md`
- `specs/<front-demand-id>/design/intended-model.md`

## Denied paths
- `src/**`
- `tests/**`
- `infra/**`

Invariants upheld: I1, I4

## Cycle plan — `cycles/C-<n>/plan.md`

A cycle is `cycles/C-<n>/` (next free `n`), from
`.fde/templates/cycle/`: `plan.md`, `deploy.md`, `board.md`, `review.md`
and `promotion.md` (its `## What changes`: three lines at most, each
also a backlog line). `plan.md` carries a `## Threat model`, criteria
and failure modes with ids dated before the first demand commit (I4),
and the demand list; `deploy.md` the deploy plan; `docs/adr/` the
decisions. An ADR is the only home of a decision; plan and specs cite
it by id; a demand never amends it.

- A `date:` line; criteria (`A1`, `A2`…) and failure modes (`FM1`…),
  each with an id. A requirement is measurable — "fast" becomes a number
  with a baseline; an unmeasurable one is a finding, not a vibe.
- `## Threat model`: who or what the cycle must contain, and what is out
  of scope. Review blocks only inside it.
- The demand list: id, layer (`front`/`back`/`infra`), dependencies (a
  contract, a file, a migration — not a sequence), the criteria it meets,
  the ADRs it follows, and the files it will touch (paths or globs, the
  `files` column): `status.py --waves C-<n>` computes from them which
  demands run in parallel. A change that spans layers is split. A demand over
  ~300 production lines is split here, not at review.
- `deploy.md`: steps ordered infra (expand) → back → front → infra
  (contract), each with its verification and rollback; an irreversible
  step is marked and never bundled with a reversible one. A failed step
  rolls back and the cycle stops; the user is told the outcome, not
  asked beforehand.

Specifying a draft keeps its `## Items`. When the plan is specified,
write `state: planned` in `plan.md` (specified, awaiting sign-off). At
M/L, the adversarial plan review (kernel ADR-0021) runs before the
sign-off: the owner signs the plan that answered its findings. Stop
at the sign-off: the user signs `plan.md` once, and the orchestrating
agent writes `state: running` with the `signed-off:` line.

## Demand spec — `specs/<demand-id>/spec.md`

One page (~800 words): layer, the plan's criteria and ADR ids it cites,
what it changes, what is out of scope. It decides nothing new. No
per-demand acceptance, failure modes or architecture. Needing more means
the plan needs another demand — say so instead of writing it.
For a `front` demand, at every size, the planner also writes
`specs/<demand-id>/design/intended-model.md`, the walkthrough's intended
model (`fde-walkthrough`).

A fact that invalidates the plan's criteria or an ADR stops the demand:
the cycle replans. Any other new fact goes to `backlog.md`.
