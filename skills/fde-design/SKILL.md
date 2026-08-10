---
name: fde-design
description: The design discipline for demands with a UI surface — foundation, flow, information architecture, wireframe, build rules, design QA, and user validation, proportional to triage size. Use whenever a demand creates or changes screens, flows, navigation, or user-facing text; when a project's design foundation is missing or drifting; when the user asks for a wireframe, mockup, redesign, UX review, or says a screen "doesn't look professional". Absorbs the discontinued prancheta suite into the kernel.
---

# fde-design

Design under the kernel follows the same doctrine as everything else: the
artifact is the contract, the review cites its principle (I8), and the
empirical checks live in the eval suite (I1). Phases scale with triage
size; artifact-quality violations reopen the phase — never patch the
symptom in code.

## What each size demands (UI surface touched)

| size | design phases | alternatives required |
|---|---|---|
| XS / S | build within the foundation, design QA | none |
| M | + flow and wireframe before build | 2, from distinct lenses |
| L | + PRD-grade spec, information architecture, user validation | 3, from distinct lenses |

## The two diamonds

Design alternates: **diverge, then converge — twice.** The first diamond
is the problem space (discovery → a stated problem); the second is the
solution space (alternatives → one chosen design). The rule that makes it
real: **never converge without having diverged, and never diverge without
a stated problem.**

This is enforced, not requested. The second diamond produces an artifact
— `specs/<demand-id>/design/alternatives.md` — and the **`divergence`
gate** (`python3 bin/fde/verify.py --gate divergence`) fails any M/L
demand that has a design surface without it, or whose alternatives share
a lens, lack a hypothesis, or record no discard. Instructing a model to
"explore alternatives" is the class of intervention the research showed
does not hold (ADR-0011, ADR-0012), so the discipline lives in a file the
gate can read.

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

Before generating anything, restate the problem as **"How might we…"** in
at least two ways, and name the framing you chose and why. The reframe is
where an extraordinary solution comes from; the render is not. A flawless
solution to the unquestioned problem statement is a well-drawn wrong
answer.

Example: "the export screen is slow" reframes to *HMW make waiting
unnecessary?* (background job + notify) · *HMW make the wait productive?*
(stream partial results) · *HMW avoid the export entirely?* (share a live
link). Those are three different products, not three layouts.

### The five lenses (alternatives must come from distinct ones)

Each alternative is generated from a different lens. **Alternatives that
share a lens count as one** — three variations of the same layout is one
idea in three costumes, and satisfies nothing.

| lens | the question it forces |
|---|---|
| **subtract** | which step, field, or decision can disappear entirely — can the system infer it? |
| **invert** | flip who acts or when: system-first instead of user-first, push instead of pull, after instead of before |
| **analogous** | which other domain solved this job well, and what would borrowing its pattern look like here? |
| **constraint-first** | design for the worst case (slow network, 10k rows, the error path, one hand) and let the happy path fall out |
| **object-first** | reorganize around the domain object instead of the task sequence |

Each alternative carries a **one-line hypothesis** (what it bets improves,
for whom). Converging, record what each discarded alternative **traded** —
the discard is evidence, and it is what makes the choice auditable
instead of invisible.

## Foundation — the suite of the design domain

Project-level artifacts, versioned at `design/`:

- `design/product.md` — what the product is (and is NOT); the quality-bar
  sentence every screen is judged against; personas (role + what they do
  + what each demands of the UI); register (operational / editorial /
  consumer, one per product); 3–6 ORDERED tie-breaking principles;
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

## Information architecture (L)

Fit the existing map before creating structure. New route only for a
place worth linking; tab = facet of the same object; section = same-task
content; in doubt, fewer surfaces. Object map with attributes at the
cardinality-correct level (DOM-1), states → screen states with a visible
trigger per actor, invariants declaring where they are enforced (UI, API,
DB). One primary action per screen; empty states teach. The decided
nomenclature is law downstream. Artifact: `specs/<demand-id>/design/ia.md`.

## Wireframe — the build contract

Grayscale plus one blue for the single primary action. Real microcopy —
lorem ipsum hides exactly what the wireframe must reveal. Realistic
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
  unimplemented state. Approved microcopy is contract — a divergent
  label is a High finding.
- Clean console is part of the gate: zero errors and warnings on the
  routes under test. A UI change never viewed in a real browser is a red
  flag — unit tests do not test rendering.
- Race probe: rapid-toggle the interaction five times — one DOM
  instance, no duplicated requests. Touch targets ≥ 44px; text survives
  200% zoom.

## User validation (L, or whenever the premise is a bet)

Value before usability — impeccable usability on an unwanted feature is
waste (fake door kept ethical; Sean Ellis >40% = strong signal). Tasks
are scenarios, never instructions, and never contain words visible in
the UI. 5 participants per profile; fix between sessions; stop at
saturation. Severity is 0–4 by frequency × impact × persistence. The
chain observation → finding → change must be auditable. Synthetic users
generate hypotheses and tasks, never findings — stamp their artifacts
"[synthetic — not evidence]".

## Findings and reopening

Product findings cite the I8 catalogs (USE-*, DOM-*, MNT-5) in
`reviews/<demand-id>/findings.toml`, like any finding. A finding about a
wrong model or structure reopens flow/IA/wireframe — a string patch on
the screen is treating the symptom. Conclusions are labeled by evidence:
[observed] / [expert-inferred] / [human evidence] — simulation is never
promoted to human evidence.
