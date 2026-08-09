---
name: fde-sync
description: Regenerates the kernel's native artifacts from fde.config.toml and detects drift in generated files edited by hand. Use whenever the user changes weights, switches or adds an agentic tool, adds a stack to the project, or when a file carrying the FDE-KERNEL:GENERATED marker looks inconsistent with the configuration. Also use when the user asks why a rule "is not kicking in" or "disappeared".
---

# fde-sync

Regeneration is you re-running `SETUP.md` steps 6–8 from the current
sources: `fde.config.toml` + `.fde/spec/` in the project, `templates/` and
`agents/` in the kernel. Idempotent: same sources, same output. If the
kernel checkout is gone, clone it again:
`git clone https://github.com/dascbh/forward.git`.

- Files WITH the `FDE-KERNEL:GENERATED` marker: overwrite entirely.
- Files WITHOUT it (user-owned `CLAUDE.md`, merged `.claude/settings.json`):
  merge, never clobber.

## Drift

To check for drift: regenerate and diff. Any difference in a marked file is
drift. The fix belongs **at the source** — `fde.config.toml` for what is the
project's, the kernel's `spec/` for what is the kernel's — then regenerate.
Never suggest "edit the generated file and skip sync": that breaks the
guarantee that the standard is the same across all tools.

## When the tool changes

The user switched from Cursor to Claude Code, or started using both? Re-run
step 8 for the tools now in use and update `[tooling] tools` in
`fde.config.toml`. Then run `fde-doctor` — the enforcement tier changes with
the tool and the user needs to know that.
