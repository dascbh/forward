# ADR-0023 — An interactive panel in the owner's terminal

date: 2026-09-29
status: accepted (owner, direct, 2026-09-29)
amends: ADR-0020, its rejection of a curses TUI

## Context

ADR-0020 printed the panel as markdown inside the conversation and
rejected a curses TUI because it cannot run inside the agent's
conversation. That is still true. The owner now wants the backlog as an
app — select, expand, collapse, shortcuts, combine items, "like vim" —
and chose to run it in a terminal of their own, beside the agent, not
inside the conversation.

## Decision

1. `runtime/backlog.py` (installed as `bin/fde/backlog.py`) is a curses
   panel the owner runs in their own terminal. stdlib only (I6); it is
   not on the gate's path and nothing in CI runs it.
2. Its writes are the owner's edits, made with a tool instead of an
   editor: group items into a draft cycle, merge items, discard,
   restore, reorder, edit, undo. The agent's `fde-backlog` procedure is
   unchanged and remains the path inside the conversation.
3. Judgment stays with the agent: on a draft, the panel copies
   `/fde-backlog specify C-<n>` for the owner to paste.
4. Ids: the panel never creates one (only main assigns them); a merge
   keeps the first id and retires the others as `merged into B-<k>`.
5. Writes cover bullet backlogs, the format every project uses; a table
   backlog is shown read-only.
6. The panel does not commit. The agent re-reads backlog.md and cycles/
   before acting after the owner used it.

## Consequences

- `status.py --panel` stays the printed view for the conversation.
- The write logic is a pure layer (`Board`) tested without a terminal;
  one pseudo-terminal test drives the curses loop.

## Rejected

- A web page (artifact): it cannot write the repository; every action
  would go back through the agent.
