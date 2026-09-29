---
name: fde-graph
description: Queries the artifact provenance graph (goal, cycle, demand, spec, review, finding, promotion). Use for "what connects to demand X", "what does this cycle cover", "which principles keep recurring", "is the chain intact", onboarding, or traceability.
---

# fde-graph

The artifacts the kernel writes are a typed graph joined by demand-id.
This layer derives it from files on demand, weighted and minable.

```bash
python3 bin/fde/graph.py --demand FWD-005   # ego-graph: all context of a demand
python3 bin/fde/graph.py --render           # one-line-per-demand overview
python3 bin/fde/graph.py --orphans          # forbidden structural gaps (the gate)
python3 bin/fde/graph.py --central          # weighted in-degree: most depended-on
python3 bin/fde/graph.py --recurring        # principles cited most, severity-weighted
python3 bin/fde/graph.py --path A B          # directed path between two nodes
python3 bin/fde/graph.py --format json       # the whole graph, one flat object
```

## The model

Nodes: product-goal, cycle, plan, demand, spec, acceptance, adr, review,
finding, promotion, attribute, principle/probe, transcript (and sprint,
read as history). Directed edges (parents, plans, follows, selects,
specified_by, accepted_by, reviewed_by, contains, against, cites,
promoted_by, supersedes, links). A cycle `plans` a demand when the
demand is a row of `cycles/C-<n>/plan.md`'s `## Demands` table (first
cell only — the depends-on column is not a link) or its spec's header
says `cycle: C-<n>`; a demand `follows` the ADRs its spec's `follows:`
header names. Sprints are retired (kernel ADR-0019): `sprints/` still reads as
`selects` edges, never required. Weights come from data
the kernel already holds: attribute nodes = vector-A weight, finding edges
= severity (critical 4 … low 1), demand nodes = triage size (XS 1 … L 4).

Every edge is derived from existing structure except one authored field:
an ADR's `supersedes:` header line (a space/comma list of ADR numbers,
above the first `##` section).

## Mining

- **`--recurring`**: a principle cited often at high severity across
  reviews is a structural weakness the project keeps hitting.
- **`--central`** ranks what the most findings and links point at; a
  demand or ADR with high weighted in-degree is load-bearing.
- **`--demand X`** is the "give me everything about X" query — its spec,
  acceptance, review, findings, the attributes/principles they cite, the
  transcript, the cycle that planned it and the ADRs it follows — without
  pulling siblings.

## The gate

`--orphans` and `python3 bin/fde/verify.py --gate traceability` share the
same check: forbidden **impossible** states only — acceptance without a
spec, a promotion without a review (per demand, or a cycle's
`promotion.md` over its specified demands), a `supersedes:` that
dangles or cycles. It never flags an
**incomplete** state (a demand mid-loop with a spec but no review yet) —
that is normal, not an orphan.

## Limits

No database, vector store, graph DB or LLM-extracted graph: the graph is
derived from files, walked just-in-time, stdlib, and consumed by a gate
(rationale: kernel ADR-0010).
