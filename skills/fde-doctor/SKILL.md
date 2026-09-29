---
name: fde-doctor
description: Reports the agentic tool's enforcement tier: what is enforced versus only suggested. Use at the start of a session in a kernel repo, on switching tools, or when asked if a rule "is active" or will block.
---

# fde-doctor

Tells a wall from a recommendation.

## Procedure

1. **Universal enforcement** — check each exists and report:
   - `.githooks/pre-commit` present AND `git config core.hooksPath` returns
     `.githooks`
   - `.github/workflows/fde-gate.yml`
   - `bin/fde/verify.py` — the gate runtime lives in the repo (I6)
   - `fde.config.toml`
2. **Native layers present** — `.claude/agents/fde-*.md`, the guard hook
   in `.claude/settings.json`, and the skills in `.claude/skills/fde-*`
   (claude-code); `.cursor/rules/fde-eval-gate.mdc` (cursor);
   `.codex/AGENTS.md` (codex); `AGENTS.md` (every tool).
3. **Declare the tier** of the tool in use:

| tier | tools | meaning |
|---|---|---|
| `loop` | claude-code | hook + per-role tool restriction. Blocks before the write. |
| `commit` | cursor, codex | no hook, but subagents/worktrees exist. Real roles, gate in git. |
| `advisory` | everything else | instruction file only. Roles are convention, the gate is CI. |

## Plugin-installed but not yet initialised

If the FORWARD plugin is installed and the project has NOT run `fde-init`,
the native layer is legitimately absent: report it as "not installed here"
and point at `/forward:fde-init`, not as a broken installation. Once
initialised, the project's own `.claude/agents/` and `.claude/skills/`
copies are the ones in force — the plugin's are the generic fallback.

## When reporting

Separate **ENFORCED** (actually blocks: pre-commit, CI, denied tools,
worktree isolation) from **advisory** (instruction the model can ignore
under pressure). If the tier is `advisory`, say that roles are convention
in that tool and the real blocking happens at commit and in CI — never
promise a guarantee the tier does not give.
