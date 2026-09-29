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

Code starts only inside a signed-off cycle (kernel ADR-0019) or in the
direct lane (`fde-triage`). Three levels: backlog → cycle → demand. A demand (e.g. `FWD-002`) is one page derived from
the plan; it decides nothing new.

1. **Triage** the cycle (`fde-triage`). Size is set on the cycle, never
   on a demand. Announce the size in one line, commit `plan.md`, and
   stop at the sign-off.
2. **Plan** the cycle (`fde-spec`; UI: `fde-design`; inherited system:
   `fde-survey`). A demand is at most about 300
   production lines and has exactly one layer: `front`, `back` or
   `infra`. A change that spans layers is always split, however small.
3. **Sign-off**: Approval happens once, at plan sign-off, and is
   inherited by everything after it, irreversible `deploy.md` steps
   included. Only a replan asks the owner again.
4. **Build**: Demands run in parallel by default, coordinated on
   `cycles/C-<n>/board.md`. Each runs in its own worktree once its
   dependencies merge. A root with no suite gets a minimal one (I1).
   Tests run once per SHA (`fde-review`).
   Never `--no-verify`. README and runbook change with how the system
   runs (MNT-10).
5. **Review the demand** (`fde-review`, kernel ADR-0021). A coding
   demand inside a signed-off plan: isolated code review (diff × demand
   spec, ADR conformance, tests, the layer's check; `kind = "code"`; ~10
   minutes; no scratch repositories or probe hunt). A sensitive or
   irreversible demand, or a real diff over ~300 production lines:
   adversarial review. An M/L plan, before sign-off: adversarial plan
   review (`kind = "plan"`). The cycle review is unchanged.
6. **Merge**: Merge happens per demand; promotion and deploy happen per
   cycle. When a demand may merge: `fde-review`.
7. **Review the cycle** (`fde-review`, cycle mode).
8. **Promote and deploy**: promotion, at every size, is
   `fde-promotion`'s decision against the plan's criteria. The deploy plan:
   `fde-spec`.

## Cycle

A cycle is `cycles/C-<n>/`, laid out by `fde-spec`. A demand is
`specs/<id>/spec.md` plus `reviews/<id>/findings.toml`, nothing more. A
cycle moves `draft` (grouped) → `planned` (specified, awaiting
sign-off) → `running` (signed off) → `closed` or `abandoned`; several
drafts may exist, one runs at a time. Who writes each state, and when a
cycle closes: `fde-backlog`.

A new fact always goes to the backlog — never a fix, an amendment or a
question. The one exception is a fact that invalidates the demand's own
ADR or criteria: the demand stops and the cycle replans. The cycle owns
its declared criteria and its blocking findings. Nothing is fixed
in-band (MNT-9 scope discipline) except a defect blocking a declared task, noted as such.
A finding's path: `fde-review`. A cycle review budget spent with a
blocker open is a replan, the owner's call: narrow, declare the limit, or
pause, recorded on `board.md` and marked in `promotion.md` at close, never
in `plan.md`.

The board is the record (I7), not the conversation. Agents decide inside
the plan and record it there. Parallel demands come from the plan's
`files` (`status.py --waves`).

Gates follow the owning level. Cycle: I4, promotion, I5, traceability;
demand: I1, I2, I3; commit: RULE. The RULE lane: `fde-triage`.

## Backlog

An idea, pain or request becomes a backlog item, not a demand: one-line
acknowledgment, nothing more. "Fix it NOW": the direct lane when it
fits, else the next cycle's first demand. Only main assigns backlog
ids. Detail:
`fde-backlog-format` skill.

## Detail

Report the change, its evidence and what stays open, never the kernel;
process gets one closing `FORWARD:` line unless the gate blocked or the
user must decide.

Skills govern where this file compresses. Never escalate
kernel-interpretation questions to the user mid-demand: resolve from the
skill, take the stricter reading, flag it afterwards.
