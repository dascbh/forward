# FWD-010 — Creative divergence and the curated UI reference base

Triage: surfaces 0 · public · reversible · ~600 LOC (spec catalog + skill
+ tests) → score 2, new spec surface + reference base, torn → **M**
(spec, impl, adversarial 2 rounds, promotion, ADR-0012).

## Problem

Two gaps, exposed by confronting an external design-architecture proposal
against the kernel:

1. **No divergence.** `fde-design` goes from information architecture
   straight to ONE wireframe. The Double Diamond's second diamond —
   explore alternatives, then converge — does not exist. This matters
   more with an agent than with a human: generating three alternatives is
   cheap, and choosing between declared alternatives is auditable;
   taking the first output is not. It is the vector-A argument one level
   up ("if everything can be high, nobody chose anything").
2. **No pattern-selection discipline.** The kernel enforces kit reuse
   (MNT-5) but says nothing about WHICH interaction pattern to choose,
   why, or what the platform's users already expect. Novelty enters by
   default, not by decision.

The constraint that shapes the solution: the erosion research (ADR-0011)
proved that instructing a model toward quality does not hold under
pressure — anti-slop prompts cut initial verbosity but degradation
resumed at the identical rate. The same applies to creativity: "be
creative" or "explore alternatives" is the failure mode, not the fix.
Divergence must be **structural** — checkable requirements on the
artifact — and pattern choice must stand on a **declared base**.

## Failure modes

- FM-1: the alternatives are cosmetic variants of one idea (three
  layouts of the same flow), satisfying the letter of divergence while
  producing no real choice.
- FM-2: the reference base becomes a bundled component library — copied
  code that rots, bloats, and drags licenses (MNT-11, MNT-12), or an
  encyclopedia nobody curates.
- FM-3: the base goes stale or contradicts the client's own foundation,
  becoming a second source of truth.
- FM-4: the divergence step is applied to demands too small to earn it,
  reintroducing the ceremony inflation FWD-003 removed.

## Requirements (EARS)

- R1: WHEN a demand with a UI surface reaches the solution space, the
  `fde-design` chain MUST require, proportional to triage size (M: 2
  alternatives, L: 3; XS/S: none), alternatives generated from DISTINCT
  named lenses — subtract, invert, analogous, constraint-first,
  object-first — where alternatives sharing a lens count as one (FM-1,
  FM-4), each carrying a one-line hypothesis, and the convergence
  recording what each discarded alternative traded.
- R2: WHEN the problem enters the solution space, it MUST first be
  reframed ("How Might We") in at least two ways with the chosen framing
  named — the generative move of Design Thinking is the reframe, not the
  render.
- R3: WHEN a UI pattern is chosen, it MUST be selected against
  `spec/references/ui-patterns.toml`: the job it serves, the platform
  convention it respects, the canonical systems where it is well solved,
  and the states it must resolve — novelty is a declared cost, not a
  default.
- R4: The reference base MUST carry decision criteria and canonical
  source pointers ONLY — never component code (FM-2) — MUST be extensible
  by the client in `design/patterns.md` without editing the kernel's copy
  (FM-3), and MUST earn entries by recurrence, not completeness.
- R5: WHEN a review judges a design decision, it MUST be able to cite
  USE-10..12 (divergence before convergence with discards recorded;
  pattern chosen for job and platform convention from the base; the
  problem reframed before it is solved).
