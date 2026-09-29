cycle: C-14
state: running
date: 2026-09-29
size: M
objective: clear the backlog — every item still needed after 0.21.0, starting with AGENTS.md as a skeleton and the detailed rules in skills
signed-off: 2026-09-29 (owner: "aprovado")

<!-- Triage: surfaces 3 (instruction layer, runtime/gate, client install)
· public · reversible · ~900 production lines across eight demands →
3 + 0 + 0 + 2 = 5 → M. Plan review done (reviews/C-14/findings-plan.toml,
2 blocking, answered below: FWD-037 split in three; B-1 declined). Every
demand is code-reviewed; none is over ~300 lines, sensitive or
irreversible. Cycle review full + delta. -->

## Items

- B-53 AGENTS.md keeps the loop's skeleton; detailed rules move into their skills
- B-21 MNT-9 cited by bare id in `## Cycle`
- B-25 walkthrough's intended model at XS/S is compiled by a role those sizes do not plan in
- B-29 a cycle review blocker at budget spent is the owner's call — state it as a replan
- B-11 resync (fetch, read the log) before proposing a plan for a paused demand
- B-48 prove a reader against a real client before the cycle review
- B-49 commit demand reviews before the cycle review starts
- B-40 the plan template's rollback is a range revert from the last pushed SHA
- B-1 cycle sizing in sensitive/irreversible projects floors every cycle at M
- B-30 promotion template and agent know met / declined / limit / not met
- B-31 a blocker fixed inside its demand leaves a closing record
- B-39 a demand merges only with its review record
- B-50 I2 reads every review record, not only files named findings.toml
- B-13 gate_scrum crashes when [scrum] is not a table
- B-34 the scrum gate accepts `goal: not set` and Goal/Date outside the header
- B-36 no test stops sprint instructions from returning
- B-37 `[scrum]` / fde-scrum renamed to what they are: the backlog
- B-32 clients receive the kernel ADRs they are pointed to
- B-38 sync fixes the old "backlog + sprints" config comment
- B-42 sync says up front it writes permissions; auto mode may block it
- B-12 I1 file lists with `-z` (git-quoted paths)
- B-14 erosion DeprecationWarning (re.split maxsplit)
- B-15 CI merge-base for new-branch pushes
- B-16 validate() rejects non-list [gate] paths
- B-20 erosion excludes cycles/ churn when no [gate] roots
- B-27 I1-REQS traces a front demand's plan criteria to evals/journeys/
- B-28 runtime messages say "kernel ADR-…"
- B-45 `--demand` parses findings.toml once
- B-46 panel helpers readable
- B-47 panel promotion cell: no escaped bold, cut at a word

## Threat model

Contained: cooperative agents and clients syncing a kernel whose
instructions and gates change under them. Old layouts, open cycles and
cycles run under 0.17–0.21 must stay green. Out of scope: hostile input
beyond what status.py and verify.py already tolerate.

## Acceptance criteria

- **A1 — AGENTS.md is a skeleton.** This repository's AGENTS.md is 1,100
  words or fewer (generated header included; the loop, cycle and backlog
  part goes from about 1,100 words to about 600). A committed inventory,
  `cycles/C-14/inventory.md`, maps every sentence of today's loop, cycle,
  backlog and detail sections to where it goes: it stays, it moves
  verbatim to a named skill, or it is a duplicate removed. It also lists
  the rules that must stay in AGENTS.md because they apply before any
  skill loads: the invariants, the three levels, one cycle running,
  sign-off once, new fact to backlog, one layer per demand, never
  `--no-verify`, and the review sizing sentence. The inventory is
  written and committed before any sentence moves. Client copies are
  measured and reported, not capped.
- **A2 — Instructions settle the open wording.** One text each for:
  - budget spent with a blocker open is a replan (B-29);
  - resync before proposing (B-11);
  - prove a reader on a real client, and commit demand reviews before
    the cycle review (B-48, B-49);
  - rollback by reverting the demand merges, not a range (B-40);
  - MNT-9 resolvable (B-21);
  - the walkthrough model's author at every size (B-25).
- **A3 — B-1 declined.** The risk rule (kernel ADR-0021) already carries
  sensitivity per demand. The cycle score keeps `sensitive` and
  `irreversible`, so a sensitive cycle keeps its plan review and full
  cycle review (plan review F2). Recorded as declined in promotion.md
  and in the backlog.
- **A4 — Review records close.**
  - Promotion knows met, declined, limit and not met (B-30).
  - A fixed blocker records where it was fixed (B-31).
  - A merge line on the board names the demand's review record (B-39).
  - I2 checks every review record in reviews/ (B-50).
- **A5 — The backlog switch is named and strict.** `[backlog]` replaces
  `[scrum]`, and `[scrum]` is still read as an alias. The fde-scrum
  skill becomes fde-backlog-format, or folds into fde-backlog, and the
  gate ids are renamed (B-37). The gate reads the header only and
  rejects `goal: not set` when the switch is on (B-34). It never crashes
  on a non-table (B-13). A test stops sprint wording in any instruction
  file (B-36).
- **A6 — Sync without surprises.**
  - Clients get the kernel ADRs read-only at `.fde/adr/` (B-32).
  - Sync rewrites the old config comment (B-38).
  - Sync states it writes permissions and tells the user to leave auto
    mode if blocked (B-42).
- **A7 — Gates hardened.**
  - B-12, B-14, B-16, B-20, B-27 and B-28 each have a test that is red
    before the fix.
  - B-15 changes the CI workflow, which is in the infra layer.
  - headlabs-platform stays green, checked read-only.
- **A8 — Panel polish.**
  - B-45: findings.toml is parsed once.
  - B-46: no nested `x and x[...]` expressions in the panel helpers.
  - B-47: the promotion cell has no escaped bold and is cut at a word.
- **A9 — Backlog clear.** Every item above is done or declined in
  promotion.md. The backlog holds only what this cycle's reviews add.
- **A10 — Ships.** The suite and `verify.py --all` are green, the
  version is 0.22.0, and the change is pushed.

## Failure modes

- **FM1:** the skeleton drops a rule. Detected in three ways:
  - the inventory (A1) is committed first and reviewed;
  - a test fails if any sentence the inventory marks "moves" is missing,
    verbatim, from its named skill;
  - a test fails if any must-stay rule is missing from AGENTS.md.

  Meets A1.
- **FM2:** renaming `[scrum]` turns an old client red. Detected by an
  alias fixture. Meets A5.
- **FM3:** shipping ADRs collides with a client's own docs/adr.
  Detected by a fixture: they are written to `.fde/adr/` only. Meets A6.
- **FM4:** a gate change turns headlabs red. Detected by a read-only run
  in every gate demand's review. Meets A7.
- **FM5:** parallel demands edit the same file (a skill, verify.py or
  status.py). Detected by board claims and by the dependency column:
  FWD-041 edits verify.py before FWD-038 and FWD-039 do. Meets A1, A4,
  A5, A7.

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-037 | back | — | inventory first (`cycles/C-14/inventory.md`), then AGENTS.md skeleton ≤ 1,100 words, sentences moved verbatim into their skills, pins moved, FM1 tests | A1 | ADR-0019, ADR-0021 |
| FWD-043 | back | FWD-037 | wording: B-29, B-11, B-48, B-49, B-40, B-21, B-25 in their skills and templates | A2 | ADR-0019, ADR-0021 |
| FWD-041 | back | — | gates: `-z` file lists, erosion warning and cycles/ exclusion, non-list [gate] validation, I1-REQS on plan criteria, "kernel ADR" in runtime messages | A7 | ADR-0019 |
| FWD-044 | infra | — | CI workflow merge-base for new-branch pushes (B-15) | A7 | ADR-0016 |
| FWD-038 | back | FWD-037, FWD-041 | review records: promotion template and agent, `fixed_in`, board merge line names the review, I2 reads every reviews/ record | A4 | ADR-0021 |
| FWD-039 | back | FWD-037, FWD-041 | `[backlog]` switch with `[scrum]` alias, skill and gate-id rename, strict header-only goal check, no crash on a non-table, sprint-wording test | A5 | ADR-0019 |
| FWD-040 | back | FWD-039 | sync: kernel ADRs to `.fde/adr/`, config comment rewrite (after the rename), permissions notice and auto-mode advice | A6 | ADR-0019 |
| FWD-042 | back | — | panel: single findings parse, helpers without nested and-expressions, promotion cell | A8 | ADR-0020 |

FWD-037, FWD-041, FWD-044 and FWD-042 start at sign-off in parallel.
FWD-043 starts when FWD-037 merges. FWD-038 and FWD-039 start when
FWD-037 and FWD-041 have both merged. FWD-040 starts when FWD-039 merges.
