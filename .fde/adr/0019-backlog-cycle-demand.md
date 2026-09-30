# ADR-0019 — Backlog, cycle, demand: plan once, derive down

date: 2026-09-29
status: accepted (owner, 2026-09-29)
superseded in part: rule 5's split clause, by ADR-0022 (a demand is one goal; the layer marks files); rule 9's "only one cycle runs", by ADR-0024 (small cycles run in parallel)
amended: 2026-09-29 — rule 9 states named by meaning and writer: planned is specified and awaiting sign-off (written by fde-spec), running is signed off (reviews/C-5 F2)

## Context

`discovery/sharpen-2026-09-29.md` measured the loops that remain after
ADR-0018. Each of them comes from a decision that has no single place or
moment:

- The owner is consulted mid-demand: 41 commits, and DEM-025/026 waited
  about 19 h.
- Acceptance is amended after construction: 51 commits, and DEM-027 went
  through 9 versions in 9 h.
- One decision is kept in an ADR, in `architecture.md` and in
  acceptance: 107 docs-only commits.
- Promotion turns into a hidden review round: 15 of 18 promotions were
  conditional.
- Non-blocking findings became cycle work under 0.17.0.

The demand is the unit that plans, decides architecture, gets promoted
and gets deployed. So each of those decisions comes up again inside every
demand.

## Decision

Three levels. Each one derives from the level above it.

```
BACKLOG  ideas and new facts; never a commitment
   │  the user picks
CYCLE    full planner: spec, threat model, dated acceptance, ADRs, demand list, deploy plan
   │  the user signs off once, here
DEMAND   quick planner: one-page spec citing the cycle's criteria and ADRs by id
```

|  | Cycle | Demand |
|---|---|---|
| Plans | spec, threat model, dated acceptance criteria (I4), demand list | one page, derived; decides nothing new |
| Architecture | decided at cycle sizing; ADRs name the demands that realize them | conforms to its ADRs; never amends them |
| Verifies | architecture review of the whole, plus what the touched layers require (rule 5), promotion (I5) | unit tests, code review, ADR conformance, plus its layer's check (rule 5); 1 round |
| Ships | promotion + deploy, following the deploy plan | merge to main behind the gate (I1) |
| New fact | backlog | backlog, always |
| Closes when | criteria met with integration evidence, deployed | gate green, no blocking finding |

Rules:

1. **A new fact goes to the backlog.** It does not become a fix, an
   amendment or a question. The only exception is a fact that
   invalidates the demand's own ADR or criteria. In that case the demand
   stops and the cycle replans; replanning is the only other point where
   the user is asked.
2. **What the cycle owns** is its declared criteria and the blocking
   findings. A non-blocking finding goes to the backlog by default. This
   replaces the 0.17.0 wording "concluded means fixed, or declined by
   the user".
3. **Size moves to the cycle.** XS/S/M/L sets the depth of the planner
   and the number of cycle review rounds. A demand has a fixed ceiling of
   about 300 production lines, and it is split at planning, not at
   review.
4. **Merge per demand; promotion and deploy per cycle.**
5. **Every demand has one layer: `front`, `back` or `infra`.**
   - `front` is the interface: screens, flows, user-facing text.
   - `back` is the API, domain logic and data access.
   - `infra` is IaC, roles, pipelines and runtime configuration.

   The layer sets what gets verified and where it goes in the deploy
   plan:

   | layer | demand verifies | cycle adds, only when a demand of this layer is in it | deploy step |
   |---|---|---|---|
   | infra | plan diff (e.g. `cdk diff`), policy check | live checks after the infra step | 1 (expand, backward-compatible) and 4 (contract, if any) |
   | back | unit + contract tests | integration tests across the cycle's demands | 2 |
   | front | unit + design QA against the approved wireframe | usability: walkthrough, user test | 3 |

   A backend-only cycle runs no walkthrough. A cycle that changes the
   interface always runs one.

   A change that spans layers is always split at planning, however small
   it is. For example, an API field and its screen label become one
   `back` demand and one `front` demand. There is no size exception:
   small demands are cheap, and a rule without exceptions is easier to
   follow (owner, 2026-09-29).

   Each deploy step has:
   - its own verification;
   - its own rollback;
   - a note if it is irreversible (migration, deletion, external side
     effect). An irreversible step is never bundled with a reversible
     one.

6. **The ADR is the only home of a decision.** The acceptance and the
   demand specs cite it by id. `specs/<demand>/architecture.md` is
   removed.

7. **Approval belongs to the cycle.** The user signs off `plan.md` once.
   That sign-off is inherited by:
   - every demand, and its merge;
   - `deploy.md`, including the irreversible steps it lists and marks.

   Promotion is the promotion role's decision against the plan's
   criteria, not a question to the user. The deploy runs the plan step by
   step. When a step's verification fails, that step is rolled back and
   the cycle stops; the user is told the outcome, not asked beforehand.
   The only thing that returns to the user is a replan, triggered by a
   fact that invalidates the plan.
8. **The sign-off is the permission.** While a cycle runs, no tool call
   waits for a prompt, and there is no "destructive" exception. A harness
   judgment of what is destructive is opaque to the user and blocks work
   that the plan already assessed.

   Install and sync open every built-in tool in `permissions.allow`
   (SETUP §8.4, FWD-025; owner, 2026-09-29):
   - a project keeps the prompts with `[tooling] open_permissions = false`;
   - the user's `ask` and `deny` entries are never touched;
   - the kernel never changes the permission mode at runtime.

   An auto-mode classifier sits outside those settings and can still
   block. Working outside auto mode is the path that is not blocked.

   An agent that leaves the plan is contained by deterministic checks
   instead:
   - the role write-scope guard (`guard.py`) denies paths outside a
     role's scope and logs every decision to `.fde/guard-audit.jsonl`;
   - the gate runs on every commit and in CI;
   - every deploy step verifies and rolls back on failure;
   - the owner reads the outcome at close.

   The accepted trade-off: an action outside the plan is caught after
   the fact, not before.
9. **The panel (`fde-backlog`).** The user operates the backlog and the
   cycles from one skill:
   - see the backlog with stable ids (`B-<n>`);
   - group items into a draft cycle, new or existing;
   - open a cycle to see its demands, specs, ADRs, deploy plan, reviews
     and promotion;
   - **specify** a draft, which runs the planner and stops at the
     sign-off.

   Grouping is organization only: no spec and no commitment. A cycle's
   states are `draft` (grouped) → `planned` (specified, awaiting
   sign-off) → `running` (signed off) → `closed` or `abandoned`. The
   panel writes `draft`, `fde-spec` writes `planned`, and the
   orchestrating agent writes `running` with a `signed-off:` line.
   Several
   drafts may exist, but only one cycle runs. The panel is
   conversational, because specifying needs the agent anyway;
   `status.py --format json` feeds it.
10. **Layout.** A cycle is `cycles/C-<n>/` with `plan.md` (criteria and
    failure modes, both with ids, plus the demand list: id, layer, order,
    criteria met, ADRs followed), `deploy.md`, `review.md` and
    `promotion.md`. A demand is `specs/<id>/spec.md` (one page, citing
    ids) plus `reviews/<id>/findings.toml`. Per-demand `acceptance.md`,
    `failure-modes.toml`, `architecture.md` and `promotions/<id>/` are
    removed.

11. **Parallel by default, coordinated on a board.** The plan declares
    dependencies between demands (a contract, a file, a migration), not a
    sequence. Every demand whose dependencies are merged runs at once, in
    its own worktree. Stages overlap too:
    - one demand is reviewed while the next is built;
    - the cycle's integration checks are written from the plan's
      criteria while the demands are built.

    Parallel agents coordinate through `cycles/C-<n>/board.md`, which
    has one line per event:
    - claim;
    - contract change proposed;
    - blocked on;
    - decided.

    Agents may message each other directly to settle a question quickly.
    The outcome is always written on the board, because the board is the
    record (I7), not the conversation.
    - A decision inside the plan is taken by the agents and recorded.
    - A decision that changes an ADR or a criterion is a replan.

    Every merge rebases onto main and passes the gate. When two demands
    turn out to need the same file, the later one waits on the board; it
    is never merged blind. Parallelism stops only where it would break
    the build or a declared contract (owner, 2026-09-29).
12. **The cycle review judges the objective, not the tasks.** It never
    re-reviews a demand. It validates two things.
    - **Functioning:** every criterion of `plan.md` shown end to end on
      the integrated result. The checks come from the touched layers
      (rule 5): integration for back, usability for front, live checks
      for infra.
    - **Readiness:**
      - the deploy plan is complete, with each step's verification and
        rollback exercised where the project allows it;
      - the signals the criteria declare exist (I5);
      - the runbook and README match how the system now runs.

    The cycle's size sets the budget: 1 round at XS/S, and full + delta
    at M/L (ADR-0018). A client with no integration suite gets a minimal
    one from the cycle, covering its criteria only.
13. **Sprints are retired.** Backlog > cycle > demand is the cadence.
    `sprints/`, the sprint goal and the sprint gates are removed, and
    `fde-scrum` shrinks to the backlog format. Lessons go in three lines
    at most, in the cycle's `promotion.md` (`## What changes`), and from
    there into the backlog.
14. **Gates follow the level that owns the thing.**
    - Cycle: I4 (`plan.md` criteria dated before the first demand
      commit), promotion, I5, and traceability (cycle → demands → ADRs).
    - Demand: I1 (eval with every behavior change) and the review
      isolation checks (I2/I3).
    - Commit: RULE.

    This moves existing checks. It adds no new gate (ADR-0018).
15. **Migration.** A cycle open before this ADR finishes under the rules
    it opened with. Replanning it mid-flight costs more than it saves:
    headlabs C-2 completes DEM-036..038 under 0.17.0. At the first sync
    after this ADR ships:
    - each `## Next cycle` list moves into `backlog.md` with `B-<n>` ids;
    - the next cycle is the first one planned under this ADR.

## Consequences

- The user's attention is spent once per cycle, at the sign-off of the
  plan, and again only if a fact forces a replan. Demands, merge,
  promotion and deploy run without asking, with no tool prompts.
- Demands get faster: no ADR, no promotion, no acceptance of their own.
- Walkthrough and integration testing get a defined place: at the cycle, and
  only for the layers the cycle touches.
- A cycle deploys later than a per-demand flow. That is the price of
  verifying the whole before it ships.
