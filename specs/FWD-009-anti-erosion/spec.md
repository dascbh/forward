# FWD-009 — Anti-erosion: entropy is measured, not assumed

Triage: surfaces 1 (runtime) · public · reversible · ~550 LOC → **M**
(spec, impl, adversarial 2 rounds, promotion, ADR-0011).

## Problem

The thesis to answer: *every application built with generative AI is
destined to fail in the long term.* Four long-horizon studies give it
teeth — coding agents degrade **monotonically** under iterative work:
SlopCodeBench (arXiv 2603.24755) measures erosion rising in **80%** of
trajectories and verbosity in **89.8%**, cyclomatic complexity growing
**10×**, agent code **2.2×** more verbose than maintained repos, while
humans stay stable. SWE-EVO, NL2Repo-Bench, and SpecBench converge:
duplication over consolidation, architectural drift, and reward hacking
("satisfy the requirement, violate the intent").

The linchpin finding: **prompt interventions fail.** Anti-slop/plan-first
prompts cut *initial* verbosity 33–34.5% but "degradation resumed at
identical rate" at 29–48% higher cost. So the directive cannot be an
instruction ("write clean code" demonstrably does not hold); it must be
**measured and gated**. The kernel measures per-change correctness (I1)
but nothing measures degradation TREND over time — the exact blind spot
the thesis exploits.

Reflexively, the papers validate the kernel: SlopCodeBench's protocol
(the agent reasons from code state alone, no conversation) is I2 + I7;
SpecBench's "explicit constraints on solution properties, not just
acceptance criteria" is vector A + the I8 catalogs. FORWARD is a
candidate for the architectural/tooling countermeasure SlopCodeBench
calls "untested."

## Failure modes

- FM-1: the directive ships as prose the model can ignore under pressure
  — the very failure the papers document. It must be an enforced,
  declared-budget gate.
- FM-2: the gate imposes universal thresholds. Erosion tolerances are
  project-specific; thresholds must be client-declared and versioned
  (I4 pattern), never hardcoded — and absent a declaration the gate is
  silent, never a false wall.
- FM-3: the measurement needs a dependency (jscpd, lizard) on the gate's
  critical path — breaks I6. The kernel computes only the
  language-agnostic stdlib subset and delegates deeper metrics (exact
  cyclomatic complexity) to the client's tools, like I1 delegates the
  eval framework.
- FM-4: erosion.py crashes on a repo with no git history, binary files,
  or an empty tree instead of degrading.

## Requirements (EARS)

- R1: WHEN `erosion.py --report` runs, it MUST compute, in stdlib over
  the git history and tree: the diff add/delete ratio over a window,
  duplicate-block density (normalized line-window hashing — the clone
  ratio the papers measure), dependency count from manifests, and the
  large-change rate; each degrades gracefully when unavailable (FM-4).
- R2: WHEN `[erosion]` declares budgets (`window`, `max_add_delete_ratio`,
  `max_duplication_pct`, `max_dependencies`, `max_change_lines`), the
  `erosion` gate MUST fail on a declared budget breach and MUST be silent
  when `[erosion]` is absent or a key is undeclared (FM-2). `[erosion]`
  budget values MUST be validated as numbers by the config gate.
- R3: WHEN a finding concerns erosion/verbosity/efficiency, a reviewer
  MUST be able to cite a catalog principle: `maintainability` gains
  MNT-11..13 (reuse over clone; deletion is a feature; AI output is a
  draft that is reviewed and understood or it does not merge), and
  `operational_cost` gains its first catalog COST-1..3.
- R4: WHEN a reader lands on the kernel, the README MUST carry the
  manifesto that answers the thesis with the evidence and the kernel's
  own metrics as Exhibit A; ADR-0011 records the decision and rejected
  alternatives; the `fde-erosion` skill carries the doctrine and how to
  read the signals.
