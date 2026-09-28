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
