# ADR-0005 — Absorb ideas, not expression; credit only what licensing requires

date: 2026-08-09
status: accepted

## Context

The kernel absorbs practices from external collections (first case:
addyosmani/agent-skills, MIT). Question: does absorption require
attribution?

## Options considered

- **Credit every inspiration in README/NOTICE** — rejected: copyright
  protects expression, not ideas; the practices are industry knowledge
  (the surveyed repo itself compiles OWASP, Google eng, NN/g), and the
  kernel already compresses Nielsen without crediting NN/g. A credit
  ledger of inspirations is noise that implies obligation where none
  exists.
- **Copy strong passages verbatim under MIT notice** — rejected: the
  kernel needs its own voice and ontology; verbatim blocks would carry
  license text and a foreign register.
- **Rewrite everything in kernel voice; provenance in commit messages;
  credit only if expression is ever copied** — accepted.

## Decision

Surveys extract concepts; everything lands rewritten and integrated
(catalog entries, probes, skill sections). Commit messages record the
source of the survey as engineering provenance. A NOTICE entry becomes
mandatory only if actual text is ever incorporated.

## Consequences

Legally clean, honest in history, no implied endorsement either
direction.
