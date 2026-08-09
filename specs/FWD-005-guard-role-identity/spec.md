# FWD-005 — Guard role identity via harness metadata

Triage: surfaces 0 · public · reversible · ~150 LOC → score 1, torn → **S**.

## Problem

The hook payload carries no role identity (finding F3), so the guard's
role branch is dead for real subagents — scope enforcement only fires in
tests that fabricate `agent_name`. The harness DOES leave an identity
trail: an isolated subagent runs inside `.claude/worktrees/agent-<id>`,
and `~/.claude/projects/<slug>/<session>/subagents/agent-<id>.meta.json`
records its `agentType` (verified empirically on this repo's own
reviewer runs).

## Requirements (EARS)

- R1: WHEN the payload carries no agent identity, the guard MUST derive
  it from the working directory: a cwd inside `.claude/worktrees/
  agent-<id>` resolves `agentType` from the harness metadata
  (`agent-<id>.meta.json` under the projects dir, overridable via
  `FDE_AGENT_META_DIR` for tests and non-standard layouts).
- R2: WHEN metadata is absent or unreadable, the guard MUST degrade to
  anonymous (no role branch) — never block by accident, never crash.
- R3: WHEN identity is derived, the existing allowlist semantics apply
  unchanged.

## Failure modes

- FM-1: metadata lookup crashes the hook (blocking every write).
- FM-2: a stale/foreign meta file misattributes a role — the lookup must
  match the exact agent id from cwd.
