---
name: fde-sync
description: Updates the kernel and re-emits everything from it. Use when the user asks to update, upgrade or sync FORWARD, changes weights, tools or stack, a generated file looks inconsistent, or a rule "is not kicking in".
---

# fde-sync

Two steps, always in this order: **bring the kernel up to date, then
re-emit the project from it.** Updating without re-emitting leaves the
project on the old artifacts; re-emitting without updating just rewrites
what it already had.

## 0. It always runs

A sync never waits for a cycle to close: a project left on old rules
drifts further every day (owner direction, 2026-09-30). It runs, then
step 4 brings the project's own records up to the new kernel.

**Say this to the user before starting:** the sync writes tool
permissions into `.claude/settings.json` (SETUP §8.4), besides the
generated files. Claude Code's auto mode may block that write. If it
does, do not stop half way silently: tell the user the sync is
incomplete, that they should leave auto mode and re-run fde-sync. The
re-run is idempotent and finishes the job.

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
and `runtime/`, `spec/`, `templates/`, `skills/`, `agents/`, `docs/adr/`
in the kernel. Idempotent: same sources, same output.

- The kernel's ADRs go to `.fde/adr/` only, a read-only copy that is
  replaced whole. Never write to the project's own `docs/adr/`.

- Files WITH the `FDE-KERNEL:GENERATED` marker: overwrite entirely.
- Files WITHOUT it (user-owned `CLAUDE.md`, merged
  `.claude/settings.json`): merge, never clobber. When the merge adds tool
  permissions that were not there (SETUP §8.4), tell the user which ones,
  and that `[tooling] open_permissions = false` keeps the prompts.
- Copy directories, never a remembered list of filenames — an enumerated
  set silently omits whatever the update added.
- Remove each installed skill the kernel no longer has: a
  `.claude/skills/` directory whose name starts with `fde-` and that is
  absent from the kernel's `skills/` (e.g. `fde-scrum`, renamed to
  `fde-backlog-format`). Tell the user which ones were removed. A
  directory whose name does not start with `fde-` is the user's and
  stays.

A project whose `fde.config.toml` declares no `[erosion]` ceiling gets
one now, from its own measurement (SETUP §6 step 8), and the owner is
told the ceilings written. A declared budget is never touched.

Then set `kernel_version` in `fde.config.toml` to the kernel's version
(`.fde/spec/invariants.toml` → `[meta] kernel_version`).
Change nothing else in the config except what a migration below names.

## 3. Retired names and migrations

Both are data in the kernel, copied to `.fde/spec/`:

- `retired.toml` — each `[[renamed]]` or `[[removed]]` skill still under
  `.claude/skills/` is removed (a renamed one's new name was installed
  above); tell the user which, and the new name. A `kind = "config"`
  entry with `alias = true` is still read: a live `[scrum]` header stays
  as it is. A retired name is never reused.
- `migrations/*.toml` — for each file whose `[migration]` `to` is above
  the version you moved from, check its `detect` signals (read only). For each that is present: follow its `guide`, tick its
  `checklist`, commit it on its own (`fde-sync: <id>`), and report its
  `title`. A migration whose signals are absent is skipped silently. The
  sync request is the approval; a failed checklist item stops the sync
  and is reported.

Close by running `python3 bin/fde/verify.py --all`. A red `CFG-VER` means
the update landed half way: the config and the installed spec disagree on
the version.

## 4. Reconcile the project to the new kernel

Reconcile **does**; it does not list. The owner hears only decisions:
a replan (a running cycle's criterion or ADR would change) and the
signature of a planned cycle. Everything else is applied, committed and
reported as done.

1. Read what the new rules flag: `python3 bin/fde/status.py --panel`,
   `python3 bin/fde/verify.py --all`, `python3 bin/fde/status.py --waves
   C-<n>` for each live cycle, and `python3 bin/fde/verify.py --gate
   backlog-length` (every open item, not only new ones).
   With `docs/map/conventions.toml`, run `python3 bin/fde/productmap.py
   --check` and regenerate the stale maps with `--write`: a map is
   derived from the code and its DECLARED block is preserved.
2. **Backlog** — reread each open item against the new kernel:
   - an item the new kernel resolves moves to discarded with
     `resolved by kernel <version>`;
   - an item over `[backlog] max_item_words` becomes one line with a
     pointer: its detail moves to the doc that already holds it (vision,
     spec, ADR), or to `docs/backlog/B-<n>.md` when none does;
   - ids: only main assigns them.
   - **Sanitize, every sync**, in one commit of its own:
     - an item already resolved — by the code, by a kernel version, or
       absorbed into a planned cycle — moves to discarded with where;
     - items that are the same work become one line pointing to the
       rest;
     - an item that only copies a non-blocking review finding goes back
       to its `findings.toml` (moved to discarded with
       `kept in reviews/<id>/findings.toml`), unless it states the value
       of doing it;
     - an item about FORWARD itself is tagged `[kernel]` and listed in
       the report;
     - an item about a test red on main becomes its quarantine in the
       code (`quarantine B-<n>`) or its fix, and the quarantined count is
       recorded (`fde-verify`).
     Nothing with a security or production evidence label is dropped.
   - An erosion debt counted by the closes of cycles planned before it
     (kernel 0.52.5 and older: parallel cycles closing in the same hour
     made a debt overdue at once) is recounted once: `debt_since` set to
     the commit that registered it, `debt_closes` to the closes that
     count (that cycle's own, or a cycle planned after it),
     `debt_overdue` removed when they are fewer than two.
   - `SCOPE` ⚠ names source outside the gate's roots: each directory it
     names that the project wrote (not a vendored library) joins
     `[gate] behavior_paths` — a config key, applied, never asked.
3. **Cycles** — by state:
   - `closed` and `abandoned` are history: never touched;
   - `draft`: its items are checked to be still open;
   - `planned` (not signed): the planner revises it against the new
     rules (the split of kernel ADR-0024, `files`, `depends:`, ids by
     slug, expand/contract of kernel ADR-0026) and asks for the
     signature it did not have yet;
   - `running`: apply everything that changes no criterion and no ADR —
     the `depends:` header, the `files` column, config keys, an id
     rename, the `docs:` line, the deploy's `## Commands` block (kernel
     ADR-0025), and each migration step's protection (kernel ADR-0026):
     - `Migration:` from reading the migration's SQL (adds only →
       expand; drops, renames, retypes or swaps a key → contract;
       rewrites rows → data);
     - `Checkpoint:` the restore-point command for the project's
       database, from its infrastructure code or an earlier deploy;
     - `Rehearsal:` the project's command that applies the migration
       on a clone of production, checks, rolls back and runs the
       previous code. When the project has no such tool, or its
       migration runner is not atomic, build them now in the project
       as a direct-lane change (test first, one isolated code review,
       merge), then fill the field;
     - `Rollback:` `code` for an expand, `down <file>` once rehearsed,
       otherwise `forward-fix`.
     A change to a criterion or an ADR is a replan proposal for the
     owner, never applied: a contract already planned inside a running
     cycle stays (splitting it is such a replan). Only what truly cannot be
     built — no access to a clone, say — is written as `Rehearsal: none
     — <why>` and reported as a limit, not asked. A new gate red on a
     demand in progress is fixed inside the demand (a triaged `patch`)
     or recorded on the board.
   - A running cycle's `promotion.md` written under the old rules
     (`PROMOTION` ⚠, e.g. conditions for the owner to accept) is decided
     again by `fde-promotion` under the new ones, never restated in new
     words: each residual risk becomes its backlog line, each production
     check a `deploy.md` step, and a question the old kernel left pending
     for the owner is withdrawn, not relayed.
   - Then `python3 bin/fde/deployallow.py --write`: signed, running
     cycles get their deploy's allow rules, ended ones lose theirs.
   - Worktrees: each one whose branch is merged into main and that has
     no uncommitted change is removed (`git worktree remove`, then
     `git worktree prune`), its branch deleted. One with work in it
     stays and is listed.
4. **Record** — one commit per kind (the kernel re-emit; the backlog;
   each cycle; each direct-lane change), and one line on each running
   cycle's board: `<date> C-<n> decided kernel sync <from>→<to>: <what
   changed>`.
5. **Report** to the owner in one message: what was done, then the only
   two things that need them — replan proposals and planned cycles
   awaiting a signature.

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
