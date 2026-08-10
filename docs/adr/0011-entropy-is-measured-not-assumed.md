# ADR-0011 — Entropy is measured, not assumed

date: 2026-08-09
status: accepted

## Context

The thesis to answer: every application built with generative AI is
destined to fail in the long term. Four long-horizon studies give it its
strongest form — coding agents degrade monotonically under iterative
work. SlopCodeBench (arXiv 2603.24755): erosion rises in 80% of
trajectories, verbosity in 89.8%, cyclomatic complexity grows 10×, agent
code is 2.2× more verbose than maintained repos, and — unlike humans,
who stay stable — agent trajectories worsen monotonically. SWE-EVO
(2512.18470), NL2Repo-Bench (2512.12730), and SpecBench (2605.21384)
converge: duplication over consolidation, architectural drift, and reward
hacking (satisfy the requirement, violate the intent).

The decisive finding is negative: prompt interventions fail.
Anti-slop/plan-first prompts cut initial verbosity 33–34.5% but
"degradation resumed at identical rate" at 29–48% higher cost. A
directive expressed as instruction is the exact failure the papers
document.

## Options considered

- **Doctrine only (a "write maintainable code" skill/prompt)** —
  rejected: SlopCodeBench proves prompt-side pressure does not stop
  degradation. Instruction the model can ignore under pressure is theater
  (the I8 rationale, now with a citation).
- **A hardcoded erosion gate with universal thresholds** — rejected:
  erosion tolerances are project-specific; a fixed threshold is a false
  wall on one repo and a rubber stamp on another, and invariants (which
  have no configurable key) therefore cannot express it.
- **A dependency-backed metric suite (jscpd, lizard, SonarQube) on the
  gate's path** — rejected: breaks I6 (client-runnable, zero-dep) and
  couples the gate to per-language tooling.
- **Measured, stdlib, opt-in declared-budget gate + principle catalogs +
  a manifesto** — accepted.

## Decision

Erosion, verbosity, and efficiency become first-class MEASURED concerns.
`runtime/erosion.py` computes, in stdlib, the language-agnostic subset the
papers rely on — diff add/delete ratio, duplicate-block density (the
clone ratio), dependency count, large-change rate — over the git history
and tree. A client declares thresholds in `[erosion]` (versioned, I4
pattern); the `erosion` gate enforces the declared budget and is silent
when undeclared. It is a gate, not an invariant, because the threshold is
necessarily configurable. Deeper metrics (exact cyclomatic complexity,
the SlopCodeBench structural-erosion measure) are delegated to the
client's tools, as I1 delegates the eval framework. The judgment part is
catalog-cited: MNT-11..13 and operational_cost's COST-1..3.

## Consequences

The thesis is answered by construction: the doom is conditional on
governance, and the kernel is the governance. The papers validate the
design — SlopCodeBench's code-state-only protocol is I2 + I7; SpecBench's
"constraints on solution properties, not just acceptance criteria" is
vector A + I8 — and FORWARD is a candidate for the tooling countermeasure
SlopCodeBench calls untested. Exhibit A is this repository: built
entirely by a generative model under its own governance across nine
demands, with tests growing every demand, adversarial review catching
real bugs, and complexity bounded — the monotonic decay the papers
measure did not occur.
