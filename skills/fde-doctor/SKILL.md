---
name: fde-doctor
description: Shows the capability tier of the agentic tool in use and what is ACTUALLY enforced versus merely suggested. Use when the user assumes a rule will block something, when switching tools, when they ask whether the standard "is active", or before promising rigor guarantees to a client. Use at the start of any session in a repository under the kernel that you have not yet inspected.
---

# fde-doctor

```bash
python bin/fde/doctor.py
```

Looks like an accessory and is politically the most important command: it keeps anyone from thinking they have a wall when they only have a recommendation.

## Tiers

| tier | meaning |
|---|---|
| `loop` | hook + per-role tool restriction. Blocks before the write. |
| `commit` | no hook, but subagents/worktrees exist. Real roles, gate in git. |
| `advisory` | instruction file only. Roles are convention, the gate is CI. |

## When reporting

Be explicit about the difference. If the tier is `advisory`, say that roles are convention in that tool and that the real blocking happens at commit and in CI — do not let the user believe in a guarantee that does not exist.

Promising parity across tools and delivering theater in three out of five is what burns an open framework. Honesty about the tier is what sustains adoption.
