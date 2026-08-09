---
demand: FWD-008
date: 2026-08-09
decision: promote
---

# Promotion decision — FWD-008 the artifact graph

Confronting the evidence against `specs/FWD-008-artifact-graph/acceptance.md`.

| criterion | evidence | met |
|---|---|---|
| `graph.py --demand FWD-005` ego-graph | prints spec, acceptance, review, 2 findings, their attributes/principles, transcript, selecting sprint — no siblings | yes |
| `--recurring` / `--central` / `--path` / `--orphans` | recurring surfaces DOM-5, OBS-1 from this repo's own reviews; central ranks functional_correctness top; orphans empty | yes |
| `--gate traceability` green here; red on removed spec / cyclic-dangling supersedes | gate green; `test_graph.py` covers acceptance-without-spec, promotion-without-review, dangling + cyclic supersedes, and the title-first ADR form | yes |
| `--staged` names the tier conflict | inherited from the FWD-002 fix; verified | yes |
| malformed artifact degrades, no traceback | `test_malformed_findings_degrade_not_crash`; config-TOML error path | yes |
| `test_graph.py` covers builder/weights/analysis/gate | 20 cases; full suite 115 green; `verify --all` green | yes |
| two isolated adversarial rounds recorded | `reviews/FWD-008/findings.toml` — 6 findings, 1 blocking, all fixed in a separate commit (I3) | yes |
| ADR-0010 records decision + rejected alternatives | present, with the research verdict | yes |

## Note on the blocking finding

The review caught the one edge that is authored rather than derived (ADR
`supersedes:`) silently not parsing, because the parser assumed a `---`
fence while the repo's ADRs are title-first — and the tests shared that
wrong assumption. This is exactly the failure the demand named (FM-1: the
graph diverging from the artifacts). Fixed and regression-locked against
the real format. It is also evidence the review pillar works on a feature
whose own subject is provenance.

## Decision

**Promote.** All acceptance criteria met; the traceability gate is in the
CI-tier gate and green. Scope held: no dependency, no index, no graph
store entered the kernel (I6 intact). Recommend closing S-003 after the
owner's review + retro sitting.
