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
SlopCodeBench calls untested. This repository is a partial datapoint,
stated precisely: built by a generative model under its own governance
across nine demands, its organic code (the install mirrors are
byte-identical, test-enforced copies, excluded as expected duplication,
not decay) holds ~1% duplicate-block density and a bounded add/delete
ratio, with tests growing every demand and adversarial review catching
real bugs each one — including, on this very demand, the overreach of an
earlier draft of this paragraph. It is a governed trajectory, measured;
not proof that governance makes decay impossible.

## Amendment — 2026-08-10 (FWD-016): what "the codebase" means

The decision above says what is measured and left *where* implicit. On
the first demand where it mattered — the gate fired at 15.11 — the
implicit answer turned out to be two answers: duplication read tracked
code files with mirrors excluded, churn read every tracked path. The
adversarial round showed the gap decided red versus green, so the
population is now part of the decision rather than a detail of it.

**One population, declared by the project, for every metric.** It is
`[gate] behavior_paths + eval_paths` — the roots already declared for I1
— minus `[erosion] generated_paths`, minus vendor trees. Three rules
follow, each answering a way the first implementation was wrong:

- **The kernel hardcodes no project-specific exclusion.** A carve-out
  worth 12.13 → 11.06 on this repository cannot live in a constant in a
  source file while the threshold it clears is declared in config. It is
  declared, diffable, contestable, and retargetable — a client whose
  generated tree is `gen/` or `.terraform/` says so.
- **A missing declaration widens, never narrows.** No `[gate]` roots
  means everything tracked. Falling back to kernel defaults would take a
  project that declared nothing and measure it over eight roots it does
  not have — a green gate over an accreting repository.
- **A threshold that measured nothing is not a pass.** The gate says
  "not measured" and names the declaration that produced the silence.

Erosion measurement is therefore coupled to `[gate]`: retargeting I1
retargets decay measurement. That coupling is deliberate — decay is
measured where the project said behavior lives — and it is the operative
fact for anyone tuning either one.

The claim in Consequences above about this repository still holds and now
has a stated population: over the declared roots minus the declared
mirrors, ~0.5% duplicate-block density and an add/delete ratio of 11.06
against a budget of 12.0 that has never been raised. Over the declared
roots *including* the mirrors it is 12.13 — over budget. Both numbers are
part of the record; the second is why the exclusion had to become a
declaration instead of a constant.
