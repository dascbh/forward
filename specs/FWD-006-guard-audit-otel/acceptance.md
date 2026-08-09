---
date: 2026-08-09
demand: FWD-006
---

# Acceptance — FWD-006

- A blocked write appends a JSONL entry (ts, path, agent, decision,
  rule) to `.fde/guard-audit.jsonl`; an identified-role allow is logged;
  an anonymous allow is not — all tested.
- Audit failure never changes the guard's exit code (tested with an
  unwritable audit path).
- SETUP step 8 documents the opt-in OTel env block and the gitignore
  entry for the audit file; this repo's .gitignore carries it.
