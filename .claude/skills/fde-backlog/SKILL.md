---
name: fde-backlog
description: The panel over backlog.md and the cycles: B-<n> ids, cycles by state, grouping items into a draft cycle, opening a cycle, specifying a draft to sign-off. Use when the user asks to see, organize or pick from the backlog.
---

# fde-backlog

You run this procedure; there is no script behind it. `status.py` only
reads. Every write below is yours, made with your own file tools.

## 1. Show the panel

Run `python3 bin/fde/status.py --format json` and show the panel:

- the `warnings`, first, as written;
- the backlog by section, each item with its `B-<n>` id (`(no id)` when
  it has none) and, when grouped, its cycle (`cycle`);
- the cycles by state, in this order: running, planned, draft, closed
  (abandoned with closed) — each with its objective and demand progress
  (`done.met`/`done.total`, and the demand ids); a draft with its
  `items` (B-ids and text).

## 2. Offer actions

Ask through the tool's question UI (AskUserQuestion in Claude Code;
multi-select for items). The actions:

- **group** — the user selects B-ids; put them into a draft cycle,
  either a new `cycles/C-<n>/plan.md` (next free `n`: `next.cycle_id`,
  which counts both `cycles/C-<n>/` and old `cycles/C-<n>.md`) or an
  existing draft. An item already grouped (its `cycle` is set, or
  another cycle lists it) is not grouped again. A new draft's plan.md:

  ```markdown
  # C-<n>

  state: draft
  objective: <one line, the user's words>

  ## Items

  - B-<n> <the item's text>
  ```

  Adding to an existing draft appends lines to its `## Items`. Then
  mark each grouped item in backlog.md: append ` → C-<n>` to its text
  (in a table row, to its item cell).
- **open** — pick a cycle; list its artifacts (plan, deploy, board,
  review, promotion, the demand specs `specs/<id>/spec.md`, the ADRs it
  cites) and read any one on request.
- **specify** — pick a draft; run the planner (the fde-spec role in
  cycle mode) to produce plan.md and deploy.md, and stop at the owner's
  sign-off. The plan keeps the draft's `## Items`. `fde-spec` writes
  `state: planned` when the plan is specified; at the sign-off the
  orchestrating agent writes `state: running` and the `signed-off:`
  line.
- **exit**.

After an action, show the panel again and ask again, until exit.

## 3. Ids

Assigning B-ids to a backlog without them: give the next free `B-<n>`
to each item that has none, as the first cell of a table row or as the
first token of a bullet. Do it in one commit, before grouping.

- Next free = `next.backlog_id`: one more than the highest `B-<n>`
  anywhere in backlog.md or in any cycle; never reuse an id, even one
  whose item is gone.
- A table whose first column is a row number (`#`): that cell becomes
  the id and the header cell becomes `id`. Any other table: add a
  leading `id` column to the header, the separator and every row.
- A bullet: `- B-<n> <text>`.
- Change nothing else in the line. Commit message:
  `backlog: B-<n> ids`.

## 4. Rules

- A cycle moves `draft` (grouped) → `planned` (specified, awaiting
  sign-off) → `running` (signed off) → `closed` or `abandoned`. This
  panel writes only `state: draft`.
- Grouping never writes a spec and never commits to anything.
- Only one cycle may be running; drafts may be many.
- A draft is organization only: no demand ids, no criteria, no specs
  until **specify**.

## 5. After every edit

After every edit, re-run status.py. The result must still parse (FM4):
valid JSON, the new draft listed with `state` draft and its `items`,
every id you wrote present in `backlog`, each grouped item's `cycle`
naming its draft, and no warning that an item is grouped into two
cycles. If not, revert the edit and tell the user
what status.py could not read.

## Never

- Open or run a cycle, or set `state: planned`/`running`.
- Edit an item's text (the ` → C-<n>` mark is the one addition),
  reorder the backlog, or delete an item.
- Wrap status.py or add a writer script: the agent is the runtime.
