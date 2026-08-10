---
date: 2026-08-09
demand: FWD-009
---

# Acceptance — FWD-009

- `bin/fde/erosion.py --report` prints add/delete ratio, duplicate-block
  density, dependency count, and large-change rate for this repo;
  degrades (no crash) on no-git / empty / binary-only inputs — tested.
- Pure cores are unit-tested independently of git: numstat parsing,
  duplicate-block density on given file contents, budget-check math.
- `[erosion]` budget: `bin/fde/verify.py --gate erosion` fails on a
  declared breach, is silent when `[erosion]` is absent, and the config
  gate rejects a non-numeric budget value — all tested.
- `--gate erosion --staged` names the tier conflict.
- Catalogs: MNT-11..13 and COST-1..3 present, each a catalog-id-prefixed
  one-liner; `operational_cost` declares `verified_by = heuristic`;
  test_spec_integrity's prefix/uniqueness checks extend to COST-*.
- README manifesto section answering the thesis, citing the four papers
  and the kernel's own metrics; ADR-0011; `fde-erosion` skill installed.
- Full suite and `verify --all` green at the demand's closing commit;
  two isolated adversarial rounds in `reviews/FWD-009/`;
  `promotions/FWD-009/decision.md` confronts this list.
