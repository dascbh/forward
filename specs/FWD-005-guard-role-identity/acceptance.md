---
date: 2026-08-09
demand: FWD-005
---

# Acceptance — FWD-005

- Guard blocks an out-of-scope write from a worktree subagent whose
  payload has NO agent_name, using cwd + meta.json agentType (tested with
  FDE_AGENT_META_DIR fixtures).
- Missing/unreadable metadata degrades to anonymous: no block, no crash
  (tested).
- Payload agent_name, when present, still wins (tested by the existing
  suite).
