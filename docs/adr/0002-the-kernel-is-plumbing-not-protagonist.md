# ADR-0002 — The kernel is plumbing, not the protagonist

date: 2026-08-09
status: accepted

## Context

Field sessions showed installed agents narrating and defending the
framework — long process recaps, "the process was worth it" arguments —
while the user just wanted the work done, plugin-style. Root cause: the
kernel's own instruction language ("announce", "declare", "report
honestly") plus the philosophy carried in AGENTS.md.

## Options considered

- **Transparency by narration** (keep announcing everything) — rejected:
  the user reads process instead of work; the framework performs itself.
- **Silent operation, artifacts only** — rejected: the user loses the
  minimum signal of what ran and what the gate said.
- **One status line; more only when it matters** — accepted.

## Decision

Reports speak of the change in the domain's terms. Process metadata is
one trailing status line (`FORWARD: M · adversarial 2r · gate ✓`). The
kernel earns more than one line only when the gate blocked something or
a decision is genuinely the user's. The full record lives in the
artifacts — that is what I7 is for.

## Consequences

Skills lost their "declare/report" phrasing; review rounds go to
findings.toml metadata. A framework that needs constant explaining is
not done — invisibility is the bar.
