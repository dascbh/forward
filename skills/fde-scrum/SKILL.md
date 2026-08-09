---
name: fde-scrum
description: The cadence layer above the demand loop — backlog with a product goal, sprints with a goal, review and retro as the user's two sittings, continuous discovery feeding evidence-labeled items. Use when [scrum] is enabled in fde.config.toml, when the user mentions sprint, backlog, planning, discovery, review, retro, or product goal, when they ask to "turn on scrum mode", or when an idea arrives that should be captured rather than built immediately.
---

# fde-scrum

The mode changes defaults; it does not add ceremony per demand. Underneath
every backlog item, the demand loop runs exactly as always — triage, spec,
implementation, review, gate. Scrum mode decides WHAT enters and WHEN the
user is consulted.

## Artifacts and their commitments (I4's pattern, three altitudes)

| artifact | commitment | rule |
|---|---|---|
| `backlog.md` | product goal, dated | one goal at a time; reached or abandoned → declare the next |
| `sprints/S-N/goal.md` | sprint goal, dated | declared BEFORE the sprint's first demand starts |
| increment | the DoD that already exists | invariants + acceptance + `verify --all` — an exit code, not a wiki page |

Traceability chain: product goal → sprint goal → demand → acceptance →
eval. Any link without the one above it is orphan work.

## Turning the mode on (once)

Add `[scrum] enabled = true` to fde.config.toml. Ask ONE question: "what
is the product goal right now?" (one sentence). Create `backlog.md` with
`goal:` and `date:` in the header. From then on the gate enforces the
cadence (`--gate scrum`).

## Capture — the default shift

An idea, pain, or "seria bom ter X" mentioned in conversation becomes a
backlog item, not an immediate demand. One-line acknowledgment, nothing
more. Each item carries: hypothesis (what value, for whom), **evidence
label** — `opinion < usage-data < user-test < production` — and a rough
size. Refinement is continuous: re-order and re-label whenever new
evidence lands; never a meeting.

## Discover — a push, not a phase

`/fde-scrum discover <topic>` (or "investiga X"): research the code,
usage data, or a user-validation plan (fde-design's validation doctrine).
Raw material goes to `discovery/`; the distilled result updates the
item's evidence label in the backlog. Discovery never blocks delivery —
it upgrades the label the user sees at planning.

## Plan — the user's first sitting

Present the backlog ordered, with hypothesis, evidence, and size visible
— selecting an `opinion` item is a declared bet, not an accident. Propose
a sprint goal (one sentence). The user adjusts and approves. Write
`sprints/S-N/goal.md` (dated) with the selected demands, each with one
line: "serves the goal because…". The kernel labels evidence; it never
blocks a value choice — the product owner is the user, and that is not
delegable.

## Execute — no interruptions

Run each demand through the demand loop without consulting the user,
except for decisions that are genuinely theirs. A demand added mid-sprint
must justify itself against the goal or wait. **Exception route**: "fix
it NOW" bypasses the backlog, runs immediately, and is recorded in
goal.md under `## Unplanned` — it surfaces at the retro, uncommented.

## Close — goal or batch, never the calendar

The sprint closes when the goal is reached or the batch is exhausted,
whichever first. Then call the user for the review — proactively.

## Review — the user's second sitting

Present the increment in the domain's terms with its evidence (voice
rule: the work, not the process). The user inspects and reorders the
backlog — that reordering is the review's real output. Write
`sprints/S-N/review.md`: what shipped, evidence, backlog changes.

## Retro — without it, the next sprint does not open

Three questions, answered with the sprint's artifacts as evidence:
1. What cost more than it returned? (ceremony friction, rework)
2. What did the gate catch — and what did it let through?
3. What changes? — each answer becomes a config change, a backlog item,
   or a kernel demand (`FWD-*`). Process friction gets a destination,
   not a chat complaint.

Write `sprints/S-N/retro.md`. The gate blocks a new sprint while the
previous one lacks it.

## Voice

Everything here is plumbing. Status is one line:
`FORWARD: S-003 · 2/3 demands · gate ✓`. The artifacts carry the rest.
