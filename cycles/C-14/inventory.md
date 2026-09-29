cycle: C-14
demand: FWD-037
date: 2026-09-29
source: AGENTS.md at 8d08fe8 (1,598 words; 502 before `## Demand loop`)

# AGENTS.md inventory — before the move

Every sentence of AGENTS.md's `## Demand loop`, `## Cycle`, `## Backlog`
and `## Detail` sections, whitespace-normalized, with where it goes
(plan A1, FM1). Written and committed before any sentence moves. The
same text applies to `templates/AGENTS.md.template` (the `agents-md`
pair in tests/mirror.toml); only the demand id example differs there.

Tags:

- `stays` — the sentence stays in AGENTS.md, word for word.
- `moves → <file>` — the sentence leaves AGENTS.md and lands verbatim
  (whitespace-normalized) in that file and in its installed copy under
  `.claude/`. tests/test_instructions.py `TestInventory` checks it.
- `duplicate of <file> <where>` — the file already states the rule; the
  AGENTS.md sentence is removed and the file keeps its own wording.

A step label (`1. **Triage** the cycle (…)`) stays as the step's pointer
line even when the sentence after it moves; where a moved sentence began
with its step label, the label is left out of the sentence below.

## Sentences

| # | section | tag | sentence |
|---|---|---|---|
| 1 | loop | stays | Never start code on request: code starts only inside a signed-off cycle (kernel ADR-0019). |
| 2 | loop | stays | A demand (e.g. `FWD-002`) is one page derived from the plan; it decides nothing new. |
| 3 | loop 1 | stays | **Triage** the cycle (`fde-triage`). |
| 4 | loop 1 | stays | Size is set on the cycle, never on a demand. |
| 5 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Inputs | Inputs are judged for THIS cycle (`sensitive` is always false in a public/internal project). |
| 6 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Inputs | Sensitive or irreversible? Unsure on either → true. |
| 7 | loop 1 | duplicate of skills/fde-triage/SKILL.md intro | Torn between sizes → take the larger. |
| 8 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## RULE | **RULE, checked mechanically, not estimated**: Categorically distinct from XS, a commit lane verified on the real diff by the `rule-lane` gate (`fde-triage`, kernel ADR-0015). |
| 9 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Score and size | score ≤ 1 → **XS** · 2–3 → **S** · 4–6 → **M** · ≥ 7 → **L**. |
| 10 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## What gets sized | Size sets the planner's depth and the cycle review rounds: 1 round at XS/S, full + delta at M/L. |
| 11 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Score and size | At every size `fde-spec` writes `plan.md` (minimal at XS) and a demand review is 1 round. |
| 12 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Score and size | M adds architecture: `fde-architecture` writes the ADRs, so M and L run all five roles. |
| 13 | loop 1 | stays | Announce the size in one line, commit `plan.md`, and stop at the sign-off. |
| 14 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Score and size | **Budgets, not minimums**, never extended. |
| 15 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Score and size | Timebox: XS 30 min, S 1 h, M 3 h, L 1 day. |
| 16 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Overrun on the real diff | An overrun is not re-split at review: it goes on the board; the cycle replans only if a criterion or an ADR changes. |
| 17 | loop 1 | duplicate of skills/fde-triage/SKILL.md ## Smallest mechanism first | A new rule ships as instruction first; a gate needs usage-data showing it failed. |
| 18 | loop 2 | moves → agents/fde-spec.md | `plan.md` carries a `## Threat model`, criteria and failure modes with ids dated before the first demand commit (I4), and the demand list; `deploy.md` the deploy plan; `docs/adr/` the decisions. |
| 19 | loop 2 | moves → agents/fde-spec.md | An ADR is the only home of a decision; plan and specs cite it by id; a demand never amends it. |
| 20 | loop 2 | stays | A demand is at most about 300 production lines and has exactly one layer: `front`, `back` or `infra`. |
| 21 | loop 2 | stays | A change that spans layers is always split, however small. |
| 22 | loop 2 | duplicate of skills/fde-survey/SKILL.md description | Undocumented system: `fde-survey` first. |
| 23 | loop 2 | duplicate of skills/fde-design/SKILL.md description | UI: `fde-design`. |
| 24 | loop 3 | stays | **Sign-off**: Approval happens once, at plan sign-off, and is inherited by everything after it, irreversible `deploy.md` steps included. |
| 25 | loop 3 | stays | Only a replan asks the owner again. |
| 26 | loop 4 | stays | **Build**: Demands run in parallel by default, coordinated on `cycles/C-<n>/board.md`. |
| 27 | loop 4 | stays | Each runs in its own worktree once its dependencies merge. |
| 28 | loop 4 | stays | A root with no suite gets a minimal one (I1). |
| 29 | loop 4 | stays | Never `--no-verify`. |
| 30 | loop 4 | stays | README and runbook change with how the system runs (MNT-10). |
| 31 | loop 5 | stays | **Review the demand** (`fde-review`, kernel ADR-0021). |
| 32 | loop 5 | stays | A coding demand inside a signed-off plan: isolated code review (diff × demand spec, ADR conformance, tests, the layer's check; `kind = "code"`; ~10 minutes; no scratch repositories or probe hunt). |
| 33 | loop 5 | stays | A sensitive or irreversible demand, or a real diff over ~300 production lines: adversarial review. |
| 34 | loop 5 | stays | An M/L plan, before sign-off: adversarial plan review (`kind = "plan"`). |
| 35 | loop 5 | stays | The cycle review is unchanged. |
| 36 | loop 5 | duplicate of skills/fde-review/SKILL.md ## What blocks | Blocking = critical/high, reachable inside the threat model, breaks a declared criterion — never weight alone. |
| 37 | loop 5 | duplicate of skills/fde-review/SKILL.md ## Cap | At most five findings per round. |
| 38 | loop 5 | duplicate of skills/fde-review/SKILL.md ## Budget | A blocker is fixed in the demand (`## Cycle`), never by one more round. |
| 39 | loop 6 | stays | **Merge**: Merge happens per demand; promotion and deploy happen per cycle. |
| 40 | loop 6 | moves → skills/fde-review/SKILL.md | A demand merges rebased onto main, with `python3 bin/fde/verify.py --all` green and no blocking finding open. |
| 41 | loop 7 | duplicate of skills/fde-review/SKILL.md ## Mode (Cycle) | The cycle review judges the objective — functioning and readiness against `plan.md` — and never re-reviews a demand. |
| 42 | loop 7 | duplicate of skills/fde-review/SKILL.md ## Mode (Cycle) | With a `front` demand, it runs `fde-walkthrough`. |
| 43 | loop 8 | stays | **Promote and deploy**: promotion, at every size, is `fde-promotion`'s decision against the plan's criteria. |
| 44 | loop 8 | duplicate of agents/fde-spec.md ## Cycle plan (`deploy.md`) | The deploy plan runs infra-expand → back → front → infra-contract, and every step has its own verification and rollback. |
| 45 | loop 8 | duplicate of agents/fde-spec.md ## Cycle plan (`deploy.md`) | An irreversible step is never bundled with a reversible one. |
| 46 | loop 8 | moves → agents/fde-spec.md | A failed step rolls back and the cycle stops; the user is told the outcome, not asked beforehand. |
| 47 | cycle | moves → agents/fde-spec.md | A cycle is `cycles/C-<n>/` (next free `n`), from `.fde/templates/cycle/`: `plan.md`, `deploy.md`, `board.md`, `review.md` and `promotion.md` (its `## What changes`: three lines at most, each also a backlog line). |
| 48 | cycle | stays | A demand is `specs/<id>/spec.md` plus `reviews/<id>/findings.toml`, nothing more. |
| 49 | cycle | stays | A cycle moves `draft` (grouped) → `planned` (specified, awaiting sign-off) → `running` (signed off) → `closed` or `abandoned`; several drafts may exist, one runs at a time. |
| 50 | cycle | moves → skills/fde-backlog/SKILL.md | `fde-backlog` groups items (backlog → draft); `fde-spec` writes `state: planned`; the orchestrating agent writes `running` with `signed-off:` at sign-off, then `closed` or `abandoned`. |
| 51 | cycle | moves → skills/fde-backlog/SKILL.md | The plan is frozen at sign-off; these header lines are the only edits it takes. |
| 52 | cycle | stays | A new fact always goes to the backlog — never a fix, an amendment or a question. |
| 53 | cycle | stays | The one exception is a fact that invalidates the demand's own ADR or criteria: the demand stops and the cycle replans. |
| 54 | cycle | stays | The cycle owns its declared criteria and its blocking findings. |
| 55 | cycle | stays | Nothing is fixed in-band (MNT-9) except a defect blocking a declared task, noted as such. |
| 56 | cycle | duplicate of skills/fde-review/SKILL.md ## Budget | A demand review's blocking finding is fixed inside that demand and proven by its regression test; the owner is asked only when the fix changes a criterion or an ADR, which is a replan. |
| 57 | cycle | duplicate of skills/fde-review/SKILL.md ## Budget | A non-blocking finding goes to `backlog.md` unless it shows a plan criterion unmet; then the cycle fixes it. |
| 58 | cycle | stays | A cycle review budget spent with a blocker open is the owner's call: narrow, declare the limit, or pause, recorded on `board.md` and marked in `promotion.md` at close. |
| 59 | cycle | stays | The board is the record (I7), not the conversation. |
| 60 | cycle | stays | Agents decide inside the plan and record it there. |
| 61 | cycle | stays | Two demands needing the same file: the later posts `blocked-on` and waits. |
| 62 | cycle | stays | Gates follow the owning level. |
| 63 | cycle | stays | Cycle: I4, promotion, I5, traceability; demand: I1, I2, I3; commit: RULE. |
| 64 | cycle | moves → skills/fde-backlog/SKILL.md | A cycle closes when its criteria are met with integration evidence and it is deployed or published; show the user its backlog lines (`fde-status`). |
| 65 | cycle | moves → skills/fde-backlog/SKILL.md | A cycle opened before kernel ADR-0019 finishes under its own rules. |
| 66 | backlog | stays | An idea, pain or request becomes a backlog item, not a demand: one-line acknowledgment, nothing more. |
| 67 | backlog | duplicate of skills/fde-scrum/SKILL.md ## backlog.md | A backlog line is `B-<n>`, the text, `(C-<n>)` when a cycle found it, and its evidence (`opinion < usage-data < user-test < production`). |
| 68 | backlog | duplicate of skills/fde-scrum/SKILL.md ## backlog.md | `backlog.md` starts with `goal:` (or `goal: not set`) and `date:`; with `[scrum] enabled = true`, `--gate scrum` requires them. |
| 69 | backlog | duplicate of skills/fde-scrum/SKILL.md ## backlog.md | The owner orders it; evidence never blocks a bet. |
| 70 | backlog | stays | "Fix it NOW" skips the backlog order, never the open cycle: it becomes the next cycle's first demand. |
| 71 | backlog | duplicate of skills/fde-scrum/SKILL.md intro | Sprints are retired; `sprints/` is history. |
| 72 | backlog | stays | Detail: `fde-scrum` skill. |
| 73 | detail | stays | Report the change, its evidence and what stays open, never the kernel; process gets one closing `FORWARD:` line unless the gate blocked or the user must decide. |
| 74 | detail | stays | Skills govern where this file compresses. |
| 75 | detail | stays | Never escalate kernel-interpretation questions to the user mid-demand: resolve from the skill, take the stricter reading, flag it afterwards. |

Count: 75 sentences — 39 stay, 9 move, 27 are duplicates removed.

## Pointer lines added

Where a step's rules leave, AGENTS.md keeps one pointer to the skill that
now holds them: step 2 names `fde-spec`, step 6 names `fde-review` for
when a demand may merge, step 7 becomes `(fde-review, cycle mode)`, step
8 names `fde-spec` for the deploy plan, `## Cycle` names `fde-spec` for
the layout, `fde-backlog` for the states' writers and the close, and
`fde-review` for a finding's path, and a line after the gate line names `fde-triage`
for RULE. One new sentence states the three levels (kernel ADR-0019),
which no sentence above named.

## Must stay in AGENTS.md

These apply before any skill loads, so they stay in AGENTS.md (and the
template) whatever else moves. Each rule is present when every anchor
listed for it is present, whitespace-normalized; tests/test_instructions.py
`TestInventory` checks both files.

| rule | anchor |
|---|---|
| invariants | ## Invariants (not configurable) |
| invariants | No key turns off an invariant |
| three levels | Three levels: backlog → cycle → demand |
| three levels | Merge happens per demand; promotion and deploy happen per cycle. |
| one cycle running | several drafts may exist, one runs at a time. |
| sign-off once | Approval happens once, at plan sign-off, and is inherited by everything after it |
| new fact to backlog | A new fact always goes to the backlog — never a fix, an amendment or a question. |
| one layer per demand | A demand is at most about 300 production lines and has exactly one layer: `front`, `back` or `infra`. |
| one layer per demand | A change that spans layers is always split, however small. |
| never --no-verify | Never `--no-verify`. |
| review sizing sentence | A coding demand inside a signed-off plan: isolated code review (diff × demand spec, ADR conformance, tests, the layer's check; `kind = "code"`; ~10 minutes; no scratch repositories or probe hunt). A sensitive or irreversible demand, or a real diff over ~300 production lines: adversarial review. An M/L plan, before sign-off: adversarial plan review (`kind = "plan"`). The cycle review is unchanged. |

Client copies of AGENTS.md are measured and reported, not capped (A1).
