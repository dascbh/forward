<!--
FDE-KERNEL:GENERATED — do not edit by hand.
Source of truth: fde.config.toml + .fde/spec/. Regenerate with the fde-sync skill.
Manual edits here are overwritten and detected as drift.
-->

# forward

## Commands

```bash
python3 -m unittest discover -s tests      # tests
python3 bin/fde/verify.py --gate eval   # evals
python3 bin/fde/verify.py    # full gate (the same one CI runs)
```

## Invariants (not configurable)

- **I1 eval-precede-merge** — No change that alters observable system behavior lands on the main branch without a corresponding entry in the evaluation suite.
- **I2 adversarial-isolation** — Adversarial review receives the artifact and the specification. It never receives the context, the history, or the reasoning of whoever built the artifact.
- **I3 adversarial-incentive** — The adversarial role is measured by failures found, not by deliveries approved. It has no write permission on the code under review — it can only record findings. Fixing is another role's job.
- **I4 promotion-criteria-declared** — No artifact is promoted to production without written, versioned, and dated acceptance criteria, declared before construction begins.
- **I5 observability-floor** — Every promoted artifact emits the minimum needed to verify in production the quality attributes it declared to meet.
- **I6 client-runnable-gate** — The gate runs in the client's environment, with the client's runner, with no framework component on the critical path. The deliverable includes the ability to run it without the FDE present.
- **I7 artifact-handoff** — Roles communicate through versioned artifacts on disk (spec, ADR, suite, review report), never through conversation continuity.
- **I8 principled-judgment** — Quality that cannot be verified by execution (eval) or by demonstrated failure (adversarial probe) is verified by heuristic review: judgment against a declared, versioned principle catalog. Every finding cites either the probe that broke it or the principle it violates, with severity. Judgment without a named principle is not a finding.

No key turns off an invariant: if the delivery does not fit one, the
scope shrinks, not the standard.

## Agreed priority (vector A, budget 100)

- functional_correctness: 30
- maintainability: 22
- reliability_resilience: 12
- usability_accessibility: 12
- observability: 10
- security_privacy: 8
- performance_scale: 3
- operational_cost: 3

Weight orders the attack and sizes the suite, never below the
attribute's floor.

## Depth per domain (vector B, derived from the stack)

- software_architecture: 1
- qa_test_strategy: 1
- platform_delivery: 1

Override is upward-only.

## Roles

- **Specification** (`fde-spec`) — writes to `specs/**, discovery/**, cycles/**, backlog.md`
- **Architecture** (`fde-architecture`) — writes to `docs/adr/**, specs/**, walkthroughs/**, backlog.md, cycles/*/board.md`
- **Implementation** (`fde-implementation`) — writes to `src/**, tests/**, evals/**, infra/**, backlog.md, cycles/*/board.md`
- **Adversarial review** (`fde-adversarial`) — writes to `reviews/**, cycles/**, backlog.md`
- **Promotion** (`fde-promotion`) — writes to `cycles/**, backlog.md, promotions/**`
- **Walkthrough evaluator** (`fde-walkthrough-evaluator`) — writes nothing

Inside `cycles/C-<n>/` each role writes only its own file; `board.md`
and `backlog.md` are open to all; `promotions/**` is legacy. "All five
roles" means the five working roles; the walkthrough evaluator is a
sixth role that writes nothing. The adversarial and promotion roles run
isolated: artifact + spec only, never the builder's thread.

## Demand loop

Never start code on request: code starts only inside a signed-off cycle
(kernel ADR-0019). A demand (e.g. `FWD-002`) is one page derived from
the plan; it decides nothing new.

1. **Triage** the cycle (`fde-triage`). Size is set on the cycle, never
   on a demand. Inputs are judged for THIS cycle (`sensitive` is always
   false in a public/internal project). Sensitive or irreversible?
   Unsure on either → true. Torn between sizes → take the larger.
   **RULE, checked mechanically, not estimated**: Categorically distinct
   from XS, a commit lane verified on the real diff by the `rule-lane`
   gate (`fde-triage`, kernel ADR-0015).
   score ≤ 1 → **XS** · 2–3 → **S** · 4–6 → **M** · ≥ 7 → **L**.
   Size sets only the planner's depth and the cycle review rounds: 1
   round at XS/S, full + delta at M/L. At every size `fde-spec` writes
   `plan.md` (minimal at XS) and a demand review is 1 round. M adds
   architecture: `fde-architecture` writes the ADRs, so M and L run all
   five roles. Announce the size in one line, commit `plan.md`, and stop
   at the sign-off. **Budgets, not minimums**, never extended. Timebox:
   XS 30 min, S 1 h, M 3 h, L 1 day. An overrun is not re-split at
   review: it goes on the board; the cycle replans only if a criterion or
   an ADR changes. A new rule ships as instruction first; a gate needs
   usage-data showing it failed.
2. **Plan** the cycle: `plan.md` carries a `## Threat model`, criteria
   and failure modes with ids dated before the first demand commit (I4),
   and the demand list; `deploy.md` the deploy plan; `docs/adr/` the
   decisions. An ADR is the only home of a decision; plan and specs cite
   it by id; a demand never amends it. A demand is at most about 300
   production lines and has exactly one layer: `front`, `back` or
   `infra`. A change that spans layers is always split, however small.
   Undocumented system: `fde-survey` first. UI: `fde-design`.
3. **Sign-off**: Approval happens once, at plan sign-off, and is
   inherited by everything after it, irreversible `deploy.md` steps
   included. Only a replan asks the owner again.
4. **Build**: Demands run in parallel by default, coordinated on
   `cycles/C-<n>/board.md`. Each runs in its own worktree once its
   dependencies merge. A root with no suite gets a minimal one (I1).
   Never `--no-verify`. README and runbook change with how the system
   runs (MNT-10).
5. **Review the demand** (`fde-review`, kernel ADR-0021). A coding
   demand inside a signed-off plan: isolated code review (diff × demand
   spec, ADR conformance, tests, the layer's check; `kind = "code"`; ~10
   minutes; no scratch repositories or probe hunt). A sensitive or
   irreversible demand, or a real diff over ~300 production lines:
   adversarial review. An M/L plan, before sign-off: adversarial plan
   review (`kind = "plan"`). The cycle review is unchanged. Blocking =
   critical/high, reachable inside the threat model, breaks a declared
   criterion — never weight alone. At most five findings per round. A
   blocker is fixed in the demand (`## Cycle`), never by one more round.
6. **Merge**: Merge happens per demand; promotion and deploy happen per
   cycle. A demand merges rebased onto main, with `python3
   bin/fde/verify.py --all` green and no blocking finding open.
7. **Review the cycle**: The cycle review judges the objective —
   functioning and readiness against `plan.md` — and never re-reviews a
   demand. With a `front` demand, it runs `fde-walkthrough`.
8. **Promote and deploy**: promotion, at every size, is
   `fde-promotion`'s decision against the plan's criteria. The deploy
   plan runs infra-expand → back → front → infra-contract, and every
   step has its own verification and rollback. An irreversible step is
   never bundled with a reversible one. A failed step rolls back and the
   cycle stops; the user is told the outcome, not asked beforehand.

## Cycle

A cycle is `cycles/C-<n>/` (next free `n`), from
`.fde/templates/cycle/`: `plan.md`, `deploy.md`, `board.md`, `review.md`
and `promotion.md` (its `## What changes`: three lines at most, each
also a backlog line). A demand is `specs/<id>/spec.md` plus
`reviews/<id>/findings.toml`, nothing more.

A cycle moves `draft` (grouped) → `planned` (specified, awaiting
sign-off) → `running` (signed off) → `closed` or `abandoned`; several
drafts may exist, one runs at a time. `fde-backlog` groups items
(backlog → draft); `fde-spec` writes `state: planned`; the orchestrating
agent writes `running` with `signed-off:` at sign-off, then `closed` or
`abandoned`. The plan is frozen at sign-off; these header lines are the
only edits it takes.

A new fact always goes to the backlog — never a fix, an amendment or a
question. The one exception is a fact that invalidates the demand's own
ADR or criteria: the demand stops and the cycle replans. The cycle owns
its declared criteria and its blocking findings. Nothing is fixed
in-band (MNT-9) except a defect blocking a declared task, noted as such.

A demand review's blocking finding is fixed inside that demand and
proven by its regression test; the owner is asked only when the fix
changes a criterion or an ADR, which is a replan. A non-blocking finding
goes to `backlog.md` unless it shows a plan criterion unmet; then the
cycle fixes it. A cycle review budget spent with a blocker open is the
owner's call: narrow, declare the limit, or pause, recorded on
`board.md` and marked in `promotion.md` at close.

The board is the record (I7), not the conversation. Agents decide inside
the plan and record it there. Two demands needing the same file: the
later posts `blocked-on` and waits.

Gates follow the owning level. Cycle: I4, promotion, I5, traceability;
demand: I1, I2, I3; commit: RULE.

A cycle closes when its criteria are met with integration evidence and
it is deployed or published; show the user its backlog lines
(`fde-status`). A cycle opened before kernel ADR-0019 finishes under its
own rules.

## Backlog

An idea, pain or request becomes a backlog item, not a demand: one-line
acknowledgment, nothing more. A backlog line is `B-<n>`, the text,
`(C-<n>)` when a cycle found it, and its evidence (`opinion < usage-data
< user-test < production`). `backlog.md` starts with `goal:` (or `goal:
not set`) and `date:`; with `[scrum] enabled = true`, `--gate scrum`
requires them. The owner orders it; evidence never blocks a bet. "Fix it
NOW" skips the backlog order, never the open cycle: it becomes the next
cycle's first demand. Sprints are retired; `sprints/` is history.
Detail: `fde-scrum` skill.

## Detail

Report the change, its evidence and what stays open, never the kernel;
process gets one closing `FORWARD:` line unless the gate blocked or the
user must decide.

Skills govern where this file compresses. Never escalate
kernel-interpretation questions to the user mid-demand: resolve from the
skill, take the stricter reading, flag it afterwards.
