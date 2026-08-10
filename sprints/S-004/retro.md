---
sprint: S-004
date: 2026-08-09
---

# Retro — S-004

## 1. What cost more than it returned?

- Nothing structurally. The demand was cheap for its weight because the
  papers did the specification work: the metrics to build were the ones
  the studies already measure, so there was no design debate about which
  signals matter.

## 2. What did the gate catch — and what did it let through?

- Caught, and this is the sprint's lesson: the install-drift test was
  checking a **hardcoded list** of three runtime modules, so the two
  newest ones — the copies CI actually executes — could rot with the
  suite green. It is the second time this class appeared (FWD-001 F4 was
  the same shape at the directory level). Fixed by discovery instead of
  enumeration: the test now walks `runtime/*.py`. **Rule extracted: a
  drift detector that enumerates is a drift detector that will miss the
  next file.**
- The review also caught the manifesto over-reading its own metric —
  prose, not code, and the honesty catalog was the tool that named it.

## 3. What changes?

- The enumeration-vs-discovery lesson generalizes: any place the kernel
  lists artifacts to check should derive the list, not hardcode it. No
  other instance found this sprint (the graph and gates already derive),
  so it stays a retro finding rather than a demand.
- S-005 takes the design gaps identified during this sprint's review of
  an external proposal. Note for that demand: the same failure mode the
  erosion papers proved for code quality ("prompting for it does not
  hold") applies to creativity — so divergence must be structural
  (distinct lenses, recorded discards), never an instruction to be
  creative.
