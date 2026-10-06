---
name: fde-design
description: The design chain for UI demands: foundation, flow, IA, wireframe, build rules, design QA, user validation. Use when screens, flows, navigation or user-facing text change, or the user asks for a wireframe, mockup, redesign or UX review.
---

# fde-design

The artifact is the contract, the review cites its principle (I8), and
the empirical checks live in the eval suite (I1). Phases scale with the
cycle's size; an artifact-quality violation reopens the phase — never
patch the symptom in code.

## Where each check runs (kernel ADR-0019 rule 5)

- A `front` demand: build within the foundation, design QA against the
  approved wireframe.
- At the cycle, only when the cycle has a `front` demand: flow, IA,
  wireframe and alternatives are planned before the sign-off; user validation and
  `fde-walkthrough` run at the cycle review. A backend-only cycle runs
  neither.

## What each size demands (UI surface touched; the cycle's size)

| size | design phases | alternatives required |
|---|---|---|
| XS / S | priority for the elements touched, build within the foundation, design QA | none |
| M | + priority, flow and wireframe before build | 2, from distinct lenses |
| L | + PRD-grade spec, priority, information architecture, user validation | 3, from distinct lenses |

## The two diamonds

**Diverge, then converge — twice**: problem space (discovery → a stated
problem), then solution space (alternatives → one chosen design). Never
converge without having diverged; never diverge without a stated problem.

The **`divergence` gate** (`python3 bin/fde/verify.py --gate divergence`)
fails any M/L demand with a design surface and no
`specs/<demand-id>/design/alternatives.md`, or whose alternatives share
a lens, lack a hypothesis, or record no discard (kernel ADR-0012).

### The artifact

`specs/<demand-id>/design/alternatives.md`, in this shape (the gate reads
the `Lens:`, `Hypothesis:`, `Traded:` and `Chose:` lines):

```
## How might we…
- HMW make waiting unnecessary?
- HMW make the wait productive?

## Alternatives
### A. Background job + notify
Lens: subtract
Hypothesis: removing the wait removes the abandonment it causes.
### B. Stream partial results
Lens: invert
Hypothesis: results-as-they-arrive beats a faster total.
Traded: gives up a single stable snapshot to review.

## Convergence
Chose: A — the wait is the problem, not its length.
```

### Reframe before you solve (the generative move)

Before generating anything, reframe: restate the problem as **"How might
we…"** in at least two ways, and name the framing you chose and why.

Example: "the export screen is slow" reframes to *HMW make waiting
unnecessary?* (background job + notify) · *HMW make the wait productive?*
(stream partial results) · *HMW avoid the export entirely?* (share a live
link). Those are three different products, not three layouts.

### The five lenses (alternatives must come from distinct ones)

Each alternative comes from a different lens. **Alternatives that
share a lens count as one.**

| lens | the question it forces |
|---|---|
| **subtract** | which step, field, or decision can disappear entirely — can the system infer it? |
| **invert** | flip who acts or when: system-first instead of user-first, push instead of pull, after instead of before |
| **analogous** | which other domain solved this job well, and what would borrowing its pattern look like here? |
| **constraint-first** | design for the worst case (slow network, 10k rows, the error path, one hand) and let the happy path fall out |
| **object-first** | reorganize around the domain object instead of the task sequence |

Each alternative carries a **one-line hypothesis** (what it bets improves,
for whom). Converging, record what each discarded alternative
**traded**.

## Foundation — the suite of the design domain

Project-level artifacts, versioned at `design/`:

- `design/product.md` — what the product is (and is NOT); the quality-bar
  sentence every screen is judged against; personas (role + what they do
  + what each demands of the UI); register (operational / editorial /
  consumer, one per product); 3–6 ORDERED tie-breaking principles,
  at least one of them a disclosure principle — what stays on screen and
  what is one click away (the product owner words it; principles that
  only say what to show make every screen show everything);
  glossary (term, meaning, grammatical gender) with per-term deny-list.
- `design/foundation.md` — token source path, primitive kit table,
  reference pages, density rules, state semantics, drift/debt log.

Tokens live in two layers (primitive holds raw values, semantic holds
intent); components use only semantic tokens. State colors are fixed
semantics (green ok, amber attention, red risk), never decorative, never
the only channel. Light and dark from day one; contrast at WCAG floors
(4.5:1 text, 3:1 UI). Drift hunt is executable: grep raw hex/px, named
colors, near-duplicates of kit primitives.

**Uncovered-root rule (same as I1's):** a UI demand in a project without
`design/foundation.md` pays the bootstrap first — register, tokens, a
5–8 primitive kit, one reference page, the file. No foundation, no build.

## Spec (L): PRD-grade, problem-first

Never mentions screens or buttons — solution talk goes back to the
problem. Mandatory: negative scope ("NOT in this version"), metrics with
a numeric baseline and a guardrail counter-metric, numbered requirements
(R#) in EARS form ("WHEN X, the system MUST Y") — R# is the traceability
thread flow, IA, and acceptance cite. No persona, no feature.

## Flow — before any screen

Start from domain events (past tense, on a timeline; event without a
command = automation; command without a screen = gap). Blocks are exactly
one of: screen, user decision, system action. Every arrow labeled; every
block has an exit. Happy path alone fails the gate: error, empty, and
abandon/resume paths are mandatory. A swimlane crossing is a handoff —
it needs notification, deadline, and what the recipient sees. Every
decision and error branch becomes an EARS criterion citing its R#.
Artifact: `specs/<demand-id>/design/flow.md` (Mermaid).

## Priority — before the hierarchy (any UI surface)

Without it, a screen is the sum of its requirements: each R# becomes a
block and the order of the spec's text becomes the order of the screen.
A client's screens came out exactly so — following the whole design
chain did not prevent it — and, generated again with this instrument,
put their main content 700–800 px higher and cut 60–70% of the fixed
text with no requirement lost. Nothing here removes a requirement: it
decides where and when each one shows. Artifact:
`specs/<demand-id>/design/priority.md`, cited by `ia.md` and the
wireframes; at XS/S, a short one for the elements the change touches.

**People and moments.** For each person of the spec who uses the screen:
when they open it (what they did before, what they do next), the verb
(what they must do there), the frequency, and the datum they look for
first. Then decide: the main person of the default state (the most
frequent, unless a reason is written); one focal point, everything else
lowered on purpose; and how each secondary person is served — by a visible, compact
element that shows the datum they look for first and opens the rest,
never by a control with no hint of what it hides. Write that datum as
the person's own question, and make the element answer it: a partner
reviewing a due diligence asks "what is missing, and what is a
priority?" — "42 pending on priority · View full summary" answers it;
"% OK per area" does not, and regenerated screens kept falling back to
such a generic figure until the question was written down.

**Priority map.** One row per element the spec asks for: element, R#,
person, frequency (daily, weekly, occasional, rare), consequence of not
seeing it (high, medium, low), and layer — from most to least visible:
header (title and at most one primary action), content bar (search,
filters, views), main content, on the object's row, on demand (dialog,
menu, panel, collapsed strip, help), off the screen. Rules:

- The order of the requirements in the text is not the order of the
  screen.
- Occasional use takes no fixed space above the main content.
- An agent's proposal sits with the object it is about, labelled, the
  human decision beside it — never a block of its own. Its provenance
  label and the request for a decision ("System proposal — confirm?")
  always stay visible: they are not spec prose, and USE-16 never cuts
  them (a regenerated screen reduced a proposed link to "85 points",
  and nothing said it awaited the lawyer's decision).
- Explanations, rules and limits live on demand, or inside the dialog
  where they are used (USE-16).
- Nothing repeats above the main content.
- At most four visible options per decision point.

**Disclosure with a cue.** What lives on demand — legal basis, origin,
criteria, explanations, a secondary person's detail — is one click away,
never permanent, and shows a visible cue of what it hides: a number, a
count, a label. Hidden content with no cue may as well not exist. Being
reachable is what auditability asks; being always on screen is not.
Never hide what the user needs to decide.

**Budget, declared and measured on the wireframe.** `priority.md`
declares each screen's budget, and design QA measures the rendered
wireframe against it before any code — in the browser, at 1440 × 900: blocks between the tabs (or header) and the
main content, words of fixed text outside the main content (titles,
tabs, control labels, column headers and numbers not counted), primary
actions per region, distance in px from the tabs to the main content,
and the text of a row in the main content. For list and table screens,
start from at most 2 blocks, 30 words, 1 primary action per region and
200 px — the values that held on the client's two list screens; an
editor, a document viewer or a form declares its own. The verdict is
against the declared budget, never a universal score. Mark the
wireframe for the measure: `data-fde="header"`, `data-fde="bar"`,
`data-fde="main"`.

**Completeness check.** Before the wireframe is handed over, list every state and action the
spec asks of the screen — each empty variant, loading, error, read-only,
conflict, the occasional actions — and mark each visible, reachable
(with the control that opens it) or absent. A list the spec enumerates
(failure causes, states, variants) is checked item by item, never as a
group — a regenerated screen kept "read failures" and lost one of its
eight causes. Each secondary person's question is checked too: its
answer is in the visible element. None
may be absent: a budget is met by moving things, never by dropping them.

## Information architecture (L)

Fit the existing map before creating structure. New route only for a
place worth linking; tab = facet of the same object; section = same-task
content; in doubt, fewer surfaces. Object map with attributes at the
cardinality-correct level (DOM-1), states → screen states with a visible
trigger per actor, invariants declaring where they are enforced (UI, API,
DB). The screen's hierarchy derives from `priority.md`, never from the order
of the R#s. One primary action per screen; empty states teach. The decided
nomenclature is law downstream. Artifact: `specs/<demand-id>/design/ia.md`.

## Wireframe — the build contract

Grayscale plus one blue for the single primary action. Real microcopy —
lorem ipsum hides exactly what the wireframe must reveal. Real means the
user's words for the next action, never the spec's (USE-16): no sentence that explains a rule, restates a criterion or an ADR, or
says what the system does behind the screen. Not prose, and never cut:
the provenance label of an agent's proposal and its request for a
decision. A rule the user must follow is designed as
behavior — a default, a disabled action with a reason of a few words,
inline validation; help text is one short sentence, only for a decision
the user makes. A client's screens carried 264 such sentences (median 11
words) — the project's spec prose, moved into the interface. Realistic
volume (20+ rows, long names): a layout that only works with little data
is a structure bug. Empty/loading/error variants for every data screen.
Cross-linked HTML; clicking through the flow is the acceptance test.
Accessibility is born here: focus order, heading hierarchy, APG pattern
per complex widget, a click alternative to drag. Fidelity by risk: lo-fi
answers layout and labeling; only a coded prototype answers
comprehension and density; only real code answers timing and keyboard.
Artifact: `specs/<demand-id>/design/wireframes/*.html`. Once approved it
is the contract — divergence during build reopens the wireframe, never
gets improvised in code.

## Five kinds in the base — do not confuse them

- **`[[system]]`** encodes *decisions*: which job, which convention, which
  states, which a11y contract. Study it to decide.
- **`[[framework]]`** encodes *scaffolding*: grid, utilities, markup. It
  decides **no job** — read its `does_not_decide` field, which is what you
  still owe after adopting it, and its `maintenance` line before you couple
  to it (MNT-2). A block library's variants are a starting point: take one,
  adapt it into the kit, delete the rest — a product with four hero
  sections is how the clone metric climbs (MNT-11).
- **`[[archetype]]`** is a whole page that recurs (sign-in, pricing,
  checkout, dashboard shell, landing, article, catalogue, not-found). It
  names the patterns it `composed_of` and, more usefully, `must_resolve`:
  the risks that appear only once the parts are combined — failure *after*
  the charge in checkout, the first run of a dashboard, the error that
  reveals which field was wrong in sign-in. Its `canonical` is
  documentation to study; its `examples` are frameworks that ship a
  scaffold — code to start from, never several of.
- **`[[pattern]]`** is one interaction job; **`[[directory]]`** is where
  to look when the base has nothing.

Start at the archetype when you are building a whole page — it hands you
the pattern list and the page-level risks in one read. **It does not
discharge the baselines**: every `baseline = true` pattern whose platform
covers your surface still applies, and archetypes deliberately do not
repeat them.

## Choosing the pattern (the curated base)

`.fde/spec/references/ui-patterns.toml` is the base: which design systems
are worth studying for what, and for each recurring job the canonical
implementations, the fit and misfit criteria, the states the pattern must
resolve, and its accessibility contract. Use it before inventing.

The order is deterministic: satisfy every **`baseline = true`** entry
whose platform covers your surface (obligations — empty state, error
recovery, primary navigation — never candidates competing for a job; a
web-only console owes nothing to a `mobile` baseline) → then name the
**job** and match on it → **exclude** entries whose platform does not
cover your surface (`all` always applies; the filter removes, it never
ranks) → among survivors, drop those whose `fails_when` describes your
case → study the **canonical** systems the entry names
(the base points; it never copies their code) → respect the platform
convention (`hig` on Apple, `material` on Android — deviating spends the
user's existing muscle memory) → resolve every state the entry lists →
implement the widget against its **APG** contract. If more than one
pattern still survives, the choice is a recorded decision naming the
trade, not a coin flip.

**Novelty is a declared cost, not a default.** If no entry fits, consult
the `[[directory]]` entries the base names — component.gallery for how
many systems implement a thing and what they call it, the design-system
galleries for breadth, designsystemsbrasileiros for pt-BR conventions the
global systems do not carry. Only after that is inventing a decision to
record, with what you are trading.

### Extending the base (client-side)

A pattern that RECURS in the project earns an entry in
`design/patterns.md` — the client's extension, never an edit to the
kernel's copy (that is drift). Same fields as the base, so the two read
alike:

```
## <pattern-id>
Job: <the user job it serves>
Platform: web | mobile | all
Canonical: <internal reference screen, or the external system studied>
Fits when: <the case that makes it right>
Fails when: <the case that makes it wrong>
States: <every state it must resolve>
A11y: <the APG pattern or the keyboard/SR contract>
```

Created on the first UI demand that needs it; read alongside the kernel
base at selection time. One entry per recurrence — never a speculative
catalog.

## Build rules (any size)

Discovery before markup: read `design/foundation.md` and 1–2 same-type
reference pages first. Reuse the kit before creating; no raw values —
missing token means stop and propose, not invent inline. Density belongs
to the register, not taste. Never break the shell. Every screen works in
light AND dark. Empty/loading/error always, in the UI language. Numbers
tabular. Data through the project's fetching layer, never a loose fetch.

## Design QA — the empirical pillar of UI (I1)

These checks live in `eval_paths` — they ARE the frontend eval suite:

- Playwright `toHaveScreenshot()` per critical route and state, light +
  dark + narrow viewport, baselines committed, tolerance small and
  explicit. Baselines change only consciously — an update in a PR
  without an intended visual change is a finding.
- axe-core per route, failing the build on critical/serious. Automated
  a11y covers ~half; a manual keyboard pass stays part of review.
- Parity diff against the approved wireframe: missing element, extra
  unapproved element, swapped order or grouping, divergent label,
  unimplemented state — and against `priority.md`: an element outside
  the map, or in another layer than the map gives it, is a finding. Approved microcopy is contract — a divergent
  label is a High finding. `python3 bin/fde/uiprose.py --changed` lists
  every explanatory sentence the change adds to the screens; each is
  judged against USE-16 (keep it only when it serves the user's next
  action).
- Clean console is part of the gate: zero errors and warnings on the
  routes under test. A UI change never viewed in a real browser is a red
  flag — unit tests do not test rendering.
- Race probe: rapid-toggle the interaction five times — one DOM
  instance, no duplicated requests. Touch targets ≥ 44px; text survives
  200% zoom.

### Browser-executed journeys

A journey end to end — not one route in isolation — is verified the same
way this section verifies everything else: execution, committed and
gated, never narrated. The artifact is a manifest at
`evals/journeys/<demand-id>/<slug>.journey.toml`, paired with a committed
Playwright script:

```toml
[meta]
id = "guest-checkout"
demand_id = "FWD-0XX"
requirements = ["R2", "R3"]          # the R# tokens from spec.md this journey verifies
script = "guest-checkout.spec.ts"    # the client-runnable artifact CI executes (I6)
authored_with = "claude-in-chrome"   # how the flow was discovered — never how it is gated
```

`authored_with` names how the flow was found (a live agent session
driving a real browser); it is never on the gated path. CI runs
`script`, always; an agent session never runs during promotion or CI
(I6).

## User validation (L, or whenever the premise is a bet)

Value before usability (an ethical fake door; a >40% "very
disappointed" score is a strong signal). Tasks
are scenarios, never instructions, and never contain words visible in
the UI. 5 participants per profile; fix between sessions; stop at
saturation. Severity is 0–4 by frequency × impact × persistence. The
chain observation → finding → change must be auditable. Synthetic users
generate hypotheses and tasks, never findings — stamp their artifacts
"[synthetic — not evidence]". An agent completing a planned journey
proves the path exists, never that an unprepared human finds it without
hesitation (USE-14); only a demonstrated friction (probe) or a cited
principle closes a usability_accessibility finding. The one admissible
synthetic claim — two blind runs sustain distinct interpretations — is
`fde-walkthrough`'s.

## Findings and reopening

Product findings cite the I8 catalogs (USE-*, DOM-*, MNT-5) in
`reviews/<demand-id>/findings.toml`, like any finding. A finding about a
wrong model or structure reopens flow/IA/wireframe — a string patch on
the screen is treating the symptom. Conclusions are labeled by evidence:
[observed] / [expert-inferred] / [human evidence] — simulation is never
promoted to human evidence.

## Unified product contract

Read `.fde/spec/product-pipeline.md` for the pre-UI UX blueprint, post-UI
validation, five UI dimensions, equivalent UX dimensions and separate DS
adherence verdict. Use fde-design-system for foundation discovery/evolution.
These extend this chain through existing evals and I8 findings, not new
verifier flags; phase depth still scales by the table above.
