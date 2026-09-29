# ADR-0003 — Heuristics is the third pillar (I8)

date: 2026-08-09
status: accepted

## Context

Empirical review verdicts by execution; adversarial review by
demonstrated failure. Neither reaches qualities that can be bad while
everything passes — usability, information architecture, craft. The
kernel already smuggled judgment inside adversarial probes without
admitting it.

## Options considered

- **Keep heuristic review advisory** — rejected: advisory dies under
  pressure, exactly like observability before its floor.
- **A sixth reviewer role for judgment** — rejected by the kernel's own
  rule: same model, same context, same access = the same role in a
  different hat.
- **I8 + verified_by + principle catalogs, second pass on the isolated
  reviewer** — accepted.

## Decision

Every attribute declares `verified_by` (empirical | adversarial |
heuristic, by primacy). Heuristic-verified attributes carry versioned
`heuristic_principles`. The isolated reviewer runs two passes: probe,
then judge. Every finding cites the probe that broke it or the principle
it violates — judgment without a named principle is not a finding, and
the gate (`finding-discipline`) rejects it.

## Consequences

Heuristic review is auditable and contestable instead of licensed
opinion. Catalogs are part of the spec, so they sync into client repos
and become the shared language of findings.
