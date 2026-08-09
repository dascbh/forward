# ADR-0008 — Scrum mode: a cadence layer, not a methodology

date: 2026-08-09
status: accepted

## Context

Demands reach the user retail — one conversation per decision. The owner
wants a Scrum-inspired mode (discover, plan, sprint, review, retro). Scrum
was built for human coordination; the kernel's own doctrine (roles.toml)
collapses structures that only exist because humans lack shared context.
Each Scrum mechanism must pass that razor before being adopted.

## Options considered

- **Adopt Scrum wholesale (events, roles, timeboxes)** — rejected: daily
  and live status solve human desynchronization (I7 already synchronizes
  by artifact); calendar timeboxes solve human procrastination (agents
  don't wait for Friday; the scarce resource is the user's attention).
- **Reject Scrum entirely** — rejected: three mechanisms survive the
  razor — the artifact→commitment trio (I4's pattern at three
  altitudes), the two inspection sittings (planning, review) that batch
  the user's decisions instead of fragmenting them, and the retrospective
  (the 0.1.x–0.5.0 field loop, formalized).
- **A cadence layer above the demand loop, optional, no new invariants**
  — accepted.

## Decision

`[scrum]` in fde.config.toml enables: `backlog.md` → dated **product
goal** · `sprints/S-N/goal.md` → dated **sprint goal** · increment → the
**DoD that already exists** (invariants + acceptance + verify). Mode
gates (not invariants): no dated goal, no sprint; no retro, no next
sprint. Defaults shift: ideas become evidence-labeled backlog items
(opinion < usage-data < user-test < production), not immediate demands;
"fix it NOW" bypasses the backlog and is recorded as unplanned.

## Provenance ledger

- **Canonical Scrum**: planning/review/retro as inspection moments; the
  artifact→commitment trio; empiricism as the pillar.
- **Dual-track (borrowed, not Scrum)**: continuous discovery feeding the
  backlog; refinement as ongoing activity, never an event.
- **FORWARD-native**: DoD as an exit code; the demand loop underneath
  each backlog item; retro findings allowed to open kernel demands
  (FWD-*); evidence ladder from the absorbed design discipline.
- **Dropped, with reasons**: daily and live status (I7); calendar
  timeboxes (goal-or-batch closure); Scrum Master (the gate); PO as an
  agent role (value decisions are genuinely the user's).

## Consequences

The user's attention is spent in two sittings per sprint instead of one
conversation per demand. Process friction gets a named destination (the
retro) instead of leaking as chat complaints. The kernel runs the mode on
itself from S-001 onward.
