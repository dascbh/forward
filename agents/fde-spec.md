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

### A large objective is several cycles (kernel ADR-0024)

When the objective has more than one goal the owner would see working
on its own, plan one cycle per slice, all in one pass, and stop at one
sign-off for the set:

1. **Seams first.** List the files each slice would touch. A file two
   slices share (migrations and their numbering, a route or handler
   registry, shared vocabulary, a shared module, the infra stack) goes
   to a small **foundation** cycle. Where you can, turn the seam into an
   extension point — a registry each slice adds its own file to — so
   later slices stop sharing it. Reserve migration numbers per slice.
2. **Vertical slices.** One goal each (kernel ADR-0022), disjoint `files`, its
   own criteria, review and deploy, and `depends: C-<foundation>` in the
   header.
3. **Hot files have one owner.** A file every slice must edit is split
   by the foundation, or owned by one slice that the others depend on.
4. Check it: `python3 bin/fde/status.py --waves` shows which cycles run
   together and warns on an overlap. Twelve demands or more in one
   cycle signal a missed split.

Write once, cite everywhere: the vision or the plan holds the text; a
backlog item from it is one line pointing to its section; a demand spec
cites criterion and ADR ids instead of restating them.

A cycle is `cycles/C-<n>/` (next free `n`), from
`.fde/templates/cycle/`: `plan.md`, `deploy.md`, `board.md`, `review.md`
and `promotion.md` (its `## What changes`: three lines at most, each
also a backlog line). `plan.md` carries a `## Threat model`, criteria
and failure modes with ids dated before the first demand commit (I4),
and the demand list; `deploy.md` the deploy plan; `docs/adr/` the
decisions. An ADR is the only home of a decision; plan and specs cite
it by id; a demand never amends it.

- Investigate before asking: the code, its history, the backlog and
  prior cycles answer most questions. Only what they cannot answer goes
  to the owner — at most three questions, all at once, each with its
  options and a recommended answer — before `plan.md` is written; each
  answer is recorded in the plan as a criterion or an assumption.
- A `date:` line; criteria (`A1`, `A2`…) and failure modes (`FM1`…),
  each with an id. A requirement is measurable — "fast" becomes a number
  with a baseline; an unmeasurable one is a finding, not a vibe.
- `## Threat model`: who or what the cycle must contain, and what is out
  of scope. Review blocks only inside it.
- The demand list: id, the layers it touches (`front`/`back`/`infra`,
  one or more), dependencies (a
  contract, a file, a migration — not a sequence), the criteria it meets,
  the ADRs it follows, and the files it will touch (paths or globs, the
  `files` column): `status.py --waves C-<n>` computes from them which
  demands run in parallel. A demand is one goal (kernel ADR-0022): two
  goals that could each merge alone are two demands; a goal over ~300
  production lines (`[lanes] demand_max_loc`) splits here into smaller
  goals, never into layers, and never at review.
- `deploy.md`: steps ordered infra (expand) → back → front → infra
  (contract), each with its verification and rollback; an irreversible
  step is marked and never bundled with a reversible one. Its
  `## Commands` block lists every command the steps run, one per line,
  exactly as the deploy agent will run it (`<placeholder>` for what
  varies): the sign-off turns them into allow rules (kernel ADR-0025).
  A schema change is expand/contract (kernel ADR-0026): this cycle only
  adds what the code it replaces still runs on; drop, rename, type change
  and key swap are a later cycle's contract. Each migration step declares
  `Migration:`, `Checkpoint:`, `Rehearsal:` and `Rollback:`.
  A failed step
  rolls back and the cycle stops; the user is told the outcome, not
  asked beforehand.

Specifying a draft keeps its `## Items`. When the plan is specified,
write `state: planned` in `plan.md` (specified, awaiting sign-off). At
M/L, the adversarial plan review (kernel ADR-0021) runs before the
sign-off: the owner signs the plan that answered its findings. Stop
at the sign-off: the user signs `plan.md` once, and the orchestrating
agent writes `state: running` with the `signed-off:` line and runs
`python3 bin/fde/deployallow.py --write` (kernel ADR-0025).

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

## Unified product entries

fde-build and fde-inspect route into this role; read
`.fde/spec/product-pipeline.md`. Use existing discovery/spec/cycle artifacts
for augmentation, hypotheses, product requirements, domain/data contracts
and pre-UI UX blueprint. Declare UI/UX criteria and separate design-system
adherence before construction. Architecture decisions remain client ADRs;
role scopes, size, sign-off and frozen plans remain authoritative.

## Main stays deployable (kernel ADR-0027)

Each demand row carries a `dark` note: how it stays invisible on main
until its cycle deploys — `flag <name>` (off by default), `unlinked
route`, `expand only` (migration), `no new behavior`. A change to
behavior already live ships with the cycle's last demand or behind the
flag. A joint deploy of several cycles is declared here, at sign-off,
only when the slices make sense only together; otherwise each cycle
deploys on its own when it finishes.
