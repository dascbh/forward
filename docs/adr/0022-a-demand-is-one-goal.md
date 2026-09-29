# ADR-0022 — A demand is one goal; the layer marks files, not demands

date: 2026-09-29
status: accepted (owner, direct, 2026-09-29)
amends: ADR-0019 rule 5, its split clause ("A change that spans layers
is always split at planning, however small")

## Context

ADR-0019 rule 5 gave every demand exactly one layer and split any change
that spans layers, with no size exception. In use, a user-facing change
becomes two or three demands with dependencies between them: an API
field and its screen label are a `back` demand, a `front` demand and a
`depends on`. Each demand pays its own spec, review, board lines and
merge. On 2026-09-29 the process-only share of commits was 76% in
headlabs-platform, 38% in auris and 56% in this repository.

Two independent frameworks studied the same day slice work the other way:
- spec-kit: one independently testable user story per slice;
- BMAD-method (`bmad-build`, SCOPE STANDARD): one user-facing goal per
  plan, "even if it spans multiple layers/files"; limits are proposals,
  not gates.

The deploy order never needed one layer per demand. Deploy runs per cycle
(ADR-0019 rule 4), and `deploy.md` orders its steps by layer whatever the
demands are.

## Decision

1. **A demand is one goal**: one change the owner or a user would
   recognise, shippable and testable on its own. It may touch several
   layers. Two goals that could each merge without the other are two
   demands.
2. **The layer marks files.** The plan's `layer` cell lists every layer
   the demand touches (`back, front`). Layers still decide what is
   verified: the demand runs the check of each layer it touches, and the
   cycle adds each touched layer's cycle check (ADR-0019 rule 5 table,
   unchanged). A `front` in the cell makes the demand a `front` demand
   for the walkthrough.
3. **Size stays the ceiling**: about 300 production lines per demand,
   split at planning. A goal over the ceiling splits into smaller goals,
   never into layers.
4. **Deploy is unchanged**: `deploy.md` runs infra-expand → back → front
   → infra-contract per cycle; a multi-layer demand contributes to each
   step its files belong to.

## Consequences

- Fewer demands per cycle and fewer `depends on` edges; the waves
  (`status.py --waves`) come from files, not layers.
- A code review of a multi-layer demand runs more than one layer's check;
  still one round.
- Readers that took the layer cell as a single value must read a list
  (fde_lib's front detection).

## Rejected

- **Keep one layer per demand.** It is the source of the demand count
  and dependency edges the owner asked to cut.
- **Drop layers altogether.** They still decide the checks, the
  walkthrough and the deploy step.
