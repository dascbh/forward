# ADR-0017 — A cycle is declared in git before it runs

date: 2026-09-28
status: accepted

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
