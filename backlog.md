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
sizes re-scored at selection with per-demand triage inputs. Items 6–8
below entered at the S-005 review; item 6 was selected into S-006 as
FWD-013.

| # | item | hypothesis | evidence | size (est.) |
|---|---|---|---|---|
| 6 | Verification discipline | five factual errors about external sources shipped in two demands, each caught only by isolated review because the accompanying tests asserted a claim existed rather than that it was true; a catalog principle plus a gate on undated/expired claims would make the failure mode detectable by the suite | usage-data (S-005 reviews, 3 rounds) | M |
| 7 | Split the reference base by kind | 55 entries across 5 node kinds in one 584-line TOML; the FWD-012 review asked whether one file is still the right container (MNT-1/MNT-2). Declined at the S-005 review — revisit if the base keeps growing | opinion | S |
| 8 | Collapse the parallel-copy defence | the graph mining the kernel's own review history ranks MNT-1 at 25.0 severity-weighted, 3x the next principle: source, installed mirror, template and generated surface each get a bespoke drift test. One mechanism could replace the case-by-case detectors | usage-data (graph --recurring) | M |

## Unplanned intake

None yet.
