# ADR-0020 — The panel is printed in the terminal

date: 2026-09-29
status: accepted with C-12's sign-off
realized by: FWD-034 (back), FWD-035 (front)

## Context

`/fde-backlog` printed a short summary and asked what to do through a
question box. The owner wants the whole picture at once, in sections, in
the terminal where they work, and not in a browser:
- the backlog;
- the cycles with their demands and artifacts;
- demands outside any cycle;
- discarded items.

The kernel stays stdlib-only (I6). The agent remains the runtime for
every write (kernel ADR-0019 rule 9).

## Decision

- `status.py` stays the single reader. Its JSON gains a `demands`
  inventory: every `specs/<id>/`, the cycle that links it, its review
  summary and its promotion. It also gains each cycle's artifact paths.
- `status.py --panel` prints the whole panel as markdown sections:
  - overview;
  - backlog;
  - cycles, each with its demands and artifacts;
  - demands, including loose ones;
  - discarded.
- `status.py --demand <id>` prints one demand: spec, findings, promotion
  and the ADRs it follows. `--cycle C-<n>` already exists for a cycle.
- `/fde-backlog` runs `--panel` and shows the output as it is. It then
  lists the actions in plain text; there is no question box. The owner
  drills down by asking, for example "abre C-5" or "mostra FWD-029", and
  the agent answers with `--cycle` or `--demand` and reads any artifact
  on request. Group, specify and sign-off stay in the conversation.

## Rejected

- An HTML page in the browser. The owner works in the terminal.
- A curses TUI. It cannot run inside the agent's conversation.
- A question box per action. The owner found it hid the panel.
