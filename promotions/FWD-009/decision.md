---
demand: FWD-009
date: 2026-08-09
decision: promote
---

# Promotion decision — FWD-009 anti-erosion

Confronting evidence against `specs/FWD-009-anti-erosion/acceptance.md`.

| criterion | evidence | met |
|---|---|---|
| `erosion.py --report` prints the signals; degrades on no-git/empty/binary | report runs on this repo; `test_empty_repo_never_crashes`, binary-skip in `parse_numstat` | yes |
| pure cores unit-tested without git | `test_erosion.py`: numstat parse, duplication, budget-check, dep count — all fixture-free | yes |
| `[erosion]` gate fails on breach, silent when absent; config gate rejects non-numeric | tested green/red/silent + `EROSION-BUDGET` config violation | yes |
| `--gate erosion --staged` names the tier conflict | inherited FWD-002 mechanism; verified | yes |
| catalogs MNT-11..13 + COST-1..3, `operational_cost` verified_by heuristic; integrity extended to COST | present; `test_spec_integrity` PREFIX map includes COST | yes |
| README manifesto + ADR-0011 + `fde-erosion` skill | present; manifesto cites the four papers | yes |
| suite + `verify --all` green; two adversarial rounds; promotion confronts the list | 130 tests green, 15 gate lines incl. EROSION; `reviews/FWD-009/` 5 findings, 2 blocking, fixed | yes |

## Note on the review

Two blocking findings, both real and both fixed: `max_change_lines` was a
false wall on any repo younger than the window (the root commit dominated
the batch-size metric — precisely FM-2), and the install-drift test
omitted the two newest CI-executed copies. A third, non-blocking, was the
sharpest: the manifesto's "Exhibit A / decay did not happen" over-read
its own metric by excluding the mirrors. The correction — a precise
"partial datapoint," honest that governance does not make decay
impossible — is the directive living its own COST/MNT catalog and the
Voice doctrine. A directive against overclaiming that caught itself
overclaiming is the review pillar working on the demand whose subject is
honest measurement.

## Decision

**Promote.** All acceptance criteria met; the erosion gate is CI-tier and
the kernel gates its own decay within budget. Scope held: stdlib only, no
dependency on the gate's path (I6), thresholds declared not hardcoded.
Recommend closing S-004 after the owner's review + retro sitting.
