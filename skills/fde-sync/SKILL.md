---
name: fde-sync
description: Updates the kernel and re-emits everything from it — one command. Use when the user asks to update, upgrade or sync FORWARD, to pull a new kernel version, when they change weights, switch or add an agentic tool, add a stack to the project, when a file carrying the FDE-KERNEL:GENERATED marker looks inconsistent with the configuration, or when they ask why a rule "is not kicking in" or "disappeared".
---

# fde-sync

Two steps, always in this order: **bring the kernel up to date, then
re-emit the project from it.** Updating without re-emitting leaves the
project on the old artifacts; re-emitting without updating just rewrites
what it already had.

## 1. Update the kernel

- **Installed as a plugin** — the kernel IS the plugin, so update it:
  ```bash
  claude plugin update forward@forward
  ```
  The files at `${CLAUDE_PLUGIN_ROOT}` change immediately, which is what
  step 2 copies from. The CLI notes a restart is required to apply — that
  applies to this session's view of the SKILL files, not to the kernel on
  disk, so the project still receives the new version. Tell the user to
  restart afterwards so their skills match what was installed.
- **Installed as a clone** — `git -C <kernel-path> pull`.
- Either way, report the version you moved from and to
  (`spec/invariants.toml` → `[meta] kernel_version`). If it did not move,
  say so instead of implying an update happened.

## 2. Re-emit the project

Re-run `SETUP.md` steps 6–8 from the **updated** sources — read SETUP.md
from disk now, not from memory: its procedure may itself have changed in
the update. Sources are `fde.config.toml` + `.fde/spec/` in the project,
and `runtime/`, `spec/`, `templates/`, `skills/`, `agents/` in the kernel.
Idempotent: same sources, same output.

- Files WITH the `FDE-KERNEL:GENERATED` marker: overwrite entirely.
- Files WITHOUT it (user-owned `CLAUDE.md`, merged
  `.claude/settings.json`): merge, never clobber.
- Copy directories, never a remembered list of filenames — an enumerated
  set silently omits whatever the update added.

Close by running `python3 bin/fde/verify.py --all`. A red `CFG-VER` means
the update landed half way: the config and the installed spec disagree on
the version.

## Drift

To check for drift: regenerate and diff. Any difference in a marked file
is drift. The fix belongs **at the source** — `fde.config.toml` for what
is the project's, the kernel's `spec/` for what is the kernel's — then
regenerate. Never suggest "edit the generated file and skip sync": that
breaks the guarantee that the standard is the same across all tools.

## When the tool changes

The user switched from Cursor to Claude Code, or started using both?
Re-run step 8 for the tools now in use and update `[tooling] tools` in
`fde.config.toml`. Then run `fde-doctor` — the enforcement tier changes
with the tool and the user needs to know that.
