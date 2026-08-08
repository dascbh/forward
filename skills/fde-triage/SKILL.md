---
name: fde-triage
description: Sizes a demand and decides which roles and how many adversarial rounds activate. Use ALWAYS before starting any implementation work in a project under the kernel — a one-line change or a whole feature. Use when the user says the process feels too heavy for the size of the task, or asks to "skip steps". It is the legitimate path to reduce ceremony without relaxing criteria.
---

# fde-triage

If the full flow runs on a three-line change, the framework gets turned off in week two. That is why sizing is code, not common sense.

```bash
python bin/triage.py --surfaces 2 --loc 120
```

## What scales

Active roles, adversarial rounds, ADR requirement.

## What never scales

The invariants. At XS and at L, all seven apply equally. What varies is the **boundary covered**, not the **criteria applied**.

When the user complains about process weight: run triage and show the reduced plan. When they ask to turn off the gate: explain that no key exists, and that the path is shrinking the delivery scope until it fits the standard — not the other way around.
