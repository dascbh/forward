# Design system lifecycle

date: 2026-09-30
status: specified — agent lifecycle and review contract
source: owner request; recovered conversation excerpt on discovery, consolidation and incremental revision

## Contract

`fde-design-system` accepts a product, repository or affected feature in
natural language. It discovers the state rather than requiring lifecycle
flags. The result is a usable, evidenced product convention: foundations,
components and semantics of use, with an adoption path. It is not a theme
picker, a component-library install, or permission to redesign every screen.

The shared stages, provenance, role scopes and sign-off rules remain in
`.fde/spec/product-pipeline.md`. `fde-design` remains authoritative for
bootstrap minimums, tokens, patterns, accessibility and design QA. This
contract adds DS-specific discovery and revision detail once, for both build
and inspect. It introduces no new role, state machine or verifier flag.

## Discover before choosing

Read existing foundations and client ADRs, package manifests, token sources,
styles, primitives, components, variants, routes and reference pages. Inspect
actual rendered usage, not documentation alone. Identify product register,
platform, users/jobs, glossary, theme support, responsiveness and accessibility.
Start with the affected surface and representative consumers; expand only
when shared semantics or conflicting implementations require it.

Record an inventory in `discovery/<objective>-design-system.md`:

| Inventory field | Evidence required |
|---|---|
| Source and authority | File/module path, Git revision, package/version if external; documented versus observed convention |
| Token layers | Primitive values, semantic aliases, consumers, raw-value exceptions and missing meanings |
| Components | Canonical primitive, variants, duplicate implementations, public API, state and interaction contracts |
| Product semantics | Register, vocabulary, object/action meaning, status meaning and density rules |
| Reference surfaces | Route/state/theme/viewport, realistic content volume, source and rendered evidence |
| Coverage and gaps | What was sampled, what remains unknown, mismatch/debt and affected consumers/map nodes where available |

Compare at least one reference surface to its code and foundation; cover each
critical state affected by the proposed change. Do not claim whole-product
coverage from one page. If live UI is unavailable, record the limitation and
schedule rendering validation; static inventory alone cannot prove parity.
External references are researched for a named uncertainty, with date,
platform fit and tradeoffs. A dependency is evidence of a kit, not a DS.

## Classify and select the smallest action

| State | Observable condition | Minimum action and exit |
|---|---|---|
| Absent | No coherent documented or observed foundation | Bootstrap with fde-design: product/register/glossary, semantic tokens, 5–8 primitives and one reference page; verify before new UI uses it |
| Implicit | Coherent recurring conventions exist in code but are not authoritative artifacts | Extract their meaning and consumers; document foundation and reference evidence; resolve uncertainty before officializing |
| Fragmented | Competing conventions disagree about the same meaning, state or component job | Compare consumers and legitimate differences; choose canonical semantics and an incremental compatibility/migration path |
| Explicit | Versioned foundation and kit declare usage contracts | Diff implementation against the pinned foundation; reuse it, correct drift or revise a demonstrated gap |

Classification can differ by subsystem. Record that boundary rather than
forcing a global label. A partial foundation is not absent, and inconsistent
usage does not automatically invalidate a sound explicit DS. Unknown evidence
is a gap, not a fifth state that silently authorizes a rewrite.

## Consolidate before officializing

For each difference, distinguish:

- **Implementation drift:** the foundation still fits the job; align the
  consumer with its current token/component/state contract.
- **Foundation gap:** the job is valid but no semantic token, variant or
  interaction contract serves it; propose a minimal extension.
- **Foundation defect:** the current convention demonstrably fails a declared
  criterion or named principle; revise it and list affected consumers.
- **Legitimate variation:** platform, register or domain meaning differs;
  document the boundary, not a false deduplication.

A consolidation record names current implementations, chosen semantic intent,
options/rejected tradeoffs, consumer impact and evidence. Never deduplicate
values solely because they share a color or pixel size: identical values may
encode distinct meanings; different values may legitimately serve one meaning
across themes/platforms. Normalize meaning first, then aliases and consumers.

Product decisions with architectural implications live only in client ADRs;
other foundation conventions live in the foundation. Plans cite decisions,
never copy them. Reuse the installed UI-pattern catalog and client patterns;
novelty requires a recorded tradeoff. Keep source-derived inventory separate
from the normative foundation so drift does not become a standard by accident.

## Establish the canonical client artifacts

Do not create a second DS directory or registry. Existing artifacts carry:

| Artifact | Content |
|---|---|
| `design/product.md` | Product boundary, users/jobs, register, quality bar, ordered principles and glossary/deny-list |
| `design/foundation.md` | Authority/source revision, token source and semantic intent, kit/variant table, reference pages, density/state rules, responsive/theme/accessibility contracts and drift/debt |
| `design/patterns.md` | Only recurring client patterns, using fde-design's existing fields |
| Client token/component source | Executable realization of the foundation using the project's existing stack and fetching conventions |

Each component contract states job, fits/fails conditions, variants, allowed
composition, required states, content rules, keyboard/focus/screen-reader
behavior and semantic tokens. Document loading/empty/error/disabled/selected
where applicable, plus recovery. Distinguish hidden actions from unavailable
actions and explain permissions without exposing restricted data.

Foundation tokens use primitive → semantic layers; components consume semantic
intent. Preserve state meaning across light/dark and non-color channels.
Use fde-design's accessibility floors, target/zoom checks and pattern contracts;
do not introduce different numeric standards here. Density derives from the
product register and realistic volume. A reference page exercises the kit in
an actual job, including failure states, not only a gallery of happy variants.

Route writes through existing scopes: fde-spec writes inventory and planning
under discovery/specs/cycles; fde-architecture writes client ADRs and design
contracts under specs; implementation realizes token/component source. Project
`design/**` is authored by the design skill's orchestrating agent, not by a
restricted role claiming new permission. Reviewers only write findings.
If a client's tool policy denies the canonical destination, stop that write
and report the exact policy; do not relocate the foundation or weaken the guard.

## Incremental revision and adoption

A revision is scoped to demonstrated need. Record:

1. Baseline foundation revision and affected contract; evidence/criterion or
   named principle supporting the change.
2. Compatibility: unchanged consumer API, additive variant/token, deprecation
   alias, or breaking semantic/API change; list consumers and map coverage.
3. Smallest migration: shared seam/foundation cycle if required, then vertical
   consumers; reserve one owner for hot files and use existing depends/files.
4. Acceptance evidence for both revised and retained consumers; theme/state,
   keyboard, responsive and realistic-volume coverage appropriate to risk.
5. Rollout/rollback: alias lifetime, migration sequence, how to restore the
   prior implementation and which compatibility measures must remain until
   all declared consumers migrate.
6. Debt: exception, reason, owner, consumer, revisit trigger/date and criterion
   for removal. Do not hide unfinished adoption behind a revised document.

Semantic or API changes require the appropriate client decision and cycle
plan; sign-off and replan follow the shared contract. A foundation revision
never retroactively changes a running cycle's criteria. Assess running consumers
on their pinned revision; plan adoption separately unless an invalidated
criterion forces replan. Git revisions version the DS; an existing published
package keeps its package versioning scheme. Do not add a second version store.

Retire aliases/components only after consumer search and declared adoption
checks find no remaining use within the claimed scope. Keep evidence of
unsupported or external consumers and compatibility limits. Trigger revision
from measured failure, recurring valid pattern, dependency/platform change
or observed accessibility/usage need; not from novelty or one decorative taste.

## Separate adherence verdict and evidence

The DS adherence gate is a review contract, separate from the five UI quality
and equivalent UX dimensions in the shared spec. Each changed consumer receives
pass/fail/unknown/not applicable with foundation revision, scope and evidence.
No aggregate score compensates for a failed declared criterion.

| Adherence check | Evidence |
|---|---|
| Tokens and kit | Consumer/source diff, raw-value and duplicate search with documented exceptions; correct semantic alias/variant, not just identical values |
| Semantics | Product glossary, status/action meaning, correct object/cardinality and allowed composition |
| Rendered parity | Approved reference/wireframe comparison across affected states, themes and viewports |
| Interaction/accessibility | Keyboard/focus/zoom, relevant APG contract, axe and recovery/race probes from fde-design |
| Adoption | Consumer list, migrations/deprecations, rollback and explicit debt compared to the declared revision scope |

Executable checks belong to client eval_paths; screenshot baselines change
only intentionally. Tool-neutral search diagnostics can suggest issues but
cannot by themselves decide semantic equivalence. Heuristic findings cite
existing I8 principles; empirical ones cite the failing probe, both with
existing review severity. Synthetic evidence is labeled and cannot establish
human comprehension. The existing verifier has no `--gate design-system`.

Before officializing, require discovery evidence, canonical contracts,
rendered validation for the claimed surfaces, migration/debt clarity and the
existing isolated review/promotion appropriate to the cycle. Unknown evidence
is never silently pass. Passing adherence cannot close a UI/UX failure.

## Completion record

Use a section in the existing cycle review, or the existing discovery artifact
for read-only inspection; no separate completion state/file is required:

```
DS state and scope: <observed classification and boundary>
Action: <bootstrap / extract / consolidate / correct drift / revise / reuse>
Foundation: <path and Git revision; predecessor if revised>
Evidence: <inventory, source, render/probe and findings references>
Adherence: <per-criterion verdicts; separate UI/UX review references>
Adoption: <migrated consumers, retained compatibility, debt and owners>
Open: <coverage gaps, revisit triggers and backlog references>
```

**Example — fragmented status badges:** inventory two kits and their consumers;
separate domain state from color, compare themes/non-color semantics and retain
legitimate platform variants. Decide canonical meaning, introduce semantic
aliases and migrate one vertical consumer at a time. Validate other consumers
before retiring old aliases; record exceptions, not a whole-product rewrite.

**Example — explicit DS, new bulk action:** keep current foundations; inspect
object/cardinality, selection states and keyboard behavior against existing
patterns. If a variant is missing, extend the component contract minimally,
pin the revision and validate affected consumers. A correct kit component with
poor action placement can pass DS adherence and fail UI action topology.
