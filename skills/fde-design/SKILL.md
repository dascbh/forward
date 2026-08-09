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

| size | design phases |
|---|---|
| XS / S | build within the foundation, design QA |
| M | + flow and wireframe before build |
| L | + PRD-grade spec, information architecture, user validation |

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
