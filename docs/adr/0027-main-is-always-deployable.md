# ADR-0027 — Main is always deployable

date: 2026-10-01
status: accepted (owner, direct, 2026-10-01)
builds on: ADR-0024 (small cycles run in parallel, each deploys on its
own), ADR-0026 (a migration is reversible by construction)

## Context

ADR-0024 split a large objective into small cycles that run at once,
each one deploying on its own. They all merge into one main. On a
client, two cycles finished and reviewed could not deploy: main already
held a third cycle's merged, half-built demands, whose code needed its
migrations. Deploying main to ship the finished cycles would have
shipped the unfinished one with it, and its cycle review called that a
blocker. The finished cycles waited for the slowest, in a joint deploy
the structure forced on everyone. The owner saw it as cycles that
stretch at the end and an agent that proposes combinations instead of
closing.

Continuous delivery solves it with one rule: the trunk is always
releasable. Unfinished work merges dark.

## Decision

1. **A demand merges only if main stays deployable with it**, as if its
   cycle stopped right there:
   - its migration only expands (kernel ADR-0026): new table, nullable
     column, key beside the old one — the code already live runs on it;
   - its new behavior is unreachable until its cycle deploys: behind a
     flag off by default, or on a route, screen or menu entry not yet
     linked. A change to behavior already live is the exception: it
     ships with its cycle's last demand, or behind the flag.
2. **Each demand declares how it stays dark** — the `dark` note of its
   row in `plan.md` (`flag <name>`, `unlinked route`, `expand only`,
   `no new behavior`). The code review checks it: "if the cycle stopped
   here, would main still deploy and behave as today?" A no is a finding
   that blocks the merge.
3. **A finished cycle deploys main when it finishes**, carrying the
   others' dark code without effect, its migrations included. It never
   waits for another cycle. Its deploy turns on what was dark for it:
   the flag, the link.
4. **A joint deploy exists only when the plan declared it at sign-off**
   (one objective whose slices only make sense together). Proposed
   later, it is a replan, never the default way out.

## Alternatives rejected

- **A release branch per cycle.** Parallel cycles interleave on main;
  cutting one cycle's commits out of it is a merge problem every time.
- **Merging a cycle only when it is whole.** Long-lived branches, big
  merges, the collisions ADR-0024 split cycles to avoid.
- **Joint deploys as the rule.** The finished cycle waits for the
  slowest; closing stretches; that is the problem.

## Consequences

- Every demand carries a little more design: a flag or a link left out.
  In exchange no cycle waits for another to deploy.
- Flags left on are debt: the cycle that turns one on removes it in its
  own close or files the removal as a backlog line.
- Migrations reach production before the code that uses them — the
  expand/contract order ADR-0026 already asks for.
