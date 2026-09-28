---
date: 2026-09-28
amended: 2026-09-28 (post-ADR-0016 attack-order drift; round-2 F9, F10, F12; round-3 F14, F15, F17)
demand: FWD-020
---

# Acceptance — FWD-020 one declared mechanism for mirror drift

Context: every source→copy pair in this self-hosted repo (runtime →
`bin/fde/`, spec → `.fde/spec/`, skills/agents → `.claude/`, templates →
`.githooks/`, workflow, `AGENTS.md`) is guarded today by thirteen bespoke
assertions across five test files (inventory D1–D13 in `spec.md`), each
with its own relation, discovery rule and blind spots, while six pairs or
pair-aspects (G1–G6) have no guard at all. This demand replaces them with
one declared manifest and one checker, so a new copy is one manifest
line, not a new test — and loses no protection in the collapse.
Declared before any code exists (I4); failure modes in
`failure-modes.toml`.

> **amended: 2026-09-28**, before any code, after the architecture step
> (ADR-0016, `architecture.md`). Reason: probing the copies found live
> drift the original "Untouched" criterion denied. The `## Attack order`
> in `.claude/agents/fde-adversarial.md` lacks three usability probes
> that `spec/dimensions/quality-attributes.toml` has carried since
> FWD-017 (`bcbb734`, 0.13.0): *ambiguous next action with multiple
> plausible controls*, *irreversible action taken with no confirmation
> or undo*, *state change with no visible feedback*. D6 checked only
> `weight W, R round` substrings, so it stayed green. Changes: "Untouched"
> now allows regenerating exactly that section and nothing else; a new
> "Regression: stale attack order" criterion (FM-15) requires the
> mechanism to go red on the pre-fix state. The criteria now also follow
> ADR-0016's answers to the spec's Ask-first items: manifest at
> `tests/mirror.toml`, test-only with no `verify.py` gate, G7/G8 as
> ordinary content tests, `generated_paths` cross-checked and not
> derived, and G10 neither derived nor checked.
>
> **amended: 2026-09-28 (after adversarial round 2,
> `reviews/FWD-020/findings.toml`)**. F12: the extent of a replaced
> section is now stated; it ends at the next heading of the same or
> higher level, or at EOF. F9: the ignore criterion now requires that no
> `[ignore]` entry matches a git-tracked file, checked against
> `git ls-files`. F10: the gate-invocation pins are now stated as what
> they are, an ordering pin plus forbidden strings, on both the template
> and the installed copy. Presence alone was shown not to be enough.
>
> **amended: 2026-09-28 (after adversarial round 3,
> `reviews/FWD-020/findings.toml`)**. F17: "heading" now means exactly
> a CommonMark ATX heading or a setext h1/h2. A heading-shaped line
> inside a code fence ends the span early and is reported as a
> difference. F14: the ignore check applies the walk's own predicate to
> every tracked file and every ancestor directory. F15: the git check
> fails closed when the root is not the work tree's top level or when
> nothing is tracked.

## Criteria

- **One manifest, closed vocabulary (R1).** A single TOML manifest at
  `tests/mirror.toml` (under `[gate].eval_paths`), parsed with
  `tomllib`, declares every pair with a relation from `identical` /
  `identical-except` / `absent`. There is exactly one copy of it. It is
  not under `spec/`, not mirrored into `.fde/`, and not named in SETUP's
  install steps (FM-9). An unknown relation, an unknown exception kind,
  or a malformed entry fails the check.
- **No protection lost (R6, FM-8).** `promotions/FWD-020/decision.md`
  confronts a table mapping each inventory row to its new home, and every
  row has one:
  - D1 `runtime/` → `bin/fde/`, identical, discovered, sanity against an
    empty root (D1's `erosion.py`/`graph.py` pin becomes the fail-closed
    empty-root rule, R4);
  - D2 + D13 `spec/` → `.fde/spec/`, identical, discovered (D13 retired as
    redundant);
  - D3 orphans in `bin/fde/`, `.fde/spec/`;
  - D4 `skills/*/` → `.claude/skills/*/`, identical, with `fde-init`
    declared `absent` and red if it appears;
  - D5 `agents/` → `.claude/agents/`, discovered — not a hand list;
  - D6 `fde-adversarial.md`, identical-except (marker block insert +
    `## Attack order` replaced), region verified per R3;
  - D7/D8 `AGENTS.md` invariants/weights/test command, verified
    placeholders per R3;
  - D9 workflow, identical-except `{{TEST_COMMAND}}`; its
    `fetch-depth: 0` / `--since` needles retained as a content test;
  - D10/D11/D12 AGENTS.md ↔ template sections, subsumed by whole-file
    identical-except, with `DEM-042` → `FWD-002` declared as one literal
    substitution with its exact count (no regex);
  - FWD-019's content needles, the score-sentence/table pins,
    `agent_transcript`, scrum elements, template placeholders, and the
    value carriers (`kernel_version`, plugin names) remain as ordinary
    tests, unweakened.
  A row the manifest cannot express at equal or greater strength stays
  as its own test, with the reason written in ADR-0016.
- **Gaps closed (G1–G6).** The manifest also covers, and the suite goes
  red on drift in: `agents/fde-walkthrough-evaluator.md` (G1);
  `templates/pre-commit` → `.githooks/pre-commit` (G2); the whole
  workflow file, not just needles (G3); the whole adversarial role file
  outside its declared regions (G4); the whole `AGENTS.md` outside its
  declared placeholders and substitution (G5); orphans of any file type
  under every declared copy root, including `.claude/skills/` and
  `.claude/agents/` (G6).
- **Bidirectional, all file types (R2, FM-2, FM-3).** Every source file
  has its copy or an `absent` declaration; every file under a declared
  copy root has a source.
- **Exceptions are literal, counted, and fresh (R3, FM-4, FM-5, FM-7).**
  No regex/glob exception and no whole-file skip exists in the manifest.
  A `replace-section` span runs from its exact heading line to the next
  heading of the same or higher level, or to EOF (F12). A heading is a
  CommonMark ATX heading (0–3 leading spaces, `#`×1–6, then a space, a
  tab or end of line) or a setext h1 (`=` underline) or h2 (`-`
  underline) (F17). Fixtures prove that content under a later heading
  of higher level in the source must appear in the copy, and that its
  absence is red, for each spelling: `# Appendix`, `#\tAppendix`,
  ` # Appendix` (leading spaces), and `Appendix` over `========`.
  A heading-shaped line inside a code fence in the source ends the
  span early and makes the check report `differs`. It never goes
  silently green.
  A declared difference that matches nothing, or a count other than
  declared, is red. Every replaced region and placeholder is verified
  against its named source: invariants (id, name, statement) from
  `spec/invariants.toml`; weights in order and depths > 0 from
  `fde.config.toml`; project name and test command from `[project]`/
  `[stack]`; attack order sorted by weight descending, `rounds =
  max(1, round(w/10))`, `BLOCKS MERGE` iff w ≥ 15, probes from
  `quality-attributes.toml`.
- **Fail closed (R4, FM-6, FM-14).** The checker is a pure core over
  (root, manifest) returning violations labeled by pair, relation, file
  and difference. An empty/missing source root, a pair that checked zero
  files, or an exception raised inside the checker is red, never a pass —
  each proven by a fixture test with a known violation.
- **Mutation evidence, driven by the manifest (R5).** For every pair
  iterated from the manifest (not a hand list), a temp copy of the pair's
  real files proves red on: one byte changed in the copy; the copy
  deleted; an extra orphan under the copy root; and, for
  `identical-except`, a change in an un-excepted region, a change inside
  a verified region (e.g. a weight, a round count, an invariant
  statement, a probe line), and a declared exception made stale. A fixture test adds a
  new pair to a fixture manifest and shows it is checked and
  mutation-tested with **zero test-code change** — the demand's headline
  claim, executed rather than asserted.
- **Dropped pair is caught (R8, FM-1, FM-12).** An agreement test between
  the manifest and the remaining declarations of the same layout goes
  red when a pair is removed from the manifest: every
  `[erosion].generated_paths` entry and every install destination named
  in SETUP §6/§8 (`bin/fde/`, `.fde/spec/`, `.githooks/pre-commit`,
  `.github/workflows/fde-gate.yml`, `AGENTS.md`, `.claude/agents/`,
  `.claude/skills/`) maps to a declared pair; each `identical` copy root
  is under a `generated_paths` entry or, but not both, its pair declares
  `erosion_measured = true` (today only `pre-commit`). Proven by a
  fixture test that deletes any one pair from a copy of the real
  manifest and sees red. `generated_paths` is cross-checked, not derived
  from the manifest: its value in `fde.config.toml` and `erosion.py`'s
  config contract are unchanged. `tests/support.py::make_project` (G10)
  is a deliberately minimal client fixture, not a layout declaration. It
  is neither derived from the manifest nor checked against it, and it is
  unchanged by this demand.
- **G7/G8 as ordinary content tests (not manifest pairs).** New tests
  assert that `CLAUDE.md`'s first line is `@AGENTS.md`, and that
  `.claude/settings.json`, parsed with `json`, has a `PreToolUse` entry
  with matcher `Write|Edit` running exactly
  `python3 "$CLAUDE_PROJECT_DIR/bin/fde/guard.py"`, and
  `worktree.baseRef == "head"`. The manifest vocabulary gains no fourth
  (`contains`) relation for them.
- **Ignore is explicit and narrow (R7, FM-11).** With an agent worktree
  present under `.claude/worktrees/`, `__pycache__/` and
  `.fde/guard-audit.jsonl` on disk, the check is green; an untracked,
  non-ignored file added under `.claude/skills/` is red. Both proven by
  fixture tests. **The ignore list never silences a git-tracked file
  (F9).** A test lists the real repo's tracked files with
  `git ls-files` and asserts that no `[ignore]` entry matches any of
  them. A fixture git repo shows that an entry over tracked content
  (such as `dimensions/`, `roles.toml` or `fde-implementation.md`) is
  reported, while an entry that matches only untracked runtime output
  (`__pycache__/`, `*.pyc`) is not. The git call lives in the test,
  never in the pure checker core. Outside a git work tree it errors;
  it never skips. Adding the matching `.gitignore` line does not make
  a tracked-file entry pass. **The check applies the walk's own match
  predicate (F14).** It runs against every tracked file path and every
  ancestor directory of a tracked file, each with its real kind (file
  or directory). So a bare `dimensions` entry, which matches the
  directory as well as `dimensions/`, is reported, and a fixture proves
  it. **It fails closed (F15)**, raising and never passing, when the
  root is not the git work tree's top level (for example, a copy
  nested inside an unrelated repo) or when `git ls-files` lists no
  tracked file. Fixtures cover both cases.
- **Gate-invocation pins: ordering plus forbidden strings (F10,
  ADR-0016 Decision 9).** On both the template and the installed copy
  of each file that runs the gate:
  - `templates/pre-commit` / `.githooks/pre-commit` start with
    `#!/bin/sh`, and the first line that is not a comment or blank is
    exactly `exec python3 bin/fde/verify.py --staged`;
  - `templates/fde-gate.yml` / `.github/workflows/fde-gate.yml` end with
    the exact `FDE gate` step running `verify.py --all --since …`, so it
    is the last step;
  - none of the four files contains `continue-on-error`, `if:`,
    `|| true`, `|| exit 0`, `; true` or `exit 0`.
  A presence-only needle, such as the line appearing somewhere or a
  regex matching anywhere, does not satisfy this criterion: F10 showed
  a preceding `exit 0` or `continue-on-error: true` passing one. These
  pins survive an edit to both the template and the copy, and any
  manifest exception.
- **Only one place compares copies (R6).** After the change, no test
  outside `tests/test_mirror.py` (and the checker `tests/mirror.py`,
  which discovery does not collect) reads a source file and its
  declared copy to assert equality. Verifiable by inspection of
  `tests/`.
- **I6 holds (R9, FM-10).** Stdlib only (`tomllib`, `pathlib`, `json`,
  `unittest`). Runs under `python3 -m unittest discover -s tests` with
  no network, no `claude` CLI, no git subprocess in the checker core,
  and no kernel checkout outside the repo. Test-only: `KNOWN_GATES`,
  `runtime/`, and `bin/fde/` gain nothing for this mechanism, so no new
  code ships into clients. Whole mirror check < 2 s on this repo
  (baseline: `tests.test_install_sync`, 17 tests, 0.72 s, 2026-09-28).
- **References follow (R10, FM-13).** `fde.config.toml`'s `[gate]` and
  `[erosion]` comments, `observability.toml`'s maintainability line,
  `discovery/survey.md`, and `tests/test_walkthrough.py`'s NOTE name the
  new mechanism. A grep for each retired test id outside `reviews/`,
  `promotions/` and other demands' `specs/` returns nothing.
- **Regression: stale attack order (FM-15).** The pre-fix state of
  `.claude/agents/fde-adversarial.md` goes red under the new mechanism.
  A test keeps that pre-fix copy as a fixture: the bytes as of the
  demand's base commit, or the regenerated section with the three probe
  lines removed. It asserts `check` reports `differs` on the
  `adversarial-role` pair, with the first differing line inside the
  `### 4. Usability & accessibility` block. This eval guards against
  that concrete drift coming back. A mutation-suite pass alone does not
  satisfy this criterion.
- **The one regenerated region.** In the same change, the copy's
  `## Attack order` section is regenerated from its sources
  (`fde.config.toml [weights]` +
  `spec/dimensions/quality-attributes.toml`), never hand-edited, and the
  source is not edited to match the copy. The resulting diff to
  `.claude/agents/fde-adversarial.md` is exactly three added lines, in
  the usability block, immediately after
  `- loading and failure states visible to the user`, in source order:
  `- ambiguous next action with multiple plausible controls`,
  `- irreversible action taken with no confirmation or undo`,
  `- state change with no visible feedback`. After that, the copy
  equals `render:attack_order`'s output byte-for-byte.
- **Untouched (amended).** Apart from those three lines, no file under
  any declared copy root or copy path changes in this demand. That
  covers `bin/fde/`, `.fde/spec/`, `.claude/skills/`, `.claude/agents/`,
  `.githooks/pre-commit`, `.github/workflows/fde-gate.yml` and
  `AGENTS.md`, and it is verifiable by `git diff --stat <base>..<closing>`
  over those paths. No source under `runtime/`, `spec/`, `skills/`,
  `agents/` or `templates/` changes either. Also unchanged:
  `runtime/verify.py::Gate.gate_eval_coverage`, `KNOWN_GATES`,
  `[gate].behavior_paths`/`eval_paths`, `[erosion].generated_paths`,
  `erosion.py`, and `tests/support.py`. The one intended copy change
  follows the rule that a generated file is fixed by regenerating it
  (ADR-0016 Decision 8), and it gets its own line in the promotion
  decision.
- **ADR (R11).** `docs/adr/0016-one-manifest-for-every-mirror.md`
  (accepted 2026-09-28) records the decisions these criteria follow:
  manifest at `tests/mirror.toml`, test-only (no gate), G7/G8 as
  content tests, G9 cross-checked not derived, G10 neither. It also
  records the rejected options: keeping case-by-case tests; a blanket
  "all copies identical" glob with a per-file skip list; generating
  copies at test time. The build honors those decisions. Deviating from
  one needs a superseding ADR, not an implementation choice.
- **Gate.** Full suite (`python3 -m unittest discover -s tests`) and
  `python3 bin/fde/verify.py --all` green at the demand's closing commit,
  with no pre-existing gate regressed.
- **Review.** Two isolated adversarial rounds in `reviews/FWD-020/`,
  prompted to: drop a pair from the manifest and see if anything notices;
  add an undeclared file under each copy root; smuggle a wildcard-strength
  exception past the vocabulary; edit a concretized region
  (adversarial attack order, AGENTS.md invariant statement) to a wrong
  but plausible value; remove one `adversarial_probes` entry from the
  copy (the stale-probe drift) and check it goes red; check that the
  closing diff to the copies is exactly the three probe lines; break the checker so it returns no violations and
  see whether any test goes red; run the suite with an agent worktree
  present; and find any D1–D13 protection with no live equivalent.
  `promotions/FWD-020/decision.md` confronts this list.
