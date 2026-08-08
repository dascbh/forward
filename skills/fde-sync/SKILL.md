---
name: fde-sync
description: Recompiles the native artifacts from fde.config.toml and detects drift in generated files that were edited by hand. Use whenever the user changes weights, switches agentic tools, adds a stack to the project, or when a file carrying the FDE-KERNEL:GENERATED marker looks inconsistent with the configuration. Also use when the user asks why a rule "is not kicking in" or "disappeared".
---

# fde-sync

Regenerates. Idempotent.

```bash
python bin/compile.py            # regenerates
python bin/compile.py --check    # validates without writing
```

## Drift

Every emitted file carries `FDE-KERNEL:GENERATED` at the top. Editing by hand is guaranteed loss: the next `sync` overwrites it.

If the user edited a generated file, the fix belongs **at the source** — `fde.config.toml` for what belongs to the project, `spec/` for what belongs to the kernel — and then recompile. Never suggest "edit directly and skip sync": that breaks the guarantee that the standard is the same across all tools.

## When the tool changes

The user switched from Cursor to Claude Code, or started using both? Just run `sync`. The source is the same; what changes is which adapter emits. Check the result with `fde-doctor` — the enforcement tier changes with the tool and the user needs to know that.
