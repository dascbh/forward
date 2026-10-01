# Unified product pipeline

date: 2026-09-30
status: specified — documentation and agent contracts; no new runtime gate
owner-request: feature/fda-unified-product-pipeline

## Purpose and compatibility

Turn an idea or an existing product into a justified, measurable vertical
slice. This is an orchestration contract over Forward, not a new workflow
engine. I1–I8, roles, triage, kernel ADR-0019, kernel ADR-0021, kernel ADR-0022 and kernel ADR-0024, backlog, cycle states,
review budgets and promotion remain authoritative. No new invariant,
parallel backlog, approval mechanism or scoring service is introduced.

`build` and `inspect` are agent commands exposed as `fde-build` and
`fde-inspect` skills, not shell executables. Neither authorizes deployment.
The owner's existing authorization applies; cycle sign-off remains the
boundary for implementation. Specifying this pipeline does not implement
new verifier flags. Existing gates still run through `verify.py --all`.

## Two entry points, one continuation

- **build** receives an outcome, user/job, constraints and known evidence.
  Discover the repository, existing product and reusable assets even for a
  new feature. An empty repository is an observed baseline, not permission
  to fabricate a domain or design system.
- **inspect** receives a product/feature and desired improvement. Run
  `fde-survey` for inherited-system uncertainty and `fde-map` for product
  structure. Sample operations manually, inspect real UI states, contracts,
  schema, telemetry and prior decisions. Distinguish observed behavior,
  inferred intent and missing evidence. Baseline findings before proposing
  changes; preserve working contracts and compatibility constraints.

Both continue through the same stages below. Scale depth with cycle size
and risk; small changes may use short sections citing existing artifacts.
Do not create an empty document for every stage. A backend-only objective
records UI/UX as not applicable with a reason, not a simulated UI review.

## Stage contracts and ownership

| Stage | Output and exit condition | Existing owner/tool |
|---|---|---|
| Request | `discovery/<objective>.md`: job, outcome, scope, constraints, evidence gaps, baseline and entry mode | fde-spec; triage each slice |
| Discovery augmentation | Same document: research, benchmarks, map references, assumptions and contradictions; unknowns have an investigation or explicit limitation | fde-survey, fde-map, fde-design |
| Hypotheses | Ranked alternatives: audience, causal bet, counter-hypothesis, falsification test, expected metric/guardrail, choice and rejected tradeoffs | fde-spec; fde-design divergence |
| Product spec | Requirements R#, negative scope, personas/jobs, outcome baseline, target and guardrail; criteria dated before construction | fde-spec; cycle plan |
| Domain + data model | Objects, vocabulary, cardinality, states, commands/events, invariants and enforcement, ownership, sources of truth, retention, migration/backfill and rollback constraints | fde-spec requirements; fde-architecture decisions |
| Architecture | Client ADRs: options, seams, contracts, dependencies, failure modes, security, observability, rollout and portability; map impact checked | fde-architecture |
| Backlog | One-line items pointing to the source; vertical cycles with disjoint files, foundation seams and depends; demand specs cite criteria and ADRs | fde-backlog, fde-spec, status --waves |
| Implementation | Signed plan; evals before changed behavior; implement within contracts; refresh evidence and affected maps | fde-implementation, fde-design |
| Deploy | Demand/cycle review, promotion against declared criteria, ordered rollout, verification and rollback; production outcomes feed backlog; the objective's lead time, request → last cycle closed, reported unasked (`status.py --flow`) | fde-review, fde-promotion; cycle deploy.md |

UX blueprint is authored with product requirements, before UI construction,
and reconciled with domain/architecture before sign-off. It describes actors,
jobs, task sequence, navigation/object structure, decisions, feedback,
permissions, errors, empty/loading, abandonment/resume, accessibility and
acceptance scenarios. Reuse `design/flow.md`, `ia.md`, `intended-model.md`
and wireframes; at XS/S a concise intended model and existing references
can carry the blueprint. M/L alternatives keep the existing divergence
format. UI is the realization of this contract, not the source of the job.

After UI construction, validate the realized journey against the blueprint
using client-runnable journeys, design QA, keyboard checks and walkthrough.
Human testing is required when the premise or comprehension risk needs it;
agent completion is not human comprehension evidence. Structural failures
reopen the owning flow/IA/wireframe; changed signed criteria require replan.

## Product Map is transversal

`docs/map/conventions.toml` and `docs/map/<feature>.md` remain the only
product-map infrastructure. Reuse the screen → component → API → handler →
rule → event → table/column graph for discovery, UX/domain alignment,
architecture impact, slice conflicts, review and production diagnosis.
Specs cite node IDs and source revision. Keep inferred links distinguishable
from declarations in `FDE-MAP:DECLARED`; never hand-edit generated edges.
Unsupported stacks and dynamic SQL are explicit coverage limits; supplement
with source-linked declarations or an adapter, never a second graph.

At inspect baseline and before planning, compare the graph to sampled code
paths. After relevant implementation, regenerate affected maps and run
`productmap.py --check`. The existing MAP gate is advisory: a warning is not
proof of freshness or completeness. If a critical acceptance path is
unmapped, resolve it or declare the coverage limit before accepting impact
analysis. Generated maps prove structure, not product intent or user value.

## UI quality: five mother metrics

Measure per critical surface, state, viewport and user job. Declare register,
reference, dataset volume and threshold before construction. There is no
universal numeric score or weighted average that hides a failed criterion.
A raw count is a diagnostic; a gate verdict needs evidence and a criterion
or named I8 principle from the installed quality catalog.

| Metric | Operational measure | Gate question and evidence |
|---|---|---|
| Information density | Relevant information/visible area; scan/task time at realistic volume; overflow and zoom behavior | Can the intended user find needed information within the declared bound without losing readability? Compare register/reference, screenshots and task probes. More density is not automatically better. |
| Semantic economy | Duplicate labels/concepts, unexplained terms, competing synonyms, text needed to identify an object/action | Is each term necessary, consistent with the glossary and comprehensible? Inspect real microcopy; task confusion or a cited vocabulary principle supports findings. Shorter is not automatically better. |
| Action topology | Primary actions per task, distance/order from context to action, navigation depth and recovery reachability | Are actions located at the correct object/cardinality and decision point, with one primary action per screen? Flow-to-UI parity and realistic task traces. |
| Visual hierarchy alignment | Order/emphasis/grouping of job-critical information versus intended reading/decision sequence | Does prominence match task priority and domain grouping across states? Annotated screenshots, focus/heading order and a cited hierarchy principle. |
| Interaction friction | Unnecessary steps, repeated input, context switches, errors, recovery effort and latency | Does the task stay within its declared effort and response bounds, including failure/resume? Browser journeys, timings and keyboard/race probes. |

**Design-system adherence is a separate gate.** Validate semantic token and
component reuse, variants, state semantics, glossary, theme, responsive and
accessibility contracts against the pinned foundation revision. Record
exceptions and migration debt with owner and expiry/revisit trigger.
Passing DS adherence cannot compensate for a poor task topology; passing UI
quality cannot excuse unexplained DS drift. Existing screenshot, axe,
console, wireframe parity, zoom and target checks remain required.

## UX quality: equivalent journey measures

| UX dimension | Baseline / measure | Acceptance evidence |
|---|---|---|
| Task effectiveness | Completion and correct domain outcome per actor/scenario, including error/resume | Journey assertions; observed human completion when validating discoverability |
| Cognitive economy | Decisions, terminology interpretations, recall burden, comprehension failures | Intended model and blind walkthrough; human observations or cited heuristic, clearly labeled |
| Journey topology | Steps, handoffs, dead ends, responsibility and recovery paths | Flow coverage; recipient context, notification/deadline and valid exits |
| Expectation/feedback alignment | Predicted versus actual state/result; feedback visibility and time | State transitions, latency checks, error messaging and walkthrough evidence |
| Effort and recovery | Time on task, repeated entry, error frequency, abandonment and recovery cost | Timed tasks, keyboard/accessibility probes, production telemetry with privacy bounds |

At planning, give each applicable dimension a criterion ID, population/job,
scenario, baseline (or explicitly unknown), target, counter-metric, method,
sample and decision rule. An unknown baseline requires measurement work;
do not invent numbers. Before UI, review blueprint coverage and assumptions.
After UI, record measured value, evidence revision and pass/fail/unknown/not
applicable separately for each criterion. Unknown is never silently pass.
Heuristic judgments cite USE/DOM or other existing principle IDs; do not
invent a parallel principle catalog. Review severity and blocking follow
`fde-review`, not a new metric-specific blocking policy. Unresolved blocking
findings stop promotion. Synthetic evidence is labeled as such.

These are review contracts executed through the existing empirical,
adversarial and heuristic pillars, not new `--gate ui` or `--gate ux` flags.
Executable checks belong in client eval_paths (I1/I6); heuristic findings
belong in existing findings.toml (I8), with probes/principles and severity.
Cycle review summarizes both contracts, their evidence and limitations.

## Design system lifecycle

`fde-design-system` follows `.fde/spec/design-system-lifecycle.md` for state
discovery, consolidation, canonical client artifacts, component semantics,
incremental revision/adoption and a separate adherence verdict. This shared
pipeline supplies its stage ownership, sign-off and provenance contracts;
fde-design supplies bootstrap minimums, token/pattern rules and design QA.

## Artifacts, provenance and versioning

Git is the version store. No separate artifact registry or lifecycle state
machine: use cycle draft/planned/running/closed/abandoned. Discovery lives
under discovery/, requirements under specs/, decisions under docs/adr/,
client foundations under design/, maps under docs/map/, evidence under
evals/ and reviews/, execution under cycles/. Roles retain their write scopes;
an orchestrator routes an artifact to its owner rather than broadening them.

Every substantive artifact records date, owner role, source paths/revisions,
criterion/requirement IDs, evidence class, assumptions, unresolved gaps and
superseded artifact if applicable. Research records URL/title, access date,
version/platform, excerpt or observation, relevance and limitations. Evidence
records script/probe and result, dataset/viewport/state, environment and SHA.
Keep secrets and participant identifiers out of versioned evidence.

Handoffs cite artifacts and revisions (I7). Pin requirements/foundation/map
references in the signed plan. Changed evidence updates reviews/board;
signed plans stay frozen. New scope enters backlog; invalidated criteria or
ADRs stop and replan. Refresh only affected contracts and evidence, retain
history, and distinguish observed, expert-inferred, human and synthetic.

## Running beside other sessions

An entry runs while other sessions build, review or deploy in the same
project. Without being told, it:

- works in a worktree of its own and commits only the paths it writes
  (`discovery/`, its report, its backlog lines) — never `git add -A`,
  never another session's board or deploy files;
- uses the connected browser without asking — the install allows the
  extension's tools (`mcp__claude-in-chrome`) — and opens tabs of its own
  (the extension's `tabs_create`), never drives a tab it did not open, and leaves out of its measures the data
  a deploy left for its checks (a folder or record named as test data);
- touches no production state: reading, clicking through and measuring
  only; a write it would need goes into the report as a proposal.

## What an inspection delivers

`fde-inspect` starts from `.fde/templates/discovery/inspect.md` and ends
with one report, `discovery/<objective>-inspect.md`
— baseline, the five UI metrics, the UX journey measures and the
separate DS adherence verdict, each with its evidence and coverage
limits — and its findings as backlog lines (worth work of their own,
`fde-backlog-format`). When the feature has no product map, it generates one first (`fde-map`,
`docs/map/<slug>.md`). It reads the suite's recorded run for the code it
inspects (`verify.py --status`) and runs a test only to prove a finding —
a fresh full run in a bare copy measures the copy, not the product. It
opens no cycle and builds nothing: a draft
cycle is grouped only when the owner asks, and signed like any other.

## Agent autonomy and internal criticism

Investigate code/history/telemetry and curated references before questions.
Research current primary documentation and representative benchmarks where
uncertainty warrants it; record dates, platform fit and transfer limitations.
Benchmarks inform a hypothesis, never become a copied requirement. Compare
existing solution, minimal change and distinct design alternatives when due.

Before implementation, record internal criticism: strongest counter-case,
unsupported claims, failure/recovery scenarios, accessibility, domain/data
contradictions, security and operational risks; resolve each or turn it into
an explicit limitation/measurement task. This self-check never substitutes
for isolated plan/code/cycle review (I2/I3). Research may generate backlog
ideas, not silently expand scope. Ask only for unresolved owner decisions;
otherwise choose inside the signed contract and record the tradeoff.

## Acceptance of this specification

- A build and an inspect example reach the same cycle/role/artifact contracts.
- UI/UX quality and DS adherence have separate verdicts with no invented
  automated enforcement or universal score.
- Product Map coverage limitations, provenance and regeneration are explicit.
- Bootstrap and incremental DS changes preserve existing ownership/review.
- Installed skills/spec copies are coherent; existing full test suite and
  verifier detect integration drift. No runtime behavior or flags are added.

## Worked paths

**Build a billing feature:** record job and evidence in discovery/billing.md;
research and falsifiable hypotheses; specify R# and UX blueprint; model invoice
states/cardinality and data ownership; architecture records ADRs and map
impact. Put shared schema/vocabulary in a foundation cycle and independent
vertical slices in dependent cycles. Sign the plans, implement with evals,
refresh billing map, review UI/UX and DS separately, promote and execute each
cycle's deployment checks/rollback. Billing privacy/risk affects triage.

**Inspect an existing export:** map screen → handler → tables, sample five
operations, record measured wait/recovery baseline and map gaps. Compare
faster synchronous export, background notification and removal of export.
Choose through falsification and tradeoffs, reuse vocabulary/foundation,
blueprint abandon/resume and domain events. Continue through the same product,
domain, architecture, backlog, signed cycle, implementation and deploy stages.
A new unrelated navigation complaint enters backlog, not the export diff.
