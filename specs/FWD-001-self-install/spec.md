# FWD-001 — Self-install: FORWARD runs under FORWARD

Triage: surfaces 0 · public · reversible · ~600 LOC → score 2 → **S**
(spec, implementation, adversarial 1 round).

## Problem

The kernel enforces eval-precede-merge and declared acceptance on every
client while its own repository has neither. Release testing is redone by
hand in a scratchpad and discarded; spec/template/version drift ships
silently (field-reported: the AGENTS.md template lacked I8).

## Failure modes this demand must cover

- FM-1: a change to `runtime/*.py` regresses gate/guard behavior with no
  failing test (I1 uncovered root).
- FM-2: spec and derived surfaces drift apart — catalog IDs, role/skill
  cross-references, template placeholders, `kernel_version` vs
  `plugin.json` vs config template.
- FM-3: the gate is not exercised on the kernel's own CI, so violations
  land on main unseen.

## Requirements (EARS)

- R1: WHEN any behavior path changes (`runtime/`, `spec/`, `skills/`,
  `agents/`, `templates/`, `SETUP.md`), the pre-commit and CI MUST demand
  a corresponding eval entry (I1).
- R2: WHEN the suite runs, it MUST fail on: budget ≠ 100, floor
  violations, empty gate lists, unparseable findings, findings citing
  neither probe nor principle, version desync, and broken
  role/skill/catalog cross-references.
- R3: WHEN a commit lands on main, CI MUST run the suite and
  `verify --all`.
