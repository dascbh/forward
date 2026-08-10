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

## Failure modes

- FM-1: the scope is chosen because it makes the number pass. The
  correction must be defensible with the gate green, and its adversarial
  round is prompted to judge exactly that.
- FM-2: a project is silently narrowed — a repo that declares no roots
  must keep being measured whole, not quietly reduced to nothing.
- FM-3: the scope becomes a third definition to maintain alongside the
  gate's and the duplication scan's.

## Requirements (EARS)

- R1: WHEN churn is measured, it MUST use the roots the project already
  declared in `[gate] behavior_paths` + `eval_paths` — the same set I1
  watches — minus the generated mirrors, and MUST NOT introduce a scope
  defined only for this metric (FM-3).
- R2: WHEN a project declares no `[gate]` roots, churn MUST be measured
  over everything tracked (FM-2).
- R3: WHEN the report prints, it MUST state the scope it measured, so a
  reader sees what was left out instead of trusting the number.
- R4: The `[erosion]` budget MUST NOT be raised as part of this change.
  If the corrected ratio still breaches, the answer is consolidation.
