---
date: 2026-08-09
demand: FWD-010
---

# Acceptance — FWD-010

- `spec/references/ui-patterns.toml` exists with: curated design systems
  (each with what it is best at and when to study it) and recurring UI
  patterns (job, platform, canonical systems, fits/fails when, mandatory
  states, accessibility pattern). No component code anywhere in it.
- `fde-design` defines the two-diamond alternation, the HMW reframe, the
  five named lenses with the distinct-lens rule, the per-size alternative
  counts (XS/S none, M 2, L 3), and pattern selection against the base
  plus client extension in `design/patterns.md`.
- Catalog gains USE-10..12, well-formed (prefix maps to
  usability_accessibility, ids unique) and passing spec integrity.
- `tests/test_references.py` verifies base integrity: unique ids, every
  pattern carries job/platform/canonical/fits_when/states/a11y, every
  canonical reference resolves to a declared system, no code blocks; plus
  skill assertions for the lenses and per-size counts, and AGENTS parity.
- SETUP step 6 copies `spec/references/` into `.fde/spec/references/`;
  install-sync covers the copy; `.fde/spec/references/ui-patterns.toml`
  is byte-identical to the source.
- Full suite and `verify --all` green at the demand's closing commit; two
  isolated adversarial rounds in `reviews/FWD-010/`;
  `promotions/FWD-010/decision.md` confronts this list; ADR-0012 records
  the decision and rejected alternatives.
