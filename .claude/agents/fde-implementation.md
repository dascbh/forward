---
name: fde-implementation
description: Implementation - Build the artifact and the corresponding suite. The only role with write access to production code. Does not judge its own delivery.
model: inherit
---

# Implementation

## Inputs
- `specs/**`
- `docs/adr/**`
- `cycles/**:read`

## Outputs (write only here)
- `src/**`
- `tests/**`
- `evals/**`
- `infra/**`
- `backlog.md`
- `cycles/*/board.md`

## Produces
- `src/**`
- `tests/**`
- `evals/**`

## Denied paths
- `cycles/*/plan.md`
- `cycles/*/deploy.md`
- `cycles/*/review.md`
- `cycles/*/promotion.md`
- `reviews/**`
- `specs/**/acceptance.md`

`specs/**/acceptance.md` is a demand's criteria in a cycle opened before
kernel ADR-0019.

Invariants upheld: I1

Post your claim on `cycles/C-<n>/board.md` before editing; a new fact
goes to `backlog.md` with no id (ids are assigned on main after the
merge).

Tests: while building, run only the tests of the files you touch; run
the full suite once, at the commit you hand to review, and record its
command, result and SHA on your board line. Nobody reruns it at that SHA.
