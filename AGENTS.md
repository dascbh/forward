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

## Demand loop — backlog > cycle > demand

Work runs on three levels, each derived from the one above; the rationale
is ADR-0019. Do not start writing code on request: a request enters the
backlog, and code starts only inside a signed-off cycle.

- **Backlog** (`backlog.md`) — ideas and new facts; never a commitment.
- **Cycle** (`cycles/C-<n>/`, `## Cycle`) — plans once: threat model,
  dated criteria, ADRs, demand list, deploy plan.
- **Demand** (e.g. `FWD-002`) — one page derived from the plan; it
  decides nothing new.

1. **Triage** the cycle. Size is set on the cycle, never on a demand.
   `score = min(3, surfaces) + (sensitive ? 2 : 0) +
   (irreversible ? 2 : 0) + (loc < 50 ? 0 : loc < 300 ? 1 : 2)`.
   All four inputs are judged for THIS cycle, never inherited wholesale:
   `surfaces` = how many of UI/frontend, API, data/schema, infra this
   cycle touches. `loc` = estimated lines of this cycle. `sensitive` =
   this cycle touches data of the class declared in `[triage]` (in a
   public/internal project: always false). `irreversible` = this change
   is hard to undo — migration, deletion, external side effect —
   with `[triage].reversibility` setting the posture. Unsure on either →
   true; torn between two sizes → take the larger.

   **RULE, checked mechanically, not estimated.** Categorically distinct
   from XS/S/M/L below, never a smaller XS: XS still runs full judgment
   in reduced form; RULE runs none (rationale: ADR-0015). A
   commit is RULE-eligible only when, checked post-hoc against what was
   actually committed — never claimed a priori: `[triage].data_class` is
   `public` or `internal`; `[triage].reversibility` is `reversible`; the
   commit's own added+deleted is under the declared `[triage].
   rule_lane_max_loc` (default `10`); no `[gate].eval_paths` file was
   deleted or shrunk. A merge commit, a commit touching a binary file, or
   any git failure while checking either is categorically ineligible too.
   I1's `eval-coverage` gate is completely unchanged
   and fully applies — RULE recognizes when it already covers everything
   there is to verify (`spec/dimensions/quality-attributes.toml`'s
   `verified_by` primacy: empirical, adversarial, heuristic), it does
   not exempt anything from it. Self-declare as the commit's first
   message line (`FORWARD: RULE — <one-line reason>`); the `rule-lane`
   gate re-verifies every claim against the real diff, every time.

   score ≤ 1 → **XS** · 2–3 → **S** · 4–6 → **M** · ≥ 7 → **L**.
   Size sets only the planner's depth and the cycle review rounds: 1
   round at XS/S, full + delta at M/L. At every size `fde-spec` writes
   `plan.md` (minimal at XS), a demand review is 1 round, and the cycle
   closes with a promotion. Announce the size in ONE line (e.g.
   `FORWARD: M — spec + impl + adversarial(2r) + promotion`), commit
   `plan.md` (`## Cycle` below), and stop at the sign-off.
   **Budgets, not minimums.** Rounds after the first are delta rounds
   (the fixes, not the whole artifact again) and are never extended.
   Timebox: XS 30 min · S 1 h · M 3 h · L 1 day. A demand whose real
   diff overruns its estimate is not re-split at review: the overrun is
   posted on the board and the demand proceeds; the cycle replans only
   if a criterion or an ADR changes. A new rule ships as instruction
   first; it becomes a gate only when usage-data shows the instruction
   failed.
2. **Plan** the cycle (`## Cycle`): `plan.md` carries a `## Threat model`
   (who the change contains, what is out of scope — it bounds what the
   review may block on), criteria and failure modes with ids, dated
   before the first demand commit (I4), and the demand list; `deploy.md`
   carries the deploy plan; decisions go to `docs/adr/` (M/L).
   An ADR is the only home of a decision. The plan and the demand specs
   cite it by id; a demand conforms to its ADRs and never amends them.
   A demand is at most about 300 production lines and has exactly one
   layer: `front`, `back` or `infra`. `front` is screens, flows and
   user-facing text; `back` is the API, domain logic and data access;
   `infra` is IaC, roles, pipelines and runtime configuration. A change
   that spans layers is always split, however small. Splitting happens
   at planning, not at review.
   *Inherited an undocumented system?* Before the first cycle, survey it
   (`fde-survey` → `discovery/survey.md`), every claim labeled
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
3. **Sign-off**: the owner signs off `plan.md`. Approval happens once, at
   plan sign-off, and is inherited by everything after it: every demand
   and its merge, promotion, and every step of `deploy.md`, the
   irreversible ones included. Only a replan asks the owner again.
4. **Build**: Demands run in parallel by default, coordinated on
   `cycles/C-<n>/board.md`. Every demand whose dependencies are merged
   runs at once, in its own worktree. Code and its eval entries land in
   the same change (I1). If the touched root has no suite at all, the
   demand includes bootstrapping the minimal one (runner + first smoke
   eval). Never `--no-verify` — it only moves the same red to CI, later
   and public. When how to run or operate the system changes, README and
   runbook update in the same change — docs drift is drift (MNT-10).
5. **Review the demand**: one round, isolated, weight-ordered: unit
   tests, code review, ADR conformance, and the layer's check — `infra`
   a plan diff and policy check, `back` unit + contract tests, `front`
   design QA against the approved wireframe. Findings go in
   `reviews/<demand-id>/findings.toml`, fixed by implementation, never by
   the reviewer (I3). Two passes by the same isolated role: adversarial
   (probe until it breaks — finding cites the probe) and heuristic (judge
   attributes verified_by heuristic against their principle catalog in
   `.fde/spec/` — finding cites the principle, I8). Blocking = critical/
   high, reachable inside the threat model, breaks a declared criterion —
   never weight alone. At most five findings per round. Budget spent with
   a blocker open → replan (`## Cycle`): the user narrows, declares the
   limit, or pauses; never one more round (`fde-review`).
6. **Merge**: Merge happens per demand; promotion and deploy happen per
   cycle. A demand merges when it is rebased onto main, `python3
   bin/fde/verify.py --all` (the same gate CI runs) is green, and no
   blocking finding is open.
7. **Review the cycle**: The cycle review judges the objective —
   functioning and readiness against `plan.md` — and never re-reviews a
   demand. Functioning: every criterion shown end to end on the
   integrated result, with the checks of the layers the cycle touches —
   integration for `back`, usability (walkthrough) for `front`, live
   checks for `infra`. Readiness: the deploy plan is complete, each
   step's verification and rollback exercised where the project allows;
   the signals the criteria declare exist (I5); runbook and README match
   how the system now runs. Budget: 1 round at XS/S, full + delta at M/L.
8. **Promote and deploy**: promotion, at every size, is
   `fde-promotion`'s decision against the plan's criteria, not a
   question to the user. The deploy plan runs infra-expand → back →
   front → infra-contract, and every step has its own verification and
   rollback. An irreversible step is marked and never bundled with a
   reversible one. A step whose verification fails is rolled back and
   the cycle stops; the user is told the outcome, not asked beforehand.

Handoff between steps is by the artifacts named above, never by
continuing the same conversation thread (I7).

## Cycle — plan once, derive down

A cycle is a directory `cycles/C-<n>/` (next free `n`), started from the
kernel's `templates/cycle/`:

- `plan.md` — header lines (`cycle:`, `state:`, `date:`, `size:`,
  `objective:`, `signed-off:`), `## Threat model`, criteria and failure
  modes with ids, and the demand list: id, layer, dependencies, criteria
  met, ADRs followed.
- `deploy.md` — the ordered steps, each with its verification and
  rollback, irreversible ones marked.
- `board.md` — one line per event: claim, proposes (a contract change),
  blocked-on, decided.
- `review.md` — the cycle review: functioning and readiness.
- `promotion.md` — the decision, and `## What changes` (three lines at
  most, each also entered in the backlog).

A demand is `specs/<id>/spec.md` plus `reviews/<id>/findings.toml`. The
spec is one page citing the plan's criteria and ADRs by id; a demand has
no acceptance, failure modes, architecture or promotion of its own.

A cycle moves `draft → planned (signed off) → running → closed`. Several
drafts may exist; one cycle runs at a time. `fde-spec` writes `state:
draft` and `state: planned`; the orchestrating agent writes `state:
running` at sign-off and `state: closed` or `state: abandoned` at close.
These header lines are the only edits a frozen plan takes.

A new fact always goes to the backlog — never a fix, an amendment or a
question. The one exception is a fact that invalidates the demand's own
ADR or criteria: the demand stops and the cycle replans. The cycle owns
its declared criteria and its blocking findings; everything else goes
to the backlog. A non-blocking finding is a backlog line; nothing is
fixed in-band (MNT-9) except a defect that blocks a declared task, fixed
and noted as such. A backlog line carries a `B-<n>` id, `(C-<n>)` and its
evidence (`opinion < usage-data < user-test < production`). Create
`backlog.md` on the first capture with a `goal:` line (or `goal: not
set`) and a `date:` line.

The board is the record (I7), not the conversation. Agents may message
each other to settle a question; the outcome goes on the board. A
decision inside the plan is taken by the agents and recorded; one that
changes an ADR or a criterion is a replan. When two demands need the
same file, the later one posts `blocked-on` and waits; it never merges
blind.

Gates follow the owning level: the cycle carries I4, promotion, I5 and
traceability; the demand carries I1, I2 and I3; the commit carries RULE.

The plan is frozen at sign-off. A cycle closes when its criteria are met
with integration evidence and it is deployed (or published, when the
project does): write `state: closed` and show the user the backlog
lines it added. `python3 bin/fde/status.py` shows the cycles and the backlog
(`fde-status`). A cycle opened before ADR-0019 (`cycles/C-<n>.md`)
finishes under the rules it opened with.

## Backlog

An idea, pain or request mentioned in conversation becomes a backlog
item, not a demand: one-line acknowledgment, nothing more. The owner
orders the backlog; the evidence label makes a bet visible, never
blocks it. "Fix it NOW" skips the backlog order, never the open cycle
(`## Cycle`): it becomes the next cycle's first demand. Sprints are
retired (ADR-0019); `sprints/` is history. With `[scrum] enabled =
true`, `--gate scrum` requires the backlog's `goal:` and `date:`.
Detail: `fde-scrum` skill.

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
