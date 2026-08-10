---
sprint: S-003
date: 2026-08-09
---

# Retro — S-003

## 1. What cost more than it returned?

- Building the graph before wiring the gate surfaced a latent
  inconsistency in the repo's own keying (spec dirs slugged, review dirs
  bare). Cheap to fix (canonicalize the id), and finding it was the
  point — but it is a reminder that the kernel accreted naming drift over
  eight demands. Noted, not fixed in-band (MNT-9).

## 2. What did the gate catch — and what did it let through?

- The isolated round caught a blocking bug on a feature whose own subject
  is provenance: the authored edge silently not parsing. The tests were
  green over a dead feature because test and code shared one wrong
  assumption about the ADR format. Lesson carried into S-004: a
  measurement's tests must exercise the repo's ACTUAL data shape, not a
  convenient synthetic one.
- Nothing else let through; CI green each push.

## 3. What changes?

- S-004's directive (anti-erosion) is itself a response to a measurement
  blind spot the graph work exposed and the four papers name: the kernel
  measures per-change correctness but not degradation TREND over time.
  SlopCodeBench's finding that prompt interventions fail to stop
  degradation is why S-004 builds a gate, not a skill-instruction —
  turning the retro's "kernel accreted drift" observation into an
  enforced measurement.
- Process working as designed; no kernel-mechanism change this retro.
