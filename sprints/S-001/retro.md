---
sprint: S-001
date: 2026-08-09
---

# Retro — S-001

## 1. What cost more than it returned?

- Version bumps remain manual toil (three sed targets plus copy resyncs);
  the version-sync and identity tests police the outcome, so the risk is
  gone but the friction stays. Accepted for now — a bump script would
  reintroduce the CLI the kernel deliberately removed (ADR-0001).
- The reviewer's probe scripts ran in an ephemeral scratchpad; their
  evidence survives only as prose in `probed`. Became backlog item 5,
  selected for S-002 (FWD-007).

## 2. What did the gate catch — and what did it let through?

- Caught by own tests before commit: `diff-tree` root-commit blindness
  and the I8 vacuous pass on unparseable findings.
- Caught by the isolated round: the lexicographic sprint ordering
  (blocking — would have inverted "no retro, no next sprint" at S-10),
  vacuous commitments by substring, empty retro counting as retro.
- Let through: nothing known yet; CI green on every push since fde-gate
  landed.

## 3. What changes?

- Capture worked as designed: two ideas arrived mid-sprint and became
  backlog items (4, 5) instead of unplanned demands — unplanned intake
  was zero. Keep.
- Planning now re-scores backlog size estimates with current triage
  rules at selection time (S-002 planning re-scored item 1's M estimate
  to S under per-demand inputs — the very rule that item ships).
