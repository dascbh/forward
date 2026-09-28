---
date: 2026-09-28
demand: FWD-021
adr: docs/adr/0017-a-cycle-is-declared-in-git-before-it-runs.md
---

# Architecture — FWD-021 declared cycle scope and a next-cycle list

> **Revised 2026-09-28 after review rounds 1–4.** The later revision
> sections at the end of this file govern wherever they differ from the
> text above them, in this order: "Revision — round 4", then "Revision —
> round 3", then "Revision — round 2" (including its part 7a), then
> "Revision — round 1", then the original contract.

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

## Revision — round 2 (2026-09-28)

This section responds to `reviews/FWD-021/findings.toml` round 2 (F18–F30).
The rationale is in ADR-0017's "Revision — 2026-09-28 (FWD-021 review
round 2)". Each subsection replaces what it names.

### 0. Preconditions (F24): new, runs first when armed

1. `git rev-parse --show-prefix` must print an empty line. Otherwise
   there is one red row: `CYCLE: the project must be the git top level
   (found prefix <p>) — move fde.config.toml to the repository root`.
   Nothing else runs.
2. Range resolution follows round 1: absent, all zeros, resolves, or red.

### 1. Examination (F19, F26): replaces round 1's "Examination and configuration"

For every commit in range, P1 is its first parent. Root commits are
skipped.

- **Batch 1.** One `git cat-file --batch-check` gets, for every distinct
  P1:
  - `P1:cycles`, where the type `tree` means present;
  - `P1:fde.config.toml`, whether it is present.
- **Batch 2.** One `git cat-file --batch` reads the config blob of every
  P1 that has no `cycles` tree and has a config. Use binary mode and
  decode as UTF-8; an undecodable config means not examined.
- **The ordered test for P1, with no breach emitted:**
  1. `cycles` is a tree → examined.
  2. Otherwise the config parses as TOML, `[cycle]` is a table and
     `enabled is True` → examined.
  3. Anything else → not examined, and never mentioned again.
- **What an examined commit is judged by.** It is judged against P1
  only. A merge's other parents are never consulted, and merges are
  never RULE-eligible.
- **Its own files.** They come from `git diff-tree -r --name-only -z P1
  C`, which is the same command for merges and non-merges.
- **Per-commit reads are for examined commits only:** P1's config (read
  again or taken from batch 2), P1's cycle files, the specs C1 needs, and
  C's config when `fde.config.toml` is among its own files.

### 2. Reading P1's configuration (F20, F29): replaces every earlier parent-config read

For an examined P1, parse `fde.config.toml` (a missing file reads as
`{}`) and take exactly these values. Each shape error is a breach, and
nothing raises:

| value | shape | error message |
|---|---|---|
| whole file | valid TOML | `C1 <sha7>: parent config is not valid TOML — this commit was pushed under the gate; re-run with --since <a base after it>` |
| `[cycle]` | `fde_lib.cycle_config_violations` returns nothing | `C1 <sha7>: parent [cycle] <violation>` |
| `[gate].behavior_paths`, `[gate].eval_paths` | absent (defaults via `gate_paths`), or a list of strings | `C1 <sha7>: parent [gate].<key> must be a list of strings` |
| `[scrum]` | absent, or a table whose `enabled` is absent or a bool | `C1 <sha7>: parent [scrum] malformed` |

Nothing else in P1's config is read. **RULE eligibility uses the
working-tree `Config`**, the same object `gate_rule_lane` receives. It is
passed to `triage.eligibility_for_commit`, which is unchanged (F29).
Round 1's parent-built `Config` is withdrawn.

### 3. C1: replaces round 1's "C1 additions" (keeps its messages)

An examined commit C is a **behavior commit** when either holds:

- **(a) behavior paths.** Its own files touch P1's `behavior_paths`.
- **(b) gate-governing config.** `fde.config.toml` is among its own files,
  and `raw.get(k)` differs between P1 and C for any `k` in `("gate",
  "triage", "cycle")`. The values are compared as parsed values, never
  as text. If C's own config does not parse, that is a behavior commit
  and a breach: `C1 <sha7>: fde.config.toml does not parse`.

A behavior commit is green only when all of these hold:
1. One of these is true:
   - P1 holds exactly one open cycle, C5 holds in P1, the cycle passes C2
     against P1's stages (size agreement excluded, as in round 1), and
     every acceptance path it names exists in P1;
   - C is not a merge, **only (a) applies** (the config is untouched),
     its subject declares `FORWARD: RULE`, and it is eligible (F7).
     Case (b) is never RULE-exempt.
2. It adds no `cycles/C-<n>.md` (F9).
3. **Stage removal (F23).** Suppose (b) holds, and some stage `s` is in
   P1's `stages` but not in C's, while P1's open cycle carries the `s`
   key. The commit is then red: `C1 <sha7>: removes stage '<s>' while
   <cycle> carries it — close the cycle first (mark '<s>' [-] with a
   reason while the stage is declared), then remove the stage`.

### 4. C4 for merges (F18)

C4's transition table runs against P1 only, on the first-parent diff's
`cycles/` paths. A side branch's `cycles/C-1.md` taken as "theirs" is
therefore a transition from P1's version, so a rewording is red.

### 5. C6: replaces round 1's "Dispositions"

- **At the absent→open transition of cycle m** (examined commit C,
  parent P1): let n be the greatest cycle number below m whose file in
  P1 is closed. If n exists:
  - **Find n's closing commit K.** `git log -1 --format=%H P1 --
    cycles/C-<n>.md` gives the last commit that touched the file, which
    for a closed file is its closing commit.
  - **Captured set.** Read `backlog.md` at K (absent reads as empty). The
    captured set is the tokens of n that appear on a line of it that also
    holds one of the four evidence labels.
  - **Coverage.** Every item of n except `none` that is not captured must
    appear exactly once in m's `## Intake` as `taken`, `deferred` or
    `dropped — <reason>`. The rules for `taken` and `deferred` are as in
    round 1. An item appearing zero times is red: `C6 <sha7> <m>: C-<n>#<k>
    has no disposition — add it to ## Intake (taken/deferred/dropped) in
    this opening commit`. An item appearing more than once is red.
  - **Captured items** may appear in m's Intake only as `taken`; that is a
    pull. Any other verdict on a captured item is red, because the item
    was already disposed of.
- **Pull uniqueness (F25).** At the same opening, a `taken` of any token
  that some other cycle's `## Intake` in P1 already lists as `taken` is
  red.
- **Unknown tokens.** An Intake token that names no existing item of a
  closed cycle in P1 is red.
- **Scrum on at close.** When P of the closing commit has scrum on, every
  item except `none` must be captured in the closing commit's own
  `backlog.md`, as in round 1. This is kept as an extra, earlier
  obligation.
- **Report (F28), for each closed cycle n:** `captured`, `taken`,
  `deferred`, `dropped`, `pending` and `missing`, which sum to the item
  count. `pending` means no later cycle exists yet. `missing` means a
  later cycle exists and the item has no disposition; it can only occur
  in history the gate did not examine. The row lists tokens per kind.
  The working tree emits no C6 red.

### 6. Instruction layer (F27): additions to round 1's table

| change | source | copy |
|---|---|---|
| remove the "must equal the size on the demand's spec.md Triage line" sentence; `size:` is the only size fact; add the stage-removal way out and the merge scope (rebase when a merge is red) | `skills/fde-triage/SKILL.md` | `.claude/skills/fde-triage/SKILL.md` |
| step 2: "with `[cycle]` on, `spec.md` also carries a `size:` header line" (conditional) | `templates/AGENTS.md.template` | `AGENTS.md` |
| C6 is checked at the next opening whatever the scrum mode; capture at close is still required with scrum on; a pull is `taken` once | `skills/fde-scrum/SKILL.md` | `.claude/skills/fde-scrum/SKILL.md` |
| the project must be the repository root | the commented `[cycle]` block in `templates/fde.config.template.toml` (one comment line) | — |

### 7. Tests added by this revision

Each red case asserts its label and way-out text.

- **F18:**
  - a pre-opt-in branch merged with code while only a closed cycle
    exists on main: red;
  - an orphan root merged with code and no open cycle: red;
  - a side branch's `cycles/C-1.md` rewording a frozen item, merged as
    theirs: red (C4);
  - a feature branch merged under an open cycle: green.
- **F19:**
  - a pre-opt-in commit with invalid TOML, or with `[cycle] enabled =
    "no"`, then opt-in: `--since` all-zeros and `--since <root>` both
    green;
  - the same breakage after the first cycle file: red.
- **F20:** `weights = 5` or `gate = "x"` in a pre-opt-in parent: green,
  with no traceback. `[gate].behavior_paths = "src/"` in an examined
  parent: red, with the row present and other gates still reported under
  `--all`.
- **F21:**
  - C-1 closed with scrum off and no capture, scrum turned on, C-2 opened
    with no Intake: red;
  - scrum on→off→close→on with an uncaptured item, then C-2 opened
    without it: red;
  - the same with Intake coverage: green.
- **F22:** narrow `behavior_paths`, change code, restore, with only closed
  cycles: red at the narrowing commit. `stages` removed and restored the
  same way: red. The same narrowing claimed as `FORWARD: RULE`: red.
- **F23:** removing `live` while the open cycle carries it: red, and the
  message names the way out. Closing with `live` `[-]` while it is
  declared, then removing it (under a new open cycle): green.
- **F24:** project in a subdirectory: one red row, and nothing else runs.
- **F25:** the same captured token taken in C-2 and again in C-3: red.
- **F26:** in a repo with 200 pre-opt-in commits, the spawn count for
  `--since` all-zeros stays constant plus a per-examined-commit cost.
  Assert this through a counter on `_run_git`, not wall time.
- **F28:** report counts sum to the item count in the F21 scenarios.
- **F29:** the parent raises `rule_lane_max_loc`, a claimed 100-line
  commit lands, and the limit is restored: `cycle` and `rule-lane` agree
  (both red). The raising commit is itself red under F22.
- **This repository:** `--gate cycle --since <root>` and `--since`
  all-zeros stay green.

### 7a. Addendum 2026-09-28: stage removal (replaces part 3 item 3 and part 7's F23 cases)

**Rule.** Let C be an examined commit whose parsed `stages` drops a
stage `s` that P1's `stages` declares.
- When P1's open cycle carries the `s` key, C is red **unless** C
  closes that cycle, meaning the file is open in P1 and has `closed:` in
  C.
- When C closes the cycle, the normal open→closed checks run against
  P1's configuration, where `s` is still declared: the full form (C2),
  the closure (C3, including the one-to-one carry of a `[-]` `s` item)
  and the scrum-on capture.
- Every other C1 condition still applies:
  - an open cycle in P1 (the one being closed);
  - not RULE-exempt (a config change);
  - no cycle file added (R1i).
- The red message: `C1 <sha7>: removes stage '<s>' while <cycle>
  carries it — remove the stage in the commit that closes <cycle>
  (resolve its '<s>' item; a [-] item is carried to ## Next cycle)`.

The fde-triage skill's "Ways out" list replaces "close the cycle first,
then remove the stage" with this sentence.

**Tests.**

The green sequence, with scrum off and stages `["live"]`:
1. C-2 opens with a `live` item. Green.
2. One commit removes `live` from `stages`, adds `closed:` to C-2, marks
   `- [-] live — we stopped deploying this service` and appends a
   next-cycle item starting with `live`. Green.
3. C-3 opens with no `live` item, and its `## Intake` disposes of every
   C-2 item, including the `live` one. Green.
4. A code commit under C-3. Green.

The red variants:

| # | what the sequence does | expected |
|---|---|---|
| a | removes `live` while C-2 stays open | red, and the message names the closing-commit path |
| b | closes C-2 first (`live` `[-]`), then removes `live` in a later commit | red: no open cycle for a gate-governing change (R2c) |
| c | removes `live` and closes C-2 while leaving `- [ ] live` unresolved | red (C3) |
| d | removes `live` and closes C-2 with `live` `[-]` but no carried next-cycle item | red (C3, one-to-one carry) |
| e | removes `live`, closes C-2, and adds C-3 in the same commit | red (R1i: a behavior commit may not add a cycle file) |
| f | the same removal claimed `FORWARD: RULE`, in a commit that does not close C-2 | red: a config change is never RULE-exempt, and the removal rule applies |
| g | after the green sequence, a commit under C-3 restores `stages = ["live"]` | the commit itself is green (open cycle, config change declared); the working tree is red until C-3 appends `- [ ] amended YYYY-MM-DD: live` |
| h | after the green sequence, the restore lands with no open cycle | red (R2c) |
| i | after the green sequence, C-3 is opened without disposing of the carried `live` item | red (R2e) |

### 8. Result row

The pass row becomes `<N> cycle(s); range <…>; <E> commit(s) examined,
<B> behavior commit(s), all declared before (<R> RULE-exempt, <M>
merge(s) examined)`. "Merge with no own change" is gone (ADR-0017 R2a).

### 9. Not changed

- F30: the profile keys stay (ADR-0017 R2j).
- The working-tree checks for open cycles, closure form at close, and the
  range rules are as in round 1.

## Revision — round 3 (2026-09-28)

This section responds to `reviews/FWD-021/findings.toml` round 3
(F31–F40), after the owner's 2026-09-28 decision to apply linear history
(`sprints/S-006/goal.md`). The rationale is in ADR-0017's "Revision —
2026-09-28 (FWD-021 review round 3)". This section governs over every
earlier one. Round 2's merge model (its parts 1, 4 and 8, and every
"P1"/"first parent" merge rule) is withdrawn.

### 0. Preconditions: replaces round 2 part 0; runs first when armed, in this order

1. **Shallow repository (F34).** `git rev-parse
   --is-shallow-repository` prints `true` → one red row, and nothing else
   runs: `CYCLE: shallow clone — the gate needs full history; fetch it
   (fetch-depth: 0, or git fetch --unshallow)`.
2. **Top level (F24).** Unchanged from round 2.
3. **Range.** Unchanged from round 1.

### 1. Examination and linearity (F31): replaces round 2 part 1

1. **Commit list.** One `git log --format=%H%x1f%P%x1f%s <range>` lists
   every commit in the range. With `--since` all-zeros or no range base,
   `<range>` is `HEAD`. There is no `--first-parent`.
2. **Opted parents.**
   - Take every distinct parent of every listed commit.
   - Decide whether each is **opted** with the batched test: a `cycles`
     tree, or a config that parses, whose `[cycle]` is a table and whose
     `enabled is True`.
   - Batch 1 is `cat-file --batch-check` over `<P>:cycles` and
     `<P>:fde.config.toml`. Batch 2 is `cat-file --batch` for the configs
     step 2 of the test needs.
   - A decode, `TOMLDecodeError` or `RecursionError` (F36) reads as not
     opted. Nothing from this step is ever a breach.
3. **Examined.** A commit is examined when **any** of its parents is
   opted. Others are counted `pre-opt-in` (and roots also `root`) and
   never read again.
4. **Linearity.** An examined commit with more than one parent is red,
   and none of its other checks run:
   `C1 <sha7>: a merge after opt-in (parents <p7>, <q7>) — history must
   stay linear once cycles exist; rebase the branch onto the protected
   line (git rebase <main>) and push the result`.
5. **The single parent.** Every other examined commit has exactly one
   parent, P. It is judged against P, and its own files are `git
   diff-tree -r --name-only -z P C`. Everything in round 2 parts 2, 3,
   5, 6 and 7a applies with "P1" read as this P.

### 2. Closing-commit lookup (F32): amends round 2 part 5

The predecessor's closing commit is found with `git log -1 --first-parent
--format=%H P -- cycles/C-<n>.md`. Under part 1 the result is the same
without `--first-parent`, because every commit after O that touches a
cycle file is examined and single-parent. The flag makes that explicit.

### 3. Close + open in one commit (F33): new C4 rule

An examined commit in which some cycle file is open in P and closed in
C, **and** some cycle file absent in P is present in C, is red:
`C4 <sha7>: closes <C-n> and opens <C-m> in one commit — commit the
close first, then open <C-m> with its ## Intake in a separate commit`.
Round 2 part 5's opening check is unchanged: its predecessor is read
from P, where the close is already committed.

### 4. Messages (F35, F37)

- **C1 "no open cycle".** The message is composed per commit from what
  the gate already knows:
  - always: `open a cycle in an earlier commit`;
  - plus `, or declare "FORWARD: RULE — <reason>" if it is RULE-sized`
    only when the commit is not a config change and has no RULE claim;
  - for a config change: `a change to [gate]/[triage]/[cycle] always
    needs an open cycle`.
- **Full-history runs.** When the range is full history (all-zero
  `--since` or none resolvable as base), every C1–C6 breach row gains
  the suffix `— if this commit is already on the protected line, this
  push did not cause it: run the branch through a pull request (its base
  resolves) or push again once the branch exists remotely (ADR-0017
  R3e)`.
- **Parent config not valid TOML.** The message loses "re-run with
  --since <a base after it>" and uses the same suffix instead.

### 5. Report (F38) and result row (F39): replaces round 2 part 8

- **Explicit report.** It takes the working tree's `behavior_paths`
  through R2f's shape check. When the shape is invalid it prints `n/a
  (working-tree [gate] paths are not a list of strings)` and runs no git
  call for the count.
- **Pass row:** `<N> cycle(s); range <…>; <T> commit(s) in range: <E>
  examined, <U> pre-opt-in (<Z> root(s)); <B> behavior commit(s), all
  declared before (<R> RULE-exempt)`. Merges no longer appear, because
  an examined merge is red.

### 6. Code hygiene (F40)

- The docstrings of `cycle.py`, `gate_cycle` and `tests/test_cycle.py`
  name "Revision — round 3" as governing.
- `triage.eligibility_for_commit` is called at most once per examined
  commit, and its result is reused for the exemption and for the
  explicit report's RULE-during-open-cycle count.

### 7. Instruction layer: additions

| change | source | copy |
|---|---|---|
| the "Feed" bullet states R2e: each item of a closed cycle is disposed of exactly once, checked when the next cycle opens — captured in `backlog.md` at close (required with `[scrum]` on) or listed in the next cycle's `## Intake` | `templates/AGENTS.md.template` | `AGENTS.md` |
| the "Open" bullet adds: history stays linear once cycles exist (rebase, never merge) and the gate needs a full clone | `templates/AGENTS.md.template` | `AGENTS.md` |
| Ways out: merge after opt-in → rebase; close + open → two commits; shallow clone → full fetch; a red commit already on main → PR or push once the branch exists (R3e). R1i's path is "close, open, code — three commits" | `skills/fde-triage/SKILL.md` | `.claude/skills/fde-triage/SKILL.md` |
| one comment line: "requires linear history after opt-in and a full clone" | `templates/fde.config.template.toml` (commented `[cycle]`) | — |

### 8. Tests: replace round 2's F18 cases and add these

Each red case asserts its label and way-out text.

- **F31:**
  - (a) a merge made on main after opt-in: red (linearity);
  - (b) main merged into an orphan root with code, then main
    fast-forwarded to it: red. Run with `--since <before>`, `--since`
    all-zeros and the default range;
  - (c) the same with a branch forked before opt-in: red;
  - (d) the same while C-1 is open, the merge rewording a frozen item:
    red, with linearity reported;
  - (e) an orphan root with `[cycle]` on and code, `merge -s ours` of
    main, fast-forward: red;
  - (f) the same content rebased linearly onto main under an open cycle:
    green.
- **Pre-opt-in merges.** A client history with merges and a root before
  its opt-in commit O, then linear history after it: `--since` all-zeros
  green, and the row counts the pre-opt-in commits and the root.
- **F32.** Covered by (b)/(d). Also a linear close whose backlog capture
  is read from the true closing commit: green, and `captured` is counted.
- **F33:**
  - close + open in one commit, with or without Intake: red, with the
    two-commit way out;
  - close, then open with Intake: green;
  - close, then open without Intake: red (C6).
- **F34.** `git clone --depth 2` of a fixture with a C1 breach behind the
  boundary: one red "shallow clone" row, for both the default range and
  all-zeros.
- **F35.** A red commit on main followed by clean work: all-zeros run is
  red with the R3e suffix; the same branch with a resolvable `--since` is
  green.
- **F36.** A pre-opt-in config nested 3000 deep: all-zeros is green with
  no traceback. The same config in an examined parent gives the red
  "not valid TOML" row, and every other gate's row still prints under
  `--all`.
- **F37.** A config narrowing claimed as RULE with no open cycle: the
  message carries no RULE advice. A plain code commit with no claim: the
  message carries it.
- **F38.** A working-tree `behavior_paths = "src/"` under `--gate
  cycle`: the report prints `n/a …`, with no git failure row.
- **F39.** The pass row numbers add up: examined plus pre-opt-in equals
  the commits in range.
- **This repository.** `--since <root>`, `--since` all-zeros and the
  default range stay green. The repository has no merges, and CI uses
  `fetch-depth: 0`.

### 9. Next-cycle items this revision creates

The orchestrator appends these to C-1's `## Next cycle`:
- the workflow template computes a merge-base for new-branch pushes (R3e;
  touches ADR-0016 Decision 9's pins);
- `validate()` rejects non-list `[gate]` paths for every client (F38);
- supporting a project in a git subdirectory (F24, carried).

## Revision — round 4 (2026-09-28)

This section responds to `reviews/FWD-021/findings.toml` round 4
(F41–F46). The next round is the fifth and final one, so every rule
below is the closed, red choice. The rationale is in ADR-0017's
"Revision — 2026-09-28 (FWD-021 review round 4)". This section governs
over every earlier one.

### 0. Run order: replaces round 3 part 0 and the arming paragraph of the original contract

1. **Cheap arming.** Take a = the working tree's `[cycle].enabled is
   True` (from `cfg`) and b = `git ls-files -z -- cycles/` lists at least
   one file.
2. **Symlinked config (F44).** If a or b holds, and the working-tree
   `fde.config.toml` is a symlink (`Path.is_symlink()`) or is tracked
   with mode `120000` (`git ls-files -s -- fde.config.toml`), emit one red
   row and stop: `CYCLE: fde.config.toml must be a regular file (found a
   symlink) — replace the link with the file`.
3. **Shallow repository.** If a or b holds and `git rev-parse
   --is-shallow-repository` prints `true`, emit round 3's red row and
   stop.
4. **Top level.** If a or b holds and `git rev-parse --show-prefix` is
   non-empty, emit round 2's red row and stop.
5. **Range.** As in round 1. An unresolvable non-zero `--since` is red
   only if a or b holds; otherwise the run stays silent.
6. **Commit list and opted test.** Run round 3 part 1 steps 1 and 2 (one
   `git log`, then batched `cat-file`) over the range. When neither a nor
   b holds and the repository is shallow, run them over what is present.
7. **Arm.** c = some parent of some commit in the range is opted. The
   run is armed when a, b or c holds.
   - Not armed: no row under `--all` or the default run. Under `--gate
     cycle`, one `cycle mode off — declared-scope gate not in force`
     pass.
   - Armed by c alone, in a repo that is shallow or not at the top level:
     emit that step's red row now and stop.
8. **Armed.** Everything else runs: round 3 part 1 steps 3–5 and every
   check that follows. The working-tree checks (open-cycle C2, C5,
   parse) run whenever the run is armed, even when the working tree's
   flag is off.

A git failure anywhere in steps 1–7 is a red row through `run_gate`, as
for every other git failure.

### 1. Serial at every cycle-touching commit (F42): new C5 rule

For every examined commit C whose own files include any `cycles/` path,
run `cycle.check_serial` on **C's own tree**. Take the cycle set from
`git ls-tree --name-only -z C -- cycles/` and read the files at C. Any
breach is red at C, with the message `C5 <sha7>: opens <C-m> while <C-n>
is open — close <C-n> first (separate commit), then open <C-m>`, or the
existing "two open cycles" or "not the highest number" text. This runs
alongside C4 and round 3's close+open rule.

### 2. Config shape at its own commit (F43, F44): replaces round 2 part 2's error column

- **Own-tree check.** For every examined commit C whose own files
  include `fde.config.toml`, check C's own config, using `git ls-tree -z
  C -- fde.config.toml` for mode and type. Red at C when any of these
  holds:
  - the mode is not `100644` or `100755`, or the entry is not a blob;
  - the file does not parse (`TOMLDecodeError`, `RecursionError` or a
    decode error);
  - `cycle_config_violations` returns anything;
  - `[gate]` `behavior_paths` or `eval_paths` is present and not a list
    of strings;
  - `[scrum]` is present and not a table with a boolean or absent
    `enabled`.

  The message: `C1 <sha7>: this commit makes fde.config.toml <problem> —
  fix it before pushing (amend or rebase); once pushed, the next commit
  repairs it and this one stays reported`.
- **Judging against a malformed parent.** When judging C against a
  parent P whose config has one of those problems, P's config is replaced
  table by table with C's own. When C's own is also malformed, or C does
  not touch `fde.config.toml` (so its config equals P's), C is red:
  `C1 <sha7>: parent config <problem> and this commit does not repair
  it`. Otherwise C is judged normally with the substituted values:
  `[gate]` paths, `[cycle]` stages and `[scrum]`.
- **What the opted test reads.** It keeps its reading. A symlink blob or
  unparseable text means "flag not set", and the `cycles` tree still
  decides.

### 3. Replace objects (F45)

Every git call made for this gate carries the global option: `_run_git`
receives `("--no-replace-objects", <subcommand>, …)`. Only the cycle
gate's call sites pass it; `_run_git`'s signature and every other gate's
calls are unchanged. `triage.eligibility_for_commit` is unchanged, and
its own spawns are on the next-cycle list.

### 4. Hygiene (F46)

- **C1 reasons.** `_c1_reason` returns a small dataclass, `Reason(kind,
  text)`, with kinds `no-open-cycle`, `two-open`, `form` and
  `missing-acceptance`. The per-commit message composition (round 3 part
  4) switches on `kind`. The `NO_OPEN` sentinel string is removed.
- **One output channel.** The per-commit examiner returns
  `(breaches, counts)` and does not append to a caller-owned list.
- **Names.** Parameters and helpers named `p1*` (`_p1_state`,
  `_opted_trees(p1s)`, `_stage_removal(..., p1, ...)`,
  `_cycle_transition(..., p1, ...)`) become `parent*`.
- **Docstrings.** Those of `cycle.py`, `gate_cycle` and
  `tests/test_cycle.py` name "Revision — round 4" as governing.

### 5. Instruction layer

| change | source | copy |
|---|---|---|
| "Once the first cycle file exists, every later pushed commit is examined, whatever the flag says (the gate must run on every push); leaving the mode afterwards means landing one deliberate red commit that deletes `cycles/` and `[cycle]` (ADR-0017 R4b)" | `skills/fde-triage/SKILL.md` | `.claude/skills/fde-triage/SKILL.md` |
| Ways out: "opens C-m while C-n is open → close first, in its own commit"; "a commit made fde.config.toml malformed → amend before push; after push the next commit repairs it" | `skills/fde-triage/SKILL.md` | same |
| the commented `[cycle]` block: "once a cycle file exists the mode is permanent for that history (ADR-0017 R4b)" | `templates/fde.config.template.toml` | — |

### 6. Tests: added; each red asserts its label and way out

- **F41 temporary disarm:**
  - push A (flag false plus code, with C-1 closed), run with `--since
    <before A>`: red (R2c config change with no open cycle), with the
    CYCLE row present under `--all`;
  - pushes B and C, each run on its own range: B's run is armed by c;
  - the sequence as one range: red.
- **F41 re-root:** push A (flag false, `cycles/` deleted, code) on its
  own range: red (C4 deletion, and the config change). Push B,
  re-enabling with code: B's parent A is unopted, so B is not examined,
  but A's red already blocks the push that contains A.
- **F41 honest exit:** a single commit deleting `cycles/` and `[cycle]`:
  red. After it, a later push of ordinary code with no cycle: its run is
  unarmed and silent.
- **Never-opted client:** `--all` output byte-identical with and without
  the gate; `--gate cycle` gives exactly one "not in force" row; a
  depth-1 clone of a never-opted client is silent.
- **F42:**
  - C-3 added while C-2 is open: red at that commit;
  - C-2 and C-3 added together: red;
  - the legal order (close C-2; open C-3 with Intake covering C-2; code):
    green;
  - the original probe range base..Z: red.
- **F43:**
  - commit M sets `behavior_paths = "src/"`: red at M;
  - N restores the list: N green, with `--since M` giving N alone;
  - N' leaves the string in place and changes code: red ("does not
    repair it").
- **F44:**
  - working-tree `fde.config.toml` as a symlink with a cycle present:
    one red row;
  - a commit that turns the config into a symlink: red at that commit;
  - the symlink history from the probe: red, not green.
- **F45:** `git replace` of an undeclared commit: the run is red locally,
  as in a fresh clone.
- **This repository:** `--since <root>`, all-zeros and the default range
  stay green.

### 7. Next-cycle items this revision creates

The orchestrator appends these to C-1:
- `GIT_NO_REPLACE_OBJECTS` (or `--no-replace-objects`) for the kernel's
  other git spawn sites: triage, erosion and I1 (F45).
