# ADR-0004 — Absorb prancheta, discontinue it

date: 2026-08-09
status: accepted

## Context

The owner maintained two frameworks: FORWARD (delivery kernel) and
prancheta (13 design/product skills, ~1500 lines, pt-BR). Decision:
FORWARD is THE framework.

## Options considered

- **Keep both, integrate via vector B depth** — rejected: two sources of
  truth, two languages, two install stories.
- **Port the 13 skills wholesale into the kernel** — rejected: bloats a
  deliberately thin kernel with method the model already carries; the
  kernel demands artifacts, it does not teach method.
- **Absorb into existing sockets: one skill + catalogs + artifacts** —
  accepted.

## Decision

brief → spec-role discipline for UI demands; flow/IA/wireframe →
architecture artifacts in `specs/<id>/design/` (approved wireframe =
build contract); construir → implementation build rules; the four audit
skills → I8 catalog growth (DOM, USE, MNT); design-qa → Playwright
baselines + axe in eval_paths (the frontend eval suite I1 demands);
criticar → promotion verdict discipline; teste → validation doctrine
(synthetic users are never evidence); produto/design.md →
design/product.md + design/foundation.md, with missing foundation as
uncovered-root debt. All of it as ONE skill, fde-design, proportional to
triage size.

## Consequences

Accepted losses, named: elicitation protocols, event-storming detail,
session-facilitation craft, criticar's execution discipline — survive
only as one-line seeds. Existing prancheta configs migrate to design/.
