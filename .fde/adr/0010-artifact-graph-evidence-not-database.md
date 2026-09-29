# ADR-0010 — The artifact graph is evidence, not a database

date: 2026-08-09
status: accepted

## Context

Interest in graph-based context ("many say it is the evolution of loops
and workflows") prompted a two-sweep research review of the 2025–2026
state of the art. The verdict was decisive and shaped the scope.

- Retrieval indexes (vector, graph-DB, GraphRAG) show near-zero measured
  benefit below ~1000 files, cost LLM-priced indexing, and are
  nondeterministic. Microsoft's own LazyGraphRAG retreated to 0.1% index
  cost at equal quality; Letta showed a plain filesystem beating graph
  memory; Anthropic and Claude Code run no index (files + conventions +
  agentic search). Every measured win concentrates in corpora orders of
  magnitude larger than a specs/reviews tree.
- The "evolution of loops" claim holds only for the model-independent
  part. The convergent architecture is deterministic scaffold at the
  boundaries, model-driven loop inside each node — which the FORWARD
  demand loop already is. The winning pattern is "graph as evidence, not
  graph as program", and its alive-vs-rot law: edges are a by-product of
  execution, and a gate consumes them.

FORWARD is already a typed artifact graph joined by demand-id.

## Options considered

- **Retrieval index / vector store / graph DB / GraphRAG** — rejected:
  breaks I6 (client-runnable, zero-dep), cannot sit in a deterministic
  gate, and the evidence shows ~zero benefit at kernel scale. This is the
  hype path the research explicitly warns against.
- **LLM-extracted knowledge graph** — rejected: nondeterministic, so no
  gate can consume it; it would become a second source of truth that
  rots (GraphRAG's community-rebuild cost is the cautionary tale).
- **Make the latent artifact graph explicit: directed, weighted, derived
  from files, mined in stdlib, consumed by a gate** — accepted.

## Decision

A stdlib graph layer (`runtime/graph.py`) derives a directed weighted
graph from the artifacts on demand — no index, no pre-summarized
community reports (LazyGraphRAG's lesson: the pre-built summary is what
rots and costs most). Nodes and edges come from existing structure joined
by demand-id; the only new authored edge is ADR `supersedes:`. Weights
come from data the kernel already holds (vector-A weights, finding
severity, triage size). A `traceability` gate consumes the graph
(forbidden orphans, cyclic/dangling supersedes) — the alive condition.
Analysis (`--central`, `--recurring`, ego-graph, paths) is the data-mining
surface. Added as a gate, not invariant I9, for now.

## Consequences

The traceability chain becomes an exit code instead of prose. Recurring
weaknesses (a principle cited often at high severity) become minable from
review history. No dependency, no service, no nondeterminism enters the
kernel. If a client ever exceeds the scale where retrieval indexing pays,
that is their optimization to add outside the kernel — never on the gate's
critical path.
