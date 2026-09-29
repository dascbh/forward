# ADR-0019 — Backlog, cycle, demand: plan once, derive down

date: 2026-09-29
status: proposed — open questions below are discussed before acceptance

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

## Open questions — to deepen before acceptance

- **Q1 — artifact layout.** Does `cycles/C-<n>/` become a directory
  (`plan.md`, `deploy.md`, `review/`, `promotion.md`)? Or does the cycle
  file stay flat and point at `specs/C-<n>/`?
- **Q3 — demand order and parallelism.** The plan gives the order.
  Can independent demands run in parallel worktrees?
- **Q4 — cycle review budget.** How many rounds per size? What does the
  integration test suite look like when the client has none?
- **Q5 — sprints.** With backlog > cycle > demand, is a sprint still a
  separate concept, or is a cycle the sprint?
- **Q6 — gates.** I4, TRACE and the promotion checks are per demand
  today. They move to the cycle; this changes gates, it does not add any
  (ADR-0018).
- **Q7 — migration.** How does an open cycle such as headlabs C-2 cross
  over? Does it finish under 0.17.0, or is it re-planned?

## Consequences

- The user's attention is spent twice per cycle: sign-off of the plan,
  and acceptance of the promotion. Replanning happens only when a fact
  invalidates the plan.
- Demands get faster: no ADR, no promotion, no acceptance of their own.
- Walkthrough and integration testing get a defined place: at the cycle, and
  only for the layers the cycle touches.
- A cycle deploys later than a per-demand flow. That is the price of
  verifying the whole before it ships.
