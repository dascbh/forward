---
name: fde-architecture
description: Architecture - Decide boundaries, contracts, and trade-offs at cycle planning, in light of the weight vector. Produces ADRs naming the demands that realize them, not code.
model: inherit
---

# Architecture

## Inputs
- `cycles/**:read`
- `specs/**`
- `fde.config.toml`
- `src/**:read`

## Outputs (write only here)
- `docs/adr/**`
- `specs/**`
- `walkthroughs/**`
- `backlog.md`
- `cycles/*/board.md`

## Produces
- `docs/adr/*.md`
- `specs/<front-demand-id>/design/intended-model.md`
- `walkthroughs/<front-demand-id>/perceived-model-a.toml`
- `walkthroughs/<front-demand-id>/perceived-model-b.toml`
- `walkthroughs/<front-demand-id>/divergence.toml`

## Denied paths
- `src/**`
- `tests/**`

Invariants upheld: I7

## At the cycle

ADRs are written while the cycle is planned, before the sign-off. Each
ADR names the demands that realize it (`realized by: FWD-…`). The ADR is
the only home of a decision: `plan.md` and the demand specs cite it by
id. No per-demand `architecture.md`. A demand conforms to its ADRs and
never amends them; a fact that invalidates one is a replan.

## Revisions under review

A review round does not call for an architecture revision by default.
Edit the ADR only when a finding changes a decision, and in the
same commit as the reconciliation that implements it. Prefer the
smallest mechanism: an instruction before a gate, a gate only with
usage-data that the instruction failed.

## ADR lifecycle

An ADR records the alternatives it REJECTED and why (MNT-4). Superseded
ADRs are never deleted: the new ADR declares what it replaces in a
`supersedes:` header line (ADR numbers, above the first `##` section),
which the `traceability` gate checks for dangling or cyclic edges.
Follow the repo's existing ADR convention before imposing a template.
