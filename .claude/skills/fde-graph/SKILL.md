---
name: fde-graph
description: Query and mine FORWARD's artifact provenance graph — the demand loop's own output seen as a directed, weighted graph (goal → sprint → demand → spec → review → finding → promotion, joined by demand-id). Use to answer "what connects to demand X", "what does this sprint cover", "which principles do our reviews keep citing", "is the artifact chain intact"; when onboarding to a repo under the kernel; or when asked about graph-based context, knowledge graphs, or traceability.
---

# fde-graph

The artifacts the kernel already writes ARE a typed graph — the demand-id
in every path is the join key. This layer makes it explicit, weighted, and
minable, deriving it from files on demand. No database, no index (see
Doctrine).

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

Nodes: product-goal, sprint, demand, spec, acceptance, adr, review,
finding, promotion, attribute, principle/probe, transcript. Directed
edges (parents, selects, specified_by, accepted_by, reviewed_by, contains,
against, cites, promoted_by, supersedes, links). Weights come from data
the kernel already holds: attribute nodes = vector-A weight, finding edges
= severity (critical 4 … low 1), demand nodes = triage size (XS 1 … L 4).

Every edge is derived from existing structure except one authored field:
an ADR's `supersedes:` front-matter (a space/comma list of ADR numbers).
A demand may also declare `references:` ADRs. Nothing else is authored —
the graph cannot drift from the artifacts because it IS the artifacts.

## Mining

- **`--recurring`** is the signal that pays: a principle cited often at
  high severity across reviews is a structural weakness the project keeps
  hitting. On this kernel it surfaced DOM-5 and OBS-1 as its own most-cited
  principles — history telling you where to harden.
- **`--central`** ranks what the most findings and links point at; a
  demand or ADR with high weighted in-degree is load-bearing.
- **`--demand X`** is the "give me everything about X" query — its spec,
  acceptance, review, findings, the attributes/principles they cite, the
  transcript, and the sprint that selected it — without pulling siblings.

## The gate

`--orphans` and `python3 bin/fde/verify.py --gate traceability` share the
same check: forbidden **impossible** states only — acceptance without a
spec, a promotion without a review, (scrum on) a review for a demand no
sprint planned, a `supersedes:` that dangles or cycles. It never flags an
**incomplete** state (a demand mid-loop with a spec but no review yet) —
that is normal, not an orphan.

## Doctrine — graph as evidence, not graph as program (ADR-0010)

The research is explicit (2025–2026): retrieval indexes, vector stores,
graph databases, GraphRAG, and LLM-extracted graphs buy ~nothing below
~1000 files, cost LLM-priced indexing, and are nondeterministic — so no
gate can consume them, and they break I6 (client-runnable, zero-dep).
Anthropic and Claude Code run no index: files + conventions + agentic
search. Do NOT add any of that. This graph is derived from files, walked
just-in-time, consumed by a gate, and written in stdlib — the only version
the evidence supports. If a client ever exceeds the scale where indexing
pays, that is their optimization, outside the kernel and off the gate's
critical path.
