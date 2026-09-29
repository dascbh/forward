---
name: fde-scrum
description: The backlog format — B-<n> ids, evidence ladder, origin (C-<n>) — and capturing an idea as a backlog item instead of a demand. Use when an idea or request should be captured rather than built, or when writing backlog.md.
---

# fde-scrum

The backlog feeds cycles (AGENTS.md `## Cycle`). Sprints are retired
(kernel ADR-0019 rule 13); a `sprints/` directory is history, never extended.

## backlog.md

Header lines: `goal:` (the product goal, or `goal: not set`) and
`date:`. Create it on the first capture. With `[scrum] enabled = true`
in fde.config.toml, `--gate scrum` requires both (first 30 lines).

One item per line, a table row or a bullet. A backlog line is `B-<n>`,
the text, `(C-<n>)` when a cycle found it, and its evidence (`opinion <
usage-data < user-test < production`).

- `B-<n>` is the next free id, never reused (`fde-backlog` assigns ids to
  a backlog that has none).
- The text states the item and its hypothesis: what value, for whom.

The owner orders it. The label makes a bet visible; it never blocks one.

## Capture

An idea, pain or "it would be nice to have X" becomes a backlog item,
not a demand: one-line acknowledgment, nothing more. Discoveries during
a cycle enter `backlog.md` as they are found, with origin `(C-<n>)` and
evidence `usage-data`. Re-label when new evidence lands.

"fix it NOW" skips the backlog order, never the open cycle: it becomes
the next cycle's first demand (AGENTS.md `## Cycle`).

## Lessons

A cycle's lessons are its `promotion.md` `## What changes`: three lines
at most, each also a backlog item with origin `(C-<n>)`.
