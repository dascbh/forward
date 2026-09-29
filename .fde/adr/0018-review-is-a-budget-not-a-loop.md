# ADR-0018 — Review is a budget, not a loop

date: 2026-09-28
status: accepted

## Context

The last four demands grew on every axis while delivering less:

| | FWD-001..009 | FWD-017..019 | FWD-020 | FWD-021 |
|---|---|---|---|---|
| spec (words) | 250–700 | 2.6k–4.7k | 11.7k | 21.7k |
| review (words) | 350–1.4k | 2.2k–2.8k | 9.4k | 19k |
| rounds | 1 | 4–5 | 4 | 5 |
| outcome | shipped | shipped | shipped | reverted |

FWD-021 was triaged at ~300 LOC and opened with a 3,163-line commit. Its
five rounds found 17, 13, 10, 6, 7 findings, and 3, 3, 3, 2, 2 of them
were blocking. The count did not converge. Four mechanisms kept the loop
running:

1. **Every round was a full review of a moving target.** Each
   reconciliation rewrote 600–1,700 lines, and the next round attacked
   that new surface from scratch. The "three cycles, then escalate" bound
   turned into asking the owner for one more round.
2. **Weight decided blocking.** `probe_plan` marked every attribute with
   weight ≥ 15 as `BLOCKS MERGE`, so any correctness edge case blocked.
   No spec said who the change had to contain, so the reviewer assumed
   the worst actor. The blockers were force-push, merge-parent and
   disable/re-enable bypasses of a gate, in a repository declared public
   and reversible, with security weighted 8.
3. **The size never changed after triage.** The skill's own rule, "near
   1000, split before reviewing", had no trigger, so it never fired.
4. **The rule shipped as a gate first.** A practice the owner reported
   working as a plain file became a git-history enforcement boundary.
   The review attacked it as a security boundary.

Two rules also conflicted. Triage set rounds per size (M = 2), while
`fde-review` set rounds per attribute (`weight/10`, 3 for correctness).

## Decision

- **Rounds come from the size and end there.** XS/S get one full round,
  M a full round plus one delta round, and L a full round plus two delta
  rounds.
  - A delta round verifies the prior findings and attacks only the
    changed lines. A new defect in untouched code goes to the backlog.
  - When the budget is spent with a blocker open, the demand is narrowed,
    the blocker is declared as a limit, or the demand is paused. There is
    never another round.
- **Blocking needs three things:** severity critical or high, a path
  reachable inside the spec's `## Threat model`, and a broken declared
  criterion or failure mode. Weight only orders the attack. `probe_plan`
  no longer returns `rounds` or `blocking`.
- **The reviewer records at most five findings per round.** Everything
  else is a one-line note.
- **Triage re-sizes on the real diff.** If the diff is more than twice
  the estimate or above ~800 changed lines, the demand is split. It is
  not reviewed. Timeboxes are XS 30 min, S 1 h, M 3 h and L 1 day.
- **Spec budget.** Each spec file fits on one page, with at most ten
  failure modes, and `spec.md` carries a threat model.
- **Smallest mechanism first.** A new rule ships as an instruction. It
  becomes a gate only in a later demand, backed by usage data.
- **Documents change only when a decision changes.** An architecture
  revision goes in the same commit as the reconciliation, not in a
  separate per-round commit.

I3 is unchanged: the reviewer is still measured by failures found. What
counts as a failure is now bounded by the declared threat model.

## Rejected alternatives

- **Keep the rounds and raise the bound.** FWD-020 and FWD-021 already
  ran past the bound with the owner's authorization, and it did not
  converge.
- **Enforce the budget with a new gate now.** That would repeat mistake
  4. The budget ships as an instruction, and it becomes a gate only if
  usage data shows the instruction is ignored.
- **Lower the correctness weight.** That would change the order of the
  attack, not the loop. The loop came from weight deciding blocking and
  rounds, and that link is what this ADR removes.

## Consequences

- An M demand is expected to take about 3 h, with a one-page spec, a
  diff of 400 lines or less, two rounds, and five findings or fewer per
  round.
- Some defects outside the threat model will ship as declared limits.
  That is the intended trade.
- The rendered attack order in `.claude/agents/fde-adversarial.md` loses
  its per-attribute rounds and `BLOCKS MERGE` tags. The mirror manifest
  renders the new form.
