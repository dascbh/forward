# FWD-006 — Guard audit trail + optional OTel wiring

Triage: surfaces 0 · public · reversible · ~150 LOC → score 1, torn → **S**.

## Problem

The guard blocks with exit 2 and leaves no record — enforcement without a
trail, against the spirit of I5. Operationally, Claude Code ships native
OpenTelemetry that the install never mentions, though the kernel already
owns the file where it is configured (settings.json).

## Requirements (EARS)

- R1: WHEN the guard blocks, it MUST append a JSONL entry to
  `.fde/guard-audit.jsonl` (timestamp, path, agent or null, decision,
  rule). WHEN it allows a write from an identified role, it MUST log the
  allow (low volume, high signal). Anonymous allows are not logged
  (noise).
- R2: WHEN auditing fails for any reason, the write decision MUST be
  unaffected — the trail never becomes a gate.
- R3: WHEN a user asks for operational telemetry at install or later,
  SETUP names the exact Claude Code OTel env block for settings.json —
  off by default, never enabled unasked.

## Failure modes

- FM-1: audit I/O failure blocks or crashes the hook.
- FM-2: the audit file churns the repo — it must be gitignored by
  install instruction.
