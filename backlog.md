---
goal: The kernel develops itself end to end under its own mechanisms — install, demand loop, cadence — and every rule ships field-proven.
date: 2026-08-09
---

# Product backlog

Items ordered by value against the goal. Evidence ladder:
`opinion < usage-data < user-test < production`.

| # | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| 1 | Per-demand `sensitive`/`irreversible` in triage | in sensitive+irreversible projects every demand floors at M, inflating ceremony for changes that touch neither (a one-line UI flip sized M in the field); per-demand judgment with strict tiebreaks would restore proportionality without relaxing criteria | usage-data (AGROMETA, DEM-reforma-prefetch) | M |
| 2 | I1 bluntness on prose-only edits | a comment or doc-only change inside a behavior root trips I1 and demands an eval touch; predicted as self-hosting friction in ADR-0007 — measure it here first, then decide (diff-content inspection vs accepting the over-approximation) | opinion (predicted, not yet felt) | S |
| 3 | Role identity in the hook payload | the guard's role branch only fires where the harness sends an agent identity (finding F3); an upstream feature request or a documented workaround would restore loop-tier scope enforcement | usage-data (F3, reproduced live) | S |
| 4 | OTel wiring + guard audit trail | SETUP optionally writes the Claude Code OTel env block (CLAUDE_CODE_ENABLE_TELEMETRY + OTLP endpoint) into the settings.json it already manages — operational audit out of the box; and the guard emits an allowed/blocked trail (today it blocks with exit 2 and leaves no record, which contradicts the spirit of I5) | opinion | S |
| 5 | Execution provenance in demand artifacts | findings.toml and decision.md record the reviewer's transcript id (agent-<id>) and session, optionally archiving the agent jsonl under reviews/<id>/ — today the forensic trail (full tool calls, probe scripts, outputs) is local and expires with harness retention, severing the link between the durable summary (probed) and the raw execution | opinion | S |

## Status

Items 1–5 selected into S-002 as FWD-003..FWD-007 (planning 2026-08-09);
sizes re-scored at selection with per-demand triage inputs.

## Unplanned intake

None yet.
