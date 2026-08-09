---
name: fde-doctor
description: Reports the enforcement tier of the agentic tool in use and what is ACTUALLY enforced versus merely suggested. Use when the user assumes a rule will block something, when switching tools, when they ask whether the standard "is active", or before promising rigor guarantees to a client. Use at the start of any session in a repository under the kernel that you have not yet inspected.
---

# fde-doctor

Looks like an accessory and is politically the most important check: it
keeps anyone from thinking they have a wall when they only have a
recommendation.

## Procedure

1. **Universal enforcement** — check each exists and report:
   - `.githooks/pre-commit` present AND `git config core.hooksPath` returns
     `.githooks`
   - `.github/workflows/fde-gate.yml`
   - `bin/fde/verify.py` — the gate runtime lives in the repo (I6)
   - `fde.config.toml`
2. **Native layers present** — `.claude/agents/fde-*.md` plus the guard
   hook in `.claude/settings.json` (claude-code);
   `.cursor/rules/fde-eval-gate.mdc` (cursor); `.codex/AGENTS.md` (codex);
   `AGENTS.md` (every tool).
3. **Declare the tier** of the tool in use:

| tier | tools | meaning |
|---|---|---|
| `loop` | claude-code | hook + per-role tool restriction. Blocks before the write. |
| `commit` | cursor, codex | no hook, but subagents/worktrees exist. Real roles, gate in git. |
| `advisory` | everything else | instruction file only. Roles are convention, the gate is CI. |

## When reporting

Separate **ENFORCED** (actually blocks: pre-commit, CI, denied tools,
worktree isolation) from **advisory** (instruction the model can ignore
under pressure). If the tier is `advisory`, say that roles are convention
in that tool and the real blocking happens at commit and in CI — do not let
the user believe in a guarantee that does not exist.

Promising parity across tools and delivering theater in three out of five
is what burns an open framework. Honesty about the tier is what sustains
adoption.
