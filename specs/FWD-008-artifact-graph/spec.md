# FWD-008 — The artifact graph: provenance as a directed, weighted graph

Triage: surfaces 1 (runtime) · public · reversible · ~600 LOC → score 3,
new subsystem + new gate, torn → **M** (spec, impl, adversarial 2 rounds,
promotion, ADR-0010).

## Problem

The kernel asserts a traceability chain in prose (AGENTS.md: "product
goal → sprint goal → demand → acceptance → eval") that nothing checks end
to end. DOM-5 is an orphan-sweep principle with no gate; `gate_adversarial`
already does a promotions→reviews join by hand (runtime/verify.py); FWD-007
added `agent_transcript` as the first explicit edge with nothing consuming
it. Research (ADR-0010): the value of "graph context" that survives on
frontier models is *graph as evidence* — provenance made queryable and
gate-enforced — not a retrieval index (near-zero benefit at this scale,
breaks I6 and determinism).

## Failure modes

- FM-1: the graph becomes a second source of truth — a hand-maintained
  file that drifts from the artifacts. (Mitigation: derived-only, never
  authored except the one `supersedes:` edge; regenerable.)
- FM-2: the gate blocks legitimate in-progress states (a demand mid-loop
  with a spec but no review yet). The gate must forbid only *impossible*
  states (acceptance without spec, review/promotion without their
  upstream, dangling supersedes), never *incomplete* ones.
- FM-3: analysis miscounts weights (severity/size/attribute) and mis-ranks
  central/recurring, producing misleading mining output.
- FM-4: builder crashes or misparses on a malformed artifact instead of
  degrading.

## Requirements (EARS)

- R1: WHEN `graph.py` runs, it MUST build a directed graph from the
  artifact tree using the demand-id as join key, deriving every edge from
  existing structure except ADR `supersedes:` (a declared front-matter
  field), and assign weights: attribute nodes = vector-A weight, finding
  edges = severity (critical 4/high 3/medium 2/low 1), demand nodes =
  triage size (XS 1..L 4).
- R2: WHEN asked, it MUST answer: `--demand <id>` (ego-graph),
  `--orphans`, `--central` (weighted in-degree), `--recurring`
  (severity-weighted principle citations), `--path <a> <b>`, `--render`,
  `--format json`.
- R3: WHEN `--gate traceability` runs, it MUST fail on forbidden orphans
  (acceptance without spec; review-id or promotion-id without its
  upstream; scrum-selected demand without a spec dir) and on a
  `supersedes:` edge that cycles or points at a missing ADR — and MUST
  NOT fail on a demand legitimately mid-loop. WHEN `[scrum]` is off,
  goal/sprint edges are not checked.
- R4: WHEN any artifact is malformed, the builder MUST degrade (skip the
  node, never crash), and the gate MUST report, never traceback.
