# ADR-0017 — A cycle is declared in git before it runs

date: 2026-09-28
status: abandoned — superseded by ADR-0018 and FWD-022

## Status — 2026-09-28: abandoned

The owner abandoned FWD-021 the same day. The need it served, a declared
cycle with a next-cycle list, shipped as an instruction in FWD-022
(AGENTS.md `## Cycle`). Under ADR-0018 a gate comes back only as a new
demand backed by usage data showing the instruction failed, and that
demand starts from its own spec, not from this ADR. The record below
stays as history. The retro is `sprints/S-006/retro-FWD-021.md`.

### Earlier status — paused, not accepted; nothing shipped

FWD-021 is **paused unpromoted**. The owner allowed a fifth review round
and made it the final one (`sprints/S-006/goal.md`). Round 5
(`reviews/FWD-021/findings.toml`) left two blocking findings, and each
contradicts statements in this ADR that were written as guarantees, not
as residuals.

**F47: a force push whose new tip is disarmed passes silently.** The
probe:
- rewrite the tip into one commit that clears `[cycle] enabled`, deletes
  `cycles/` and adds code;
- force-push it.

The old tip does not resolve, so the range is empty. Round 4 part 0 step
5 made an unresolvable `--since` red only when the tip itself arms the
run, so the run was unarmed: undeclared code landed, and a frozen cycle
file was deleted. This contradicts:
- R1g: "after push, a force push reaches R1f, which is red";
- R3a's residual: "R1f turns it red when the old tip does not resolve";
- R4c, the premise the single-opt-in-point argument rests on;
- the round-1 acceptance amendment: "a force push after push is red
  through the range rule".

**F48: never-opted clients go red.** Round 4's arming tests b ("any
tracked file under `cycles/`") and c ("an opted parent", where opted
included any root-level `cycles` tree) read signals that are not the
project's opt-in. Three cases showed it:
- a client with an unrelated `cycles/` directory (billing cycles,
  planning notes) got red C2 "stray entry" rows, and then C1 rows;
- a client whose history once held such a directory got a CYCLE row on
  new-branch runs;
- a nested project in a monorepo whose root had opted got the "must be
  the git top level" red row.

This contradicts R9 (byte-identical output for a client that never opts
in) and FM-10, rated critical in the spec. It also contradicts R4a's
claim that a never-opted client stays silent.

**Nothing shipped.** No commit of the gate was pushed. By the owner's
decision, the gate code (`runtime/cycle.py`, `gate_cycle`, the
`validate()` rule, the graph node), its tests, the instruction layer
(AGENTS.md and its template, fde-triage, fde-scrum, fde-sync,
fde-review, role inputs) and `[cycle]` in `fde.config.toml` were
reverted on main to their state at `a6b4cd3`. The revert is `d1bb0f0`,
because the plugin is distributed from main. This ADR, the spec,
`architecture.md`, the five review rounds and `cycles/C-1.md` stay as the
record. C-1 is closed, and its next-cycle items are captured in
`backlog.md`.

**What a successor demand inherits.**
- **The starting point.** The contract as of `architecture.md`
  "Revision — round 4", together with every earlier revision it lists
  in precedence order, and the decisions and rejected options recorded
  below.
- **The review record.** The 53 findings in
  `reviews/FWD-021/findings.toml` (F1–F53, rounds 1–5). The probes are
  the regression suite a successor must pass.
- **The declared residuals.** They are in `acceptance.md`: its "Declared
  residuals" and the residual lists of each amendment.
- **Known direction for F47.** An unresolvable `--since` is red whenever
  the history was **ever** opted. For example, when the repository's
  current HEAD, or any commit reachable from it, carries a valid cycle
  file at the project root, not only when the new tip arms the run. The
  cost to decide is the history probe that a never-opted client must
  then pay.
- **Known direction for F48.** Arm only on a **valid cycle file at the
  project root**: a `cycles/C-<n>.md` that parses under the schema,
  inside the directory that holds `fde.config.toml`. Never arm on an
  unrelated `cycles/` directory, on stray files in it, or on the
  repository root when the project is nested. Tests b and c, and the
  opted test in history, must all use that one predicate.

Everything below this section is the decision record as it stood when
the demand paused. It is kept unchanged.

## Context

`specs/FWD-021-cycle-scope/spec.md` (read in full, with
`failure-modes.toml` and `acceptance.md`) asks for three things the kernel
lacks: a definition of done below S and for multi-demand rounds, a
scope-freeze rule outside `[scrum]`, and a next-cycle list that is
presented at the close and consumed by the next cycle. The owner chose
gate enforcement over an instruction-only rule on 2026-09-28.

The spec settles the vocabulary (cycle, open/closed, profile, next-cycle
list) and the requirements R1–R16. It leaves A1–A8 and A12 to this ADR
and A9–A11 to the owner. The build contract is
`specs/FWD-021-cycle-scope/architecture.md`; this ADR records the
decisions and what each rejected option traded.

The spec's Finding F-A matters here: `gate_promotion_criteria` checks that
`acceptance.md` exists and is dated, never that it precedes code. In each
of FWD-016..FWD-020 the commit that added `acceptance.md` also changed
behavior paths. I4 held in the session, not in git.

Three facts about the current runtime shape the design:
- `Gate._resolve_range`, `GitOpFailure`, `run_gate` and
  `triage.eligibility_for_commit` already give a fail-closed, per-commit
  way to walk a range. ADR-0015 is the posture: where mechanical
  certainty is unavailable, the answer is never "pass".
- Every opt-in mode (`[scrum]`, `[erosion]`, `[walkthrough]`) is silent
  under `--all` when off and prints one "not in force" pass under
  `--gate <id>`.
- In a client, the default `behavior_paths` (`src/`, `lib/`, `app/`, …)
  do not include `bin/fde/`, `.fde/` or `.claude/`. Only this repository
  declares its installed copies as behavior (ADR-0007, finding F4).

Weights: functional_correctness 30 and maintainability 22 lead;
reliability and usability 12 each. The kernel's own warning applies with
full force: if a three-line change pays the full flow, the framework is
turned off in week two (FM-8).

## Options considered

**Instruction-only (a rule in AGENTS.md and the skills, no gate).**
Rejected by the owner on 2026-09-28. It is also what exists today: MNT-9
("adjacent improvements are noted for later, never fixed in-band") has
been in the catalog since 0.3.0 and is cited by one skill. Finding F-A
shows that even I4's "before" did not survive as an instruction. What it
traded: zero runtime code, against a rule that holds only while the
context window holds it.

**The cycle file under `specs/<demand-id>/`.** Rejected (FM-8).
`gate_promotion_criteria` requires `acceptance.md` in every `specs/*/`
directory, and graph rule 1 forbids `acceptance.md` without `spec.md`. An
XS cycle there would have to write both, which is the S ceremony XS
exists to skip. It would also tie one cycle to one demand, and a round
file lists several. What it traded: no new top-level directory, against
either XS ceremony or an exception carved into two existing gates.

**Under `sprints/S-<n>/`.** Rejected: the cycle must work with `[scrum]`
off, and a sprint contains many cycles.

**Seven hard-coded done criteria (the owner's round file, verbatim).**
Rejected (FM-12). "Live in production" and "published" mean nothing in a
project that deploys and publishes nothing, this one included, and
ticking a meaningless box trains box-ticking. The profile is computed
from each demand's size and from the stages the project declares.

**A per-cycle path scope ("this cycle may touch only these paths") to
detect side tasks mechanically.** Rejected as ceremony. Every cycle would
have to predict its file set, a wrong prediction would block legitimate
work mid-cycle, and a side task inside a declared path would still pass.
It buys a weak signal at the price of the exact friction FM-8 warns
about. FM-4 is covered instead by freezing the declaration (Decision 6),
by review against MNT-9 with the cycle file as the reference (MNT-4), and
by the report's RULE-during-open-cycle count (Decision 9).

**Attribution by commit trailer (`Cycle: C-7`) or by `<demand-id>:`
subject prefix (A1).** Rejected. A trailer is one more per-commit claim
the gate would have to verify against something anyway, and with serial
cycles (Decision 2) there is only one candidate to verify it against, so
it adds ceremony and no information. The subject prefix is this
repository's habit (62 of 99 commits), not a kernel rule, and clients do
not follow it.

**Per-branch or per-worktree cycle numbering (A2).** Rejected. The
branch is git state, not tree content, so the numbering could not be
checked from a tree and would collide or vanish at merge. Parallel
branches that each open a cycle collide on the next number; that
conflict is the intended signal.

**Pre-commit participation (`--staged`, A6).** Rejected. RULE
eligibility is decided after the fact against the real commit
(ADR-0015); before the commit exists there is only `triage.py --check`'s
advisory preview. A staged C1 would either block RULE-eligible work
(FM-7) or trust a preview, which is the claim-based exemption R3 forbids.
It would also break "pre-commit stays fast". The pre-commit hook, pinned
by ADR-0016 Decision 9, is unchanged.

**A named path exemption for `fde-sync` and version-bump commits
(A7).** Rejected. R3 forbids exemption by path, and none is needed; see
Decision 7.

**Freezing the definition of done at the first behavior commit's parent
(the spec's R6 wording).** Rejected in favor of freezing at the opening
commit. Finding "the first behavior commit since open" needs a history
walk that can reach outside the checked range, which costs time and
brings back the range-boundary uncertainty ADR-0015 refuses. Freezing at
open makes every check a comparison of one commit with its own parent.
Before the opening commit is pushed, `git commit --amend` remains the
free fix. After that, the honest fix is to close the cycle with its items
marked not met and open the next. Acceptance's R6 red cases stay red.

**Mechanically cross-checking `review-rounds` against
`reviews/<id>/findings.toml` (offered under A5 by FM-14).** Rejected for
this demand. Reading findings for an open blocking item means judging
review content, which the gate's "form and ordering only" boundary
excludes. Promotion at M/L and review at XS/S remain the check.

**Placeholder detection by a byte list copied from the skill.**
Rejected (MNT-1). The gate would have to carry a second copy of the
skill's schema text. The rule is structural instead: a value or item
that is exactly one `<…>` span is unfilled. Every placeholder the skill
ships uses that form, and a test pins it.

## Decision

The build contract (schema grammar, check-by-check git operations, label
table, file landing list) is `specs/FWD-021-cycle-scope/architecture.md`.
The decisions are these.

1. **A3 — location and id.** `cycles/C-<n>.md` at the repository root,
   numbered like `sprints/S-<n>` and ordered numerically. Any other entry
   under `cycles/` is a form breach. `cycle:` must equal the file's stem.

2. **A2 — one open cycle at a time.** An open cycle must be the
   highest-numbered file, and every lower-numbered cycle must be closed
   ("no closure, no next cycle"). This is checked in the working tree and
   in the parent tree of every examined behavior commit. The accepted
   cost is that parallel branches cannot each hold their own cycle.
   Subagents are not affected: an implementation subagent's worktree is
   based on HEAD (`worktree.baseRef = "head"`) and so contains the
   orchestrator's open cycle, and review and promotion write no behavior
   files. A multi-demand round is one cycle that lists N demands.

3. **A1 — attribution is structural.** A behavior commit belongs to the
   one open cycle in its parent tree. There is no trailer and no subject
   convention. Serial cycles make "some open cycle" mean "the open cycle".

4. **Declared before (C1) is pure parent-tree ordering, and it is the fix
   for Finding F-A in every project that opts in.** For each non-merge
   commit in range whose parent tree has `[cycle] enabled = true` and
   whose own diff touches a `[gate].behavior_paths` file, one of two
   things must hold:
   - it is RULE-eligible by `triage.eligibility_for_commit`, never by its
     message; or
   - its parent tree holds exactly one open, well-formed cycle whose
     profile is complete, and every `specs/…/acceptance.md` path that
     cycle names for its S+ demands exists in that parent tree.

   So `acceptance.md` can no longer arrive in the same commit as the code
   it governs. The fix is scoped. It applies only after opt-in, only to
   S+ demands named by a cycle, and never to history (R9).
   `gate_promotion_criteria` is not changed.

   One mechanical cross-check is added because the profile is computed
   from declared sizes: when a listed demand has a `spec.md` whose Triage
   line states a size (the rule `graph.py` already uses), the cycle's
   declared size must equal it. Without this, declaring an M demand as
   XS would silently drop its `acceptance.md` and promotion requirements.

5. **A4 — the orchestrating thread writes `cycles/`.** That is the thread
   that triages, opens the cycle, appends discoveries, closes it, and
   already writes `backlog.md` and `sprints/`. No role gains `cycles/**`
   in `write_scope`, and the guard is unchanged. The frozen declaration
   is enforced by the gate whoever writes the file (Decision 6), so
   scope enforcement is not needed to protect it. Subagents hand
   discoveries back through their existing artifacts:
   - review through `findings.toml`;
   - implementation through its handoff.

   The orchestrator appends them. The adversarial and promotion roles
   gain `cycles/**:read` as an input. The reviewer judges the diff
   against the declared Tasks under MNT-9, and a `## Next cycle` entry
   never excuses a finding. Promotion checks the resolved done items
   (FM-14).

6. **A8 — the declaration is frozen from the opening commit.** Take any
   examined commit that changes a cycle file which is open in its parent
   tree. Between the parent's version and the commit's version, only
   three changes are allowed:
   - appends to `## Next cycle`;
   - appends to `## Done when` of the form `- [ ] amended YYYY-MM-DD:
     <text>`, while the cycle stays open;
   - in the closing commit only, the addition of `closed:` and the
     resolution of every done item. Resolution sets the mark to `[x]`
     (met) or `[-]` (not met) and appends ` — <evidence or reason>` to
     the unchanged item text.

   Everything else is frozen. That covers the header values, `## Tasks`,
   `## Intake`, the existing done items and the existing next-cycle
   items. A closed file never changes again, and deleting any cycle file
   is a breach. Freezing Tasks and the header is stricter than R6, which
   names only the DoD and the list. It is the owner's rule taken
   literally: something discovered cannot become a task of the running
   cycle. None of these checks is RULE-exempt, because a three-line
   commit that deletes a done item is RULE-sized.

7. **A7 — no exemption for sync or version-bump commits.** In a client,
   `fde-sync` rewrites `bin/fde/`, `.fde/` and `.claude/`, which are not
   default behavior paths, so C1 never fires. In a project that
   declares them as behavior paths (this one), a sync or version bump is
   a behavior change like any other and runs inside an open cycle. Here
   it always has: kernel version bumps are commits of the demand that
   causes them. `fde-sync` gains one sentence saying so.

8. **A12 — stable item references are positional and derived.** Item
   *k* of cycle *n*'s `## Next cycle` is `C-<n>#<k>` (1-based). Nothing
   is written into the item. Positions are stable because the list is
   append-only while open and frozen once closed (Decision 6). A citation
   (in `backlog.md`, or in a next cycle's `## Intake`) writes the token.
   The `--gate cycle` report prints each item with its token, so nobody
   counts lines by hand.

9. **A5 — the graph gains a `cycle` node and no orphan rule.**
   `graph.build_graph` adds these:
   - `cycle:C-<n>` nodes, labelled with the objective;
   - `executes` edges to each declared demand;
   - `carries` edges to the next cycle when its `## Intake` cites the
     predecessor's tokens.

   `cycle` joins `Graph.TERMINAL`, as `sprint` does, so an ego graph
   does not fan out through it. `forbidden_orphans` is unchanged: the
   `cycle` gate owns every cycle check, and the graph stays evidence
   derived from files (ADR-0010). Parsing is `runtime/cycle.py`'s, and
   the graph never parses cycle files itself.

10. **R10 — merges are neither silently passed nor red by default.** A
    merge's parents are in the range as ordinary commits, and each is
    checked on its own diff. The merge itself is examined for what it
    changes on its own:
    - its own files are `git diff-tree -c` (files that differ from every
      parent), which needs no parent choice;
    - if they touch a behavior path, C1 must hold in every enabled
      parent tree;
    - if they touch a cycle file, Decision 6's transition must hold
      against every parent that has the file.

    Both rules are conjunctions, so there is still no parent choice. Two
    branches that appended to the same next-cycle list cannot both be
    prefixes, so the merge is red and the fix is to rebase. A merge with
    no change of its own is counted in the result row. It is never a
    silent pass.

11. **R2 — the profile.** One function computes it from the declared
    sizes and `[cycle].stages`. It contains:
    - `declared-before`, `regression-proven`, `review-rounds` and
      `residuals`, always;
    - `promotion` when any listed demand is M or L;
    - `live` and `published` only when declared, and red when present
      without being declared.

    Each required key appears exactly once. A done item counts as key K
    when its text, after an optional `amended YYYY-MM-DD: ` prefix,
    equals K or starts with K followed by a space.

12. **`[cycle]` config: two keys, closed set.**
    - `enabled` is a TOML boolean, checked strictly as `[scrum]` is.
    - `stages` is a list drawn from `live` and `published`. It is empty
      when absent, and a duplicate is a violation.

    `validate()` flags a wrong type, an unknown stage and any other key,
    because an unknown key silently ignored is how a bypass key would
    look. The gate is armed by the working tree's config, as every mode
    is. Each commit is examined only when its own parent tree's config
    enables the mode (R9). A parent-tree config that is not valid TOML is
    red, never "off". This repository's 81 historical configs were
    checked on 2026-09-28 and all parse.

13. **Fail closed.** These cases are red, with a labelled reason:
    - a git failure, through `GitOpFailure` and `run_gate`;
    - an undecodable or malformed cycle file;
    - a stray entry under `cycles/`;
    - an unparseable parent config;
    - a missing parent object, as in a shallow clone.

    A root commit has no parent tree and is not examined. The gate adds
    no `except Exception` inside its checks.

### Owner decisions (2026-09-28)

- **A9 — RULE commits stay outside every cycle.** C1 exempts a commit
  that is actually RULE-eligible, whether or not a cycle is open. The
  instruction layer says that anything discovered goes to the
  next-cycle list even when it is RULE-sized. The gate cannot tell a
  planned RULE commit from an in-band fix. That is a declared, permanent
  limit of the mechanism, and review is the backstop. The explicit
  report counts RULE-eligible behavior commits made while a cycle was
  open, so the retro can see the pattern. ADR-0015 is not changed.
- **A10 — `[cycle]` ships commented out in
  `templates/fde.config.template.toml`.** It is opt-in for every client.
  The commented block explains the mode in its comment lines. `fde-init`
  gains no interview question.
- **A11 — this repository declares no stages (`stages = []`).** Done ends
  at promotion plus declared residuals. The push is the gate's own CI,
  and there is no separate publish step.

### How FWD-021 complies with its own rule

The gate examines only commits whose parent tree has the mode on, and
enablement lands in the implementation commit. The sequence is:
1. **Commit 1** (before any code): spec, failure modes, acceptance, this
   ADR, `architecture.md`, the S-006 goal line, and `cycles/C-1.md`
   declaring FWD-021 (content in `architecture.md`). It touches no
   behavior path.
2. **Commit 2** (implementation): the gate, its tests, the instruction
   layer, the regenerated copies, and `[cycle] enabled = true` in
   `fde.config.toml`. Its parent does not enable the mode, so it is not
   examined. It is the last commit the gate does not examine, and so the
   one place where `cycles/C-1.md` may still be corrected if the
   implemented grammar differs from this contract.
3. **Commits 3 onward** (review reconciles, promotion, and the commit
   that closes C-1): all are examined, and C-1 is open in each parent.

So FWD-021's `acceptance.md` and its cycle precede its code in git.
Enforcement is live for FWD-021's own review rounds.

## Consequences

**What this closes.** "Before" becomes a git fact for every opted-in
behavior commit: FM-2, and F-A going forward. The declaration cannot be
weakened or grown mid-cycle (FM-3, and the mechanical half of FM-4). An
omnibus cycle blocks the next one (FM-5). Every next-cycle item gets
exactly one disposition (FM-6's consumption half). XS pays a file of
about 16 lines and no new `specs/` directory (FM-8). Clients that do not
opt in see nothing (FM-10).

**What it costs.**
- Parallel branches cannot run separate cycles.
- A declaration mistake found after push costs a close-and-reopen.
- The next-cycle list must be curated at close.

**What stays review's, permanently.** These are named, not closed:
- whether a done item is true;
- whether an objective is verifiable;
- whether something discovered was acted on silently inside a declared
  task;
- whether the list was actually shown in chat;
- whether a RULE commit during an open cycle was planned.

**I4 is fixed only where the mode is on.** A project without `[cycle]`
keeps I4's ordering unverified, as today. Making it unconditional would
need demand attribution without a cycle, which does not exist, and a
change to `gate_promotion_criteria`, which this demand forbids. The
choice is recorded as a question for the owner, to revisit after the
mode has field data (A10 again).

**The grammar is now a contract with history.** Closed cycle files are
immutable and are re-parsed by every later run. A future kernel may only
widen the grammar. A narrowing change needs a superseding ADR that says
how closed files from the older grammar are read.

## Revision — 2026-09-28 (FWD-021 review round 1)

`reviews/FWD-021/findings.toml` round 1 recorded 17 findings, three of
them blocking (F1–F3). The decisions below change Decisions 4, 6, 10, 11
and 12 and the fail-closed list. The build contract is the
"Revision — round 1" section of `architecture.md`. Where the two differ,
that section governs over the contract text above it.

**R1a — examination follows the cycles, not only the flag (F1,
blocking).** Examining a commit only when its parent's flag was on let a
disable → act → re-enable sandwich pass. It also passed through a merged
side branch, and the net diff never showed the off window.
- *Rejected: taking the mode from the range's first enabled state.* That
  depends on the range and on topological order, and it can examine
  unrelated pre-opt-in commits brought in by a merge (FM-10).
- *Rejected: making the disabling commit a breach.* Opting out must stay
  free, and a flag rule alone still misses a later rewording.
- *Chosen:* a commit is examined when its parent tree enables the mode
  **or holds any tracked `cycles/C-<n>.md`**. Deleting a cycle file is
  already a C4 breach, so once the first cycle exists every later
  commit is examined, whatever the flag says. The sandwich is red at Y,
  which is C4, or at the code commit, which is C1 against the open
  cycle. The side-branch variant is red the same way, because every
  side-branch commit is in the range and judged on its own parent.
  - The only off switch is `enabled = false` in the working tree. It
    disarms the whole run and stays visible in the net diff, so the
    existing residual stands.
  - Work done before the first cycle file exists is pre-opt-in history,
    even if the flag was toggled around it.
  - R9 is restated to match: a commit is never examined when its parent
    tree has neither the flag nor a cycle file. That still keeps every
    client that never opts in, and this repository's pre-FWD-021 history,
    out of the gate.

**R1b — a commit is judged by its parent's configuration (F8).** Mode,
`stages`, `behavior_paths` (through `gate_paths` of the parent's raw
config), the RULE axes and `rule_lane_max_loc` (a `Config` built from
the parent's raw TOML, passed to the unchanged
`triage.eligibility_for_commit`) and the scrum mode all come from P. A
commit that narrows `behavior_paths` can no longer exempt itself.
Narrowing `behavior_paths` in a later commit, which then governs that
commit's children, remains a named residual. It is the same residual as
I1's, where a config change is judged by review.

**R1c — size is declared, not scraped (F2, blocking).** The Triage line
is prose. It is unreadable in 9 of this repository's 15 specs, and a
spec could opt out just by its wording.
- `spec.md` carries a header line `size: XS|S|M|L` before its first `## `
  section. The gate reads only this line.
- A cycle that names a demand with a matching `specs/<dir>/` is red when
  that `spec.md` has no readable `size:`, and red when the size differs
  from the declared one. The message names the fix.
- Demand ids are normalized before any match: uppercased, and every
  digit run read as an integer, so `fwd-050`, `FWD-50` and `FWD-050` are
  one id.
- `graph.spec_size` prefers the header and keeps the Triage fallback for
  analytics only.
- A demand named under an id that matches no spec directory remains
  review's to judge (residual).

**R1d — closed cycles are judged once, at their closing commit (F3,
blocking).** Re-judging frozen files against today's `stages` or specs
made any later config change permanently red, with no legal fix.
- The open→closed transition runs the full form check (C2) and the
  closure check (C3) against the closing commit's parent configuration
  and specs, and the disposition check (C6, see R1e).
- In the working tree, a closed cycle is only parsed, for C5 and for its
  tokens.
- Open cycles are still checked in full in the working tree.
- Size agreement moves the same way. It is checked at the absent→open
  transition, on open cycles in the working tree, and at close. It is no
  longer part of C1's parent-tree form check, so history is never
  re-judged by a size line added later. FWD-021's own `spec.md` gains
  `size: M` in this revision.

**R1e — dispositions are events at transitions, not permanent state
(F5).**
- **Scrum on:** each next-cycle item must be cited, with an evidence
  label, in `backlog.md` of the **closing commit's own tree**. After
  that, the backlog is groomed freely. An `## Intake` item under scrum on
  is a pull from the backlog: it must be `taken`, it may cite a token of
  any closed cycle, and it is not a second disposition.
- **Scrum off:** at the absent→open transition, the new cycle's
  `## Intake` must cover every item of its immediate predecessor exactly
  once. Items the parent's `backlog.md` already cites with a label are
  not covered here, which handles a scrum on→off switch.

Intake is frozen by C4, so the record persists. The working tree only
reports pending items.

**R1f — an unresolvable `--since` is red (F4).** The narrowing is decided
in the cycle gate. The shared `_resolve_range` is unchanged, so I1 and
rule-lane are unaffected.
- A `--since` that is given, is not all zeros and does not resolve is a
  force push or a shallow fetch. It is red and names the remedy: fetch
  full history, or re-run with `--since <merge-base>`.
- An all-zero `--since` is the first push of a new branch. It examines
  the full history from HEAD.
- The rejected alternative was a full-history fallback for every
  unresolvable base. It passes a rewritten push by re-examining a
  history the rewrite already made self-consistent, which is F6's case.

**R1g — history rewriting before push is a named limit (F6).** Git
cannot tell a local reset and cherry-pick from honest ordering, and
comparing `opened:` with commit dates adds nothing, because both are
forgeable. The limit, and what still catches part of it:
- after push, a force push reaches R1f, which is red;
- before push, the rewrite is undetectable, and review is the backstop;
- the skill's advice narrows to amending the opening commit only while
  it is still HEAD. Otherwise, close as not met and open the next cycle.

**R1h — the RULE exemption requires the claim (F7).** C1 exempts a
commit only when its first message line self-declares `FORWARD: RULE`
**and** `triage.eligibility_for_commit` verifies it. This is still
exemption by verification. The claim is a precondition, as ADR-0015
already requires for the RULE lane. Every exemption is then a visible,
rule-lane-re-verified claim.

Splitting a feature into several self-declared RULE commits without a
cycle remains possible. That is ADR-0015's named risk (mechanically
small, semantically large). The owner's A9 decision keeps RULE outside
cycles, so this revision does not add a cumulative bound. The report
counts RULE-exempt commits with no cycle, and review and the retro read
that count.

**R1i — a behavior commit cannot open a cycle (F9).** A commit whose own
changes, a merge's included, touch a behavior path must not add a cycle
file. Closing the parent's cycle in a behavior commit stays legal: the
code is attributed to the cycle it closes. Close-and-open without code,
then code, is the only path into a new cycle.

**Contract fixes with no new decision.**
- **F10:** file lists use `-z`, so quoted paths match. I1's `changed()`
  shares the limit and is out of scope; it goes to C-1's list.
- **F11:** an open cycle, and a cycle at its adding commit, carries only
  `[ ]` marks.
- **F12:** carrying a not-met item over is one-to-one. Each not-met item
  must be the prefix of a distinct next-cycle item.
- **F13:** the working-tree set of cycle files is what `git ls-files`
  lists, so untracked droppings are ignored.
- **F15:** the stage set and the `[cycle]` validation live once in
  `fde_lib`, and are used by `validate()`, the parent-config check and
  `cycle.py`.
- **F16:** every breach names a legal way out, and the skill carries a
  "Ways out" list.
- **F17:** the result row names the range it covered.
- **F14:** suite cost, not a design change. `architecture.md` states the
  expectation.

## Revision — 2026-09-28 (FWD-021 review round 2)

Round 2 of `reviews/FWD-021/findings.toml` recorded F18–F30, three of
them blocking (F18, F19, F21). The build contract is `architecture.md`,
section "Revision — round 2". It governs over both earlier contract
texts.

This is the second round with blocking findings. Where modelling a case
exactly would keep producing holes, this revision **shrinks the scope and
makes the case red** instead. Those choices are marked *(shrink)* so the
owner can see the smaller, closed gate being chosen.

**R2a — a commit's own change is its diff against its first parent;
merges are judged against the first parent only (F18, blocking)
*(shrink)*.** The combined diff (`-c`) left out every file equal to one
parent, on the premise that the parent had been judged. That premise
fails for a parent the gate never examined: a branch forked before
opt-in, an orphan root merged with `--allow-unrelated-histories`, or a
pre-opt-in `cycles/C-1.md` taken as "theirs".
- A merge is examined when its **first** parent is examined.
- Its own change is `git diff-tree -r P1 M`, the whole of what it brings
  onto the first-parent line, whether or not a side commit was already
  judged.
- C1, C4 and R2c's config rule apply against P1 alone. Merges are never
  RULE-eligible.

The "merge with no own change" concept is removed. Content that arrives
through a merge is judged at the merge, against the mainline's open
cycle.

What this costs, stated as scope:
- the gate protects the first-parent line;
- a merge whose first parent is not the protected line (a `git pull`
  merge on a local branch, for example) is judged the same way and may
  be red;
- a merge that brings in a newly opened cycle together with code is red
  by R1i;
- the way out is to rebase.

The smaller alternative is to reject merge commits altogether in an
examined range, making the history linear only. That alternative is
recorded here in case round 3 finds a hole in this rule. This repository
has no merge commits.

**R2b — decide what is examined before parsing anything (F19,
blocking).** The examination test for a parent P is ordered, and nothing
it reads is reported as a breach:
1. `P:cycles` is a tree → P is examined.
2. Otherwise, if `P:fde.config.toml` parses as TOML **and**
   `[cycle].enabled is True` → P is examined.
3. Anything else, including an unparseable or mistyped config, means P
   is not examined. It is pre-opt-in history.

Configuration errors are breaches only for examined commits. An old
broken config before opt-in can no longer turn full-history runs red.

Named residual: before the first cycle file exists, the flag alone arms
examination. Breaking the TOML in that window hides that window, which
ADR-0017 R1a already treats as pre-opt-in.

**R2c — gate-governing configuration is behavior (F22).** An examined
commit is a **behavior commit for C1** when either holds:
- its own diff touches a path in P's `behavior_paths`;
- it changes the parsed value of `[gate]`, `[triage]` or `[cycle]`,
  comparing C's `fde.config.toml` with P's.

A config change of this kind is **never RULE-exempt**, because a
one-line narrowing is RULE-sized. So narrowing `behavior_paths` or
removing a stage needs an open cycle whose Tasks can be reviewed, and
the "disable, act, restore" sandwich on `behavior_paths` or `stages` is
red at its first commit. This also answers, as a fix, the owner question
from round 1 about whether gate-governing config should count as
behavior; that residual is withdrawn.

Two effects follow:
- turning the flag off inside an examined range is itself a behavior
  commit;
- a permanent opt-out (a working tree with `enabled = false`) disarms the
  run, as before, and is visible in the net diff.

`[scrum]` is not gate-governing. Under R2e, scrum mode no longer decides
whether an item is disposed.

**R2d — a stage cannot be removed from under an open cycle (F23).**
- A commit that removes a stage from `[cycle].stages` is red when P's
  open cycle carries that stage's key. The message names the way out:
  close the cycle first, marking the item `[-]` with a reason while the
  stage is still declared, then remove the stage.
- Adding a stage while a cycle is open is repaired with an `amended`
  done item, as before.

The rule "an undeclared stage key is red" is unchanged. It just can no
longer be reached by a legal path.

**R2e — every next-cycle item is disposed of exactly once, checked at
the next opening, whatever the scrum mode (F21, blocking; F25, F28).**
- **At the absent→open transition of cycle m**, take predecessor n, the
  greatest closed number below m in P. Every item of n except `none` is
  disposed of by exactly one of:
  - a line of the `backlog.md` **as it stood at n's closing commit**
    that holds the token and an evidence label. The closing commit is
    the last commit that touched the file, because a closed file never
    changes;
  - m's `## Intake`, as `taken`, `deferred` or `dropped — <reason>`.
- **Scrum toggles cannot drop an item**, because the check does not
  depend on the mode.
- **Scrum on at close** (P of the closing commit) additionally requires
  the capture in that commit's `backlog.md`, as in round 1. This is
  stricter, never weaker.
- **Pulling a captured item** into m's Intake as `taken` is a pull, not a
  disposition. It is red when any earlier cycle's Intake in P already
  took the same token (F25).
- **The report** counts, for each closed cycle: `captured`, `taken`,
  `deferred`, `dropped`, `pending` (no next cycle yet) and `missing`.
  The counts sum to the item count (F28).

**R2f — the parent's configuration is read narrowly, and a malformed
section is a red row, never a traceback (F20, F29).**
- For an examined P, the gate reads exactly three things, each shape
  checked:
  - `[cycle]`, through `fde_lib.cycle_config_violations`;
  - `[gate].behavior_paths` and `eval_paths`, each a list of strings;
  - `[scrum].enabled`, a table with a boolean.
- A wrong shape is a breach naming the commit and key. It is never an
  exception.
- **RULE eligibility uses the working-tree `Config`, the same one
  `gate_rule_lane` uses.** One claim gets one verdict (F29). This does
  not reopen R1b's gap: any change to `[triage]` is a behavior commit
  under R2c and needs an open cycle.
- Round 1's "RULE `Config` built from the parent" is withdrawn.
- `run_gate` is unchanged. The gate catches no broad exception, because
  only the shape checks above interpret parent data.

**R2g — the project must be the repository's top level (F24)
*(shrink)*.** Tree paths (`rev:path`) are root-relative, while
`ls-files` and `ls-tree` are cwd-relative. The kernel's other range
gates already assume the root: I1's `changed()` compares root-relative
names with project-relative `behavior_paths`. When `git rev-parse
--show-prefix` is non-empty, the gate returns one red row: `CYCLE: the
project must be the git top level (found prefix <p>) — move
fde.config.toml to the repository root`. Supporting subdirectory
projects is kernel-wide work and goes to C-1's next-cycle list.

**R2h — cost (F26).** The examination decision is made in batch: one
`git cat-file --batch-check` over `<P>:cycles` and `<P>:fde.config.toml`
for every parent in range, then one `git cat-file --batch` for the
configs R2b step 2 needs. Unexamined commits cost nothing more. Only
examined commits pay for the per-commit diff and reads.

**R2i — F27.** The size fact lives in one place: the `size:` header.
- The fde-triage sentence about the Triage line is removed.
- `templates/AGENTS.md.template` step 2 asks for `size:` only "with
  `[cycle]` on".
- `graph.spec_size` keeps its Triage-line fallback for analytics on
  specs without a header, and no gate reads it.

**R2d addendum — 2026-09-28 (a contradiction found in implementation).**
Three rules, taken together, left no green sequence for removing a stage:
- R2c: a `[cycle]` change needs an open cycle;
- R2d: removing a stage that the open cycle carries is red;
- the profile rule: every cycle opened while a stage is declared must
  carry that stage's key.

The route R2d's message named ("close first, then remove") ends with no
open cycle. Any new cycle opened before the removal must carry the key.

**Decided: the stage is removed in the commit that closes the cycle
carrying it.** R2d becomes the following. A commit C that removes stage
`s` (in P1's `stages`, not in C's) is red when P1's open cycle carries
the `s` key, **unless C closes that cycle** (open in P1, closed in C).
The closing transition is judged against P1's configuration, where `s`
is still declared. So the `s` item must be resolved like any other done
item under C3, and a `[-]` item is carried one-to-one into
`## Next cycle`, where the next opening must dispose of it (R2e). The
next cycle opens with `s` undeclared, so its profile no longer requires
the key.

The rejected alternative was to append `- [ ] amended YYYY-MM-DD: <s>
dropped` while the cycle stays open. It leaves an open cycle carrying an
undeclared key. That is red under the unchanged "undeclared stage key"
rule, both in the working tree and at close. Making it legal would have
needed exceptions to that rule and to the close-time form check, which
is two new rules against one.

**Why this does not reopen F22 or F23.**
- The removal is still a gate-governing change inside a declared cycle
  (R2c), never RULE-exempt.
- It leaves a resolved `s` item and, when `[-]`, a carried next-cycle
  item with a reason.
- Code after it needs a newly opened cycle (R1i forbids opening one in
  the same commit).
- Restoring the stage is another R2c change inside that cycle, and it
  forces an `amended` `s` item into it, because an open cycle missing a
  required key is red in the working tree.

Every step of a narrow → act → restore on `stages` is therefore declared
and leaves artifacts in the cycle files. None of it is hidden in the net
diff, which was F22's actual failure. F23's dead end is gone: the red
message now names this path.

**R2j — F30 declined for now.** Dropping `declared-before` and
`residuals` from the mandatory profile would remove items the
acceptance criteria and the owner's seven criteria name. That is not
"only stricter". It is recorded as a question for the owner: both
checks are enforced by C1 and C3 whether or not the items are listed.

## Revision — 2026-09-28 (FWD-021 review round 3)

Round 3 of `reviews/FWD-021/findings.toml` recorded F31–F40: F31
critical, and F32 and F33 blocking. On 2026-09-28 the owner applied
R2a's declared fallback (linear history) and authorized a fourth round
(`sprints/S-006/goal.md`). The build contract is `architecture.md`,
section "Revision — round 3". It governs over every earlier revision.
R2a's first-parent merge model is withdrawn.

**R3a — linear history after the opt-in point (F31, critical).** R2a let
whoever made a merge choose which history the gate saw. Merging main
into an orphan root, or into a branch forked before opt-in, and then
fast-forwarding, put an unexamined first parent onto HEAD's line. The
reviewer's point holds: "reject merges in an examined range" fails too,
because such a merge is itself never examined when examination depends
on its first parent. The rule is therefore stated over **all** parents.
- *Opted tree.* A tree is **opted** when it holds a `cycles` tree, or
  when its `fde.config.toml` parses with `[cycle].enabled is True`. This
  is R2b's test, applied to a tree.
- *Examined commit.* Every commit in the range with **at least one opted
  parent** is examined, whichever parent is first.
- *Linearity.* An examined commit must have **exactly one parent**. A
  merge with any opted parent is red. This covers:
  - a merge made on main;
  - main merged into an orphan root or a pre-opt-in branch, then
    fast-forwarded;
  - `-s ours` deleting every cycle file.

  The message names the way out: rebase the branch onto the protected
  line (`git rebase <main>`) and push the linear result.
- *Pre-opt-in history stays out of scope.* A commit with no opted parent
  (roots included) is pre-opt-in history and is never judged. A merge of
  two pre-opt-in parents is such a commit, so clients' and this
  repository's pre-opt-in history stay green.
- *A single opt-in point.* In a history the gate passes, the opted
  commits reachable from HEAD form one linear chain that starts at
  exactly one commit O: opted, with no opted parent.
  - Below O's successors every commit has one parent, and following
    parents from HEAD stays on opted commits until O.
  - An opted commit never has an unopted child that passes. Such a child
    either deleted every cycle file (C4) or turned the flag off with no
    cycle file present, which is an R2c config change with no open
    cycle.
  - So a second opted chain could only join through a commit with an
    opted parent and two parents, which is red.
- *Residual.* Replacing the protected branch wholesale with an unrelated
  history (a force push) creates a new O. That is history rewriting, R1g's
  limit, and R1f turns it red when the old tip does not resolve.

**R3b — the closing commit, under linearity (F32).** Every commit that
changes a cycle file after O is examined, so it has exactly one parent.
Walking from any examined P towards O therefore crosses no merge, and
`git log -1 P -- cycles/C-<n>.md` equals its `--first-parent` form. The
lookup uses `--first-parent` anyway, which makes the independence from
merges explicit at no cost. A close that arrives through a merge is red
at the merge (R3a), so the probe's side-branch backlog cannot be read.

**R3c — close and open in one commit is red (F33).** Handling it would
have meant a second source of "predecessor" (the commit's own tree) and a
second definition of the closing commit. The simpler choice, which
cannot lose items, is to forbid it. An examined commit in which one
cycle goes from open to closed and another cycle file is added is red:
`close <C-n> and open <C-m> in separate commits — the opening commit's
## Intake disposes of <C-n>'s items`. The path into a new cycle is
therefore three commits: close, open, then code. R1i's wording is
narrowed to match.

**R3d — a shallow repository is red (F34).** When armed, the gate asks
`git rev-parse --is-shallow-repository` first. `true` gives one red row
naming the fix: fetch full history (`fetch-depth: 0`, or `git fetch
--unshallow`). This makes Decision 13's "a missing parent object, as in
a shallow clone" hold. A shallow boundary commit would otherwise look
like a root and be skipped as pre-opt-in.

**R3e — a red commit already on the protected line (F35).** This is a
named limit, with a way out that is stated rather than silently absent.
A commit that reached the protected line while red (a direct push past
a red CI, or before branch protection) stays red in every later
full-history run, which is what CI does for a new branch's first push.
The limit stays for three reasons:
- a baseline or waiver key is exactly the bypass key the spec forbids;
- limiting it to already-pushed history needs the range base that a new
  branch push does not have;
- computing a merge-base in the workflow changes the run line that
  ADR-0016 Decision 9 pins.

The ways out, stated in the breach message for full-history runs and in
the fde-triage skill:
- run the branch through a pull request, whose base resolves;
- push the branch after it has at least one commit on the remote, so
  `before` resolves.

Prevention is branch protection requiring the gate. The workflow
merge-base goes to the next-cycle list as a kernel item, because it
touches ADR-0016's pins.

**R3f — contract fixes with no new decision.**
- **F36:** the config parser catches `RecursionError` alongside
  `UnicodeDecodeError` and `TOMLDecodeError`. When deciding examination,
  that reads as not opted. For an examined parent it is the "not valid
  TOML" breach.
- **F37:** the C1 message is composed per commit. The RULE advice
  appears only when the commit could be RULE-exempt: no merge, no config
  change, no claim yet. Merge advice now belongs only to R3a's
  linearity message.
- **F38:** the explicit report reads the working tree's `[gate]` paths
  through R2f's shape check. An invalid shape prints `n/a (working-tree
  [gate] paths are not a list of strings)` instead of calling git.
  Rejecting a string `behavior_paths` in `validate()` for every client
  is kernel-wide and goes to the next-cycle list.
- **F39:** the pass row accounts for the whole range: examined,
  pre-opt-in and roots.
- **F40:**
  - docstrings name the governing revision;
  - RULE eligibility is computed at most once per commit;
  - the AGENTS "Feed" bullet states R2e's mode-independent rule.

## Revision — 2026-09-28 (FWD-021 review round 4)

Round 4 of `reviews/FWD-021/findings.toml` recorded F41–F46: F41
critical, and F42 blocking. The owner decided (`sprints/S-006/goal.md`)
to fix them and run a fifth and final round. A blocking finding in round
5 pauses the demand unpromoted. Every choice below therefore takes the
closed rule that is red, over a rule that models the case. The build
contract is `architecture.md`, section "Revision — round 4". It governs
over every earlier revision.

**R4a — the run is armed by history, not by HEAD's flag (F41,
critical).** Arming read only the checked commit's own `[cycle]
enabled`. A push that turned the flag off, with code or with `cycles/`
deleted, therefore ran unarmed. The next push, turning it back on, then
judged only itself. Every push was an ordinary fast-forward, and the net
diff hid the off window.
- *Rule.* A run is armed when any of these holds:
  1. the working tree's `[cycle] enabled is True`, as before;
  2. `git ls-files` lists any file under `cycles/`;
  3. **any parent of any commit in the range is opted**, by R3a's test:
     a `cycles` tree, or a parsed `[cycle] enabled = true`.

  Test 3 needs the commit list and the batched opted test, which R3a
  already computes. The only change is that they now run before the
  arming decision rather than after it.
- *The two probes.*
  - The temporary disarm: push A's parent is opted, so push A's run is
    armed. A is examined: its `[cycle]` change is a config change with no
    open cycle (R2c), which is red.
  - The re-root: push A is examined. Deleting `cycles/C-1.md` is red under
    C4, and the config change is red as well.
- *What a never-opted client pays.* Test 3 costs one `git log` over the
  range and one `cat-file --batch-check`, even for a client that never
  opted in. R9's promise holds as written: byte-identical `--all` output
  and a single "not in force" row under `--gate cycle`. The
  architecture's earlier "no git when off" is withdrawn. A git failure in
  that probe gives a red row, and I1 is red on the same range for the
  same failure.
- *Shallow clones.* R3d's shallow-clone red row is emitted only when the
  run is armed by test 1 or 2. When test 3 alone would arm a shallow
  clone, the probe sees only the history present, so a never-opted
  client on a depth-1 runner stays silent (FM-10).

**R4b — once opted, always opted; the exit is a deliberate red (F41, the
residual corrected).** The earlier residual ("a permanent opt-out, a
working tree with `enabled = false`, disarms the run and is visible in the
net diff") was wrong, as the probes show. Under R4a it no longer holds
at all, for two reasons:
- turning the flag off is an examined config change;
- deleting a cycle file is always a C4 breach.

So after the first cycle file exists, the mode is permanent for that
history.

A pure opt-out commit (delete `cycles/`, clear the flag, nothing else,
no open cycle) was considered and **rejected**. It reopens the window F41
exploits: opt out, act while unexamined, opt back in with a fresh C-1,
all in one pull request. Closing that window would need rules about
re-opt-in, which is modelling.

The honest residual is this. A project that wants to leave lands one
commit that deletes `cycles/` and removes `[cycle]`. That commit is red
(C4), and the owner merges it deliberately past the gate. Later runs are
unarmed, because no parent is opted any more, and full-history runs
re-report that commit under R3e. Before the first cycle file exists,
`enabled = false` is still a free opt-out, as the spec's "opt-out of a
mode" intended.

**R4c — the single opt-in point, with its premise stated (F41, F46).**
R3a's argument ("an opted commit never has an unopted child that
passes") needs one premise: every commit that reaches the protected line
falls inside some armed run's range. With per-push CI over `before..after`
and R4a's arming, every pushed commit with an opted parent is examined.
- A force push whose old tip does not resolve is red (R1f).
- A history rewritten before push is R1g's limit.

The fde-triage sentence "once the first cycle file exists every later
commit is examined, whatever the flag says" gains that premise: "every
later pushed commit, with the gate running on every push".

**R4d — serial is checked at every examined commit that touches
`cycles/` (F42).** C5 ran only in the working tree and in the parent
trees of behavior commits. So a push could open C-3 while C-2 was open,
close C-2, and have C-3's opening check read C-1 as its predecessor. C-2's
items were then disposed of by nothing.
- *Rule.* For every examined commit whose own files touch `cycles/`, the
  commit's **own** tree must satisfy C5: at most one open cycle, and it is
  the highest number.
- *Result.* Opening C-3 while C-2 is open is red at that commit:
  `C5 <sha7>: opens <C-m> while <C-n> is open — close <C-n> first
  (separate commit), then open <C-m>`. Adding two open cycles in one
  commit is red the same way. With R3c this leaves one legal order:
  close, open, code.

**R4e — a malformed config is red at the commit that introduces it (F43,
F44).** The shape error was reported at the child, including the child
that repaired it. The rules are now:
1. An examined commit whose own files include `fde.config.toml` has its
   own config shape-checked. Red at that commit when any of these holds:
   - `[cycle]` fails `cycle_config_violations`;
   - `[gate]` paths are not lists of strings;
   - `[scrum]` is not a table with a boolean `enabled`;
   - the TOML does not parse;
   - `fde.config.toml` is not a regular file. `git ls-tree` gives mode
     `120000` for a symlink and type `tree` for a directory.

   The message: `C1 <sha7>: this commit makes fde.config.toml <problem>
   — fix it before pushing (amend or rebase); once pushed, the next
   commit repairs it and this one stays reported`.
2. A commit whose parent's config has such a problem is judged with the
   parent's malformed tables **replaced by its own**, when its own are
   well-formed. That is the repair, and it is green on its merits. When
   its own are also malformed, it is itself red under rule 1, if it
   touched the config, or with `C1 <sha7>: parent config <problem> and
   this commit does not repair it`.
3. When the gate is armed, a working-tree `fde.config.toml` that is a
   symlink, or that is tracked with mode `120000`, gives one red row, and
   nothing else runs: `CYCLE: fde.config.toml must be a regular file`.
   Arming (through `Config.load`, which follows symlinks) and examination
   (through blobs) can then never disagree about opt-in.

   A parent blob that is a symlink reads as "flag not set" in the
   examination test, as unparseable text always did. Once a cycle file
   exists, parents are opted by their `cycles` tree regardless, and rule
   1 is red at the commit that made the config a symlink.

The red moves to its cause. A child of a malformed parent is no longer
red when it repairs it. The introducing commit, which used to land green,
is now always red. The acceptance amendment states this explicitly.

**R4f — replace objects (F45).** Every git call the cycle gate makes
through `_run_git` carries the global option `--no-replace-objects`, so
a local run judges the same objects CI fetches. `triage.eligibility_for_commit`
is unchanged and spawns its own git. Making replace objects inert across
the kernel's other spawn sites (triage, erosion, I1) goes to the
next-cycle list. It matters only locally, because `refs/replace/*` is not
fetched by CI.

**R4g — F46 hygiene.**
- R3c's message above is a paraphrase. The emitted text is the one in
  `architecture.md` round 3, section 3, and that section governs.
- C1 reasons become a small value, kind plus text, with no string
  sentinel.
- The per-commit examiner returns its breaches and counts through one
  channel.
- Parameters named `p1*` are renamed to `parent*`, because first-parent
  semantics were withdrawn in round 3.
