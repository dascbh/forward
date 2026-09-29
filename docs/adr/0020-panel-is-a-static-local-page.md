# ADR-0020 — The panel is a static local page

date: 2026-09-29
status: accepted with C-12's sign-off
realized by: FWD-034 (back), FWD-035 (front)

## Context

`/fde-backlog` printed a summary in the chat and asked what to do. The
owner asked for a panel that shows everything at once, in sections:
- the backlog;
- the cycles expandable to their demands and artifacts;
- demands outside any cycle;
- discarded items.

The kernel must stay stdlib-only, with no server (I6), and the agent
remains the runtime for every write (kernel ADR-0019 rule 9).

## Decision

- `status.py --format json` stays the single reader. It gains a
  `demands` inventory: every `specs/<id>/`, its cycle when one links it,
  its review summary and its promotion. It also gains each cycle's
  artifact paths.
- A new read-only `runtime/panel.py` renders that JSON into one
  self-contained HTML file with tabs:
  - overview;
  - backlog;
  - cycles;
  - demands;
  - discarded.

  All CSS and JS are inline, with no network and no dependency. The
  artifacts' text is embedded, collapsed.
- `/fde-backlog` writes the page to `.fde/panel.html`, which is
  gitignored, and opens it. The page only shows. Group, specify and
  sign-off stay in the conversation, because they need the agent.

## Rejected

- A local server with buttons that write. It needs a running process and
  a write path outside the agent, which breaks I6 and rule 9.
- A published claude.ai page. It moves project content off the machine
  and goes stale between publishes.
- A terminal text view. That is what the owner found insufficient.
