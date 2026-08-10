# FWD-015 — Brownfield survey: taking over a system nobody documented

Triage: surfaces 0 · public · reversible · ~500 LOC → score 2, new skill +
gate + tests, torn → **M** (spec, impl, adversarial 2 rounds, promotion).

## Problem

`fde-init` classifies a stack to fill `fde.config.toml` — about fifteen
file-signature facts plus the code and eval roots. That is all it does,
and by design: it is an installer. It never reads architecture, never
reads history, never interprets what the code decided.

So the kernel has nothing for the most forward-deployed situation there
is: **you are embedded into a system that already exists, badly
documented, and what you have is the code and some git history.** Today
the kernel assumes you either start fresh or already understand the
system.

The slot is already there and has been empty for ten demands:
`discovery/` is created at install and is declared as the spec role's
input in `roles.toml` (`inputs = ["discovery/**", ...]`). Nothing has
ever written to it.

## Failure modes

- FM-1 (the dangerous one): the survey reads as authoritative on someone
  else's system while being inference. A confident wrong map is worse
  than no map — it gets acted on. Every claim must be labeled by how it
  was obtained.
- FM-2: the survey becomes a second source of truth that rots — a
  snapshot presented as current long after the code moved.
- FM-3: it duplicates mechanism the kernel already has (history signals
  are `erosion.py`; artifact provenance is `graph.py`) instead of
  composing them.
- FM-4: it demands a comprehension pass so heavy nobody runs it, or so
  shallow it only restates the directory listing.

## Requirements (EARS)

- R1: WHEN the survey runs, it MUST produce `discovery/survey.md` — an
  artifact on disk (I7), never a conversational answer — carrying: how
  the system runs and deploys; the real module boundaries and their
  dependencies; what the git history shows (churn hotspots, frozen
  areas, pace changes, the erosion signals); the seams where coupling is
  real; decisions the code made that no ADR records; a risk register;
  and an explicit list of what remains unknown.
- R2: WHEN any claim is written, it MUST carry its evidence label —
  `[observed]` (read in the code or measured), `[inferred]` (reasoned
  from evidence, could be wrong), `[to confirm]` (a question for whoever
  remains) — and the survey MUST NOT present inference as observation
  (FM-1).
- R3: WHEN the survey needs history or provenance signals, it MUST invoke
  `erosion.py` and `graph.py` rather than reimplementing them (FM-3).
- R4: WHEN the survey is written, it MUST record the commit it surveyed
  and the date, and the `survey` gate MUST fail when the survey exists
  but its recorded commit is not an ancestor of HEAD by more than a
  declared drift (FM-2) — opt-in via `[survey] max_drift_commits`,
  silent when undeclared.
- R5: WHEN a project has no `discovery/survey.md` and its history shows
  it predates the kernel install, the first demand SHOULD pay the survey
  — the same rule as the design foundation. Stated in the demand loop,
  not gated (a greenfield project owes nothing).
