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

   **RULE, checked mechanically, not estimated.** Categorically distinct
   from XS/S/M/L below, never a smaller XS: XS still runs full judgment
   in reduced form; RULE runs none (*Noise*'s rule-vs-standard
   distinction — a high-volume, low-stakes decision becomes a
   deterministic rule with zero judgment; deliberate, multi-perspective
   judgment stays reserved for what is genuinely risky or novel). A
   commit is RULE-eligible only when, checked post-hoc against what was
   actually committed — never claimed a priori: `[triage].data_class` is
   `public` or `internal`; `[triage].reversibility` is `reversible`; the
   commit's own added+deleted is under the declared `[triage].
   rule_lane_max_loc` (default `10`); no `[gate].eval_paths` file was
   deleted or shrunk. A merge commit, a commit touching a binary file, or
   any git failure while checking either is categorically ineligible too
   — none of those can be mechanically known as "zero," so RULE defaults
   to never rather than guess.
   I1's `eval-coverage` gate is completely unchanged
   and fully applies — RULE recognizes when it already covers everything
   there is to verify (`spec/dimensions/quality-attributes.toml`'s
   `verified_by` primacy: empirical, adversarial, heuristic), it does
   not exempt anything from it. Self-declare as the commit's first
   message line (`FORWARD: RULE — <one-line reason>`); the `rule-lane`
   gate re-verifies every claim against the real diff, every time.

   score ≤ 1 → **XS**: implementation, adversarial, 1 round ·
   2–3 → **S**: + spec · 4–6 → **M**: + promotion, 2 rounds, ADR ·
   ≥ 7 → **L**: all six roles, 3 rounds, ADR.
   Announce the sizing in ONE line (e.g. `FORWARD: M — spec + impl +
   adversarial(2r) + promotion`), commit the cycle file (`## Cycle`
   below), then start.
   **Budgets, not minimums.** Rounds after the first are delta rounds
   (the fixes, not the whole artifact again) and are never extended.
   Timebox: XS 30 min · S 1 h · M 3 h · L 1 day. Re-size on the real
   diff before review: over twice the estimate or ~800 changed lines →
   split, don't review. A new rule ships as instruction first; it becomes
   a gate only when usage-data shows the instruction failed.
2. **Spec** (unless XS): `specs/<demand-id>/spec.md`,
   `failure-modes.toml`, and `acceptance.md` with a `date:` line —
   declared before any code exists (I4). One page each; `spec.md`
   carries a `## Threat model` (who the change contains, what is out of
   scope) — it bounds what the review may block on.
3. **Architecture** (L only): `docs/adr/`, `specs/<demand-id>/architecture.md`.
   *Inherited an undocumented system?* Before the first demand, survey it
   (`fde-survey` → `discovery/survey.md`): how it runs, its real
   boundaries, what the history shows, the seams, the decisions no ADR
   records, the risk, and what stays unknown — every claim labeled
   `[observed]`/`[inferred]`/`[to confirm]`. A greenfield project owes
   nothing.
   *UI surface touched?* The design chain (`fde-design` skill) applies,
   proportional to size: M adds flow + wireframe before implementation;
   L adds PRD-grade spec, IA, and user validation. The approved wireframe
   is the build contract; design-QA baselines live in the eval suite (I1).
   No `design/foundation.md` yet → the first UI demand pays that
   bootstrap. **Diverge before converging**: at M/L, reframe the problem
   ("How might we…", ≥2 framings) and produce alternatives from DISTINCT
   lenses — subtract, invert, analogous, constraint-first, object-first
   (M: 2, L: 3; alternatives sharing a lens count as one) — recorded in
   `specs/<demand-id>/design/alternatives.md` with each hypothesis, what
   each discard traded, and the choice. The `divergence` gate enforces
   it. Patterns are chosen from the curated base in
   `.fde/spec/references/ui-patterns.toml`; novelty is a declared cost.
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
   `.fde/spec/` — finding cites the principle, I8). Blocking = critical/
   high, reachable inside the threat model, breaks a declared criterion —
   never weight alone. At most five findings per round. Budget spent with
   a blocker open → the user narrows, declares the limit, or pauses
   (`## Cycle`); never one more round (`fde-review`).
6. **Promotion** (M/L): `promotions/<demand-id>/decision.md` against the
   declared acceptance criteria.
7. **Gate**: `python3 bin/fde/verify.py --all` — the same one CI runs.

Handoff between steps is by the artifacts named above, never by
continuing the same conversation thread (I7).

## Cycle — one request, run to the end

A cycle is one request from the user: one or more demands run together.
Before the first behavior change of a request, write and commit
`cycles/C-<n>.md` (next free `n`) with an `objective:` line, a `demands:`
line (id and size each), and two sections: `## Tasks` (what this cycle
does, nothing else) and `## Done when`.

`## Done when` carries one line per demand, marked when that demand is
done, and the cycle's own items: always declared-before (this file
precedes the code) and backlog-captured (the backlog lines this cycle
added, shown at close); regression-proven (tests red before, green after)
when the cycle changes behavior; review-rounds (the size's budget spent,
no blocking finding open) for every sized demand; add promotion only for
M/L, and deploy or publish only when the project deploys or publishes. A
RULE commit (`fde-triage`) needs no cycle.

One cycle is open at a time, and it runs to the end: no other cycle opens
while any done item is `[ ]`. Each item ends `[x]` (met) or `[-]`
(declined by the user, with the date and reason). A new request that
arrives mid-cycle goes to `backlog.md`, not to a new cycle — "fix it NOW"
included: it starts when the open cycle closes, or at once if the user
abandons the open cycle. The only way out before the end is the user
abandoning the cycle in so many words: add `abandoned:` to its header
lines with the date and the user's reason and mark unmet items `[-]`.
The agent never proposes it to start other work; it names it only as one
of the user's options when a review budget is spent with a blocker open
(step 5).

What belongs to the cycle's request is concluded in the cycle: a review
finding on its changes, a residual of its demands, a defect its objective
owns. Concluded means fixed, or declined by the user — a declared limit, a
narrowed cut, or a paused demand (step 5, `fde-review`), its done line
marked `[-]` — never deferred by the agent to a later cycle; a cut or a
paused demand enters `backlog.md` as a new idea. Anything else found during the cycle
goes to `backlog.md` as one line carrying `(C-<n>)` and its evidence, and
is never fixed in-band (MNT-9) — the one exception is a defect that
blocks a declared task, fixed and noted as such. The backlog holds ideas
and discoveries, not commitments; create it on the first capture with a
`goal:` line (the user's product goal, or `goal: not set`) and a `date:`
line, so `[scrum]` adopts it unchanged; evidence follows `opinion <
usage-data < user-test < production`.

The declaration is frozen after the first behavior commit except for
marking done items. Ask the user before widening `## Tasks`; the answer
is a backlog line, not an edit. Under `[scrum]`, a sprint holds several
cycles, one after another.

At close no done item is `[ ]`: add `closed:` to the header lines and
show the user the backlog lines this cycle added — the user chooses the
next request from the backlog. `python3 bin/fde/status.py` shows the open cycle and the backlog
(`fde-status`). This is an instruction, not a gate (ADR-0018): it assumes
a cooperative agent.

## Scrum mode — when `[scrum]` is enabled

The cadence layer above the demand loop. Defaults shift: an idea or pain
mentioned in conversation becomes an evidence-labeled backlog item
(`opinion < usage-data < user-test < production`), not an immediate
demand. The user's attention is spent in two sittings — planning (dated
sprint goal + selection in `sprints/S-N/goal.md`) and review + retro
(increment inspected, backlog reordered, process findings recorded).
Between them, demands run the loop without interruptions. "Fix it NOW"
skips the backlog order, never the open cycle (`## Cycle`), and is
recorded as unplanned; it surfaces at the retro. No dated goal, no sprint; no retro, no next sprint (`--gate
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
- The backlog lines a closing cycle added are domain content, not process:
  show them in full (`## Cycle`).

## Detail

Per-step procedures live in the kernel's `skills/` (Agent Skills format,
portable across tools; installed at `.claude/skills/` for Claude Code).
This file is deliberately thin: Codex truncates AGENTS.md at 32 KiB
without warning. Where this summary compresses a rule, the skill's
definition governs. Never escalate kernel-interpretation questions to the
user mid-demand — resolve from the skill, take the stricter reading if
still torn, and flag the ambiguity as kernel feedback afterwards.

The artifacts form a provenance graph joined by demand-id; `fde-graph`
queries and mines it (`--demand`, `--central`, `--recurring`) and the
`traceability` gate keeps it connected. It is evidence derived from files,
not a database — the kernel adds no index or graph store (ADR-0010).

Long-term decay is measured, not assumed (`fde-erosion`, ADR-0011):
`erosion.py` reports the clone ratio, add/delete ratio, and batch size,
and the opt-in `[erosion]` budget gates them — because the evidence shows
instruction alone does not stop the rot; only measurement and review do.
Every metric reads ONE population: the roots `[gate]` declares, minus the
copies `[erosion] generated_paths` declares, minus vendor. Retargeting
`[gate]` retargets decay measurement; declaring no roots measures
everything. A threshold with nothing to measure reports "not measured",
never "within budget".
