---
sprint: S-002
date: 2026-08-09
---

# Review — S-002

**Goal**: reached. Ceremony now judges the demand, and every enforcement
decision leaves a trail.

**Increment**: five demands shipped through the loop.
- FWD-003: triage's `sensitive`/`irreversible` are per-demand judgments
  (data class as ceiling, reversibility as posture, strict tiebreaks) —
  ends project-level ceremony inflation (ADR-0009).
- FWD-004: I1's file-level bluntness decided and recorded, not softened.
- FWD-005: the guard derives role identity from harness metadata when the
  payload lacks it — loop-tier scope enforcement fires for real
  subagents again.
- FWD-006: guard writes an audit trail (`.fde/guard-audit.jsonl`);
  optional OTel wiring documented, off by default.
- FWD-007: findings link to the raw transcript (`agent_transcript`).

Suite 83 → 97; `verify --all` and CI green. Adversarial round: 6 findings,
1 blocking — experienced live by the reviewer (FWD-005's identity plus
the allowlist false-blocked the reviewer from writing its own findings
inside its worktree); fixed.

**Backlog decision (owner)**: two ideas captured mid-sprint (OTel/guard
trail, execution provenance) had already been folded into the sprint;
unplanned intake was zero. New direction selected at S-003 planning: the
artifact graph (research-driven — see the S-003 goal and ADR-0010).
