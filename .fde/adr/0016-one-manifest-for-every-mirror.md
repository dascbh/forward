# ADR-0016 — One manifest for every mirror

date: 2026-09-28
status: accepted

## Context

This repository is FORWARD installed on itself (ADR-0007): every piece of
kernel behavior exists as a source (`runtime/`, `spec/`, `skills/`,
`agents/`, `templates/`) and as the installed copy CI and agents execute
(`bin/fde/`, `.fde/spec/`, `.claude/skills/`, `.claude/agents/`,
`.githooks/pre-commit`, `.github/workflows/fde-gate.yml`, `AGENTS.md`).
`specs/FWD-020-mirror-drift/spec.md` inventories thirteen bespoke drift
assertions (D1–D13) in five test files, each with its own relation,
discovery rule and blind spot, and six unguarded pairs or pair-aspects
(G1–G6). MNT-1 leads `graph.py --recurring` at 28.0.

Probing the current copies for this ADR found a live instance of the
spec's FM-7. `.claude/agents/fde-adversarial.md`'s `## Attack order`
lists three usability probes. `spec/dimensions/quality-attributes.toml`
has had six since 0.13.0 / FWD-017 (`bcbb734`): *ambiguous next action
with multiple plausible controls*, *irreversible action taken with no
confirmation or undo*, *state change with no visible feedback*. D6
checks only `weight W, R round` substrings, so it has stayed green
through three demands while the reviewer role worked from a stale
probe list. `AGENTS.md`, by contrast, re-renders byte-exact from
`templates/AGENTS.md.template` plus `fde.config.toml` plus
`spec/invariants.toml` (checked 2026-09-28).

## Options considered

**Keep case-by-case tests, add the missing ones (G1–G6).** Rejected.
This is the process that produced the inventory. Each new copy needs a
new test with its own discovery rule, and each test encodes a weaker
relation than the one it claims (needles for D6–D9, a regex for D10, a
hand list for D5). The stale attack order above is what "one more
needle" leaves behind. Adding a pair should cost one manifest entry,
not one test.

**A blanket "every copy is identical" glob with a per-file skip list.**
Rejected. Four copies are generated, not copied (the adversarial role,
`AGENTS.md`, the workflow, and `fde-init`'s deliberate absence), so the
skip list would hold exactly the files most likely to drift, the ones
D6–D10 exist for. A skip is a whole-file wildcard, which the spec rules
out (Never). It also leaves the generated content unchecked, and that
is where the one real drift was found.

**Generate the copies at test time instead of committing them.**
Rejected. The copies are what CI, the pre-commit and agents actually
execute, and they must be present without a kernel checkout (I6).
Under ADR-0001 the agent is the installer, and no kernel CLI exists. A
test-time generator would become exactly that CLI, owned by `tests/`.
It would also drop the copies from reviewable diffs.

This ADR does let the checker *render the expected bytes of a
generated region* to compare against the committed copy. That is
different from the rejected option. The renderer never writes a file,
and it covers only a named region whose source of truth is declared.
The committed copy stays the artifact. The attack-order renderer
formats the kernel's own plan (`runtime/fde_lib.py::probe_plan`), and
the list renderers are the executable form of SETUP §7's format rules,
which D6–D8 already restated as needles.

**Manifest under `spec/`.** Rejected (FM-9). `spec/` is rglob-mirrored
into `.fde/spec/` and installed into clients by SETUP §6 step 2. A
kernel-self-hosting manifest there would either ship to every client,
where it means nothing, or need an exception to the `spec/` pair. That
would create a new source/copy disagreement in the mechanism meant to
remove them.

**A `verify.py` gate id.** Rejected. In a client the sources live in
the kernel, which I6 forbids the gate from needing. So the gate would
be silent everywhere except this repo: dead code shipped into every
client's `bin/fde/`, plus one more `KNOWN_GATES` entry to keep
coherent. Client-side drift of installed copies is `fde sync`'s job
("regenerate and diff", SETUP). The mechanism's only population is
this repo's self-installation, and this repo's suite already runs in
CI (`[stack].test_command` in the workflow). A test module is enough.

**Deriving `[erosion].generated_paths` from the manifest (G9).**
Rejected. `erosion.py` is client runtime, and clients have no
manifest. Deriving would couple `runtime/` to a `tests/` file and
change erosion's config contract for every client. Instead, the two
declarations are cross-checked (R8).

**Deriving or cross-checking `tests/support.py::make_project` (G10).**
Both rejected; see Decision.

**A fourth relation (`contains`) for G7/G8.** Rejected. `CLAUDE.md`
and `.claude/settings.json` are user-owned merge targets (SETUP §8.3,
§8.4), not copies. A needle-strength relation inside the manifest
would reopen the vocabulary to the weak relation D6–D9 are being
retired from.

**Normalize-then-compare (D10's regex) or structural parsing of
generated regions.** Rejected. Normalization hides any change it
matches. Parsing a region is more code, and it is weaker than
comparing it byte-for-byte with its rendering.

**Git-based ignore (`git ls-files` / `check-ignore`).** Rejected. It
puts a subprocess inside the pure core, and fixtures would need
`git init`. It also asks the wrong question: an *untracked*, non-ignored
file under a copy root must be an orphan (R7), and `ls-files` would
hide it. This rejection is about git *deciding what the checker
ignores*. Decision 10 uses git for something else: validating the
manifest's ignore list in a test.

## Decision

1. **One manifest, `tests/mirror.toml`, under `[gate].eval_paths`.**
   Removing a pair shrinks an eval file. That makes the commit
   RULE-ineligible (ADR-0015 criterion 4) and puts the change in front
   of review. Adding an exception grows the file, and placement does
   not guard that; Decision 9 covers it. There is a single copy of the
   manifest, and it is not mirrored or installed.
2. **Test-only. `KNOWN_GATES` is unchanged.** The pure checker is
   `tests/mirror.py`. Its name does not match `test*.py`, so discovery
   does not collect it; test modules import it the way they import
   `support`. `tests/test_mirror.py` holds the tests that run it: the
   real repo, fixtures with known violations, the mutation suite
   driven by the manifest, and R8 agreement.
3. **Closed vocabulary.** Relations: `identical`, `identical-except`,
   `absent`. Exception kinds: `placeholder`, `substitute`, `insert`,
   `replace-section`, every one literal and counted. A placeholder
   value or section replacement is a `config:<dotted.key>` or a
   `render:<name>`. Four renderers exist, a closed set: `invariants_list`,
   `weights_list`, `depths_list`, `attack_order`. `attack_order`
   formats `fde_lib.probe_plan`'s output, imported from this
   repository's `runtime/`, and never re-derives it (F2, MNT-11). So
   ties follow `quality-attributes.toml` order, and an attribute that
   `[weights]` omits is planned at its floor. `weights_list` and
   `depths_list` have no runtime counterpart; they sort by value,
   descending, with ties kept in declaration order. The checker renders
   each one's expected text from the declared sources of truth, applies
   every exception to the source, and requires the result to equal the
   copy byte-for-byte. So verified regions are checked exactly, not by
   needles. The full schema is in
   `specs/FWD-020-mirror-drift/architecture.md`.
4. **G9: cross-checked, not derived.** `generated_paths` stays in
   `fde.config.toml` with its value unchanged. R8's agreement test
   requires every entry to contain a declared copy root and no
   non-ignored file outside one. It also requires every `identical`
   copy root to sit under an entry, or its pair to declare
   `erosion_measured = true`. `templates/pre-commit` →
   `.githooks/pre-commit` is the only such pair today. It is a
   four-line file, and excluding it is an erosion decision this demand
   does not make.
5. **G10: neither derived nor cross-checked.** `make_project` builds a
   *minimal client* and is deliberately a subset of this repo's layout.
   It is not a declaration of that layout. Its runtime copy is already
   discovered (`runtime/*.py`). Its four enumerated `spec/` files fail
   loudly if renamed (`shutil.copy` raises, and every fixture test goes
   red). A new spec file the fixture lacks matters only if the runtime
   needs it, and then the runtime's own tests go red. FM-12's
   consequences (erosion measuring another population, SETUP describing
   another layout) do not apply to a test fixture.
6. **G7/G8 stay outside the manifest as ordinary content assertions,
   added in this demand.** `CLAUDE.md`'s first line is `@AGENTS.md`.
   `.claude/settings.json` (parsed with `json`) has a `PreToolUse` entry
   with matcher `Write|Edit` running exactly
   `python3 "$CLAUDE_PROJECT_DIR/bin/fde/guard.py"`, plus
   `worktree.baseRef == "head"`. Neither is a copy, so R6's rule (no
   source-vs-copy equality outside the mechanism) is untouched.
7. **What does not collapse.** D9's `fetch-depth: 0` and `--since`
   needles stay as a content test. Byte-identity with the template only
   proves the copy matches the template, not that the template still
   fetches full history. D11's content needles, FWD-019's pins,
   `agent_transcript`, the scrum elements, template placeholders, and
   the value carriers stay as they are (spec, "adjacent").
8. **The stale attack order is fixed at the copy in this demand.** The
   source (`quality-attributes.toml`) is correct. The copy is the drift,
   and SETUP's rule is that a generated file is fixed by regenerating
   it, never by editing the source to match. So this is the one copy
   whose content this demand changes. `acceptance.md`'s "Untouched"
   criterion states that every copy is in sync today, which is false
   for that region, so it needs a matching amendment by the spec role.
9. **A literal exception that legalizes drift (review F3): accepted as
   residual risk, with a bounded mitigation.** A small commit can add a
   `[[pair.except]]` that excuses a behavior change in a copy (for
   example `--all` → `--gate eval` in the workflow) and still qualify
   for the RULE lane with no review. Two fixes were considered and
   rejected:
   - *Making edits to `tests/mirror.toml` RULE-ineligible* would put a
     path-specific rule in `runtime/triage.py`. That is client runtime,
     so it would either carry a kernel-self-hosting path or need a new
     `[triage]` key in every client's config contract. ADR-0015 rejected
     path- and content-aware eligibility checks for exactly this reason.
     It would also close only one door. Editing the template and the
     copy together (two lines, and the `identical` pair still holds)
     weakens CI the same way without touching the manifest. That is
     ADR-0015's named residual risk (a mechanically small, semantically
     large change), not a gap this manifest opened.
   - *Bounding what an exception may cover* has no mechanical rule that
     tells legitimate from legalizing: `--all` → `--gate eval` is as
     literal and counted as `DEM-042` → `FWD-002`. Any restriction is
     either arbitrary or rejects a real exception.

   Against the weight vector: functional correctness (30) is protected
   where it matters, on the lines that run the gate. Maintainability (22)
   is not charged a client-contract change for a risk that predates this
   demand (review F3 itself says "not a regression").
   The mitigation is bounded to the two installed files that invoke the
   gate. Each is pinned on the template *and* the installed copy, so a
   pin survives a template-plus-copy edit and any manifest exception.
   Presence alone is not enough (review F10: an `exit 0` before the
   hook's exec line, or `continue-on-error: true` on the CI step, kept
   presence pins green). So the pins also fix the gate's position and
   ban a named list of one-line disablers. Exactly what they cover:
   - `templates/pre-commit` and `.githooks/pre-commit`: line 1 is
     `#!/bin/sh`. The first line after it that is neither blank nor a
     comment is exactly `exec python3 bin/fde/verify.py --staged`.
     `exec` replaces the shell, so nothing after it runs, and nothing
     can run before it.
   - `templates/fde-gate.yml` and `.github/workflows/fde-gate.yml`: the
     file ends with the exact two-line `FDE gate` step, whose `run:`
     is `python bin/fde/verify.py --all --since "${{ … }}"`. The
     workflow also has exactly one `on:` key, and it is the exact line
     `on: [push, pull_request]` (F16), so the trigger is pinned too.
   - Neither file may contain `continue-on-error`, `if:`, `"if"`,
     `'if'`, `"on"`, `'on'`, `|| true`, `|| exit 0`, `; true` or
     `exit 0`. The forbidden-string list closes **only these literal
     spellings**. YAML has many others for the same key, for example
     `if : false`, `? if`, `"i\x66"` and `? !!str if` (review F20),
     and the list does not close them.
   - The installed hook `.githooks/pre-commit` must carry the
     executable bit that SETUP §6 step 3's `chmod +x` gives it (review
     F21). Git silently skips a non-executable hook, and a mode-only
     commit has numstat 0/0, so without this check it would be
     RULE-eligible. `templates/pre-commit` is a source (tracked
     100644) and is not held to the bit.
     `test_installed_pre_commit_is_executable` checks `X_OK` on disk
     and mode 100755 in the git index, on the installed hook only.

   These are literal string checks with no YAML or shell parsing. They
   do **not** establish that the gate runs unconditionally. Named
   residuals, all green under the pins and left to isolated review
   (review F16):
   - an earlier step that overwrites, replaces or shadows
     `bin/fde/verify.py` (or `python`) before the pinned step runs;
   - **any YAML spelling of a job- or step-level `if` (or of a second
     trigger) other than the listed literals**: `if : false`, `? if`,
     escaped keys such as `"i\x66"`, tagged keys such as `? !!str if`,
     flow mappings, anchors and aliases (review F20). The pins do not
     close this class. They close only the literal strings listed;
   - job-level settings or environment tricks earlier in the file.

   What the pins do close: the trigger *line* (`on: [push,
   pull_request]`, exactly one `on:` key, and no literal `"on"` or
   `'on'`), and the literal `if:`, `"if"` and `'if'` spellings.

   The pins make the common one-line disablers mechanical. They do not
   close the door, and a promotion must not read them as if they do.
   Parsing YAML or shell to close these was not adopted: it adds a
   parser to a stdlib-only suite for a risk ADR-0015 already names as
   review's.
10. **The ignore list may never silence a tracked file (review F9),
    checked with git in the test layer.** An `[ignore]` entry drops
    matching paths from both sides of every walk, and `.gitignore`
    membership was its only guard. So a small commit could add
    `dimensions/` or `roles.toml` to both files and hide drift in a
    tracked, executed copy, and that commit would qualify for the RULE
    lane.
    - *The reviewer's rule was rejected:* no entry may match a file
      under any pair's source. On disk, a source directory holds
      legitimate runtime output (`runtime/__pycache__/`, and
      `bin/fde/__pycache__/` on the copy side), so the rule would
      reject the entries R7 requires. No filesystem-only rule
      separates runtime output from tracked content. Tracked-ness is
      the distinguishing fact, and only git knows it.
    - *Chosen:* `silenced_tracked(root, manifest)` in
      `tests/test_mirror.py`. It runs `git ls-files -z` and fails if
      any `[ignore]` entry would hide any tracked file anywhere in the
      repository. There is **one ignore predicate**,
      `mirror.hidden(rel, is_dir, entries)`: a path is hidden when it,
      or any ancestor directory of it, is ignored. The checker's walk,
      `copy_dirs`, the tests' `files_under`, and `silenced_tracked` all
      call it. What a walk drops and what the validator counts as
      dropped therefore cannot diverge. Review F14 showed why this
      matters: a bare `dimensions` matched the *directory*
      `spec/dimensions/` in the walk, while the file-only validation
      passed it. `tracked_files` fails closed, never skipped, in three
      cases:
      - outside a work tree;
      - when `git rev-parse --show-toplevel` is not the checked root
        (F15: a root nested inside another repository lists nothing);
      - when `ls-files` returns no files.
    - *How this differs from the rejected "Git-based ignore":* git
      never decides what the checker ignores. `tests/mirror.py` stays
      pure, spawns no process, and its fixtures need no `git init`.
      Git only validates the manifest's ignore list, from one test,
      against the real repository. Untracked, non-ignored files under
      a copy root are still orphans (R7), which is exactly the case
      `ls-files` as an ignore mechanism would have hidden.
    - *I6:* acceptable. Git is already on this suite's critical path:
      `tests/support.py` runs `git init`/`commit` for every fixture,
      `verify.py`'s range gates require git, and the CI workflow checks
      out with `fetch-depth: 0`. This adds no dependency, network
      access, CLI or kernel checkout beyond what the client's runner
      already has. The one environment it fails in, a source export
      with no `.git`, already fails the rest of the suite, and failing
      closed there is the I6-correct direction.

   Isolated review stays the backstop for exceptions on other copies.
   The adversarial rounds' "smuggle an exception" probe is where that
   happens.

## Consequences

**What this closes.** G1–G6 become manifest entries, not new tests.
Every copy root is walked in both directions over all file types. The
four generated regions are compared exactly against sources that
D6–D8 only sampled. The three unpropagated usability probes are the
first thing the mechanism catches.

**The concentration risk, named.** One checker now guards every pair.
If it has a bug that returns no violations, all pairs go green at once
(FM-14). The design answers this with a pure core exercised on fixtures
with known violations, a mutation suite iterated from the manifest,
fail-closed rules for empty roots and zero-file pairs, and no broad
`except` anywhere in the checker. These reduce the risk but do not
remove it, and it is the first attack for the adversarial rounds.

**The list renderers are a second statement of SETUP §7's format
rules** (MNT-1, accepted knowingly). If SETUP §7 changes format and a
renderer does not, the suite goes red and forces the two to agree.
Today the same rules live in SETUP and in D7–D8's needles, with no
such forcing, so this is a gain over the status quo, not a new cost.
The attack order is not a second statement. Only its markdown layout
lives in `tests/mirror.py`; the order, floor, rounds and blocking rule
come from `probe_plan`.

**Rounding, flagged as kernel feedback.** SETUP says `rounds =
max(1, weight/10 rounded)`. `probe_plan` (and D6 before it) computes
Python `round()`, which is banker's rounding: weight 25 gives 2 rounds,
where half-up gives 3. The renderer uses `probe_plan`'s arithmetic, so
this demand changes no behavior. No
declared weight here ends in 5. The ambiguity belongs in SETUP's text
and is recorded, not resolved, here.

**Residual gaps.**
- R8 takes SETUP's install destinations from §6's `→` lines plus a
  pinned list for §7/§8 (`AGENTS.md`, `.claude/agents/`,
  `.claude/skills/`). A new pair that neither a parent pair,
  `generated_paths`, nor the orphan walk beside its copy would notice
  being dropped must name its destination in a SETUP §6 `→` line. That
  line is the one non-manifest edit a new pair may need, and it is
  documentation, not test code.
- An exception can excuse drift (Decision 9).

## Revision — 2026-09-28 (FWD-020 review round 1)

Revised in place before the demand closed, after
`reviews/FWD-020/findings.toml` round 1. The changes are:
- F2: the attack order formats `probe_plan` (Decision 3 and
  Consequences).
- F3: Decision 9 added, and Decision 1 narrowed to what placement
  actually guards.
- F1: the residual gap now names the SETUP §6 line.

The build-contract changes for F1 and F4–F7 are in
`specs/FWD-020-mirror-drift/architecture.md`.

## Revision — 2026-09-28 (FWD-020 review round 2)

Revised in place after round 2 (F9–F13):
- F9: Decision 10 added, and the "Git-based ignore" rejection scoped
  to what it rejects.
- F10: Decision 9's pins restated as ordering and forbidden-string
  pins, with their real reach stated.
- F11–F13 are contract changes, recorded in `architecture.md`:
  - F11: the marker check compares the whole block;
  - F12: a replaced section ends at a heading of the same or a higher
    level;
  - F13: a symlinked copy directory or symlinked parent is
    `not-a-regular-file`.

## Revision — 2026-09-28 (FWD-020 review round 3)

All round-3 items are reconciled and closed:
- F14: Decision 10's validator and every walk use one predicate,
  `mirror.hidden` (the path or any ancestor directory is ignored), so a
  bare entry matching a directory (`dimensions`) is caught.
- F15: `tracked_files` requires root to be the work-tree top and
  `ls-files` to be non-empty.
- F16: Decision 9 no longer claims the gate "runs unconditionally".
  `on: [push, pull_request]` is pinned, and the literal `"if"`,
  `'if'`, `"on"` and `'on'` are forbidden. (Round 4 restates the
  remaining residuals; see below.)
- F17: a replaced section ends at the next CommonMark heading of the
  same or a higher level, ATX or setext. The rule is in
  `architecture.md`.

## Revision — 2026-09-28 (FWD-020 review round 4)

- F22: the round-3 revision above is rewritten so that it no longer
  contradicts itself. F14 is closed, not "in progress", and the quoted
  `if` and changed trigger are described by what is pinned.
- F20: Decision 9 no longer says the quoted forms close the
  YAML-quoted-key spelling. The forbidden-string list closes only its
  listed literals. Any other YAML spelling of an `if` (`if : false`,
  `? if`, `"i\x66"`, `? !!str if`, …) is a named residual for review.
- F19: closed. Heading forms the section-end recognizer does not
  model exactly fail closed: a multi-line or lazy-continuation setext
  heading, or a block-quoted heading, after the replaced heading makes
  `tests/mirror.py::_unmodelled_heading` report `stale-exception` on
  the source path. The checker never computes a span from them. The
  contract is in `architecture.md`.
- F21: closed. `test_installed_pre_commit_is_executable` requires
  `.githooks/pre-commit` to be executable on disk (`X_OK`) and recorded
  as mode 100755 in the git index. It checks the installed hook only,
  never the template (Decision 9).
