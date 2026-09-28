---
date: 2026-09-28
demand: FWD-021
---

# Acceptance — FWD-021 declared cycle scope and a next-cycle list

## Context

Long agent loops drift into side tasks and burn tokens. The owner wants
three things:

- every cycle declares its tasks, objective and definition of done before
  execution;
- whatever is discovered during execution goes to a list, not into the
  current cycle;
- that list is presented at the close and becomes the next cycle's input.

The owner chose gate enforcement. This file was declared before any code
existed (I4). The failure modes are in `failure-modes.toml`, and the
requirements R1–R16 and Ask-first items A1–A12 are in `spec.md`.

## Criteria

Architecture's ADR resolves A1–A8 and A12, and the owner answers A9–A11.
Any criterion below that depends on one of those answers is amended
here, dated, before implementation starts. The criterion is never
loosened after code exists.

### Gate: `cycle`

- `runtime/verify.py` gains `gate_cycle` and a `cycle` id in
  `KNOWN_GATES`, as a pure addition: no existing id is renamed, removed or
  reordered.
- The gate runs outside `--staged`, next to `gate_scrum` and
  `gate_rule_lane`. It is mirrored to `bin/fde/` and checked by
  `tests/mirror.toml`.
- It is armed only when `[cycle] enabled` is strictly `true`.

### Silence and compatibility (R9)

On a fixture client project with no `[cycle]` section:

- `verify.py --all` output is byte-identical before and after this change;
- `--gate cycle` prints exactly one "not in force" pass.

In this repository:

- `verify.py --all --since <root commit>` stays green;
- the five pre-opt-in demands that committed `acceptance.md` together with
  code (FWD-016 to FWD-020) are not examined;
- no commit whose parent tree lacked `[cycle] enabled = true` is examined.

### Declared before (R3, C1)

For every commit in range that meets all four conditions:

- it changes a `[gate].behavior_paths` file;
- it is not a merge;
- its parent tree has the mode on;
- `triage.eligibility_for_commit` does not verify it as RULE-eligible.

Its parent tree must hold an open cycle file that meets R1 and R2. For
each S+ demand that cycle lists, the parent tree must also hold
`specs/<id>/acceptance.md`.

The suite proves:

| case | expected |
|---|---|
| no cycle in the parent | red |
| only a closed cycle in the parent | red |
| `acceptance.md` added in the same commit as the code | red |
| `acceptance.md` added in an earlier commit | green |
| a RULE-eligible commit with no cycle | green |
| a `FORWARD: RULE`-claiming, ineligible commit with no cycle | red |

Every red names the commit and the check.

### Form, profile and project-awareness (R1, R2, R4)

- One function computes the required profile keys:
  - from each demand's size: `declared-before`, `regression-proven`,
    `review-rounds` and `residuals` always; `promotion` at M/L;
  - from `[cycle].stages`: `live` and `published` only when declared.
- An unknown stage is a `validate()` config violation.
- The following are red, each labeled per file:
  - a missing or empty header or section;
  - a required key that is missing;
  - an undeclared-stage key that is present;
  - an item byte-identical to the shipped placeholder;
  - an S+ demand without its `acceptance.md` path;
  - an XS demand without at least one inline item.
- No criterion from `acceptance.md` is restated in the cycle file (MNT-1).
  Isolated review checks this.

### Closure (R5, C3)

A cycle carrying `closed:` must meet all of these:

- every `## Done when` item is marked either met, or not met with a
  non-empty reason;
- every not-met item also appears in `## Next cycle`;
- `## Next cycle` holds at least one item or the literal `none`;
- the file is unchanged in every later commit.

Each violation is red in the suite.

### Frozen DoD and append-only list (R6, C4)

Take the `## Done when` item set as it stands in the parent of the
cycle's first behavior commit:

- a later version with an item removed or reworded is red;
- additions are allowed only as the ADR's A8 decision permits;
- a `## Next cycle` item removed or reworded before closure is red.

### Serial cycles (R7, C5)

Subject to A2: a cycle open while its numerically previous cycle is not
closed is red.

### The list feeds the next cycle (R8, C6)

Every item of a closed cycle has exactly one disposition, cited by its
stable token.

- **With `[scrum]` on:** the token appears in `backlog.md`, or in the next
  cycle's `## Intake` as taken or dropped with a reason.
- **With it off:** the numerically next cycle's `## Intake` lists every
  item as taken, deferred (re-listed in its own `## Next cycle`), or
  dropped with a non-empty reason.

The suite proves red for an item with no disposition, both with scrum on
and with scrum off.

### Fail closed (R10)

The suite proves each of these is red, never green:

- a git failure (routed through `run_gate`, labeled);
- an unparseable cycle file;
- an unparseable config.

A merge commit is handled exactly as the ADR records, and never silently
passed.

### Cost (R11)

The `cycle` gate adds at most 0.5 s wall to `verify.py --all` on this
repository.

- Baseline: 5.11 s on 2026-09-28, from one run.
- Promotion measures the median of 5 runs before the change and 5 runs
  after it, and reports both.

### Ceremony budget (R12)

- `skills/fde-triage` ships a minimal cycle example for one XS demand, in
  a project with no stages, of at most 20 lines.
- A test runs that example through the real gate and asserts two things:
  it is valid, and it is within the limit.

### Report (R16)

`--gate cycle` prints, beyond pass/fail:

- the open cycle's id, `opened:` date, and the number of behavior commits
  since it opened;
- for each closed cycle, its `## Next cycle` item count and the count of
  each disposition kind;
- the number of RULE-exempted commits in range.

Under `--all`, only the pass/fail rows are printed.

### Instruction layer (R13)

The same four-part rule appears in all of these:

- `templates/AGENTS.md.template` and `AGENTS.md`, in the demand loop,
  with an open-the-cycle step before the first behavior change and a
  closing rule;
- `skills/fde-triage/SKILL.md`, which also carries the schema, the profile
  table and the minimal example;
- `skills/fde-scrum/SKILL.md`, for how the list feeds the backlog.

The four parts:

1. Open and commit the cycle before the first behavior change.
2. Anything discovered goes to `## Next cycle` and is not acted on in this
   cycle. This includes a RULE-sized fix (A9), and the rule cites MNT-9.
3. At the close, resolve the DoD and present the list in the closing
   report. The Voice section states that the list is domain content and
   is not suppressed by the one-status-line rule.
4. With scrum on, items go to the backlog with evidence labels. With it
   off, they go to the next cycle's intake.

Content needles pin each part in each surface. `fde.config.toml` and
`templates/fde.config.template.toml` carry the `[cycle]` section, following
the A10 and A11 decisions. `tests/mirror.toml` passes with no new drift
test.

### ADR (R15)

`docs/adr/0017-*.md` records the A1–A12 decisions and these rejected
alternatives, each with what it traded (MNT-4):

- instruction-only;
- the cycle file under `specs/`;
- seven hard-coded criteria;
- a per-cycle path scope to detect side tasks mechanically.

### Untouched

These are unchanged in body:

- `gate_eval_coverage`, `gate_promotion_criteria`, `gate_scrum` and
  `gate_rule_lane`;
- `triage.eligibility_for_commit`, which is called and not modified.

No historical artifact is rewritten: no earlier `specs/`, `reviews/` or
`promotions/` file, and no commit. `acceptance.md` keeps its format and
its I4 gate.

### Gate

- `python3 -m unittest discover -s tests` is green.
- `python3 bin/fde/verify.py --all` passes, with no gate regressed.
- The size's two isolated adversarial rounds close with no blocking
  finding open.

## Declared residuals (accepted up front, not defects)

- **Content quality of the DoD.** The gate checks form and ordering.
  Whether an objective is verifiable, or whether an XS inline item means
  anything, is judged by the size's isolated review (FM-1).
- **Silent side tasks.** A discovered item acted on without being listed
  is not mechanically detectable without a per-cycle path scope, which is
  rejected as ceremony. The instruction rule and review under MNT-9 cover
  it (FM-4).
- **RULE as a side door.** The gate exempts RULE-eligible commits and
  cannot tell a planned one from a discovered one. The rule against it is
  instruction-level (A9, FM-7).
- **Presentation.** Nobody can gate whether the list was shown in chat.
  Consumption is gated by R8, and presentation is instruction-level
  (FM-6).
- **Truth of checked boxes.** The gate cannot see that `review-rounds` is
  ticked while a blocking finding is open. Promotion at M/L and review at
  XS/S check that (FM-14).
- **Forced close.** The gate cannot force a perpetual cycle to close.
  Serial cycles (A2) and the R16 age report make one visible (FM-5).
- **Outcome.** "Fewer side tasks and tokens" has no baseline, so it is
  not an acceptance criterion. The R16 counts and `graph.py --recurring`
  MNT-9 citations are the proxy a retro reads.

## Amendment — 2026-09-28 (ADR-0017 and owner answers A9–A11)

Made before implementation starts, as the Criteria section requires. It
only adds criteria or makes them stricter. The build contract is
`architecture.md`.

- **Serial (A2 adopted).** "Subject to A2" is now unconditional. These
  are also red:
  - a new cycle whose number is below an existing one;
  - a behavior commit whose parent tree holds two open cycles.
- **Frozen declaration (A8, and R6 made stricter).** The freeze starts at
  the opening commit. The suite also proves these cases:
  - a task added mid-cycle (red);
  - a header value changed (red);
  - a cycle file deleted (red);
  - an `- [ ] amended YYYY-MM-DD: …` done-item append (green);
  - a RULE-eligible commit that rewords a done item (red: C4 is never
    RULE-exempt).
- **Size agreement.** A demand declared at a size different from its
  `spec.md` Triage size is red.
- **Merges (R10).** These cases are proved:
  - a merge with no change of its own is green and counted in the result
    row;
  - a merge whose own changes touch a behavior path without an open
    cycle in every enabled parent is red.
- **Placeholders (R4).** A value or item that is exactly one `<…>` span is
  red. A test parses the skill's schema block and asserts that every
  field is caught.
- **Report (R16).** The report also gives the count of RULE-eligible
  behavior commits made while a cycle was open, which is the proxy for
  A9.
- **Config (A10, A11).** `fde.config.toml` carries `[cycle] enabled =
  true` and `stages = []`. `templates/fde.config.template.toml` carries
  the section commented out. `validate()` flags each of these:
  - a non-table `[cycle]`;
  - a non-boolean `enabled`;
  - a stage outside `live`/`published`, or a duplicate stage;
  - any other key.
- **Instruction layer.** Beyond the four surfaces listed in the
  Instruction layer section above:
  - `skills/fde-sync` states A7;
  - `skills/fde-review` hands the reviewer the open cycle file and says
    that a next-cycle entry never excuses a finding;
  - `spec/roles.toml`, `agents/fde-adversarial.md` and
    `agents/fde-promotion.md` list `cycles/**:read`.

  `tests/mirror.toml` passes with no new drift test.
- **Self-compliance.** Commit 1 holds this file, the ADR and
  `cycles/C-1.md`, and touches no behavior path. The implementation
  commit, which enables the mode, has commit 1 as its parent. The promotion
  decision cites both SHAs as the evidence for FWD-021's
  `declared-before`.
- **Residual added (A9, owner-confirmed).** A RULE-eligible commit made
  during an open cycle passes. The explicit report counts these commits,
  and review judges them against MNT-9.
- **Residual added.** Disabling `[cycle]` also stops the gate from
  examining history in that run, as with every opt-in mode. The disabling
  diff is the evidence, and review judges it.

## Amendment — 2026-09-28 (adversarial round 1, ADR-0017 revision)

Made after round 1 (`reviews/FWD-021/findings.toml`). Every change is
stricter or closes a demonstrated bypass; none relaxes a criterion. The
contract is `architecture.md` "Revision — round 1".

- **Silence and compatibility (restated, F1).** The line "no commit
  whose parent tree lacked `[cycle] enabled = true` is examined" becomes
  "no commit whose parent tree has neither `[cycle] enabled = true` nor
  a tracked `cycles/C-<n>.md` is examined". FM-10's protection is
  unchanged:
  - a client that never opts in gets no rows;
  - this repository's pre-FWD-021 history is not examined;
  - `--all --since <root>` stays green.

  The disable → act → re-enable sandwich, both linear and through a
  merged side branch, is red.
- **Declared before (C1 table, F7).** The row "a RULE-eligible commit
  with no cycle | green" now requires the `FORWARD: RULE` claim. An
  eligible commit with no claim and no cycle is red.
- **C1 additions:**
  - the configuration a commit is judged by is its parent's, so
    narrowing `behavior_paths` in the same commit as the code is red
    (F8);
  - a behavior commit that adds a cycle file is red (F9);
  - a change to a non-ASCII path such as `src/ação.py` is examined (F10).
- **Size (F2).** Size agreement reads the `size:` header line of
  `spec.md`. These are red:
  - a missing or unreadable `size:` for a demand the cycle names that has
    a spec directory;
  - a mismatch after id normalization (`fwd-050` = `FWD-50` = `FWD-050`);
  - more than one matching spec directory.
- **Closure (F3, F12).** A closed cycle is judged once, at its closing
  commit. A later change to `[cycle].stages` or to a spec does not turn it
  red. Carrying a not-met item over is one-to-one.
- **Open cycles (F11).** An open cycle carrying `[x]` or `[-]` marks is
  red.
- **Dispositions (F5).** The rule for R8/C6 above is replaced:
  - **with `[scrum]` on**, every item except `none` is cited, with an
    evidence label, in the closing commit's `backlog.md`. Later backlog
    grooming is green. Pulling a captured item into a later cycle's
    `## Intake` as `taken` is green;
  - **with it off**, the next cycle's `## Intake`, at its opening commit,
    covers every predecessor item exactly once. Items already captured
    in `backlog.md` are exempt.

  The suite still proves red for an item with no disposition, both with
  scrum on and with scrum off.
- **Range (F4, F17).** These are proved:
  - an unresolvable, non-zero `--since` is red;
  - an all-zero `--since` examines the full history;
  - the pass row states the range it covered.
- **Untracked files (F13).** An untracked file under `cycles/` is
  ignored. A tracked stray entry is still red.
- **Ways out (F16).** Every red message names a legal next step, and
  `skills/fde-triage` carries the "Ways out" list.
- **Residuals added:**
  - rewriting history locally before push (reset and cherry-pick) is
    undetectable (F6). A force push after push is red through the range
    rule. The skill's amend advice is narrowed to the opening commit
    while it is still HEAD;
  - a feature split into several self-declared RULE commits with no
    cycle passes each one (F7), which is ADR-0015's named risk. The
    report counts these commits;
  - narrowing `behavior_paths` in one commit governs that commit's
    children (F8). This is the same residual as I1's, and review judges
    config changes;
  - a demand declared under an id that matches no spec directory is not
    size-checked (F2). Review judges it.

## Amendment — 2026-09-28 (adversarial round 2, ADR-0017 revision 2)

Made after round 2 (`reviews/FWD-021/findings.toml`, F18–F30). Every
change is stricter, or conforms to a criterion already stated (R9). None
relaxes. The contract is `architecture.md` "Revision — round 2".

- **Merges (F18).** A merge is judged against its first parent, on
  everything it brings onto that line (`diff-tree P1 M`). Each of these is
  red:
  - a merge bringing code from a branch forked before opt-in while no
    cycle is open;
  - an orphan root merged with `--allow-unrelated-histories` and no open
    cycle;
  - a merged side branch replacing a frozen `cycles/C-1.md` item.

  The round-1 line "a merge with no change of its own is green and
  counted" becomes: a merge whose first-parent diff touches neither a
  behavior path, gate-governing config nor `cycles/` is green, and the
  result row counts every merge examined.
- **Pre-opt-in history is never judged (F19, conforming to R9).** Whether
  a commit is examined is decided first: its parent holds a `cycles/`
  tree, or its config parses with `[cycle] enabled = true`. An
  unparseable or mistyped config in an unexamined parent is never a
  breach. `--since` all-zeros and `--since <root>` over such a history
  are green.
- **No traceback (F20).** A mistyped section in any parent config
  produces either nothing (unexamined) or a labelled red row. Under
  `--all`, every other gate's row is still printed.
- **Every item disposed of exactly once, whatever the scrum mode (F21,
  F25).** At each cycle's opening commit, every item of its predecessor
  is either captured in `backlog.md` as it stood at the predecessor's
  closing commit, or listed exactly once in the new cycle's `## Intake`.
  Each of these is red:
  - toggling scrum between a close and the next opening so that an item
    escapes;
  - a captured item taken by two cycles.

  With scrum on, capture at close is still required.
- **Gate-governing config is behavior (F22).** A commit that changes
  `[gate]`, `[triage]` or `[cycle]` in `fde.config.toml` needs an open
  cycle and is never RULE-exempt. Narrowing then restoring
  `behavior_paths` or `stages` around a code commit is red.
- **Stage removal (F23).** Removing a stage while the open cycle carries
  its key is red, and the message names the way out.
- **Repository root (F24).** A project that is not the git top level
  gets one red row, and the message names the way out.
- **Report (F28).** The disposition counts (`captured`, `taken`,
  `deferred`, `dropped`, `pending`, `missing`) sum to each closed
  cycle's item count.
- **One RULE verdict (F29).** The `cycle` and `rule-lane` gates judge a
  RULE claim with the same working-tree configuration. A change to
  `[triage]` is itself a declared-cycle change, so the same-commit gap
  closed in round 1 stays closed.
- **Size (F27).** Only the `size:` header is read. The fde-triage skill no
  longer states a Triage-line rule. The client template asks for `size:`
  only when `[cycle]` is on.
- **Residuals added:**
  - merges whose first parent is not the protected line are judged as if
    it were, and may be red; rebasing is the way out *(scope)*;
  - before the first cycle file exists, an unparseable config hides the
    flag; that window is pre-opt-in (ADR-0017 R2b).
- **Not changed (F30).** `declared-before` and `residuals` stay required
  profile keys. Removing them is an open question for the owner.

## Amendment — 2026-09-28 (adversarial round 3, owner decision: linear history)

Made after round 3 (`reviews/FWD-021/findings.toml`, F31–F40) and the
owner's decision recorded in `sprints/S-006/goal.md`. Every change is
stricter. The contract is `architecture.md` "Revision — round 3".

- **Linear history after opt-in (F31).** Every commit in range with at
  least one opted parent is examined, whichever parent is first. Such a
  commit must have exactly one parent. These are red:
  - a merge made on main;
  - main merged into an orphan root or a pre-opt-in branch, then
    fast-forwarded;
  - `merge -s ours` deleting cycle files.

  The message names rebase as the way out. This replaces the round-2
  lines on merges ("judged against the first parent", and "a merge whose
  first-parent diff touches nothing is green"): after opt-in, every merge
  is red.
- **The opt-in boundary.** History before the single opt-in commit
  (merges and roots included) stays unexamined and green. That holds for
  `--since` all-zeros and `--since <root>` on clients and on this
  repository.
- **Closing commit (F32).** Found with `--first-parent`. Under linearity
  it cannot differ from the plain lookup.
- **Close and open in one commit (F33).** Red. The way out is two
  commits, so no item can lose its disposition.
- **Shallow clone (F34).** One red row naming a full fetch, never a
  silently narrowed range.
- **A red commit already on main (F35).** Full-history runs append the
  way out: a pull request, or a push once the branch exists remotely.
  The limit itself is named (ADR-0017 R3e).
- **No traceback (F36).** A `RecursionError` from a deeply nested config
  is handled like any unparseable config.
- **Messages (F37).** RULE advice appears only where RULE could apply.
- **Report (F38).** An invalid working-tree `[gate]` shape prints `n/a`,
  never a git-failure row.
- **Result row (F39).** The row accounts for every commit in range:
  examined, pre-opt-in and roots.
- **AGENTS Feed bullet (F40).** It states the mode-independent
  disposition rule.
- **Residuals added:**
  - replacing the protected branch wholesale with an unrelated history
    creates a new opt-in point (history rewriting, ADR-0017 R1g, R3a);
  - a commit that landed red on main keeps full-history runs red until
    the workflow computes a merge-base (next-cycle item, R3e).

## Amendment — 2026-09-28 (adversarial round 4; final round 5 follows)

Made after round 4 (`reviews/FWD-021/findings.toml`, F41–F46) and the
owner's decision in `sprints/S-006/goal.md`. The contract is
`architecture.md` "Revision — round 4". Every change is stricter. The
one exception is a red that moves to its cause (F43); it is stated
explicitly below.

- **Arming follows history (F41).** A run is armed when any of these
  holds:
  - the working tree enables `[cycle]`;
  - it tracks a file under `cycles/`;
  - any parent of a commit in the range is opted.

  Each of these is red in its own push's run:
  - a push that turns the flag off with code;
  - a push that deletes `cycles/` to re-root;
  - a push that turns the flag off and back on around a code commit.

  This **replaces** the round-1 residual ("disabling `[cycle]` also
  stops the gate from examining history in that run"), which no longer
  holds.
- **Once opted, always opted (F41).** After the first cycle file exists,
  the mode cannot be switched off green. Leaving means one red commit
  (deleting `cycles/` and `[cycle]`) merged deliberately. Before the
  first cycle file, `enabled = false` remains a free opt-out.
- **Never-opted clients (R9, unchanged).** `--all` output stays
  byte-identical, and `--gate cycle` gives one "not in force" row. A
  depth-1 clone of such a client is silent.
- **Serial at every cycle-touching commit (F42).** These are red at the
  commit that does them:
  - opening a cycle while another is open;
  - adding two open cycles in one commit.
- **Malformed config (F43, F44).** The commit that makes `fde.config.toml`
  malformed is red at that commit. That covers a wrong `[gate]`,
  `[cycle]` or `[scrum]` shape, TOML that does not parse, and a file that
  is not a regular file (a symlink or a directory). Before this
  revision, that commit landed green.

  *The moved red.* A child that repairs the parent's malformed config is
  judged by its own repaired values. It is green on its merits. Round 2's
  line ("a mistyped section in any parent config produces ... a labelled
  red row") is now met at the introducing commit, not at the repair. A
  child that does not repair it is still red.

  An armed working tree whose `fde.config.toml` is a symlink is one red
  row.
- **Replace objects (F45).** The cycle gate ignores `git replace`
  objects, so a local run agrees with a fresh clone.
- **Residuals changed:**
  - "permanent opt-out disarms the run" is withdrawn;
  - an intentional exit is a deliberate red commit, re-reported by
    full-history runs (ADR-0017 R4b);
  - the kernel's other git spawn sites still follow replace objects
    (next-cycle item).
