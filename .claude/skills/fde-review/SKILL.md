---
name: fde-review
description: Runs the adversarial review in an isolated context, with attack order derived from the project's weights. Use before promoting any artifact, when the user asks for review, code review, red team, "try to break this", or asks whether something is secure/robust enough. The reviewer must NOT be the thread that built the code — isolate first.
---

# fde-review

## Build the probe plan (deterministic)

1. Read `[weights]` from `fde.config.toml`; sort attributes descending.
   Weight orders the attack — nothing else. It does not add rounds and it
   does not make a finding blocking (ADR-0018).
2. Probes per attribute come from
   `.fde/spec/dimensions/quality-attributes.toml` (`adversarial_probes`).
3. Read `plan.md`'s `## Threat model`: who the cycle must contain, and
   what is declared out of scope. It bounds every probe.
4. Demand mode: create `reviews/<demand-id>/findings.toml` from the
   kernel's `templates/findings.template.toml`. Cycle mode: write
   `cycles/C-<n>/review.md`.

## Mode — demand or cycle (ADR-0019 rule 12)

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
| M | 2 | full, delta |
| L | 3 | full, delta, delta |

- **Full** (round 1): the whole artifact against the whole spec.
- **Delta** (every later round): the prior findings plus the diff that
  answered them. The reviewer verifies each prior finding, then attacks
  only the changed lines. A new defect in untouched code goes to the
  backlog (`blocking = false`, `backlog = true`) — it never reopens the
  demand.
- **No extension.** When the budget is spent with a blocking finding
  open, the user picks one (AGENTS.md `## Cycle`: nothing is declined
  without the user), and the builder records it in the promotion or the
  closing commit:
  1. *narrow* — cut the part the finding lives in, ship the rest, the cut
     goes to the backlog as its own demand;
  2. *declare* — the owner accepts it as a dated, named limit in
     `plan.md` (a limit, not a pass);
  3. *pause* — revert, nothing ships, the backlog keeps the record.
  "One more round" is not an option: a round on a moving target finds the
  surface the last fix created, and never converges.

## What blocks

`blocking = true` only when all three hold: severity `critical`/`high`;
the path is reachable inside the plan's threat model; it breaks a declared
acceptance criterion or failure mode of `plan.md`. Anything else records,
and a non-blocking finding goes to the backlog. A defect
reachable only by an actor or sequence the threat model excludes (an
owner rewriting history to defeat their own gate, say) is a declared
limit. No threat model in the plan → that is the first finding.

## Cap

At most five `[[finding]]` entries per round, the five most severe. Every
other observation is one line in `[meta].notes`. Five findings a builder
can act on beat twenty they must triage.

## Non-negotiable rules

**Isolation (I2).** The reviewer receives the artifact and the
specification. It does not receive the context, the history, or the
reasoning of whoever built it. If you are in the same thread that produced
the code, you **cannot** be the reviewer:

- Claude Code: invoke the `fde-adversarial` subagent — it runs in an
  isolated worktree, and the guard hook blocks its writes outside
  `reviews/**`.
- Any other tool: `git worktree add --detach ../.fde-review-<demand-id>`
  and run the review inside it, in a fresh session with no builder context.

**No fixing (I3).** The adversarial role records in
`reviews/<id>/findings.toml` and stops. Fixing belongs to the
implementation role. A reviewer who fixes what they found erases the record
of the finding.

**Success is findings.** The goal is not to approve. A review that found
nothing is suspicious before it is good news — record rounds run and what
was probed in the `[meta]` of `findings.toml`. In chat, the findings
speak; the process does not.

**Pass the SHA, verify the SHA.** Invoke the reviewer with the commit SHA
under review in its prompt. First step inside the worktree: `git log -1`
must match that SHA — isolation tooling can pin an older base (notably
`origin/HEAD` when local commits are unpushed; the kernel sets
`worktree.baseRef: "head"` at install to prevent this). If it does not
match, check out the right commit before probing: reviewing stale code
produces confident nonsense.

**Record provenance (FWD-007).** The reviewer writes its own worktree
directory name (`.claude/worktrees/agent-<id>`) into `[meta]` as
`agent_transcript = "agent-<id>"` — the durable link between the summary
(`probed`) and the harness's raw execution transcript while it lives.

## The heuristic pass (same reviewer, same isolation)

After probing, judge the attributes whose `verified_by` includes
`heuristic` (`.fde/spec/dimensions/quality-attributes.toml`) against
their `heuristic_principles`. A heuristic finding cites `principle` and
severity; judgment without a named principle is not a finding (I8) —
"the UI feels off" does not exist; "USE-3: the same filter is called
'Period' on one screen and 'Range' on another — medium" does.

## Reconciliation — reviewer output is data, not a verdict

The builder reconciles findings with a fixed precedence: contract
misread > actionable > trade-off > noise. Rubber-stamping every finding
equals ignoring every finding. Re-reviewing an unchanged artifact is
stalling; two consecutive rounds of substantive findings with zero
classified actionable means the review turned into validation — stop.

One commit per reconciliation: the fixes, their evals, and — only when a
decision changed — the ADR edit. No separate
"architecture revision" commit per round; a finding that only needs a
fix changes no document.

A fix that rewrites more than it repairs is a smell: if answering a
round's findings changes more lines than the finding's own evidence
spans several times over, the design is wrong for this scope — narrow
(Budget, option 1) instead of rebuilding under review.

## Change sizing

~100 changed lines review well; ~300 is the ceiling for one logical
change; above ~800 (behavior + evals, not counting specs or reviews) the
demand is split before any review starts — `fde-triage` re-sizes on the
real diff. One structural problem outranks ten nits — the structural
problem IS the review. A dependency bump is a behavior change nobody
wrote: read the changelog, diff the lockfile, one package per change.

## Order

Derived from vector A weights, not from your intuition about what is
interesting. High weight attacks first; a low-weight attribute is still
probed in the full round — a floor, not zero.
