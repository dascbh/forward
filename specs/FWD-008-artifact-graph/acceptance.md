---
date: 2026-08-09
demand: FWD-008
---

# Acceptance — FWD-008

- `bin/fde/graph.py --demand FWD-005` prints FWD-005's ego-graph (spec,
  acceptance, review, findings, transcript) built from files.
- `bin/fde/graph.py --recurring` ranks principles by severity-weighted
  citation across `reviews/**`; `--central` ranks nodes by weighted
  in-degree; `--path` finds a directed path; `--orphans` is empty on this
  repo.
- `bin/fde/verify.py --gate traceability` green on this repo; removing a
  `spec.md` whose demand has an acceptance turns it red; a cyclic or
  dangling ADR `supersedes:` turns it red.
- `--gate traceability --staged` names the tier conflict (CI-tier gate).
- Malformed artifact → builder degrades, gate reports (no traceback) —
  tested.
- `tests/test_graph.py` covers the builder, weights, every analysis, and
  the gate red/green cases; full suite and `verify --all` green at the
  demand's closing commit.
- Two isolated adversarial rounds recorded in `reviews/FWD-008/`;
  `promotions/FWD-008/decision.md` confronts this list. ADR-0010 records
  the decision and rejected alternatives.
