---
date: 2026-09-28
demand: FWD-020
adr: docs/adr/0016-one-manifest-for-every-mirror.md
---

# Architecture — FWD-020 one declared mechanism for mirror drift

Decides the spec's "Ask first" points (rationale and rejected options
are in ADR-0016); this file is the build contract. Stdlib only
(`tomllib`, `pathlib`, `json`, `unittest`, `fnmatch`, `os`, `re`), plus
this repository's own `runtime/fde_lib.py`.

Amended 2026-09-28 after review round 1 (`reviews/FWD-020/findings.toml`)
to match the reconciled code. The amendments are:
- F2: the attack order formats `probe_plan`.
- F4: a `*.<suffix>` ignore form.
- F5: pairing matches exact letter case.
- F6: the directory holding a file pair's copy is walked for orphans.
- F7: the SETUP marker check.
- F1: the new-pair test runs on a repo slice.
- F3: the gate-invocation pins (ADR-0016 Decision 9).

Amended again 2026-09-28 after review round 2 (F9–F13):
- F9: the ignore list is checked against git-tracked files (Tests 10,
  ADR-0016 Decision 10).
- F10: the gate pins fix ordering and forbid disablers (Tests 8).
- F11: the marker check compares the whole block (Tests 7).
- F12: a replaced section ends at a heading of the same or a higher
  level.
- F13: a symlinked copy directory or symlinked parent is
  `not-a-regular-file`.

Amended again 2026-09-28 after review round 3:
- F14: one ignore predicate, `mirror.hidden`, is used everywhere
  (Walk semantics, Tests 10).
- F15: `tracked_files` fails closed unless root is the work-tree top
  and `ls-files` is non-empty.
- F16: the workflow trigger and quoted keys are pinned, and the
  residuals are stated (Tests 8).
- F17: section ends follow CommonMark ATX and setext headings
  (Exception kinds).

Amended again 2026-09-28 after review round 4:
- F19: heading forms the recognizer does not model exactly fail closed
  (Exception kinds), as `stale-exception` on the source path.
  Implemented.
- F20: the forbidden-string list closes only its literals (Tests 8).
- F21: the installed hook must be executable (Tests 8). Implemented.

## Files

| Path | Role |
|---|---|
| `tests/mirror.toml` | the manifest — single copy, under `[gate].eval_paths`, never installed |
| `tests/mirror.py` | pure checker core + renderers; not collected by discovery (`test*.py` pattern); imported like `support` |
| `tests/test_mirror.py` | real-repo run, fail-closed fixtures, manifest-driven mutation suite, R7 ignore fixtures, R8 agreement, zero-test-code-change fixture |
| content tests (where the implementer places them) | G7, G8, D9's retained needles, the gate-invocation pins (ADR-0016 Decision 9) |

No change to `runtime/`, `bin/fde/`, `KNOWN_GATES`, `erosion.py`, or
`tests/support.py`.

## Manifest schema (`schema = 1`)

Top level has exactly these tables; any other key is `malformed`.

```toml
[meta]
schema = 1

[sources]                       # sources of truth for config:/render: values
config     = "fde.config.toml"
invariants = "spec/invariants.toml"
attributes = "spec/dimensions/quality-attributes.toml"

[ignore]                        # literal entries: verbatim .gitignore lines; `*.<suffix>`: see Walk semantics
entries = ["__pycache__/", "*.pyc", ".DS_Store", ".claude/worktrees/", ".fde/guard-audit.jsonl"]

[[pair]]
id = "runtime"                  # unique, [a-z0-9-]+
source = "runtime/"             # trailing "/" = directory pair; none = file pair
copy = "bin/fde/"               # same kind as source
relation = "identical"          # identical | identical-except | absent
# erosion_measured = true       # optional, identical pairs only (R8/G9)
# [[pair.except]] ...           # identical-except only; >= 1 required there
```

Declared pairs (reflecting the tree on 2026-09-28):

| id | source | copy | relation | notes |
|---|---|---|---|---|
| `runtime` | `runtime/` | `bin/fde/` | identical | D1, D3 |
| `spec` | `spec/` | `.fde/spec/` | identical | D2, D3, D13 |
| `skills` | `skills/` | `.claude/skills/` | identical | D4, G6 |
| `skills-init` | `skills/fde-init/` | `.claude/skills/fde-init/` | absent | D4 |
| `agents` | `agents/` | `.claude/agents/` | identical | D5, G1, G6 |
| `adversarial-role` | `agents/fde-adversarial.md` | `.claude/agents/fde-adversarial.md` | identical-except | D6, G4 |
| `pre-commit` | `templates/pre-commit` | `.githooks/pre-commit` | identical, `erosion_measured = true` | G2 |
| `workflow` | `templates/fde-gate.yml` | `.github/workflows/fde-gate.yml` | identical-except | D9, G3 |
| `agents-md` | `templates/AGENTS.md.template` | `AGENTS.md` | identical-except | D7, D8, D10–D12, G5 |

### Exception kinds (`[[pair.except]]`, applied to the source text in declared order)

| kind | keys | semantics | stale / count rule |
|---|---|---|---|
| `placeholder` | `token`, `count`, `value` | every occurrence of literal `token` → resolved `value` | occurrences of `token` in the source ≠ `count` → `stale-exception` (0) or `count-mismatch` |
| `substitute` | `from`, `to`, `count` | every occurrence of literal `from` → literal `to` | same as placeholder |
| `insert` | `before`, `text` | literal `text` inserted immediately before the single occurrence of literal `before` | `before` must occur exactly once in the source |
| `replace-section` | `heading`, `value` | the source line equal to `heading` through the line before the next heading of the **same or higher** level (or EOF) → resolved `value`; "heading" is defined below the table (F12, F17) | `heading` must occur exactly once as a whole line |

**Heading, for `replace-section` ends (F12, F17).** A heading is
either of these CommonMark forms:
- ATX: 0–3 leading spaces, `#{1,6}`, then a space, a tab, or end of
  line. Its level is the number of `#`.
- setext: a non-blank line followed by a line of only `=` (level 1) or
  only `-` (level 2). The heading starts at that text line.

The section ends at the first heading after the start whose level is
≤ the replaced heading's level. So a `# Appendix` after
`## Attack order` is not part of the section.

**Known simplifications, and the direction each one fails.** Every one
must fail closed (red), never silently green:
- Code fences are not modelled. A `#` line inside a fence ends the span
  early, and the copy then reports `differs`. This is safe as it
  stands; round 4 re-verified it with closed and unclosed fences, HTML
  comments, `---` over `---`, and `- item` over `---`.
- **Unmodelled heading forms (F19): fail closed.** The recognizer looks only one line ahead. So a setext
  underline that closes a *multi-line* paragraph, a lazy continuation
  line, or a heading inside a block quote (`> # …`) would otherwise
  shorten or extend the replaced span silently. The span would absorb
  source lines the copy never receives, which is green and unsafe.
  Contract, implemented by `tests/mirror.py::_unmodelled_heading`:
  when any such construct occurs after the replaced heading, the pair
  reports `stale-exception` **on the source path**, with a detail
  naming the construct. The constructs are:
  - a setext underline whose text line is itself preceded by a
    non-blank line (a multi-line paragraph, or a lazy continuation);
  - a line starting with 0–3 spaces and `>` whose remainder is
    heading-shaped.

  The checker never computes a span from any of these. The earlier sentence "treated as starting at its last text
  line" is withdrawn: it described a fail-open behavior.

`value` is exactly one of:
- `config:<dotted.key>` — a string/int read from `[sources].config` (missing key → `source-of-truth-missing`);
- `render:<name>` — `name` from the closed set below (unknown → `malformed`).

No regex, glob, or skip exists in the schema. An unknown `kind`, a
missing or extra key, a `count < 1`, an `except` on a non-`identical-except`
pair, or an `identical-except` pair with no exceptions → `malformed`.

The declared exceptions today:

- `agents-md`: `placeholder` `{{PROJECT_NAME}}`→`config:project.name`,
  `{{TEST_COMMAND}}`→`config:stack.test_command`,
  `{{INVARIANTS_LIST}}`→`render:invariants_list`,
  `{{WEIGHTS_LIST}}`→`render:weights_list`,
  `{{DEPTHS_LIST}}`→`render:depths_list` (each `count = 1`);
  `substitute` `DEM-042`→`FWD-002`, `count = 1`.
- `workflow`: `placeholder` `{{TEST_COMMAND}}`→`config:stack.test_command`,
  `count = 1` (the `${{ github… }}` expression is not the token).
- `adversarial-role`: `insert` before `"# Adversarial review\n"` of the
  literal `FDE-KERNEL:GENERATED` comment block plus its two trailing
  blank lines; `replace-section` heading `## Attack order` →
  `render:attack_order`.

### Renderers (closed set; each returns text; never writes)

`weights_list` and `depths_list` sort descending by value, with ties
kept in `[weights]` or depth declaration order (a stable sort).
`attack_order` takes its order from `probe_plan`.

- `invariants_list` — per `[[invariant]]` in file order:
  `- **{id} {name}** — {" ".join(statement.split())}`, lines joined by `\n`.
- `weights_list` — `- {attr}: {w}` per `[weights]`, stable-descending.
- `depths_list` — effective depth = `max([derived.depths][k], [depths][k])`;
  keep > 0; `- {k}: {d}` stable-descending.
- `attack_order` formats `fde_lib.probe_plan(cfg, spec)`, which is
  imported from `<repo>/runtime/` (the kernel's own derivation) and
  never re-derived (F2, MNT-11).
  - Order and values come from the plan. It iterates
    `quality-attributes.toml` and sorts stably by weight, descending,
    so ties follow the spec's attribute order. An attribute that
    `[weights]` omits is planned at its `floor`. Rounds are
    `max(1, round(w/10))`, and the plan marks an attribute blocking
    when `w >= 15`.
  - The checker adds only the markdown, and pre-checks its inputs:
    - a heading line, `## Attack order — this project's weights,
      descending`, followed by a blank line;
    - per plan step `n`, the line `### {n}. {label} — weight {w},
      {r} round{s}`, plus ` — BLOCKS MERGE` when the step is blocking;
    - one `- {probe}` line per probe, then a blank line;
    - every line newline-terminated;
    - before calling the plan: a `[weights]` key that is not a known
      attribute, or a value that is not an integer, raises
      `SourceOfTruthMissing`, which becomes `source-of-truth-missing`.
  - Purity note: this import is code, not data under `root`. A fixture
    root is rendered with this repository's `probe_plan`, which is the
    intended meaning, since the copy must be what the kernel would
    emit.

Verified on 2026-09-28: the first three plus the two placeholders and
the substitution reproduce `AGENTS.md` byte-exact. `attack_order`
reproduces the current copy **except** three usability probes missing
from the copy since 0.13.0 — real drift (ADR-0016 Decision 8); the
copy is regenerated in this demand.

## Checker contract (`tests/mirror.py`)

```
load(path) -> dict                         # tomllib only; no validation
check(root: Path, manifest: dict) -> list[Violation]
check_with_counts(root, manifest) -> (list[Violation], {pair_id: files_compared})  # absent: 1
sibling_dirs(pairs) -> {dir/: [file pairs whose copy sits directly in it]}
resolve(root: Path, manifest: dict, value: str) -> str   # config:/render: → text
Violation = NamedTuple(pair: str, relation: str, path: str, kind: str, detail: str)
```

- **Pure**: reads only under `root`; no writes, subprocess, git,
  network, env, or cwd dependence. Manifest paths are relative,
  POSIX, no `..`, no absolute — else `malformed`.
- **Fail closed**: schema problems are violations (pair `"<manifest>"`),
  never exceptions; I/O or decode errors propagate (the calling test
  errors → red). No bare/broad `except`. Empty list = the only green.
- `kind` is from a closed set: `malformed`, `missing-source`,
  `empty-source`, `zero-checked`, `missing-copy`, `differs`, `orphan`,
  `present-but-absent`, `stale-exception`, `count-mismatch`,
  `source-of-truth-missing`, `not-a-regular-file`, `ignore-not-in-gitignore`.
  `differs.detail` names the first differing line number.

### Walk semantics

- Files are compared as bytes (`identical`) or as strict UTF-8 text
  (`identical-except`, compared after applying exceptions).
- **One ignore predicate (F14):** `hidden(rel, is_dir, entries)` is
  true when `rel` or any ancestor directory of it matches an entry. The
  checker's walk, `copy_dirs`, the tests' `files_under`, and
  `silenced_tracked` all call it, and nothing else decides
  "ignored".
- Ignore entries have four forms, and nothing else is ignored:
  - A bare directory name ending in `/` (`__pycache__/`) matches any
    path component equal to it.
  - An entry with an inner `/` (`.claude/worktrees/`,
    `.fde/guard-audit.jsonl`) matches a root-relative path prefix.
  - A bare file name (`.DS_Store`) matches a basename.
  - `*.<suffix>` (full match `\*\.[A-Za-z0-9_-]+`, e.g. `*.pyc`)
    matches a file whose basename ends in `.<suffix>` (F4).

  Any other glob character is `malformed`. A literal entry must be a
  verbatim `.gitignore` line. A `*.<suffix>` entry must instead be
  matched, as the basename `x.<suffix>`, by
  `fnmatch.fnmatchcase(probe, line)` against some `.gitignore` line
  that is not a comment, not a negation, and contains no `/`. That is
  how `*.pyc` is covered by `*.py[co]`. Otherwise the kind is
  `ignore-not-in-gitignore`.
- **Exact case (F5).** A source or copy counts as present only if every
  path component exists with that exact spelling in its parent's
  `os.listdir`. So a macOS/APFS case-insensitive `is_file()` hit is a
  miss (`missing-copy` / `missing-source`, detail "exists only under
  another letter case"), and the orphan walk's source lookup is
  case-exact too. This matches CI's case-sensitive filesystem.
- **Nesting**: a pair whose source lies inside another pair's source
  directory governs those files (longest source prefix wins). It is
  `malformed` unless its copy equals the parent's copy + the same
  relative offset. Duplicate sources or overlapping non-nested copies
  → `malformed`.
- **Directory pair**: for every non-ignored file under source not
  governed by a nested pair → copy must exist and satisfy the relation;
  for every non-ignored file under copy not governed by a nested pair →
  source counterpart must exist, else `orphan`. Source missing →
  `missing-source`; zero non-ignored files → `empty-source`; zero files
  compared → `zero-checked`. Symlinks on either side → `not-a-regular-file`.
- **Symlinks are never resolved through (F13).** A source or copy file
  is `not-a-regular-file` in two cases: it is itself a symlink, or any
  of its parent directories under root is one (detail "parent d/ is a
  symlink"). A symlinked directory-pair copy root is
  `not-a-regular-file`, and so is a symlinked `sibling_dirs` directory
  (detail "copy directory is a symlink"). Such a directory is reported,
  never skipped.
- **Beside file pairs (F6).** `sibling_dirs` groups the non-`absent`
  file pairs by the directory that directly holds their copy. Two kinds
  of directory are excluded: the repository root, which holds
  user-owned files such as README and `CLAUDE.md`, and any directory
  inside a directory pair's copy, which is already walked. Each
  remaining directory (today `.githooks/` and `.github/workflows/`) is
  scanned one level deep:
  - a non-ignored regular file that is not some pair's declared copy is
    an `orphan`, attributed to the first pair in that directory;
  - a symlink or special file is `not-a-regular-file`;
  - subdirectories are not descended.
- **`absent`**: any non-ignored file (or the path itself) under copy →
  `present-but-absent`; source must exist (else `missing-source`, so a
  stale `absent` is red too).

## Tests (`tests/test_mirror.py`)

1. **Real repo**: `check(ROOT, load(ROOT/"tests/mirror.toml")) == []`;
   also asserts every pair compared ≥ 1 file.
2. **Fail-closed fixtures** (temp dirs): empty source root, missing
   source root, unknown relation, unknown exception kind, extra key,
   stale placeholder, wrong count, an ignore entry absent from
   `.gitignore`, each → exactly the expected `kind`.
3. **Mutation suite, iterated from the manifest** (R5): for each pair,
   build a temp root containing that pair, the pairs nested in it,
   `[sources]` files and `.gitignore`; the base must check clean. Then,
   each on a fresh copy: change one byte in a copy file; delete a copy
   file; add an orphan under the copy root (directory pairs), or a
   stray file beside the copy (file pairs in a `sibling_dirs`
   directory); for `absent`, create a file at the forbidden copy;
   and for `identical-except`: one byte changed outside every exception
   region, one byte changed inside each resolved value's span in the
   copy (located via `resolve`), and each exception made stale in the
   source (placeholder: token → resolved value; substitute: `from` →
   `to`; insert: remove `before`; replace-section: alter `heading`).
   Every mutation must produce ≥ 1 violation of the expected `kind`.
4. **Zero test-code change (F1)** runs on `repo_slice`, a temp copy
   of this repository's pair sources and copies, sources of truth,
   `.gitignore`, `SETUP.md`, `fde.config.toml` and `generated_paths`
   trees. The test appends new pairs of every relation to the **real**
   manifest text. The result must pass every manifest-iterating check
   with no change to the test module: the real-repo check, the mutation
   suite, R8 agreement, the dropped-pair check, the inventory check and
   the marker check.
   - The only non-manifest edit allowed is a SETUP §6 `→ \`dest\``
     line, for a new pair that nothing else would notice being dropped.
     "Nothing else" means no parent pair, no `generated_paths` entry,
     and no orphan walk beside its copy (a copy at the repository
     root, or a new directory pair outside `generated_paths`).
   - The test also shows that line is load-bearing: with it removed,
     those pairs appear in `drop_unnoticed`.
   - `INVENTORY` is history. Every home it names must exist, but a new
     pair needs no row.
5. **R7**: fixture with `.claude/worktrees/x/…`, `__pycache__/`,
   `.fde/guard-audit.jsonl`, and a `*.pyc` beside a source → clean; an
   untracked non-ignored file under `.claude/skills/` → `orphan`.
6. **R8 agreement** requires:
   - every `[erosion].generated_paths` entry contains at least one
     declared copy root, and no non-ignored file outside declared copy
     roots;
   - every `identical` copy root is under an entry XOR its pair has
     `erosion_measured = true`;
   - every `→ \`path\`` in SETUP §6 is a declared copy, and so are the
     pinned §7/§8 destinations (`AGENTS.md`, `.claude/agents/`,
     `.claude/skills/`), each of which must still appear backticked in
     SETUP §7–§8.

   `drop_unnoticed(root, manifest)`, iterated from the manifest, must
   be empty. Removing any one pair must make `check` or `agreement` go
   red.
7. **Marker (F7).** SETUP §6's "Generated-file marker" code block is the
   single declaration. `marker_problems(root, manifest)` checks every
   `identical-except` pair's `insert` texts and template source that
   carry `FDE-KERNEL:GENERATED`. The carrier's **whole block** must
   equal SETUP's block exactly (F11), not merely a prefix of the same
   length. The block starts at the marker line and keeps every
   following line that starts with that line's comment prefix. It ends
   at the first line that lacks the prefix, or whose remainder after
   the prefix is blank, `-->` or `*/`. The prefix is stripped from each
   line before the comparison. So a SETUP block shortened, or a carrier
   grown, is red. Plain
   `identical` copies (e.g. the one-line marker in `pre-commit`) are
   not held to it. A reworded SETUP marker goes red on both the
   adversarial insert and `templates/AGENTS.md.template`.
8. **Gate-invocation pins (F3/F10, ADR-0016 Decision 9).** These are
   content tests in `tests/test_install_sync.py`, not manifest entries.
   Each one runs on the template **and** the installed copy.
   - Pre-commit (`templates/pre-commit`, `.githooks/pre-commit`):
     line 1 is `#!/bin/sh`. The first line after it that is neither
     blank nor a comment is exactly
     `exec python3 bin/fde/verify.py --staged`.
   - Workflow (`templates/fde-gate.yml`,
     `.github/workflows/fde-gate.yml`): the file ends with exactly
     `      - name: FDE gate\n        run: python bin/fde/verify.py --all --since "${{ github.event.pull_request.base.sha || github.event.before }}"\n`.
   - The workflow has exactly one `on:` key, on the exact line
     `on: [push, pull_request]` (F16).
   - Neither file contains `continue-on-error`, `if:`, `"if"`, `'if'`,
     `"on"`, `'on'`, `|| true`, `|| exit 0`, `; true` or `exit 0`.
     This closes **only those literal spellings**. Any other YAML
     spelling of an `if` or a trigger key (`if : false`, `? if`,
     `"i\x66"`, `? !!str if`, flow mappings, anchors) is a named
     residual for review (F20).
   - `.githooks/pre-commit` is executable on disk (`os.access` `X_OK`)
     and recorded as mode 100755 in the git index (SETUP §6 step 3,
     `chmod +x`). This is checked by
     `test_installed_pre_commit_is_executable` (F21), because git skips
     a non-executable hook silently. `templates/pre-commit` is a source
     and is not held to it.

   These are literal checks with no YAML or shell parsing. They are
   bounded to the two files that invoke the gate and are not a pattern
   to extend to every copy. They fix the gate's position, text and
   trigger, but not that it runs. Named residuals left to review
   (ADR-0016 Decision 9):
   - an earlier step overwriting `bin/fde/verify.py`;
   - any YAML spelling of `if` or `on` other than the listed literals
     (F20);
   - job-level or environment tricks.
9. Timing: the module stays < 2 s on this repo (R9).
10. **The ignore list never silences a tracked file (F9, ADR-0016
    Decision 10).** `tracked_files(root)` fails closed, never skipped,
    in three cases:
    - it raises outside a work tree (`check=True`);
    - it raises if `git rev-parse --show-toplevel` does not resolve to
      `root` (F15);
    - it raises if `git ls-files -z` returns no files (F15).

    `silenced_tracked(root, manifest)` lists every tracked file for
    which `mirror.hidden(path, False, entries)` holds. That is the same
    single predicate the walk uses, covering the file and its ancestor
    directories (F14). The real
    repository's list must be empty. A git-initialised fixture shows
    two things:
    - runtime output (`runtime/__pycache__/…pyc`, `runtime/b.pyc`,
      untracked and gitignored) is not reported;
    - entries `dimensions/`, `dimensions` (bare, which matches the
      directory, F14), `fde-implementation.md`, `roles.toml` and `*.py`
      report exactly the tracked files they would hide.

    This is the only test in the module that runs git. `tests/mirror.py`
    itself never does, and git never decides what the checker ignores.

## Inventory → new home

| Row | New home |
|---|---|
| D1 | `runtime` pair; sanity pin → `empty-source`/`zero-checked` |
| D2, D13 | `spec` pair (D13 retired as redundant) |
| D3 | orphan walk of `runtime`, `spec` (all file types) |
| D4 | `skills` + `skills-init` (absent) |
| D5 | `agents` pair (discovered; covers G1) |
| D6 | `adversarial-role`: insert + `replace-section` = `render:attack_order`, byte-exact |
| D7, D8 | `agents-md` placeholders via renderers/config, byte-exact |
| D9 | `workflow` pair; `fetch-depth: 0` / `--since` needles **retained** as content test |
| D10–D12 | `agents-md` whole-file identical-except; D11's content needles retained |
| G1–G6 | pairs above + all-file-type bidirectional walk + the `sibling_dirs` walk beside file pairs |
| G7, G8 | content tests (ADR-0016 Decision 6) |
| G9 | R8 agreement; `generated_paths` value unchanged |
| G10 | not derived, not checked (ADR-0016 Decision 5) |

## Open for other roles

- ~~**Spec role**: amend "Untouched" for the stale attack order.~~
  Done in `acceptance.md` (amended, FM-15).
- ~~**Implementation (round-1 follow-up)**: the `templates/pre-commit`
  pin.~~ Done, and strengthened in rounds 2–3 (Tests 8).
- ~~**Round 3**: F14–F17.~~ Reconciled.
- ~~**Round 4**: F19–F22.~~ Closed:
  - F19: `_unmodelled_heading` reports `stale-exception` on the source
    path for multi-line or lazy setext headings and block-quoted
    headings;
  - F21: `test_installed_pre_commit_is_executable` checks `X_OK` and
    index mode 100755 on `.githooks/pre-commit` only;
  - F20 and F22 were documentation only.

  No open implementation work.
- **Kernel feedback** (not blocking): SETUP's "weight/10 rounded" vs
  Python banker's `round()` at `.5` (ADR-0016 Consequences).
