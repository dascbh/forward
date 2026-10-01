---
name: fde-backlog-format
description: The backlog format — B-<n> ids, evidence ladder, origin (C-<n>) — and capturing an idea as a backlog item instead of a demand. Use when an idea or request should be captured rather than built, or when writing backlog.md.
---

# fde-backlog-format

The backlog feeds cycles (AGENTS.md `## Cycle`). Sprints are retired
(kernel ADR-0019 rule 13); a `sprints/` directory is history, never extended.

## backlog.md

Header lines: `goal:` (the product goal, or `goal: not set`) and
`date:`. Create it on the first capture. With `[backlog] enabled = true`
in fde.config.toml, `--gate backlog` requires both in the header (the
lines before the first `## `) and rejects `goal: not set`. `[scrum]` is
the switch's old name, still read.

One item per line, a table row or a bullet. A backlog line is `B-<n>`,
the text, `(C-<n>)` when a cycle found it, and its evidence (`opinion <
usage-data < user-test < production`).

- `B-<n>` is the next free id, never reused (`fde-backlog` assigns ids to
  a backlog that has none).
- Ids are assigned on main only. A line written in a demand's worktree
  has no id; after the merge, main gives it the next free `B-<n>`
  (`fde-backlog` §3), so parallel demands never collide.
- The `BL-IDS` gate fails when one `B-<n>` opens two different items —
  in backlog.md, or between this checkout and another worktree or main.
  Fix: give the later item the next free id.
- The text states the item and its hypothesis: what value, for whom.
- One line with a pointer, not a mini-spec: at most `[backlog]
  max_item_words` (default 60). The detail lives in the doc the line
  points to; a new longer line fails `BL-LEN`.

The owner orders it. The label makes a bet visible; it never blocks one.

## Capture

An idea, pain or "it would be nice to have X" becomes a backlog item,
not a demand: one-line acknowledgment, nothing more. Discoveries during
a cycle enter `backlog.md` as they are found, with origin `(C-<n>)` and
evidence `usage-data` — at most 5 a cycle; a review finding stays in its
`findings.toml` unless it is worth work of its own (`fde-review`
Triage). Re-label when new evidence lands. An item about FORWARD itself
— a rule, a gate, a skill that misled — is tagged `[kernel]`: `fde-sync`
lists those for the kernel's maintainer instead of leaving them in the
client.

"fix it NOW" skips the backlog order, never the open cycle: it becomes
the next cycle's first demand (AGENTS.md `## Cycle`).

## Lessons

A cycle's lessons are its `promotion.md` `## What changes`: three lines
at most, each also a backlog item with origin `(C-<n>)`.
