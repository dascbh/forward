---
name: fde-triage
description: Sizes a demand and decides which roles and how many adversarial rounds activate. Use ALWAYS before starting any implementation work in a project under the kernel — a one-line change or a whole feature. Use when the user says the process feels too heavy for the size of the task, or asks to "skip steps". It is the legitimate path to reduce ceremony without relaxing criteria.
---

# fde-triage

If the full flow runs on a three-line change, the framework gets turned off
in week two. That is why sizing is a rule table, not common sense. Apply the
table; do not negotiate it, and do not interview the user about the formula
— estimate the inputs from the demand yourself and, if torn between two
sizes, take the larger.

## Inputs — all four judged for THIS demand

- `surfaces` — how many of the four surface kinds (UI/frontend, API,
  data/schema, infra) **this demand** touches — never the project's
  fixed count from install
- `loc` — estimated lines changed by this demand
- `sensitive` — **this demand** touches data of the class declared in
  `[triage].data_class`. The declaration is a ceiling: in a
  public/internal project, sensitive is always false; in a
  personal/financial/health project, judge whether the demand's paths
  read or write that data. Unsure → true.
- `irreversible` — **this change** is hard to undo once shipped: schema
  migration, deletion, external side effect, published artifact.
  `[triage].reversibility` sets the posture (a reversible project's
  demand is false unless the demand itself creates irreversibility).
  Unsure → true.

## Score and size

```
score = min(3, surfaces)
      + (sensitive ? 2 : 0)
      + (irreversible ? 2 : 0)
      + (loc < 50 ? 0 : loc < 300 ? 1 : 2)
```

| score | size | active roles | adversarial rounds | ADR |
|---|---|---|---|---|
| ≤ 1 | XS | implementation, adversarial | 1 | no |
| 2–3 | S | spec, implementation, adversarial | 1 | no |
| 4–6 | M | spec, implementation, adversarial, promotion | 2 | yes |
| ≥ 7 | L | all five | 3 | yes |

Announce the result in one line — size, roles, rounds — and start. The
table is deterministic; the reasoning behind the score does not belong in
chat.

## What never scales

The invariants. At XS and at L, all eight apply equally. What varies is the
**boundary covered**, not the **criteria applied**.

When the user complains about process weight: apply the table and show the
reduced plan. When they ask to turn off the gate: explain that no key
exists, and that the path is shrinking the delivery scope until it fits the
standard — not the other way around.
