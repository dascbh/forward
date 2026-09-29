# FWD-024 — Cycle and backlog view

size: S

Triage: surfaces 1 (a read-only report) · public · reversible · ~250 LOC
with tests → 1 + 1 = 2 → **S** (spec, impl, 1 adversarial round; 1 h).

## Problem

The owner cannot see where a project stands: which cycle is open, what it
promised, how far it got, and what is only an idea. The information is in
`cycles/*.md` and `backlog.md` but spread across files written for agents.
In headlabs-platform a cycle's `## Done when` stayed all `[ ]` with one of
four demands in production, and a `## Next cycle` list grew into nine
mixed blocks.

## Requirements

- **R1** — `python3 bin/fde/status.py [--root DIR]` prints, in this order:
  the open cycle (id, objective, demands, each done item with its mark,
  and `n/m done`); the backlog lines that name that cycle (`C-<n>` as a
  whole token); every closed or abandoned cycle on one line (id, closed
  date, objective, `n/m`); the backlog grouped by its `##` sections, one
  line per item (table rows by their first two cells, bullets as is).
- **R2** — warnings, printed first: more than one open cycle; a cycle
  file with no `objective:`; no `backlog.md`. It never exits non-zero on
  content — it reports, it does not gate (ADR-0018). Exit 2 only for a
  bad argument.
- **R3** — `--cycle C-<n>` shows that cycle in full; `--backlog` and
  `--cycles` show one part only.
- **R4** — tolerant input: missing `cycles/`, empty files, a cycle
  without `## Done when`, non-UTF-8 bytes, headings in any case. Never a
  traceback.
- **R5** — stdlib only, no git calls, mirrored to `bin/fde/`; skill
  `fde-status` tells the agent to run it and relay the output unedited.

## Threat model

Contained: files written by a cooperative agent or by hand, with typos
and missing sections. Out of scope: hostile file content, huge
repositories (a cycle directory is tens of files), enforcing anything.

## Boundaries

- Always: read-only, exit 0 on any content.
- Never: a gate, a git call, a write.
