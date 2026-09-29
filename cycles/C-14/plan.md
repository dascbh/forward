cycle: C-14
state: planned
date: 2026-09-29
size: L
objective: clear the backlog — every item still needed after 0.21.0, starting with AGENTS.md as a skeleton and the detailed rules in skills
signed-off:

<!-- Triage: surfaces 3 (instruction layer, runtime/gate, client install)
· public · reversible · ~900 production lines across six demands →
3 + 0 + 0 + 2 = 5 → M by score. Taken as L: 30 items, 6 demands, and
the instruction rewrite touches every client (tie → larger). Plan
review (adversarial, kernel ADR-0021) before sign-off; each demand is
code-reviewed, except FWD-037 (the rewrite of every instruction file,
over ~300 lines), which gets adversarial review (the risk rule); cycle
review full + delta. -->

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

- **A1 — AGENTS.md is a skeleton.** At most 900 words. It holds one step
  per stage of backlog → cycle → demand and a pointer to the skill that
  owns each rule. Every rule removed from it lives verbatim in its skill,
  and the pins move with it. The loaded text per session shrinks.
- **A2 — Instructions settle the open wording.** One text each for:
  - budget spent with a blocker open is a replan (B-29);
  - resync before proposing (B-11);
  - prove a reader on a real client, and commit demand reviews before
    the cycle review (B-48, B-49);
  - range-revert rollback in the plan template (B-40);
  - MNT-9 resolvable (B-21);
  - the walkthrough model's author at every size (B-25).
- **A3 — Sizing without double counting (B-1).** `sensitive` and
  `irreversible` stop raising the cycle's size. They act per demand, and
  only through the risk rule (adversarial review) and the deploy plan's
  irreversible marks. The owner decides this at the sign-off of this
  plan.
- **A4 — Review records close.**
  - Promotion knows met, declined, limit and not met (B-30).
  - A fixed blocker records where it was fixed (B-31).
  - A merge line on the board names the demand's review record (B-39).
  - I2 checks every review record in reviews/ (B-50).
- **A5 — The backlog switch is named and strict.** `[backlog]` replaces
  `[scrum]`, and `[scrum]` is still read as an alias for old clients
  (B-37). The gate reads the header only, rejects `goal: not set` when
  the switch is on (B-34), and never crashes on a non-table (B-13). A
  test stops sprint wording in any instruction file (B-36).
- **A6 — Sync without surprises.**
  - Clients get the kernel ADRs read-only at `.fde/adr/` (B-32).
  - Sync rewrites the old config comment (B-38).
  - Sync states it writes permissions and tells the user to leave auto
    mode if blocked (B-42).
- **A7 — Gates hardened.** Covers B-12, B-14, B-15, B-16, B-20, B-27 and
  B-28, each with a red-before test. headlabs-platform stays green,
  read-only.
- **A8 — Panel polish.** Covers B-45, B-46 and B-47.
- **A9 — Backlog clear.** Every item above is done or declined in
  promotion.md. The backlog holds only what this cycle's reviews add.
- **A10 — Ships.** The suite and `verify.py --all` are green, the
  version is 0.22.0, and the change is pushed.

## Failure modes

- **FM1:** the skeleton rewrite drops a rule. Detected by the pins
  moving with their rule (FWD-033's lesson) and by a test that every
  kernel ADR-0019/0021 key term is reachable from AGENTS.md through its
  pointer. Meets A1.
- **FM2:** renaming `[scrum]` turns an old client red. Detected by an
  alias fixture. Meets A5.
- **FM3:** shipping ADRs to clients collides with a client's own
  docs/adr. Detected by a fixture: `.fde/adr/` only. Meets A6.
- **FM4:** a gate change turns headlabs red. Detected by a read-only run
  in every gate demand's review. Meets A7.
- **FM5:** parallel demands edit the same skill. Detected by claims on
  the board, and by FWD-037 merging first. Meets A1, A2.

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-037 | back | — | AGENTS.md skeleton (≤ 900 words) with the rules moved verbatim into fde-triage, fde-review, fde-backlog, fde-scrum and fde-spec, pins moved; B-29, B-11, B-48, B-49, B-40, B-21, B-25 wording; B-1 sizing rule — **adversarial review** (risk rule: rewrite of every instruction file) | A1, A2, A3 | ADR-0019, ADR-0021 |
| FWD-038 | back | FWD-037 | review records: promotion template and agent (met/declined/limit/not met), `fixed_in` in findings, board merge line names the review, I2 reads every reviews/ record | A4 | ADR-0021 |
| FWD-039 | back | FWD-037 | `[backlog]` switch with the `[scrum]` alias, strict header-only goal check, no crash on a non-table, sprint-wording test over every instruction file | A5 | ADR-0019 |
| FWD-040 | back | FWD-037 | sync: kernel ADRs to `.fde/adr/`, config comment rewrite, permissions notice and auto-mode advice | A6 | ADR-0019 |
| FWD-041 | back | — | gates: `-z` file lists, erosion warning and cycles/ exclusion, CI merge-base, non-list [gate] validation, I1-REQS on plan criteria, "kernel ADR" in runtime messages | A7 | ADR-0019 |
| FWD-042 | back | — | panel: single findings parse, readable helpers, promotion cell | A8 | ADR-0020 |

FWD-037, FWD-041 and FWD-042 start at sign-off, in parallel. FWD-038,
039 and 040 start when FWD-037 merges, because they edit the skills it
restructures.
