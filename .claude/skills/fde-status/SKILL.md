---
name: fde-status
description: Shows where the project stands — the open cycle (objective, demands, done items with progress, the backlog lines it produced), every closed cycle on one line, and the backlog by section, with warnings first (more than one open cycle, a cycle ready to close, no backlog.md). Use when the user asks "where are we", "what is open", "show the cycle", "show the backlog", "what is pending", before opening a new cycle, and at every cycle close.
---

# fde-status

One read-only report over `cycles/` and `backlog.md`:

```bash
python3 bin/fde/status.py              # warnings, open cycle, closed cycles, backlog
python3 bin/fde/status.py --cycle C-3  # one cycle in full
python3 bin/fde/status.py --cycles     # cycles only
python3 bin/fde/status.py --backlog    # backlog only
```

Run it and show the user the output as it is. Do not summarize it or
reword it. Add at most one line after it, and only when a warning calls
for a decision that belongs to the user.

## What it reads

The format comes from AGENTS.md `## Cycle`.

- A cycle is open while its header (the lines before the first `##`)
  has neither `closed:` nor `abandoned:`. When one of those keys appears
  lower in the file, the view names it instead of guessing.
- Done items are counted as `[x]` met, `[-]` declined by the user, and
  anything else pending. An unknown mark is shown as it was written.
- A backlog line belongs to a cycle when the line (every cell of a table
  row), or the `##` section holding it, names that cycle (`C-3`, never
  matching `C-30`).
- An old-format `## Next cycle` list is shown with a warning to move it
  into `backlog.md`.

## Never

- A gate: it exits 0 on any content (ADR-0018). A warning is information
  for the user, not a block.
- A writer: it changes no file. The fixes a warning points to go through
  AGENTS.md `## Cycle`.
