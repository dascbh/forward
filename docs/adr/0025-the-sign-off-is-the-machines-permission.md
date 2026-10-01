# ADR-0025 — The sign-off is the machine's permission

date: 2026-09-30
status: accepted (owner, direct, 2026-09-30)
realizes: ADR-0019 rule 3, "approval happens once, at plan sign-off, and
is inherited by everything after it, irreversible deploy steps included"

## Context

A client's cycle was signed, and its deploy stopped half way: Claude
Code's auto mode refused to apply migrations to the production database.
Production stayed consistent only because the step that had run was
independent; the next step was irreversible.

The kernel already opens the built-in tools at install (SETUP §8.4,
`Bash` in `permissions.allow`). Auto mode suspends broad rules such as
`Bash` and judges every production deploy itself. It never reads
`plan.md`. A sentence in the conversation is not enough either: it must
name the exact action, and context compaction can drop it. Narrow allow
rules, such as `Bash(<one command>)`, are resolved before the classifier
(code.claude.com/docs/en/auto-mode-config). So the owner's signature
existed on disk, but nothing the machine reads carried it.

The owner's direction: loosen it. The cycle's approval is enough to run
everything in the cycle.

## Decision

1. **`deploy.md` declares its commands.** Under `## Commands`, a fenced
   block holds one command per line, exactly as the deploy agent will run
   it. A `<placeholder>` marks the part that varies. A line that chains
   commands is refused and must be split, so each rule names one command.
2. **The sign-off writes the permission.** When the orchestrating agent
   writes `state: running` and `signed-off:`, it runs
   `bin/fde/deployallow.py --write`. That adds one `Bash(<command>)` rule
   per declared command to `.claude/settings.json`, each placeholder a
   `*`.
3. **The close takes it back.** The same script, run at a close, an
   abandon or a sync, removes the rules of cycles that no longer run.
   Only rules it wrote are ever removed; it records them in
   `.fde/deploy-allow.json`.
4. **A deploy never starts in order to stop.** Before step 1, the deploy
   agent runs `deployallow.py --check`. A missing rule is written (the
   sign-off covers it) before any step runs, never discovered mid-way.
5. **The sync applies it everywhere.** Reconcile adds `## Commands` to a
   running cycle's `deploy.md` (it changes no criterion and no ADR) and
   writes the rules, so every installed project gets this on its next
   sync.
6. **The owner's opt-out stays.** With `[tooling] open_permissions =
   false`, nothing is written and the prompts stay. `permissions.ask`
   and `permissions.deny` are never touched; they are the owner's and
   take precedence.

## Alternatives rejected

- **An `autoMode.allow` rule in the project's settings.** Claude Code
  does not read `autoMode` from project settings, by design, so that a
  repository cannot widen its own trust. That rule belongs in the
  owner's personal `~/.claude/settings.json`. It is complementary and
  the owner's call, not the kernel's.
- **Parsing commands out of the deploy prose.** In real `deploy.md` files,
  commands sit beside backticked file, function and stack names, with
  placeholders and environment prefixes. A parser would write wrong
  rules. A declared section is exact.
- **One broad rule per tool (`Bash(python3 *)`).** It would allow far more
  than the cycle signed. A rule per declared command allows what was
  signed and nothing else.

## Consequences

- A signed deploy no longer stops between steps for a permission. The
  classifier still judges everything the deploy did not declare.
- A command the deploy runs must match its declared line. Running it
  another way (other flags, a chained form) falls back to the classifier.
- The rules live while the cycle runs and leave when it ends, so a
  project does not accumulate production permissions.
- `DEPLOY-ALLOW` (⚠) warns when a signed, running cycle has no
  `## Commands`, a refused line, or a rule missing from the settings.
