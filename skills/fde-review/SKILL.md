---
name: fde-review
description: Runs the isolated adversarial and heuristic review, attack ordered by the project's weights. Use before promotion, or when the user asks for review, code review, red team, "try to break this", or whether something is secure or robust enough.
---

# fde-review

## Build the probe plan (deterministic)

1. Read `[weights]` from `fde.config.toml`; sort attributes descending.
   Weight orders the attack — nothing else. It does not add rounds and it
   does not make a finding blocking (kernel ADR-0018). A low-weight attribute is
   still probed in the full round.
2. Probes per attribute come from
   `.fde/spec/dimensions/quality-attributes.toml` (`adversarial_probes`).
3. Read `plan.md`'s `## Threat model`: who the cycle must contain, and
   what is declared out of scope. It bounds every probe.
4. Demand mode: create `reviews/<demand-id>/findings.toml` from
   `.fde/templates/findings.template.toml`. Cycle mode: write
   `cycles/C-<n>/review.md`.

## Mode — demand or cycle (kernel ADR-0019 rule 12)

- **Demand**: the code against the demand spec, plus conformance to the
  cycle ADRs it cites, plus its layer's check (`back` unit + contract
  tests, `front` design QA against the approved wireframe, `infra` plan
  diff + policy check). 1 round.
- **Cycle**: the objective on the integrated result; it never re-reviews
  a demand. *Functioning*: every `plan.md` criterion shown end to end
  (integration for back, usability for front, live checks for infra).
  *Readiness*: `deploy.md` complete with each step's verification and
  rollback exercised where the project allows, the signals the criteria
  declare (I5), runbook and README current. `fde-walkthrough` runs here,
  only when the cycle has a `front` demand. Rounds: the budget below.

## Budget — cycle rounds come from the cycle's size, and they end

| size | rounds | kinds |
|---|---|---|
| XS, S | 1 | full |
| M, L | 2 | full, delta |

A demand review is always 1 round. A demand review's blocking finding
is fixed inside that demand and proven by its regression test; the owner
is asked only when the fix changes a criterion or an ADR, which is a
replan. A non-blocking finding goes to `backlog.md` unless it shows a
plan criterion unmet; then the cycle fixes it.

- **Full** (round 1): the whole artifact against the whole spec.
- **Delta** (every later round): the prior findings plus the diff that
  answered them. The reviewer verifies each prior finding, then attacks
  only the changed lines. A new defect in untouched code goes to the
  backlog (`blocking = false`, `backlog = true`) — it never reopens the
  demand.
- **No extension.** When a cycle review's budget is spent with a
  blocking finding open, the owner picks one (AGENTS.md `## Cycle`). The
  choice is recorded on the cycle's `board.md`; a narrowed or declared
  item is marked in `promotion.md` at close; `plan.md` stays frozen.
  1. *narrow* — cut the part the finding lives in, ship the rest, the cut
     goes to the backlog;
  2. *declare* — the owner accepts it as a dated, named limit (a limit,
     not a pass);
  3. *pause* — revert, nothing ships, the backlog keeps the record.
  "One more round" is not an option (kernel ADR-0018).

## What blocks

`blocking = true` only when all three hold: severity `critical`/`high`;
the path is reachable inside the plan's threat model; it breaks a declared
acceptance criterion or failure mode of `plan.md`. Anything else records,
and a non-blocking finding goes to the backlog unless it shows a plan
criterion unmet. A defect reachable only by
an actor or sequence the threat model excludes is a declared limit. No
threat model in the plan → that is the first finding.

## Cap

At most five `[[finding]]` entries per round, the five most severe. Every
other observation is one line in `[meta].notes`.

## How to run it

- **Isolate (I2).** The thread that produced the code cannot review it.
  Claude Code: invoke the `fde-adversarial` subagent (isolated worktree;
  the guard hook blocks its writes outside its scope). Any other tool:
  `git worktree add --detach ../.fde-review-<demand-id>` and review there
  in a fresh session.
- **Record, never fix (I3).** Findings go in `reviews/<id>/findings.toml`;
  fixing belongs to the implementation role.
- **Pass the SHA, verify the SHA.** Put the commit SHA under review in
  the reviewer's prompt; its first step is `git log -1`, which must match
  (isolation tooling can pin an older base; install sets
  `worktree.baseRef: "head"`). If not, check out the right commit first.
- **Record provenance (FWD-007).** `[meta]` carries the rounds run, what
  was probed, and `agent_transcript = "agent-<id>"` (the reviewer's
  worktree directory name). In chat, the findings speak.

## The heuristic pass (same reviewer, same isolation)

After probing, judge the attributes whose `verified_by` includes
`heuristic` (`.fde/spec/dimensions/quality-attributes.toml`) against
their `heuristic_principles`. A heuristic finding cites `principle` and
severity (I8): "USE-3: the same filter is called 'Period' on one screen
and 'Range' on another — medium".

## Reconciliation — reviewer output is data, not a verdict

The builder reconciles findings with a fixed precedence: contract
misread > actionable > trade-off > noise. Two consecutive rounds of
substantive findings with zero classified actionable means the review
turned into validation — stop.

One commit per reconciliation: the fixes, their evals, and — only when a
decision changed — the ADR edit. A fix that rewrites far more than the
finding's evidence spans is the wrong design for this scope: narrow
(Budget, option 1) instead of rebuilding under review.

## Change sizing

One ceiling: a demand is split at planning to fit ~300 production lines,
never at review; an overrun is posted on the board and the review
proceeds (`fde-triage`). A dependency bump is a behavior change: read the
changelog, diff the lockfile, one package per change.
