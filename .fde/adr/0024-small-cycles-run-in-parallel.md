# ADR-0024 — Small cycles run in parallel; the planner splits by seams

date: 2026-09-30
status: accepted (owner, direct, 2026-09-30)
amends: ADR-0019 rule 9, "only one cycle runs"

## Context

A cycle is where the owner signs, and deploy happens per cycle
(ADR-0019 rule 4). With one running cycle at a time, the only way to run
work in parallel was to put it all in one cycle. In a client project
(2026-09-30), a product vision split into four slices, each meant to be "a demo live
fast". To run them in parallel, the planner packed them into one L cycle
with 14 demands and 11 migrations, deploying only at the end.

The owner's direction: the most parallelism, with smaller slices. The
kernel must steer the split: work that crosses slices, coding, and how
agents collaborate.

## Decision

1. **A cycle is one slice.** It is the smallest change the owner sees
   working and that deploys on its own. Deploy stays per cycle, so a
   smaller cycle is a faster demo.
2. **Several cycles run at once.** Two running cycles may not touch the
   same files unless one declares `depends: C-<n>` on the other; it then
   starts once that cycle has merged what it needs. `status.py --waves`
   computes which cycles run together. An overlap without `depends:` is
   a warning on every status and the `CYCLES` gate.
3. **The planner splits a large objective in one pass** (`fde-spec`):
   - **Seams first.** A file that two slices would touch (schema and
     migration numbering, a route or handler registry, shared vocabulary,
     a shared module, the infra stack) goes to a small **foundation**
     cycle. The other cycles depend on it. Where possible, the seam
     becomes an extension point, so that each slice adds its own file
     instead of editing a shared one.
   - **Then vertical slices.** Each is one goal the owner recognises
     (ADR-0022), with disjoint files and its own criteria, deploy and
     review.
   - **Hot files have one owner.** A file every slice needs to edit is
     either split by the foundation or owned by one slice, and the
     others depend on it.
   - Inside a cycle, demands still run in waves by `files` (ADR-0019,
     `status.py --waves C-<n>`).
4. **One sign-off for the set.** The owner signs all the slices of one
   objective in one message; each plan records it. A replan of one
   slice does not reopen the others.
5. **Agents collaborate through files, never through chat (I7).** Each
   demand runs in its own worktree. Each running cycle has its own
   board. Across cycles, the only contracts are `files` and `depends:`,
   plus `blocked-on C-<n>` on a board.
6. **Size is per slice.** Triage sizes each cycle. Twelve demands or
   more in one cycle signals a missed split.

## Consequences

- More, smaller cycles, each with its own deploy and review, in exchange
  for one foundation cycle that must land first.
- `fde-sync` still waits until no cycle is running. With small cycles,
  those windows come often.

## Rejected

- **Deploy per wave inside one big cycle.** It keeps one sign-off and
  one review for work the owner sees as separate demos, and a failed
  wave stops every other wave.
- **Unlimited parallel cycles with no file contract.** Parallel agents
  editing the same file is what the waves exist to prevent.
