---
name: fde-sync
description: Updates the kernel and re-emits everything from it. Use when the user asks to update, upgrade or sync FORWARD, changes weights, tools or stack, a generated file looks inconsistent, or a rule "is not kicking in".
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
  `.claude/settings.json`): merge, never clobber. When the merge adds tool
  permissions that were not there (SETUP §8.4), tell the user which ones,
  and that `[tooling] open_permissions = false` keeps the prompts.
- Copy directories, never a remembered list of filenames — an enumerated
  set silently omits whatever the update added.

Then set `kernel_version` in `fde.config.toml` to the kernel's version
(`.fde/spec/invariants.toml` → `[meta] kernel_version`); change nothing
else in the config.

## 3. Migrate the project's records

A `## Next cycle` list in a cycle file (`cycles/C-<n>.md` or
`cycles/C-<n>/*.md`) moves to `backlog.md` (kernel ADR-0019 rule 15):
each line becomes a backlog line with the next free `B-<n>` id and the
`(C-<n>)` of the cycle it came from, and the section leaves the cycle
file. A cycle opened before kernel ADR-0019 otherwise finishes under its
own rules. Commit the move on its own: `backlog: migrate ## Next cycle`.

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
