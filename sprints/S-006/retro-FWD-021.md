---
demand: FWD-021
date: 2026-09-28
outcome: abandoned
---

# Retro — FWD-021 (declared cycle scope, as a gate)

A demand retro, which will be input to the S-006 retro. FWD-021 is
abandoned. The need shipped as an instruction in FWD-022, and ADR-0017
is marked superseded.

## Evidence

| | FWD-021 (gate) | FWD-022 (instruction) |
|---|---|---|
| triage estimate | M, ~300 LOC | S |
| real diff | 9,186 insertions, 36 files (to round-4 fix) | 288 insertions, 19 files |
| spec | 21.7k words | 586 words |
| rounds | 5 (17, 13, 10, 6, 7 findings) | 1 (5 findings) |
| blocking | 3, 3, 3, 2, 2, never converged | 0 |
| wall clock | 11:32 → 16:09, then revert | shipped |
| outcome | reverted, abandoned | 0.16.0 |

Sources: `git log` for both demands, `reviews/FWD-021/findings.toml`,
`cycles/C-1.md`, `cycles/C-2.md`, and ADR-0018's context table.

## 1. What cost more than it returned?

All of it. Five rounds and about 4.5 hours produced a gate that was
reverted. The same need then shipped as about 300 lines of text.

- **The request became a security boundary.** The owner asked to keep
  agents on task. The build defended against force push, forged merges,
  and history rewrites, which are attacks by someone with owner
  permissions. No spec named who the gate had to contain, so the
  reviewer assumed the worst actor on every round.
- **Every round reviewed a new artifact.** Each reconciliation also
  committed a separate architecture revision (commits `0a7fe5d`,
  `e9d305c`, `f19e0a6`, `b793449`), so the next round attacked
  600–1,700 lines of new surface.
- **The trend was visible and was not shown.** By round 2 the blocker
  count was flat, at 3 → 3. The owner was instead asked twice to
  authorize "one more round" (rounds 4 and 5, recorded in S-006
  `## Owner decisions`). Only after the revert did the owner hear the
  real cost: about 15 min and 150 tests per round.
- **The owner chose a gate without its cost.** "Gate vs instruction" was
  offered with no estimate of diff size or rounds, and the lighter
  option was not the default.

## 2. What did the gate catch, and what did it let through?

The verify gate caught nothing that mattered, and that was correct:
each commit was green. The isolated review did its job. The 53 findings
were real defects in the gate as designed. What nothing caught was the
problem that mattered: the triage estimate (300) against the real diff
(3,163 lines in the first commit). No rule re-sized a demand on its real
diff, so a demand ten times its estimate went to review unsplit.

A second miss happened after the revert. The session negotiating how to
finish FWD-021 did not see ADR-0018 and FWD-022 land on `main` from a
parallel session, and proposed a plan that was already obsolete. It
found out only when `fde-sync` read the log.

## 3. What changes?

**Already changed by ADR-0018:**
- rounds come from the size, and later rounds are delta rounds;
- blocking requires the spec's threat model;
- at most five findings per round;
- re-size on the real diff (over 2× the estimate or ~800 lines means
  split);
- one-page spec;
- instruction before gate;
- no per-round architecture commits.

FWD-022 is the first data point under it: 1 round, 0 blocking, shipped.

**Not covered by ADR-0018, now backlog items:**

1. **Report the timebox, don't just declare it** (item 10). At every
   round boundary, the status line shows elapsed time against the
   timebox, and findings and blockers per round so far. When the
   timebox runs out, the agent stops and shows the owner the trend
   before proposing anything. ADR-0018 set the timeboxes. Nothing makes
   the agent say when one has run out.
2. **Resync before proposing** (item 11). Before proposing a plan for a
   paused or long-running demand, `git fetch` and read the log since the
   last known commit. Another session may already have changed the
   premise.
3. **A heavier mechanism is offered with its price** (folded into item
   10). When the owner is asked to choose between an instruction and a
   gate, the offer carries the estimated diff and rounds of each, and
   the instruction is the default.

**Watch, no change yet:** the next three demands under ADR-0018. Record
spec words, real diff against the estimate, rounds, and blockers, the
same columns as ADR-0018's table. If any demand exceeds 2× its timebox,
the budget moves from instruction to gate.
