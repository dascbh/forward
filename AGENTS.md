<!--
FDE-KERNEL:GENERATED — do not edit by hand.
Source of truth: fde.config.toml + .fde/spec/. Regenerate with `fde sync`.
Manual edits here are overwritten and detected as drift.
-->

# forward

This repository operates under a delivery kernel with non-negotiable
invariants. Instructions here apply to any coding agent (Codex, Cursor,
Claude Code, Copilot, Kiro, Gemini CLI, Windsurf, Aider).

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

No key exists that can turn off an invariant. If the delivery does not fit
one, the scope shrinks — the standard does not.

## Agreed priority (vector A, budget 100)

- functional_correctness: 30
- maintainability: 22
- reliability_resilience: 12
- usability_accessibility: 12
- observability: 10
- security_privacy: 8
- performance_scale: 3
- operational_cost: 3

Weight orders the adversarial attack and sizes the suite. Weight never goes
below the attribute's floor.

## Depth per domain (vector B, derived from the stack)

- software_architecture: 1
- qa_test_strategy: 1
- platform_delivery: 1

Override is upward-only. The nature of the system sets the minimum, not
preference.

## Roles

- **Specification** (`fde-spec`) — writes to `specs/**, discovery/**`
- **Architecture** (`fde-architecture`) — writes to `docs/adr/**, specs/**`
- **Implementation** (`fde-implementation`) — writes to `src/**, tests/**, evals/**, infra/**`
- **Adversarial review** (`fde-adversarial`) — writes to `reviews/**`
- **Promotion** (`fde-promotion`) — writes to `promotions/**`

Handoff is by artifact on disk, never by conversation continuity. The
adversarial and promotion roles run isolated: artifact + spec only, never
the builder's thread.

## Demand loop — how work enters

Every feature, fix, or change request follows this cycle. Do not start
writing code on request; start by sizing. Pick a short demand id first
(e.g. `FWD-002`).

1. **Triage**: `score = min(3, surfaces) + (sensitive ? 2 : 0) +
   (irreversible ? 2 : 0) + (loc < 50 ? 0 : loc < 300 ? 1 : 2)`.
   All four inputs are judged for THIS demand, never inherited wholesale:
   `surfaces` = how many of UI/frontend, API, data/schema, infra this
   demand touches. `loc` = estimated lines of this change. `sensitive` =
   this demand touches data of the class declared in `[triage]` (in a
   public/internal project: always false). `irreversible` = this change
   is hard to undo — migration, deletion, external side effect —
   with `[triage].reversibility` setting the posture. Unsure on either →
   true; torn between two sizes → take the larger.
   score ≤ 1 → **XS**: implementation, adversarial, 1 round ·
   2–3 → **S**: + spec · 4–6 → **M**: + promotion, 2 rounds, ADR ·
   ≥ 7 → **L**: all five roles, 3 rounds, ADR.
   Announce the sizing in ONE line (e.g. `FORWARD: M — spec + impl +
   adversarial(2r) + promotion`), then start.
2. **Spec** (unless XS): `specs/<demand-id>/spec.md`,
   `failure-modes.toml`, and `acceptance.md` with a `date:` line —
   declared before any code exists (I4).
3. **Architecture** (L only): `docs/adr/`, `specs/<demand-id>/architecture.md`.
   *UI surface touched?* The design chain (`fde-design` skill) applies,
   proportional to size: M adds flow + wireframe before implementation;
   L adds PRD-grade spec, IA, and user validation. The approved wireframe
   is the build contract; design-QA baselines live in the eval suite (I1).
   No `design/foundation.md` yet → the first UI demand pays that
   bootstrap.
4. **Implementation**: code and its eval entries in the same change (I1).
   If the touched root has no suite at all, the demand includes
   bootstrapping the minimal one (runner + first smoke eval). Never
   `--no-verify` — it only moves the same red to CI, later and public.
   When how to run or operate the system changes, README and runbook
   update in the same change — docs drift is drift (MNT-10).
5. **Review**: isolated, weight-ordered, findings in
   `reviews/<demand-id>/findings.toml`, fixed by implementation, never by
   the reviewer (I3). Two passes by the same isolated role: adversarial
   (probe until it breaks — finding cites the probe) and heuristic (judge
   attributes verified_by heuristic against their principle catalog in
   `.fde/spec/` — finding cites the principle, I8).
6. **Promotion** (M/L): `promotions/<demand-id>/decision.md` against the
   declared acceptance criteria.
7. **Gate**: `python3 bin/fde/verify.py --all` — the same one CI runs.

Handoff between steps is by the artifacts named above, never by
continuing the same conversation thread (I7).

## Scrum mode — when `[scrum]` is enabled

The cadence layer above the demand loop. Defaults shift: an idea or pain
mentioned in conversation becomes an evidence-labeled backlog item
(`opinion < usage-data < user-test < production`), not an immediate
demand. The user's attention is spent in two sittings — planning (dated
sprint goal + selection in `sprints/S-N/goal.md`) and review + retro
(increment inspected, backlog reordered, process findings recorded).
Between them, demands run the loop without interruptions. "Fix it NOW"
bypasses the backlog but is recorded as unplanned and surfaces at the
retro. No dated goal, no sprint; no retro, no next sprint (`--gate
scrum`). Detail: `fde-scrum` skill.

## Voice — the kernel is infrastructure

The kernel is plumbing, not the protagonist. Do not narrate it, praise
it, or argue that "the process was worth it" — and do not make it the
subject of your reports.

- Report the change in the domain's terms: what changed, the evidence it
  works, what remains open. If a review finding altered the outcome,
  state the finding — not the virtue of the process that produced it.
- Process metadata (size, roles, rounds, gate result) is one status line
  at the end: `FORWARD: M · adversarial 2r (1 blocking, fixed) · gate ✓`.
  The full record already lives in the artifacts (specs/, reviews/,
  promotions/) — that is what they are for.
- The kernel earns more than one line in chat only when: the gate blocked
  something (say which invariant and the fix), or a decision is genuinely
  the user's to make.

## Detail

Per-step procedures live in the kernel's `skills/` (Agent Skills format,
portable across tools; installed at `.claude/skills/` for Claude Code).
This file is deliberately thin: Codex truncates AGENTS.md at 32 KiB
without warning. Where this summary compresses a rule, the skill's
definition governs. Never escalate kernel-interpretation questions to the
user mid-demand — resolve from the skill, take the stricter reading if
still torn, and flag the ambiguity as kernel feedback afterwards.
