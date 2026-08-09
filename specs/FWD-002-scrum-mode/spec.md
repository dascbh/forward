# FWD-002 — Scrum mode: the cadence layer above the demand loop

Triage: surfaces 0 · public · reversible · ~450 LOC → score 2 → **S**
(spec, implementation, adversarial 1 round).

## Problem

Demands arrive one by one from conversation, and every decision reaches
the user retail — sized, specced, and reviewed in isolation. There is no
value layer above demands (what should we build next, and why), and no
formal loop that turns process friction into kernel change (it happened
all through 0.1.x–0.5.0, but only because the maintainer pasted field
reports by hand).

## Shape (decided in design, ADR-0008)

Scrum's artifact→commitment trio extended from I4's pattern, three
altitudes: backlog → dated product goal · sprint → dated sprint goal ·
increment → the DoD that already exists (invariants + acceptance + gate).
Discovery is a continuous track feeding the backlog with evidence-labeled
candidates (opinion < usage-data < user-test < production). Dropped:
daily and live status (I7 already synchronizes), calendar timeboxes
(sprints close on goal-or-batch), Scrum-Master-as-role (it is the gate).

## Failure modes

- FM-1: mode gates fire on projects that never enabled `[scrum]`.
- FM-2: a sprint opens without a dated goal, or while the previous
  sprint has no recorded retro — the cadence's own I4 pattern broken.
- FM-3: the backlog exists without a dated product goal — items with no
  ruler to order against.

## Requirements (EARS)

- R1: WHEN `[scrum].enabled` is true, the gate MUST fail on: backlog.md
  missing a dated `goal:`; any `sprints/S-*/` without a dated `goal.md`;
  any non-latest sprint without `retro.md`. WHEN scrum is not enabled,
  these checks MUST NOT run (explicitly requesting `--gate scrum`
  reports the mode as off).
- R2: WHEN the mode is used, the `fde-scrum` skill MUST define: passive
  capture, discover push, planning, execution without interruption,
  close triggers (goal-or-batch), review, retro (blocking the next
  sprint), and the unplanned exception route.
- R3: WHEN AGENTS.md is emitted for a project, it MUST carry the
  scrum-mode default shift (idea → backlog item, two sittings, exception
  route) so any agent honors the mode without the skill loaded.
- R4: WHEN this demand closes, the kernel itself MUST be running the
  mode: dated product goal in backlog.md, S-001 open with a dated goal
  containing FWD-002.
