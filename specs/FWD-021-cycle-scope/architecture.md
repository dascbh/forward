---
date: 2026-09-28
demand: FWD-021
adr: docs/adr/0017-a-cycle-is-declared-in-git-before-it-runs.md
---

# Architecture — FWD-021 declared cycle scope and a next-cycle list

> **Revised 2026-09-28 after review round 1.** The section
> "Revision — round 1" at the end of this file governs wherever it
> differs from the contract above it.

This file is the build contract. It decides A1–A8 and A12 and records the
owner's A9–A11. The rationale and the rejected options are in ADR-0017.
Stdlib only (`tomllib`, `re`, `datetime`, `pathlib`, `subprocess` through
the existing `Gate._run_git`), plus this repository's own `runtime/`
modules.

## Files

| Path | Change |
|---|---|
| `runtime/cycle.py` | **new.** Pure core: parse, profile, the C2–C6 checks, tokens. No git and no filesystem access; inputs are texts and plain data. Imports `graph._header_fields` and `graph.canon_demand` and never copies them (MNT-11) |
| `runtime/verify.py` | `"cycle"` appended to the end of `KNOWN_GATES`. New `Gate.gate_cycle(cfg, since, explicit)`, dispatched through `run_gate(..., gid="CYCLE")` right after rule-lane, inside `if not args.staged`. `_run_git` stays the single spawn site. `_commits_in_range` may be extended to also return parent SHAs (see "Git operations"). No change to the bodies of `gate_eval_coverage`, `gate_promotion_criteria`, `gate_scrum`, `gate_rule_lane` or the `--staged` allow-list |
| `runtime/fde_lib.py` | `validate()` gains rule 6c for `[cycle]` (see "Config") |
| `runtime/graph.py` | the `cycle` node and its edges (ADR-0017 Decision 9). `"cycle"` joins `Graph.TERMINAL`. The Triage-line size lookup is extracted into one helper, `spec_size(text) -> str \| None`, that `build_graph` and `cycle` both call. `forbidden_orphans` is unchanged |
| `runtime/triage.py` | unchanged; `eligibility_for_commit` is called, not modified |
| `tests/test_cycle.py` | **new.** R14's cases plus the cases this contract adds |
| `tests/support.py` | `make_project` gains `cycle=False, stages=None` and appends `[cycle]` the way it appends `[scrum]` (extended, not cloned) |
| instruction layer | see "Instruction layer" |
| `fde.config.toml` | `[cycle] enabled = true`, `stages = []`, **in the implementation commit** (see "Enablement") |
| `cycles/C-1.md` | FWD-021's own cycle, written by the orchestrator in commit 1 (see "Enablement") |

## Cycle file grammar

`cycles/C-<n>.md`, where `<n>` is a decimal integer without leading
zeros. It is UTF-8. A file that fails to decode is a C2 breach.

**Header.** It covers the lines before the first line that starts with
`## `, and at most the first 30 lines. Parse it with
`graph._header_fields` applied to those lines (keys are lowercased and
values stripped). A `# ` title line and `---` fences are allowed and
ignored. Unknown keys are ignored.

| key | required | rule |
|---|---|---|
| `cycle` | yes | equals the file stem (`C-<n>`) |
| `objective` | yes | non-empty and not a placeholder |
| `opened` | yes | `YYYY-MM-DD`, accepted by `date.fromisoformat` |
| `demands` | yes | a comma-separated list of `<id> (<size>)`. `<id>` matches `[A-Za-z][A-Za-z0-9._-]*`, `<size>` is exactly `XS`, `S`, `M` or `L`, and no id is repeated |
| `closed` | only when closed | `YYYY-MM-DD`, not earlier than `opened` |

**Sections.** A section is introduced by a line that exactly equals its
heading. Each heading appears at most once.

| heading | required | items |
|---|---|---|
| `## Tasks` | yes | at least one |
| `## Done when` | yes | at least one |
| `## Next cycle` | yes | none required while open; at least one when closed |
| `## Intake` | when R8 requires it | see C6 |

Any other `## ` section is allowed and ignored. An **item** is a line
that starts with `- ` at column 0 inside a known section. All other
lines are non-normative: blank lines, prose, indented lines and lines
under unknown sections. Only items are checked and frozen.

- **Task item:** `- <text>`, non-empty and not a placeholder.
- **Done item:** `- [<m>] <text>`, where `<m>` is a space (open), `x`
  (met) or `-` (not met). A resolved item is `<text> — <evidence>`,
  where the separator is ` — ` (U+2014 with a space on each side) or
  ` -- `, and `<evidence>` is non-empty. Any `- ` line in `## Done when`
  that does not match this grammar is a C2 breach, because an ignored
  line could not be frozen.
- **Next-cycle item:** `- <text>`, non-empty. The literal `- none` is
  allowed only as the sole item of a closed cycle.
- **Intake item:** `- C-<m>#<k> taken`, `- C-<m>#<k> deferred`, or
  `- C-<m>#<k> dropped — <reason>`, where the reason is non-empty.

**Placeholder.** A header value or item text that is exactly one `<…>`
span (`^<[^<>]*>$` after stripping) is unfilled. It is a C2 breach. Every
placeholder the skill's schema ships uses this form. A test parses the
skill's schema block and asserts that every field is reported as a
placeholder, so the skill cannot ship a placeholder the gate misses
(R4).

**Minimal valid XS cycle (R12, 16 lines).** The skill ships it verbatim,
and a test runs it through the real checks and asserts it has at most 20
lines. The closed form adds `closed:` and inline evidence, reaching 18
lines:

```
cycle: C-12
objective: validate() rejects a [cycle] section that is not a table
opened: 2026-10-02
demands: FWD-030 (XS)

## Tasks
- reject a non-table [cycle] in fde_lib.validate()

## Done when
- [ ] declared-before
- [ ] regression-proven
- [ ] review-rounds
- [ ] residuals
- [ ] `[cycle] = 1` yields a CYCLE-TYPE violation

## Next cycle
```

## Profile (R2): one function

`cycle.profile(sizes: list[str], stages: list[str]) -> set[str]` works as
follows:
- `{"declared-before", "regression-proven", "review-rounds",
  "residuals"}` always;
- `"promotion"` added when any size is `M` or `L`;
- `"live"` and `"published"` added only when they are in `stages`.

A done item's key is found this way. Take its text before any resolution
separator. Remove an optional `amended YYYY-MM-DD: ` prefix. If what
remains equals a key, or starts with that key followed by a space, the
item carries that key.

These cases are C2 breaches:
- a required key that is missing;
- a required key that appears more than once;
- `live` or `published` present when the stage is not declared.

**Demand-specific part.**
- **S+ demand `<id>`:** some done item's text contains a path
  `specs/<dir>/acceptance.md` whose `<dir>` equals `<id>` or starts
  with `<id>-`. The prefix match respects the id boundary, so `FWD-1`
  never matches `FWD-17-x`.
- **XS demand:** at least one done item that is neither a profile key
  nor an acceptance path. When the cycle lists more than one XS demand,
  each XS id must appear in at least one such item.

**Size agreement.** Take a listed demand that has a `specs/<dir>/spec.md`
in the tree being checked, using the same `<dir>` rule. If
`graph.spec_size` returns a size for it, that size must equal the
declared one. A spec with no parsable Triage line imposes nothing.

## Checks and labels

Every breach string is `C<k> <where>: <reason>`. `<where>` is a cycle
path (`cycles/C-3.md`) or a short SHA. The gate emits one result row,
`CYCLE`, joining the first three breaches the way `gate_rule_lane` does.

| label | what | where it is evaluated |
|---|---|---|
| C1 | declared before | every examined behavior commit, against its parent tree |
| C2 | form: header, sections, items, placeholders, profile, demand part, size agreement, stray entries under `cycles/` | every cycle in the working tree, and the open cycle of every C1 parent tree |
| C3 | closure: every done item resolved, every not-met item's text (before the separator) contained verbatim in some next-cycle item, next-cycle list non-empty or `none` | every closed cycle in the working tree. Immutability is under C4 |
| C4 | frozen declaration: allowed transitions only, no deletion, no change after close, a cycle is added open | every examined commit whose own diff touches `cycles/` (**never RULE-exempt**) |
| C5 | serial: at most one open cycle, and it is the highest number | the working tree, every C1 parent tree, and every added cycle file (its number is greater than every number in its parent tree) |
| C6 | disposition of every item of every closed cycle | the working tree |

**C1 in full.** Take a commit C in the range with exactly one parent P.
It is examined when `P:fde.config.toml` exists and has
`[cycle].enabled is True`. It is a behavior commit when its own changed
files (`git diff-tree --root --no-commit-id --name-only -r C`) include a
`path_matches(f, behavior_paths)` hit, where the paths come from
`gate_paths(cfg.raw)` of the working tree (the same ones I1 uses). A
behavior commit is green when either of these holds:
- `triage.eligibility_for_commit(project, C, cfg=cfg)` is eligible
  (working-tree `cfg`, as `gate_rule_lane` uses). Evaluate this only when
  the next condition fails, to save subprocesses.
- In P, C5 holds, exactly one open cycle exists, it passes C2 against
  P's own `[cycle].stages`, and every acceptance path it names for an S+
  demand exists in P.

Otherwise the commit is red, labelled with the first failing reason: no
open cycle, two open, form, or a missing `acceptance.md`.

**C4 transitions.** For each `cycles/C-<n>.md` path in an examined
commit's own changed files, compare P's version with C's:

| P | C | verdict |
|---|---|---|
| absent | present | green only when C's version is open. Its number must exceed every number in P (C5). Its form is left to C2 |
| present | absent | red: a cycle file was deleted |
| closed | any change | red: a closed cycle changed |
| open | open | the parsed header (without `closed`), Tasks and Intake are equal. Done items: P's list is a prefix of C's list, and every added item is `- [ ] amended YYYY-MM-DD: <text>`. Next-cycle items: P's list is a prefix of C's list |
| open | closed | the header is equal apart from the added `closed:`. Tasks and Intake are equal. Done items have the same length, and each C item is P's item with its mark changed from space to `x` or `-` and ` — <non-empty>` appended to the unchanged text. Next-cycle items: P's list is a prefix of C's list |

When P's version is present but does not parse, the check is red
("cannot verify transition"), never skipped. Rename detection is not
used, so a rename reads as a deletion plus an addition and is red.

**C6 dispositions.** Item *k* of closed cycle *n* has the token
`C-<n>#<k>`. `none` has no token. Token matching uses the regex
`C-<n>#<k>(?!\d)`. The *next cycle* is the smallest-numbered cycle with a
number greater than *n* that exists in the working tree. Each item's
dispositions are counted from three places:
- an `## Intake` item of the next cycle that cites the token. `taken`
  additionally requires some Tasks item of that cycle to contain the
  token. `deferred` additionally requires some next-cycle item of that
  cycle to contain the token;
- with `[scrum]` on in the working tree, a line of `backlog.md` that
  contains the token and one of `opinion`, `usage-data`, `user-test` or
  `production`;
- more than one disposition, counted across both places, is a breach.

The item is red in these cases:
- **scrum off:** a next cycle exists and the item has no disposition;
- **scrum on:** the item has no disposition at any gate run after the
  close. With no next cycle yet, that means the item must be in
  `backlog.md`.

With scrum off and no next cycle yet, the item is pending: it is reported
and not red. Intake lines that cite a token of a cycle other than the
immediate predecessor, or a token that does not exist, are C6 breaches.

**Merges (R10, ADR-0017 Decision 10).** A commit M with two or more
parents is examined when any parent tree enables the mode. Its own files
are `git diff-tree -c --no-commit-id --name-only -r M`. If they touch a
behavior path, C1's second condition must hold in every enabled parent.
RULE does not apply, because merges are ineligible. If they touch
`cycles/`, the C4 table must hold against every parent that has the file.
A merge whose own-file list touches neither is counted as a "merge with
no own change" in the result row.

## Git operations

All git calls go through `Gate._git`, which is strict, or through
`_run_git` where an exit code carries meaning (as in `_rev_ok`). None
goes through `_git_lenient`.

| need | operation | absent vs failure |
|---|---|---|
| commits in range + parents | the `_resolve_range` tier chain (one definition), then one `git log --format=%H%x1f%P%x1f%s <range>`. Extend `_commits_in_range` to carry `%P` so there is one log call and one tier-3 `HEAD` check. `gate_rule_lane`'s observed behavior is unchanged | empty range is legitimate; non-zero exit → `GitOpFailure` |
| does P have path X | `git ls-tree --name-only P -- X` | exit 0 with no output = absent; non-zero → `GitOpFailure` |
| list `cycles/` in P | `git ls-tree --name-only P -- cycles/` | same |
| read a blob in P | `git show P:X`, only after `ls-tree` said it exists | non-zero → `GitOpFailure` |
| a commit's own files | `git diff-tree --root --no-commit-id --name-only -r C` (merges: `-c`) | non-zero → `GitOpFailure` |
| RULE eligibility | `triage.eligibility_for_commit`, which is unchanged and already fail-closed | a git failure there is "ineligible", so C1 decides on the cycle |
| report: behavior commits since open | the adding commit: `git log --diff-filter=A --format=%H -1 -- cycles/C-<n>.md`; then `git rev-list --count <add>..HEAD -- <behavior paths>` | explicit mode only |

The implementation may batch blob reads with `git cat-file --batch` in
binary mode, provided `_run_git` stays the only spawn site and a
`missing` line is treated as absent only for a path `ls-tree` already
listed as absent. Cost (R11): under `--all` without `--since`, the range
is `HEAD~1..HEAD`, which is about seven spawns. Commits whose parent
config is not enabled cost two spawns each and nothing more.

**Fail-closed table.**

| condition | result |
|---|---|
| `GitOpFailure` anywhere in the gate | red `CYCLE` row through `run_gate`, naming the operation |
| `P:fde.config.toml` present but not valid TOML, or `[cycle]` in P not a table, or `P`'s `stages` invalid | red `C1 <sha>: parent config …` |
| P object missing (shallow clone) | `ls-tree` fails → `GitOpFailure` → red |
| root commit (no parent) | not examined; there is no parent tree, so the mode is off |
| undecodable, malformed or stray cycle file | red C2 |
| `import cycle` fails | red `CYCLE` row, as `gate_rule_lane` does for `triage` |

## Gate behavior and output

- **Arming.** The gate is armed when the working tree's
  `cfg.raw.get("cycle", {}).get("enabled") is True`. When it is not
  armed, it adds no row under `--all` or the default run, spawns no
  git, and reads no file. Under `--gate cycle` it adds exactly one row:
  `CYCLE ✓ cycle mode off — declared-scope gate not in force`. That
  gives R9 byte-identical output on a client that never opts in.
- **Disabling the mode.** Disabling `[cycle]` also disarms history for
  that run. This is a declared residual: the disabling diff is visible
  evidence, and review judges it. This matches every other opt-in mode.
- **Row under `--all`.** One `CYCLE` row.
  - Pass text: `<N> cycle(s), <B> behavior commit(s) examined, all
    declared before (<R> RULE-exempt, <M> merge(s) with no own change)`.
  - Fail text: `"; ".join(breaches[:3])`.
- **Report under `--gate cycle` (R16).** Informational rows, each with
  `passed=True` and gid `CYCLE-RPT`:
  - the open cycle's id, its `opened:` date, and the number of behavior
    commits since it was added (0 when nothing is open);
  - one row per closed cycle: its item count, the counts of `taken`,
    `deferred`, `dropped`, `backlog` and `pending`, and its tokens;
  - the number of behavior commits in range exempted as RULE-eligible
    with no valid cycle, and separately the number of RULE-eligible
    behavior commits made while a cycle was open (A9's proxy). The
    second count calls eligibility for every behavior commit, and only
    in explicit mode.

## Config

This repository's `fde.config.toml`, in the implementation commit:

```toml
# Declared cycle scope (ADR-0017, FWD-021). Each cycle declares tasks,
# objective and done criteria in cycles/C-<n>.md before its first
# behavior commit; discoveries go to its next-cycle list.
# stages = [] — owner decision A11, 2026-09-28: nothing deploys, and the
# push is the gate's own CI, so done ends at promotion + residuals.
[cycle]
enabled = true
stages = []
```

`templates/fde.config.template.toml` (A10, commented out), placed after
`# [scrum]`:

```toml
# [cycle]
# optional declared cycle scope (fde-triage skill): every cycle declares
# its tasks, objective and done criteria in cycles/C-<n>.md before its
# first behavior commit, and anything discovered goes to its next-cycle
# list instead of into the cycle — the gate is silent when this is absent
# enabled = true
# stages = []      # delivery stages done must cover: "live", "published"
```

`validate()` rule 6c:
- `[cycle]` present but not a table: `CYCLE-TYPE`;
- `enabled` present and not a `bool`: `CYCLE-TYPE`;
- `stages` present and not a list of strings: `CYCLE-STAGES`;
- a stage outside `{"live", "published"}`, or a duplicate stage:
  `CYCLE-STAGES`;
- any key other than `enabled` and `stages`: `CYCLE-KEY`.

## Instruction layer (R13) and where each change lands

Content rules for every surface:
- the added text never contains `DEM-042`, `FWD-002` or any `{{…}}`
  token, because the `agents-md` pair's substitute and placeholder
  exceptions are counted;
- the rule's four parts (a)–(d) are stated with the needles R13's tests
  pin.

| surface | source (edit here) | installed copy (regenerate) | manifest pair |
|---|---|---|---|
| demand loop hook in step 1 ("with `[cycle]` on, open the cycle before the first behavior change"), a new `## Cycle scope — when [cycle] is enabled` section holding (a)–(d) after `## Scrum mode`, and one Voice bullet saying the next-cycle list is domain content and is presented at close outside the one-status-line rule | `templates/AGENTS.md.template` | `AGENTS.md` | `agents-md` (identical-except) |
| the cycle schema, the profile table, the 16-line minimal example, scope freeze (b) citing MNT-9 and A9, and the closing rule (c) | `skills/fde-triage/SKILL.md`, a new section `## Cycle — declared scope (when [cycle] is on)` after `## Score and size` | `.claude/skills/fde-triage/SKILL.md` | `skills` |
| (d) with scrum on: at close each item becomes a backlog row citing its token with an evidence label. "Execute" also names discoveries made inside a running demand | `skills/fde-scrum/SKILL.md` | `.claude/skills/fde-scrum/SKILL.md` | `skills` |
| A7 sentence | `skills/fde-sync/SKILL.md` | `.claude/skills/fde-sync/SKILL.md` | `skills` |
| the reviewer receives the open cycle file with the spec, judges the diff against its Tasks under MNT-9, and a next-cycle entry never excuses a finding | `skills/fde-review/SKILL.md` | `.claude/skills/fde-review/SKILL.md` | `skills` |
| `cycles/**:read` input for adversarial and promotion | `spec/roles.toml`, `agents/fde-adversarial.md`, `agents/fde-promotion.md` (`## Inputs`) | `.fde/spec/roles.toml`, `.claude/agents/…` | `spec`, `agents`, `adversarial-role` |
| gate, parser, validate, graph | `runtime/*.py` | `bin/fde/*.py` | `runtime` |
| config section | `fde.config.toml` (not mirrored), `templates/fde.config.template.toml` (source only; `fde-init` renders it into clients) | — | none |

No new drift test. `tests/test_mirror.py` covers every copy above, and a
new pair is not needed. `CLAUDE.md` is unchanged (`@AGENTS.md`). `SETUP.md`
is unchanged: runtime modules are copied by directory, not by list.

## Tests (R14 plus this contract)

The tests use temp git repos from `make_project(..., cycle=True)`. Every
red case asserts its label and reason. The spec requires these cases:
- **C1:** no cycle in the parent (red); only a closed cycle (red);
  acceptance in the same commit (red); acceptance in an earlier commit
  (green); RULE-eligible with no cycle (green); `FORWARD: RULE`-claiming,
  ineligible, no cycle (red).
- **C4:** a reworded done item (red).
- **C5:** a second cycle opened while one is open (red).
- **C6:** no disposition with scrum on (red) and with scrum off (red).
- **R9:** pre-opt-in history (green).

This contract adds these cases:
- **C1:**
  - a behavior commit in the enabling commit's child with no cycle
    (red);
  - an S+ demand declared `XS` while its `spec.md` Triage says `M` (red,
    C2 size agreement).
- **C2:** the placeholder schema from the skill (red on every field).
- **C3:**
  - a not-met item missing from Next cycle (red);
  - `none` alongside other items (red);
  - a closed file edited later (red, C4).
- **C4:**
  - a task added mid-cycle (red);
  - a `- [ ] amended 2026-10-01: …` append (green);
  - a next-cycle item removed (red);
  - a cycle file deleted (red);
  - a 3-line RULE-eligible commit that rewords a done item (red: C4 is
    not RULE-exempt).
- **C5:** a new cycle numbered below an existing one (red).
- **C6:** a double disposition (red); scrum on with the token in
  `backlog.md` lacking an evidence label (red); pending with scrum off
  (green, reported).
- **R10:**
  - a merge with no own change (green, counted);
  - an evil merge touching a behavior path with no open cycle in one
    parent (red);
  - an unparseable parent config (red);
  - a `GitOpFailure` injected (red through `run_gate`).
- **R12:** the skill's minimal example (valid, ≤ 20 lines).
- **R9:**
  - `--all` on a fixture without `[cycle]` gives byte-identical output
    with the gate present and absent;
  - this repository under `--all --since <root>` stays green.

## Enablement and FWD-021's own compliance

1. **Commit 1: declaration, no behavior path.** The orchestrator commits,
   before implementation starts:
   - `specs/FWD-021-cycle-scope/` (spec, failure modes, acceptance, this
     file);
   - `docs/adr/0017-…`;
   - the S-006 goal line;
   - `cycles/C-1.md` with the content below.
2. **Commit 2: implementation + `[cycle] enabled = true`.** Its parent
   does not enable the mode, so the gate does not examine it (R9). This
   is the last unexamined commit. If the implemented grammar differs from
   this contract, `cycles/C-1.md` is corrected here and nowhere later.
3. **Commits 3 onward.** Review reconciles, promotion and the closing
   commit are all examined against C-1. C-1 closes after promotion, and
   its next-cycle items are captured in `backlog.md` in the same commit
   or earlier (scrum is on).

`cycles/C-1.md` (commit 1):

```
cycle: C-1
objective: the cycle gate lands, with its instruction layer, and this repository is opted in
opened: 2026-09-28
demands: FWD-021 (M)

## Tasks
- runtime/cycle.py and gate_cycle per specs/FWD-021-cycle-scope/architecture.md
- validate() rule 6c, the graph cycle node, make_project(cycle=True), tests/test_cycle.py
- instruction layer (AGENTS template + AGENTS.md, fde-triage, fde-scrum, fde-sync, fde-review, role inputs) and regenerated copies
- [cycle] enabled = true in fde.config.toml, in the implementation commit
- two isolated adversarial rounds, then promotion

## Done when
- [ ] declared-before
- [ ] regression-proven
- [ ] review-rounds
- [ ] promotion
- [ ] residuals
- [ ] specs/FWD-021-cycle-scope/acceptance.md

## Next cycle
```

## Revision — round 1 (2026-09-28)

This section responds to `reviews/FWD-021/findings.toml` round 1. The
rationale is in ADR-0017's "Revision — 2026-09-28". Each subsection
replaces the contract text it names.

### Examination and configuration (F1, F8): replaces C1's "It is examined when…" and the per-commit config reads

- A commit C is **examined** when either of these holds for some parent
  P:
  - `P:fde.config.toml` has `[cycle].enabled is True`;
  - `git ls-tree --name-only -z P -- cycles/` lists at least one
    `cycles/C-<n>.md`.

  A root commit is never examined.
- **Every rule applied to C reads P's configuration.** For a merge, the
  rules are conjunctions over every examined parent. From P come:
  - `stages`;
  - `behavior_paths`, through `gate_paths(P_raw)`;
  - the scrum mode;
  - the RULE `Config`, built as `Config(path=<project>/fde.config.toml,
    raw=P_raw, weights=dict(P_raw.get("weights", {})),
    depths=dict(P_raw.get("depths", {})))` and passed to
    `triage.eligibility_for_commit(project, C, cfg=that)`, which is
    unchanged.

  A P with no config file reads as `{}`, so the defaults apply. A P
  config that is not valid TOML, or whose `[cycle]` fails
  `fde_lib.cycle_config_violations`, is red.
- **Arming is unchanged.** The working tree's `enabled is True` arms the
  run. Off means no row, no git and no read.

### Range (F4, F17): replaces the "commits in range" row of "Git operations"

The cycle gate decides its range before it calls the shared chain.
`_resolve_range` is unchanged. One way to build it is a keyword on
`_commits_in_range` whose default keeps rule-lane's behavior.

| `--since` | range | row states |
|---|---|---|
| absent | `_resolve_range(None)`: `HEAD~1..HEAD`, or everything in a young repo | `range: last commit only (<sha7>)`, or `range: full history` |
| all zeros | `git log HEAD` (full history) | `range: full history (new branch)` |
| resolves | `<since>..HEAD` | `range: <since7>..<head7>` |
| does not resolve | none; one red row | `CYCLE range: --since <x> does not resolve (force push or shallow clone) — fetch full history (fetch-depth: 0) or re-run with --since <merge-base>` |

The pass row becomes `<N> cycle(s); range <…>; <B> behavior commit(s)
examined, all declared before (<R> RULE-exempt, <M> merge(s) with no own
change)`.

### File lists (F10)

Every file list the cycle gate reads uses NUL separation:
- `git diff-tree --root --no-commit-id --name-only -z -r C`;
- `-c` in place of `--root` for a merge;
- `git ls-tree --name-only -z P -- cycles/`;
- `git ls-files -z -- cycles/`.

The output is split on NUL. All of this goes through one strict helper
over `_run_git`: a non-zero exit is `GitOpFailure`. The strict `_git`
keeps its line-splitting contract for everything else. I1's `changed()`
keeps its limit; it goes to C-1's next-cycle list.

### Size (F2): replaces "Size agreement"

- **Declaration.** `spec.md` carries `size: <XS|S|M|L>` in its header,
  meaning the lines before the first `## ` within the first 30 lines,
  parsed with `graph._header_fields`. The value is stripped and
  uppercased, and must be one of the four sizes.
- **Id normalization.** One function, `cycle.norm_id(s)`: uppercase,
  then replace every `\d+` run by `str(int(run))`. The rules that use it:
  - duplicate detection in `demands:` compares normalized ids;
  - a spec directory matches a demand when `norm_id(dir) == norm_id(id)`
    or `norm_id(dir)` starts with `norm_id(id) + "-"`;
  - more than one matching directory is red (ambiguous);
  - the acceptance-path rule for S+ demands uses the same match.
- **Check.** For each listed demand with a matching directory, the check
  is red when:
  - `spec.md` is absent;
  - it has no readable `size:`. The message reads `add "size: <declared>"
    to specs/<dir>/spec.md's header, or correct demands:`;
  - its size differs from the declared one.

  A demand declared XS with no matching directory imposes nothing.
- **Where it runs.** It runs at the absent→open transition, against the
  adding commit's own tree; on open cycles in the working tree; and at
  the open→closed transition, against P. It does **not** run inside C1's
  parent-tree form check, so history is never re-judged by a size line
  added later.
- **Graph.** `graph.spec_size(text)` returns the `size:` header when
  present and otherwise falls back to the Triage-line parse. It is for
  analytics only; the gate calls the header-only reader.

### Closed cycles (F3): replaces the C2/C3 "where it is evaluated" cells

| check | open cycle | closed cycle |
|---|---|---|
| C2 form, profile, demand part, size | working tree (current config and specs), at add, and C1's parent tree (minus size) | once, at the open→closed transition, against P's config and specs |
| C3 closure | — | once, at the open→closed transition |
| parse, C5, tokens | working tree | working tree |

### Dispositions (F5): replaces C6

- **Scrum on, read from P of the closing commit.** At the open→closed
  transition, every item except `none` must be cited in the closing
  commit's own `backlog.md`. The citation is a line containing the token
  (`C-<n>#<k>(?!\d)`) and one of `opinion`, `usage-data`, `user-test`
  or `production`. After the close, `backlog.md` is never re-read for
  that cycle; grooming is free.
- **Scrum off, read from P of the adding commit.** At the absent→open
  transition of cycle m, take predecessor n, the greatest closed number
  below m in the same tree. Every item of n that P's `backlog.md` does
  not cite with a label must appear exactly once in m's `## Intake`, as
  `taken`, `deferred` or `dropped — <reason>`:
  - `taken` requires a Tasks item of m containing the token;
  - `deferred` requires a next-cycle item of m containing it.
- **Intake under scrum on** (P of the adding commit). Items must be
  `taken`. They may cite any existing closed cycle's token, and each
  token appears at most once.
- **Invalid tokens.** An Intake token that does not exist is red at the
  adding transition.
- **Working tree.** C6 only reports: items of the latest closed cycle
  not yet taken up (scrum off, no next cycle), and backlog pulls. It is
  never red there.

### C1 additions (F7, F9)

- **RULE exemption.** Requires `triage.declares_rule(subject)` **and**
  `eligible`, computed with P's `Config`. An eligible commit that does
  not make the claim, with no valid cycle, is red:
  `C1 <sha7>: no open cycle — open one in an earlier commit, or declare
  "FORWARD: RULE — <reason>" if it is RULE-sized`.
- **No cycle opened by code.** An examined commit whose own files touch
  a behavior path must add no `cycles/C-<n>.md` (P lacks it, C has it).
  The message reads `a behavior commit opens <path>: commit the new
  cycle first, then the code`. Closing P's open cycle in a behavior
  commit stays legal.

### Form and closure fixes (F11, F12)

- **F11.** An open cycle, in the working tree and at the absent→open
  transition, has only `[ ]` done items. Any `[x]` or `[-]` is red: `an
  open cycle is declared unresolved — remove the marks before
  committing`.
- **F12.** At close, not-met items are matched one-to-one:
  - order the not-met texts (before the separator) by length,
    descending;
  - assign each to the first next-cycle item that is not yet used and
    **starts with** that text;
  - an item with no match is red: `not-met item "<t>" needs its own
    next-cycle item starting with its text`.

### Working-tree cycle set (F13)

The working-tree cycle set is `git ls-files -z -- cycles/`, meaning
tracked and staged files, read from disk. Among listed paths, anything
that is not `cycles/C-<n>.md` is a stray. Untracked files are ignored.
This adds one git call, only when the gate is armed.

### One stage set and one `[cycle]` validator (F15)

- `fde_lib.CYCLE_STAGES = ("live", "published")`.
- `fde_lib.cycle_config_violations(section) -> list[Violation]` holds
  the rule 6c logic. `validate()` calls it.
- The parent-config check calls it on P's `[cycle]`, and any violation is
  red.
- `cycle.py` imports `CYCLE_STAGES`, and no other module spells the
  literals.

### Ways out (F16)

Every breach string ends with the legal next step. The fde-triage
skill's cycle section gains a short "Ways out" list:
- a wrong declaration while the opening commit is still HEAD: amend
  that commit;
- otherwise: close it with `[-]` items and reasons, and open the next;
- stages or specs changed: nothing to do for closed cycles, and fix open
  ones in the spec (`size:`) or with an `amended` item;
- an unresolvable `--since`: re-run with a known base;
- code and a new cycle in one commit: split the commit before push.

The skill's amend advice narrows to "only while the opening commit is
still HEAD" (ADR-0017 R1g).

### Instruction-layer additions

| change | source | copy |
|---|---|---|
| `size:` header in `spec.md`, and the Ways out list | `skills/fde-triage/SKILL.md` | `.claude/skills/fde-triage/SKILL.md` |
| step 2 names `spec.md` "with a `size:` header line" | `templates/AGENTS.md.template` | `AGENTS.md` (`agents-md` pair; no counted token added) |
| backlog capture happens in the closing commit, grooming afterwards is free, and Intake under scrum on is a pull (`taken`) | `skills/fde-scrum/SKILL.md` | `.claude/skills/fde-scrum/SKILL.md` |
| RULE exemption from C1 requires the `FORWARD: RULE` claim | `skills/fde-triage/SKILL.md` (cycle section) | `.claude/skills/fde-triage/SKILL.md` |

### Tests added by this revision (each red asserts its label and remedy)

- **F1:**
  - the linear sandwich: red at Y (C4 rewording), and red at a code-only
    Y when the tree holds only closed cycles (C1);
  - the side-branch sandwich, merged: red;
  - pre-opt-in history, meaning no cycle files and flag off: still not
    examined.
- **F2:** `size:` absent (red); mismatch (red); `fwd-050` and `FWD-50`
  against `specs/FWD-050-x` (both matched, so mismatch is red); two
  matching directories (red).
- **F3:** add a stage, or remove one, after a cycle closed (green); the
  same change while a cycle is open (red, with the ways-out remedy).
- **F4:** all-zero `--since` examines full history and catches the
  breach; an unresolvable `--since` is red; the pass row names the range.
- **F5:**
  - scrum on: backlog row removed after close (green); captured item
    pulled as `taken` into a later cycle (green); close without capture
    (red);
  - scrum off: next cycle opened without covering an item (red).
- **F7:** an eligible commit without the claim and without a cycle (red);
  the same commit with the claim (green, counted).
- **F8:** narrowing `behavior_paths` in the same commit as the code (red).
- **F9:** close + open + code in one commit (red); close + code (green).
- **F10:** a change to `src/ação.py` with no cycle (red).
- **F11:** an open cycle added with `[x]` (red).
- **F12:** one next-cycle item carrying two not-met items (red).
- **F13:** an untracked `cycles/.DS_Store` (green); a tracked stray (red).
- **This repository:** `verify.py --gate cycle --since <root>` stays
  green. `3672a68` becomes examined, because its parent holds C-1, and
  passes: C-1 is open, `acceptance.md` is present, and its C-1 change is
  next-cycle appends only.

**F14 (suite cost).** This is not a criterion. Build each test class's
repositories once (`setUpClass`), and call `Gate` in-process where the
case does not need `main()`. That brings `test_cycle` back near the
builder's earlier 12 s.
