---
name: fde-triage
description: Sizes a demand and decides which roles and how many adversarial rounds activate. Use ALWAYS before starting any implementation work in a project under the kernel — a one-line change or a whole feature. Use when the user says the process feels too heavy for the size of the task, or asks to "skip steps". It is the legitimate path to reduce ceremony without relaxing criteria.
---

# fde-triage

If the full flow runs on a three-line change, the framework gets turned off
in week two. That is why sizing is a rule table, not common sense. Apply the
table; do not negotiate it.

## Inputs

- `surfaces` — how many surfaces the demand touches (UI, API, schema,
  infra…), 1–3+
- `loc` — estimated lines changed
- from `fde.config.toml` `[triage]`:
  `sensitive` = data_class in {personal, financial, health};
  `irreversible` = reversibility != reversible

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

Report the size, the active roles, and the plan before starting the work.

## What never scales

The invariants. At XS and at L, all seven apply equally. What varies is the
**boundary covered**, not the **criteria applied**.

When the user complains about process weight: apply the table and show the
reduced plan. When they ask to turn off the gate: explain that no key
exists, and that the path is shrinking the delivery scope until it fits the
standard — not the other way around.
