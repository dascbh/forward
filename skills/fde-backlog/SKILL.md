---
name: fde-backlog
description: The terminal panel: backlog with B-<n> ids, cycles with their demands, loose demands, discarded; grouping into a draft cycle, opening a cycle or demand, specifying a draft. Use when the user asks to see, organize or pick from the backlog.
---

# fde-backlog

You run this procedure; there is no script behind it. `status.py` only
reads. Every write below is yours, made with your own file tools.

## 1. Show the panel

Run `python3 bin/fde/status.py --panel` and show the output as it is.
Do not summarize, reorder or reword it. It prints five sections from
the same data as `--format json`: Overview, Backlog, Cycles, Demands,
Discarded. The Overview ends with a suggested `next:` action. Running
and planned cycles show in full, with their demands
and artifacts. Drafts show with their items. Ended cycles and loose
demands show one line each.

## 1b. The interactive panel

In a terminal of their own, the owner can run `python3 bin/fde/backlog.py`:
the same data as a keyboard panel (j/k, space to select, enter to open,
`/` to search, `?` for every key). It writes the mechanical actions itself
— group, merge, discard, restore, reorder, edit, undo — and copies
`/fde-backlog specify C-<n>` for a draft, the one action that needs you.
After the owner used it, re-read backlog.md and cycles/ before acting.

## 2. Offer actions

After the panel, list the actions in plain text, one line each. Never
use the question box (AskUserQuestion or any other); the owner answers
in the conversation. The actions:

- **group** — the user names B-ids; put them into a draft cycle,
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
- **open** — "abre C-<n>": run `python3 bin/fde/status.py --cycle
  C-<n>` and show the output as it is (each demand with its review and
  promotion). Its artifacts (plan, deploy,
  board, review, promotion, the demand specs `specs/<id>/spec.md`, the
  ADRs it cites) are named on the panel; read any one on request.
- **show** — "mostra <id>": run `python3 bin/fde/status.py --demand
  <id>` and show the output as it is (spec, findings, promotion, the
  ADRs it follows); read any artifact on request.
- **specify** — pick a draft; run the planner (the fde-spec role in
  cycle mode) to produce plan.md and deploy.md, and stop at the owner's
  sign-off. Before proposing a plan for a paused or long-running cycle,
  fetch and read the log since the last known commit (`git fetch`, then
  `git log <sha>..origin/<default branch>`): a parallel session may have
  made the proposal obsolete. The plan keeps the draft's `## Items`. `fde-spec` writes
  `state: planned` when the plan is specified; at the sign-off the
  orchestrating agent writes `state: running` and the `signed-off:`
  line.
- **exit**.

After an action that edits a file, run `--panel` again and list the
actions again, until exit.

## 3. Ids

Assigning B-ids to a backlog without them: give the next free `B-<n>`
to each item that has none, as the first cell of a table row or as the
first token of a bullet. Do it in one commit, before grouping.

- Next free = `next.backlog_id`: one more than the highest `B-<n>`
  anywhere in backlog.md or in any cycle, in every worktree and on
  main (`fde_lib.used_backlog_ids`); never reuse an id, even one
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
- `fde-backlog` groups items (backlog → draft); `fde-spec` writes
  `state: planned`; the orchestrating agent writes `running` with
  `signed-off:` at sign-off, then `closed` or `abandoned`. The plan is
  frozen at sign-off; these header lines are the only edits it takes.
- A cycle closes when its criteria are met with integration evidence
  and it is deployed or published; show the user its backlog lines
  (`fde-status`). A cycle opened before kernel ADR-0019 finishes under
  its own rules.
- Grouping never writes a spec and never commits to anything.
- Only one cycle may be running; drafts may be many.
- A draft is organization only: no demand ids, no criteria, no specs
  until **specify**.

## 5. After every edit

After every edit, re-run status.py. The result must still parse (FM4):
valid JSON from `--format json`, the new draft listed with `state` draft and its `items`,
every id you wrote present in `backlog`, each grouped item's `cycle`
naming its draft, and no warning that an item is grouped into two
cycles. If not, revert the edit and tell the user
what status.py could not read.

## Never

- Open or run a cycle, or set `state: planned`/`running`.
- Edit an item's text (the ` → C-<n>` mark is the one addition),
  reorder the backlog, or delete an item.
- Wrap status.py or add a writer script: the agent is the runtime.
