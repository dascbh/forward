cycle: C-12
state: running
date: 2026-09-29
size: S
objective: /fde-backlog prints everything in the terminal, in sections — overview, backlog, cycles with their demands and artifacts, loose demands, discarded — and drills down on request
signed-off: 2026-09-29 (owner: "sim")

<!-- Triage: surfaces 2 (terminal output + reader data) · public ·
reversible · ~270 production lines → 2 + 0 + 0 + 1 = 3 → S. Planner
with ADR-0020; demand reviews 1 round each; cycle review 1 round. A
front demand is present: its usability check is a cold read of the
printed panel by an isolated agent, because fde-walkthrough drives a
browser and this surface is terminal text (declared limit). -->

## Items

- B-43 owner request — `/fde-backlog` shows everything, in sections, in the terminal

## Threat model

Contained: the owner reading their own repository in the agent's
terminal. The panel prints the files as they are, malformed ones
included, and never breaks. Out of scope: hostile content beyond keeping
the markdown intact, and editing from the panel.

## Acceptance criteria

- **A1 — Everything in one print.** `/fde-backlog` shows the whole panel
  in the terminal, in five sections: overview, backlog, cycles, demands
  and discarded. No browser and no question box. The actions follow as
  plain text.
- **A2 — Overview.** It shows the running cycle, or "none", with its
  criteria progress; the planned and draft cycles; the warnings; the next
  ids; and counts per section.
- **A3 — Cycles with demands.** Each cycle shows its objective, state,
  criteria progress and items. Each of its demands shows its layer,
  review status (findings and blocking) and promotion. The cycle's
  artifacts are named.
- **A4 — Loose demands.** Every `specs/<id>/` that no cycle links is
  listed with its review and promotion status, including the old layout
  (FWD-001..025).
- **A5 — Backlog and discarded.** Items show by section with id and
  cycle mark. Discarded items show with their reason.
- **A6 — Drill down.** `status.py --demand <id>` prints one demand's
  spec, findings, promotion and ADRs. The skill tells the agent to
  answer "abre C-n" or "mostra <id>" with `--cycle` or `--demand`, and to
  read any artifact on request.
- **A7 — Ships.** status.py stays read-only and exits 0 on any content.
  The full suite and `verify.py --all` are green, the version is 0.20.0,
  and the change is pushed.

## Failure modes

- **FM1:** a file whose text holds markdown table pipes or headings
  breaks the panel's layout. Detected by a fixture with hostile text.
  Meets A1.
- **FM2:** a demand no cycle links is missing. Detected by an
  old-layout fixture. Meets A4.
- **FM3:** a large repository floods the terminal. Long text is clipped
  to one line per item, and closed cycles and loose demands fold to one
  line each, with detail by drill-down. Detected by a line-count test.
  Meets A1.
- **FM4:** the panel and the JSON disagree. `--panel` renders only from
  the same data as `--format json`. Detected by a test that the counts
  are equal. Meets A2.

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-034 | back | — | status.py JSON: a `demands` inventory (every spec dir, its cycle link, review summary: findings, severity, blocking; promotion) and per-cycle artifact paths; old and new layouts; `--demand <id>` | A3, A4, A6 | ADR-0020 |
| FWD-035 | front | FWD-034 | `status.py --panel`: the five markdown sections, with the folding rule; fde-backlog runs it, shows the output as it is, lists the actions in plain text and drills down on request | A1, A2, A3, A5, A6 | ADR-0020 |

FWD-034 starts at sign-off. FWD-035 builds when FWD-034 merges.
