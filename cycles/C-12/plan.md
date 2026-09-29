cycle: C-12
state: planned
date: 2026-09-29
size: M
objective: /fde-backlog shows everything in one visual panel with sections — overview, backlog, cycles with their demands and artifacts, loose demands, discarded
signed-off:

<!-- Triage: surfaces 2 (UI + reader data) · public · reversible · ~450
production lines → 2 + 0 + 0 + 2 = 4 → M. Planner with ADR (kernel
ADR-0020); demand reviews 1 round each; cycle review full + delta; a
front demand is present, so the cycle review runs fde-walkthrough. -->

## Items

- B-43 owner request — `/fde-backlog` opens a visual panel with sections/tabs showing everything

## Threat model

Contained: the owner reading their own repository on their own machine.
The page shows the files as they are, including malformed ones, and never
breaks on them. Out of scope: hostile file content beyond escaping it,
multi-user access, and editing from the page.

## Acceptance criteria

- **A1 — One page, everything.** `/fde-backlog` writes `.fde/panel.html`
  and opens it. The page has five sections: overview, backlog, cycles,
  demands and discarded. It works offline, with no dependency.
- **A2 — Overview.** It shows the running cycle, or "none", with its
  criteria progress; the planned and draft cycles; the warnings; the next
  ids; and counts per section.
- **A3 — Cycles expand.** Each cycle opens to its objective, state,
  criteria (met, declined or pending) and items. Its demands open to the
  spec, the review findings (with severity and blocking), the ADRs they
  follow, and the cycle's board, deploy, review and promotion. The text
  is readable in place.
- **A4 — Loose demands.** Every `specs/<id>/` that no cycle links is
  listed with its review and promotion status. Demands in the old layout
  (FWD-001..025) appear.
- **A5 — Backlog and discarded.** Items show by section with id,
  evidence and cycle mark. Discarded items show with their reason.
- **A6 — Safe and read-only.** All file text is HTML-escaped. The
  generator writes only `.fde/panel.html`, which is gitignored.
  status.py stays read-only and exits 0 on any content.
- **A7 — Ships.** The full suite and `verify.py --all` are green, the
  version is 0.20.0, and the change is pushed.

## Failure modes

- **FM1:** a file with `<script>` or `</details>` in it breaks or
  injects into the page. Detected by an escaping test on hostile
  fixture text. Meets A6.
- **FM2:** a demand linked to no cycle is missing from the page.
  Detected by a fixture with old-layout specs. Meets A4.
- **FM3:** a large repository makes the page unusable. Artifacts are
  collapsed by default, and each embedded file is capped with a "…
  truncated, open the file" note. Detected by a size test. Meets A3.
- **FM4:** the panel and status.py disagree. The page is rendered only
  from `status.py --format json`. Detected by a test that the counts on
  the page equal the JSON's counts. Meets A2.

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-034 | back | — | status.py JSON: a `demands` inventory (every spec dir, its cycle link, review summary: findings, severity, blocking; promotion) and per-cycle artifact paths; old and new layouts | A3, A4, A6 | ADR-0020 |
| FWD-035 | front | FWD-034 | design first (fde-design, M: flow + wireframe + 2 alternatives from distinct lenses in `specs/FWD-035/design/`); then runtime/panel.py renders the JSON into the five-section page; fde-backlog writes and opens `.fde/panel.html`; `.gitignore` | A1, A2, A3, A5, A6 | ADR-0020 |

FWD-034 starts at sign-off. FWD-035 starts its design at sign-off in
parallel, and builds when FWD-034 merges.
