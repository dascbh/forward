cycle: C-5
state: running
signed-off: 2026-09-29 (owner: "aprovado, pode seguir")
objective: the kernel runs backlog > cycle > demand (ADR-0019) — cycles plan once and own approval, review, promotion and deploy; demands derive, run in parallel and only execute; the instructions are coherent and terse
size: L
opened: 2026-09-29
date: 2026-09-29

## Threat model

Contained: cooperative agents that follow the instructions but drift,
contradict each other, or re-ask the owner. Contained too: repositories
with the old per-demand layout (headlabs-platform, and this repository's
own history). They must stay green. Out of scope: hostile agents,
rewritten history, enforcement beyond the existing gates.

## Acceptance criteria

- **A1 — draft without spec.** From `fde-backlog`, the owner selects
  backlog items (`B-<n>`) and puts them in a new or open draft cycle.
  Nothing is specified and nothing is committed to.
- **A2 — specify.** Specifying a draft produces `cycles/C-<n>/plan.md`
  with:
  - dated criteria and failure modes with ids;
  - a threat model;
  - the demand list, each demand with its layer (`front`/`back`/`infra`),
    dependencies, the criteria it meets and the ADRs it follows;
  - `deploy.md` ordered infra → back → front → contract, each step with
    its verification and rollback.

  The planner stops at the sign-off.
- **A3 — the view.** `status.py` shows:
  - the draft, planned, running and closed states;
  - the backlog with ids;
  - the cycle directories, and the old single-file cycles;
  - `--format json` output that feeds the panel.
- **A4 — demands derive.** A demand spec is one page that cites the
  plan's ids. No demand has its own acceptance, failure modes,
  architecture or promotion.
- **A5 — parallel.** The instructions run independent demands at once in
  worktrees and coordinate through `cycles/C-<n>/board.md`. A merge
  always rebases and passes the gate.
- **A6 — the cycle review.** It judges functioning and readiness against
  `plan.md` and never re-reviews demands. Walkthrough runs only when a
  `front` demand is in the cycle.
- **A7 — gates by owning level.**
  - Cycle: I4, promotion, I5 and traceability.
  - Demand: I1, I2 and I3.
  - The sprint gates are removed.
  - The old per-demand artifacts still pass.
- **A8 — coherence.** Each of the 15 inconsistencies in
  `discovery/sharpen-2026-09-29.md` is resolved or no longer applies. A
  fresh isolated consistency audit finds no contradiction about the
  backlog/cycle/demand model.
- **A9 — terse.** AGENTS.md has at most 1,600 words. Every skill and
  agent `description:` has at most 40 words. Rationale lives in ADRs.
- **A10 — ships.** The full suite and `verify.py --all` are green, the
  version is 0.19.0, and the change is pushed.

## Failure modes

- **FM1:** the gate change turns an old-layout repository red (headlabs).
  Detected by a test over an old-layout fixture. Meets A7.
- **FM2:** two parallel demands edit the same instruction file and one
  silently overwrites the other. Contained by the board claim and
  rebase-before-merge. Meets A5.
- **FM3:** the terse rewrite drops a rule that an eval pins. Detected by
  `test_instructions` staying green, since each rule is pinned verbatim.
  Meets A9.
- **FM4:** the panel mutates the backlog in a way `status.py` cannot
  read. Detected by a round-trip test. Meets A1 and A3.

## Demands

| id | layer | depends on | what | meets |
|---|---|---|---|---|
| FWD-026 | back | — | AGENTS.md + template: the demand loop and `## Cycle` rewritten for backlog > cycle > demand; cycle directory templates (`plan.md`, `deploy.md`, `board.md`, `review.md`, `promotion.md`) | A2, A4, A5 |
| FWD-027 | back | — | `status.py`: states, backlog ids, cycle directories plus the old files, `--format json` | A3 |
| FWD-028 | back | — | agents and roles: the spec role plans the cycle and derives demands; architecture works at the cycle; promotion and walkthrough work at the cycle; the adversarial role gains a cycle mode (functioning + readiness); `roles.toml` scopes | A4, A6 |
| FWD-029 | back | — | gates: I4, promotion, I5 and TRACE move to the cycle; the sprint gates are removed; old-layout fixtures stay green | A7 |
| FWD-030 | back | FWD-027 | `fde-backlog` skill (the panel): view, group into a draft, open a cycle, specify | A1 |
| FWD-031 | back | FWD-029 | retire sprints: `fde-scrum` shrinks to the backlog format; this repository's `sprints/` stays as history | A7 |
| FWD-032 | back | FWD-026, FWD-028 | the remaining coherence items from the discovery | A8 |
| FWD-033 | back | FWD-026, 028, 031, 032 | the terse pass: AGENTS.md, skills, agents, descriptions; rationale to ADRs | A9 |

FWD-026, 027, 028 and 029 start at once. FWD-030 and 031 start when
their dependency merges. FWD-033 comes last because it edits every text
the others touch.

## Deploy

1. Bump to 0.19.0 and push `main`.
   - Verification: CI green on the pushed SHA.
   - Rollback: `git revert` the release commit and push.
2. Clients take it with `fde-sync`.
   - Verification: headlabs-platform stays green.
   - Its `## Next cycle` lists move to `backlog.md` (ADR-0019 rule 15).

No step is irreversible.
