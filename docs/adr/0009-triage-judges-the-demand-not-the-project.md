# ADR-0009 — Triage judges the demand, not the project

date: 2026-08-09
status: accepted

## Context

Triage inherited `sensitive` and `irreversible` wholesale from
`[triage]`, so a personal+difficult project floored every demand at M —
a one-line reversible UI flip paid full ceremony in the field (AGROMETA).
`surfaces` had already moved to per-demand judgment (0.1.3) after the
same class of complaint.

## Options considered

- **Keep project-level inputs** — rejected: the proxies sit at the wrong
  granularity; the framework's own doctrine says ceremony scales with
  the demand, and the field showed the M floor teaching users to resent
  the process.
- **Drop the inputs entirely (surfaces + loc only)** — rejected: a
  demand that DOES touch health data or ship a migration deserves the
  +2s; the signal is right, only the scope was wrong.
- **Per-demand judgment with the project declaration as ceiling/posture,
  strict tiebreaks** — accepted.

## Decision

`sensitive` = this demand touches data of the declared class (public/
internal projects: always false). `irreversible` = this change is hard
to undo (migration, deletion, external side effect), with the declared
reversibility as posture. Unsure → true; torn between sizes → larger.
The rule lives identically in the fde-triage skill and the demand loop
(template + this repo), with suite-enforced parity.

## Consequences

Ceremony inflation ends without relaxing criteria: the tiebreaks keep
the conservative bias, but it now binds to the demand's actual risk.
Data-class ceilings still govern vector A floors and vector B depths —
this changes sizing only.
