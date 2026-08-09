# ADR-0006 — The gate retargets, never empties

date: 2026-08-08
status: accepted

## Context

First real install (a monorepo): I1's hardcoded behavior paths (`src/`,
`app/`…) did not cover `backend/app/` and `frontend/src/` — the gate
never fired on the real code. Paths are project topology, which is
parameterizable; but a freely configurable gate is a bypass vector.

## Options considered

- **Grow the hardcoded default list** — rejected: the next layout breaks
  it again; topology cannot be enumerated centrally.
- **Fully free `[gate]` config** — rejected: `behavior_paths = []`
  silently turns I1 off, and invariants have no key.
- **Config with a floor: retarget allowed, emptying rejected** —
  accepted.

## Decision

`[gate] behavior_paths` / `eval_paths` in fde.config.toml, filled by the
installing agent from the layout it actually detected. Empty lists fail
validation (GATE-EMPTY). Defaults remain for single-root repos.

## Consequences

The gate covers real code in any layout; the config diff shows exactly
what the gate watches, auditable like every other declaration. The same
doctrine (parameterize the where, never the whether) applies to future
gates.
