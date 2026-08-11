# FWD-016 — Erosion measures churn where the project said behavior lives

Triage: surfaces 0 · public · reversible · ~150 LOC → score 1 → **XS**
(implementation + adversarial 1 round).

## Problem

The erosion gate fired on the kernel: add/delete ratio 15.11 against a
declared budget of 12.0. Investigating produced two candidate readings,
and the honest work was distinguishing them rather than picking the
convenient one.

**The hypothesis that was wrong.** I proposed that the audit trail
inflated the ratio — 3,409 lines of findings, specs, sprints and
promotions added over the window against 7 lines ever deleted — and that
scoping to code files would correct it. Scoping to code files made the
ratio **worse**, 15.11 → 16.15, because `.md` and `.toml` were already
in `CODE_SUFFIXES`: the artifacts had never been excluded. What the
exclusion removed was the generated mirrors (`bin/fde/`, `.fde/`,
`.claude/`), which are deletion-heavy because every sync overwrites them.
The change removed the denominator, not the numerator.

**What the data actually says.** The erosion signal is real. The kernel
is growing by accretion, and the parallel-copy debt (backlog item 8) is
part of why.

**The defect that is still a defect.** The two metrics disagree about
what they measure: duplication counts tracked code files with mirrors and
vendor excluded; churn counted every tracked path. One tool, two
definitions of "the codebase".

## The number the first attempt did not publish

The adversarial round recomputed the ratio under thirteen scopes and
found the one comparison that tests this demand's central claim, which
the first implementation's record did not contain. Measured over the same
50-commit window at `33d55da`, the red baseline:

| scope | ratio |
|---|---|
| everything tracked | 15.11 |
| code files, mirrors excluded (the wrong hypothesis) | 16.15 |
| **declared roots exactly as declared** | **12.14** |
| declared roots minus the mirrors (first attempt shipped this) | 10.77 |
| everything minus the audit trail alone | 11.75 |
| mirrors alone | 14.60 |
| audit trail alone | 430.50 |

**The first clause does not clear the budget on its own.** "Measure decay
where the project said behavior lives" gives 12.14 against a budget of
12.0 — still red. What cleared it was the second clause, excluding the
mirrors, which at the time was a hardcoded constant that un-declared
three roots `fde.config.toml` explicitly declares as `behavior_paths`.
The narrative led with the clause that does not do the work.

Two things follow, and both are recorded rather than argued away:

- The chosen scope is not a lone outlier tuned to clear 12.0. Every
  plausible scope containing the audit trail breaches (15.11, 15.36,
  15.39, 16.15); every scope excluding it passes (10.77, 10.31, 11.09,
  11.75). It sits inside a coherent passing family. That is the change's
  real defence, and it rests on the classification of the audit trail.
- A carve-out that decides red-versus-green cannot be a constant in a
  source file. It is now **declared** in `[erosion] generated_paths`,
  visible in the config diff, contestable, and retargetable by the
  project it measures. Without that line this repository reads 12.13 —
  over budget — and 75.9% duplication; with it, 11.06 and 0.5%. Both
  numbers are in the config comment, next to the line that produces
  them.

## Failure modes

- FM-1: the scope is chosen because it makes the number pass. The
  correction must be defensible with the gate green, and its adversarial
  round is prompted to judge exactly that.
- FM-2: a project is silently narrowed — a repo that declares no roots
  must keep being measured whole, not quietly reduced to nothing.
- FM-3: the scope becomes a third definition to maintain alongside the
  gate's and the duplication scan's.
- FM-4: the gate claims a green over a population it never measured — a
  stale root, a typo, or a window that touched nothing in scope.

## Requirements (EARS)

- R1: WHEN churn is measured, it MUST use the roots the project already
  declared in `[gate] behavior_paths` + `eval_paths` — the same set I1
  watches — minus paths the project itself declared generated in
  `[erosion] generated_paths`, and MUST NOT introduce a scope defined
  only for this metric (FM-3). The kernel MUST NOT hardcode any
  project-specific exclusion; the only hardcoded exclusion is vendor
  trees, which are code the project did not write.
- R2: WHEN a project declares no `[gate]` roots, churn MUST be measured
  over everything tracked (FM-2). A declaration the parser cannot read as
  a list of paths — a bare string, a number — counts as no declaration,
  never as a scope that matches nothing.
- R3: WHEN the report prints, it MUST state the population it measured:
  the roots included, the paths excluded as generated, the count of
  tracked code files left out, and any declared root matching no tracked
  file — so a reader sees what was left out instead of trusting the
  number.
- R4: The `[erosion]` budget MUST NOT be raised as part of this change.
  If the corrected ratio still breaches, the answer is consolidation.
- R5: WHEN a declared threshold has nothing to measure, the gate MUST say
  so and MUST NOT report it as within budget (FM-4). It does not fail: a
  stale root and a greenfield root are indistinguishable from outside,
  and `[gate]` is written at install time while `[erosion]` is opt-in.
- R6: The duplication scan and the churn metrics MUST read the same
  population — the acceptance criterion's "one definition of the
  codebase, used by every metric".

## Path handling

`git log --numstat` does not emit a plain path in every row. Two forms
escaped both the scope and the exclusions in the first implementation,
and both are now resolved before the row is classified:

- quoted paths — `"src/caf\303\251.py"` — git quotes anything with
  non-ASCII or special bytes (`core.quotePath` defaults to true);
- renames — `old.py => new.py` and `pre/{old => new}/f.py` — resolved to
  the path as it stands after the commit.
