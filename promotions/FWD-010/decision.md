---
demand: FWD-010
date: 2026-08-09
decision: promote
---

# Promotion decision — FWD-010 creative divergence + UI reference base

Confronting evidence against `specs/FWD-010-creative-divergence/acceptance.md`.

| criterion | evidence | met |
|---|---|---|
| curated base: systems + patterns, no component code | `spec/references/ui-patterns.toml` — 10 systems, 16 patterns; the no-code guard is itself tested against pasted JSX/CSS/SwiftUI/module syntax | yes |
| fde-design defines diamonds, HMW, five lenses, per-size counts, selection | present, plus the artifact shape and the deterministic selection order (baseline → job → platform → fails_when → recorded trade) | yes |
| catalog USE-10..12 well-formed | present; spec-integrity prefix/uniqueness passes | yes |
| base integrity tested (ids, required fields, resolvable canonical, no code) | `tests/test_references.py` | yes |
| SETUP copies `spec/references/`; install-sync covers it; byte-identical | SETUP step 6 updated; install-sync now discovers `spec/**/*.toml` in both directions | yes |
| suite + `verify --all` green; two rounds; promotion confronts the list | 157 tests, 16 gate lines incl. DIVERGE; `reviews/FWD-010/` 15 findings, 5 blocking, all fixed | yes |
| **enforcement (R1/R2), not instruction** | **added after review**: `runtime/design.py` + DIVERGE gate; the review's fabricated demand (flow + wireframe + dated acceptance, zero divergence) passed clean at 0d082ae and exits 1 now | yes |
| AGENTS parity claim in the acceptance | **corrected by implementation**: AGENTS.md and the template now carry the rule (the claim was unmet as written — F7) | yes |

## Note on the review

The critical finding was self-refutation: a demand whose founding
argument is "instruction does not hold" shipped as instruction — the
skill even claimed the kernel "enforces the second diamond structurally"
while nothing did, and the tests were tautologies that a rewrite to
"alternatives are optional" left green. Fifteen findings, five blocking,
all fixed; the two that matter most (the missing gate, the tautology
suite) are exactly what separates this demand from the thing it argues
against.

That the review could exploit the hole by fabricating a demand — and that
the same fabrication now fails — is the acceptance evidence for R1.

## Decision

**Promote.** All criteria met, two of them only after the review forced
the demand to obey its own thesis. Scope held: no new role, no
dependency, no component code; divergence stays proportional (XS/S
exempt). Recommend closing S-005 after the owner's review + retro
sitting, carrying one process finding: a demand that argues for
enforcement must ship its gate in the same commit as its doctrine.
