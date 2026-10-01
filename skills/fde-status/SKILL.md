---
name: fde-status
description: Shows where the project stands: the running cycle, drafts, ended cycles, the backlog with B-<n> ids, warnings first; `--panel` the whole panel, `--demand` one demand. Use for "where are we", "what is open", "show the cycle/backlog", at every cycle close.
---

# fde-status

One read-only report over `cycles/` and `backlog.md`:

```bash
python3 bin/fde/status.py              # warnings, open cycle, closed cycles, backlog
python3 bin/fde/status.py --cycle C-3  # one cycle in full
python3 bin/fde/status.py --cycles     # cycles only
python3 bin/fde/status.py --backlog    # backlog only
python3 bin/fde/status.py --format json  # same content: warnings, cycles, demands, backlog
python3 bin/fde/status.py --panel      # markdown: overview, backlog, cycles, demands, discarded
python3 bin/fde/status.py --demand FWD-7  # one demand: spec, findings, promotion, ADRs
python3 bin/fde/status.py --flow       # cycle time, lead time, wait for sign-off
python3 bin/fde/status.py --forecast   # when each running cycle likely ends
```

`--flow` reads the minutes from git, not the plan's dates, with nothing
to fill in: request is the first commit that put one of the cycle's
`## Items` in backlog.md; then the plan's first commit, its first
`running`, its first `closed`. Wait for sign-off is plan → running,
cycle time running → closed, lead time request → closed; cycles joined
by `depends:` are one objective, whose lead time ends at its last cycle
closed. Wall-clock hours. A cycle that never read `running` in git has
no cycle time.

**When will it end** — every time the status is shown with a cycle
running, add the `--forecast` lines, unasked: each running cycle's likely
end (p50) and its worst (p85), as clock times, from this project's own
history — how long its demands took to merge and its closings to close.
Nobody estimates; the past does. Demands run in parallel unless one
depends on another; a cycle that waits for another starts when that
one's build ends. Too little history says so instead of a number. Closing is the last demand merged → closed (or now) and
its share of the cycle, target under 20%; deploy stops are the board's
lines of a deploy that stopped, target 0 for defects of the plan itself
(`preflight.py` before the promotion).

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
  met, and a last field `declined` or `limit` settles it on the
  budget-spent path (anything else is pending). A closed directory
  cycle without promotion.md, or with a criterion not settled there,
  warns (the gate's I4 also fails on the first). An old file counts `## Done when`:
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
- A demand is a `specs/<id>/` directory, linked by a plan's `## Demands`
  table or its spec's `cycle:` line, else loose (a `cycle:` naming no
  cycle on disk warns), with its review summary and promotion, read from
  `reviews/<id>/` and `promotions/<id>/`, bare or `-<slug>`.
- `--cycle` lists each demand with its review and promotion.
- `--panel` renders only from the JSON: its Overview ends with a
  `next:` action and shows at most ten warnings. `--demand` on an
  unknown or empty id exits 2.
- An old-format `## Next cycle` list is shown with a warning to move it
  into `backlog.md`.

## Never

- A gate: it exits 0 on any content (kernel ADR-0018). A warning is information
  for the user, not a block.
- A writer: it changes no file. The fixes a warning points to go through
  AGENTS.md `## Cycle`.

## Progress — what each agent is doing, and for how long

```bash
python3 bin/fde/status.py --progress        # running cycles, printed
python3 bin/fde/backlog.py --progress       # the same, navigable, in the owner's own terminal
```

To navigate rather than read a print, the owner runs the panel in a
terminal of their own: j/k move, enter/→ open a cycle, ← close it, d
opens a demand (its name, phase, files and board timeline with times),
r reloads (it also reloads every 30 s), Tab switches to the backlog, q
quits. Offer the command when the owner asks to follow the work.

Each running cycle shows its phases (plan · sign-off · build · cycle
review · deploy: ✓ done, ▸ now, · to come) and one line per demand: its
current phase, how long that phase has run, and which of build · suite ·
review · merge are done. A demand that waits on another says which. The
times are the commit times of the board lines (`git blame`), read from
every worktree, so a demand building in its own worktree shows before it
merges. The same tree sits under each running cycle at the top of
`--panel`.

Name every agent you launch `C-<n> › <demand> › <phase>` (for example
`C-6 › CTR-10 › review`), so a notification says which cycle, demand and
phase finished. The tree is the place to read how long a phase has run.

