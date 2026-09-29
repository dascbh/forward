---
name: fde-status
description: Shows where the project stands — the running cycle (objective, demands, artifacts, done items with progress, the backlog lines it produced), drafts and planned cycles, every ended cycle on one line, and the backlog by section with its B-<n> ids, with warnings first (more than one running cycle, a cycle ready to close, no backlog.md). `--format json` feeds the panel. Use when the user asks "where are we", "what is open", "show the cycle", "show the backlog", "what is pending", before opening a new cycle, and at every cycle close.
---

# fde-status

One read-only report over `cycles/` and `backlog.md`:

```bash
python3 bin/fde/status.py              # warnings, open cycle, closed cycles, backlog
python3 bin/fde/status.py --cycle C-3  # one cycle in full
python3 bin/fde/status.py --cycles     # cycles only
python3 bin/fde/status.py --backlog    # backlog only
python3 bin/fde/status.py --format json  # same content: warnings, cycles, backlog
```

Run it and show the user the output as it is. Do not summarize it or
reword it. Add at most one line after it, and only when a warning calls
for a decision that belongs to the user.

## What it reads

The format comes from AGENTS.md `## Cycle`.

- A cycle is a directory `cycles/C-<n>/` (header in `plan.md`; the view
  lists which of plan, deploy, board, review, promotion exist and the
  `## Demands` table: id, layer, depends on) or an old file `cycles/C-<n>.md`.
- State, from the header (the lines before the first `##`): a `closed:`
  or `abandoned:` line with a value ends the cycle, whatever `state:`
  says (a disagreement warns); else the first word of `state:` (draft |
  planned | running | closed | abandoned); else running. More than one
  running cycle warns; drafts may be many. An end key lower in the file
  is named, not guessed.
- Progress: a directory cycle counts plan.md's `## Acceptance criteria`
  ids against promotion.md, where `- A1 — <evidence> — met` marks A1
  met (anything else is pending). An old file counts `## Done when`:
  `[x]` met, `[-]` declined by the user, anything else pending, an
  unknown mark shown as written. All met without an end line warns.
- A backlog line belongs to a cycle when the line (every cell of a table
  row), or the `##` section holding it, names that cycle (`C-3`, never
  matching `C-30`).
- A backlog item's id is `B-<n>` as the first cell of a table row or the
  first token of a bullet (after a checkbox), backticks or bold
  optional. A `B-<n>` in any other id-like place (a heading, a numbered
  line, a later cell) warns; a reused id warns.
- JSON items carry the full `text` and, for a table row, every `cells`
  value; only the text view clips.
- An old-format `## Next cycle` list is shown with a warning to move it
  into `backlog.md`.

## Never

- A gate: it exits 0 on any content (ADR-0018). A warning is information
  for the user, not a block.
- A writer: it changes no file. The fixes a warning points to go through
  AGENTS.md `## Cycle`.
