---
sprint: S-003
date: 2026-08-09
---

# Review — S-003

**Goal**: reached. The artifact graph is explicit, queryable, minable, and
gate-enforced — evidence, not a database.

**Increment**: FWD-008 (M). `runtime/graph.py` derives a directed weighted
graph from the artifacts (demand-id join), with query + mining (`--demand`
ego-graph, `--central`, `--recurring`, `--path`, `--render`, `--format
json`) and a `traceability` gate consuming forbidden orphans. Research
(ADR-0010) refused the retrieval-index / graph-DB path as hype at this
scale and an I6 break. Adversarial round (2): 6 findings, 1 blocking —
the one authored edge (ADR `supersedes:`) silently never parsed because
the parser assumed a `---` fence while the repo's ADRs are title-first,
and the tests shared that wrong assumption. Fixed and regression-locked.
Suite 97 → 115; `verify --all` green (14 gate lines incl. TRACE).

**Owner's backlog decision**: a research question — "is graph the
evolution of loops?" — drove S-003; the follow-on ("every AI app is
doomed long-term") drives S-004, now armed with four long-horizon
degradation papers (SlopCodeBench, SWE-EVO, NL2Repo-Bench, SpecBench).
Backlog is otherwise empty of selectable items.
