# FWD-020 — One declared mechanism for mirror drift

Triage: surfaces 2 (gate/test runtime + install/CI copies) · public ·
reversible · ~300+ LOC → score 3 + loc 2 → **M** (spec, impl,
adversarial 2 rounds, promotion, ADR-0016).

Input: `backlog.md` item 8 "Collapse the parallel-copy defence"
(evidence: usage-data, `graph --recurring`), pulled forward on
2026-09-28 as an unplanned demand in `sprints/S-006/goal.md`.

## Problem

This repository is FORWARD installed on itself (ADR-0007). Every piece
of kernel behavior exists at least twice: once as source (`runtime/`,
`spec/`, `skills/`, `agents/`, `templates/`) and once as the installed
copy that CI and agents actually execute (`bin/fde/`, `.fde/spec/`,
`.claude/skills/`, `.claude/agents/`, `.githooks/`,
`.github/workflows/`, `AGENTS.md`). The copies are change-controlled
(`[gate].behavior_paths`, finding F4) and their eval is "the source/copy
identity suite".

That suite is not one suite. It is a set of case-by-case detectors that
accreted one review finding at a time, in five test files, each with its
own notion of what "in sync" means (byte-identical, identical except a
section, identical after a regex normalization, "contains these
needles"), each with its own discovery rule (glob, rglob, hard-coded
list), and each with its own blind spots. `python3 bin/fde/graph.py
--recurring` ranks MNT-1 ("single source of truth: every fact lives in
one place; duplication is drift waiting") first at **28.0**
severity-weighted on 2026-09-28 (25.0 when the backlog item was written),
more than twice OBS-1 (12.0). Not every MNT-1 citation is about file
copies (FWD-008's ADR-format finding, FWD-010's catalog restatement are
content duplication), so this demand does not promise that number drops —
historical findings stay in the graph. It promises the thing the
hypothesis actually claims: **a new copy is one manifest line, not a new
test**, and no protection that exists today is lost in the collapse.

### Inventory — every drift/identity assertion in `tests/` today

Observed by reading `tests/*.py` in full for this spec (2026-09-28).
"Relation" is the relation the assertion actually enforces, not the one
its name implies.

| # | Test | Pair | Relation enforced | Discovery | Blind spots |
|---|---|---|---|---|---|
| D1 | `test_install_sync::TestRuntimeCopies::test_every_runtime_module_is_identical_in_bin_fde` | `runtime/*.py` → `bin/fde/*.py` | byte-identical, copy must exist | glob, plus a sanity pin that `erosion.py`/`graph.py` are in the glob result (guards against an empty glob passing vacuously) | non-`.py` files in `runtime/` |
| D2 | `…::test_fde_spec_is_identical_to_spec` | `spec/**/*.toml` → `.fde/spec/**` | byte-identical, copy must exist | rglob | non-`.toml` files |
| D3 | `…::test_no_orphan_files_in_the_installed_copies` | reverse of D1/D2 | no file in `.fde/spec/**/*.toml` or `bin/fde/*.py` without a source | rglob / glob | orphans in `.claude/skills/`, `.claude/agents/`, and any non-`.py`/non-`.toml` file under `bin/fde/`, `.fde/spec/` |
| D4 | `…::TestClaudeLayerCopies::test_skills_are_installed_identically_except_init` | `skills/*/SKILL.md` → `.claude/skills/*/SKILL.md` | byte-identical; `fde-init` MUST be absent from the copy | iterdir | any second file in a skill directory; orphan skill dirs in `.claude/skills/` |
| D5 | `…::test_generic_role_files_are_installed_identically` | `agents/fde-{spec,architecture,implementation,promotion}.md` → `.claude/agents/` | byte-identical | **hard-coded list** | `fde-walkthrough-evaluator.md` (added by FWD-018) is not in the list — identical today, unprotected |
| D6 | `…::test_adversarial_is_concretized_to_this_repos_weights` | `agents/fde-adversarial.md` → `.claude/agents/fde-adversarial.md` | copy contains `weight W, R round` per attribute and `BLOCKS MERGE` when W ≥ 15 | config weights | everything outside those substrings: frontmatter, Inputs/Outputs/Denied/Conduct sections, the marker block, attribute order, the probe lists |
| D7 | `…::TestGeneratedSurfaces::test_agents_md_lists_every_invariant_from_the_spec` | `spec/invariants.toml` → `AGENTS.md` | contains `**<id> <name>**` per invariant | spec | the statement text after the name |
| D8 | `…::test_agents_md_carries_this_repos_weights_and_test_command` | `fde.config.toml` → `AGENTS.md` | contains test command and `- attr: w` per weight | config | order, depths list, eval command |
| D9 | `…::test_workflow_runs_tests_and_a_ranged_gate_on_full_history` | `templates/fde-gate.yml` → `.github/workflows/fde-gate.yml` | contains test command, `fetch-depth: 0`, `--since`; no `{{TEST_COMMAND}}` left | fixed path | every other line of the workflow — it is never compared to its template |
| D10 | `test_instructions::TestPerDemandTriage::test_demand_loop_carries_the_rule_identically_in_both_surfaces` | `templates/AGENTS.md.template` → `AGENTS.md`, `## Demand loop` section | identical after replacing every `` `[A-Z]+-\d+` `` with `` `ID` `` | section split | the normalization is a wildcard over the whole section, broader than the one real difference (`DEM-042` vs `FWD-002`) |
| D11 | `test_instructions::TestRuleLaneIsAParagraphNotATableRow::test_rule_paragraph_is_byte_identical_between_agents_and_template` | same pair, RULE paragraph | byte-identical span, plus content needles | index-based span | — (content needles are not drift and stay) |
| D12 | `test_scrum::TestScrumR2R3Artifacts::test_template_and_repo_carry_the_same_scrum_section` | same pair, `## Scrum mode` section | byte-identical section | section split | — |
| D13 | `test_references::…::test_base_is_installed_byte_identical` | `spec/references/ui-patterns.toml` → `.fde/spec/references/` | byte-identical | fixed path | fully redundant with D2 |

Adjacent assertions that are **not** source→copy drift and stay where
they are, untouched by this demand (listed so no one reads their survival
as an incomplete collapse):

- `test_instructions::…::test_agents_and_template_score_sentence_is_unmodified`
  and `…::test_skill_table_is_unmodified_and_rule_precedes_it_as_prose` —
  pin literal content and position (FWD-019 R6), in each file on its own.
- `test_instructions::TestExecutionProvenance::test_all_provenance_surfaces_name_agent_transcript`
  — a content needle across four files (two of which are a pair).
- `test_spec_integrity::TestTemplatesAndVersions::test_templates_carry_their_placeholders`
  — the templates' own shape, including `fde.config.template.toml`, which
  has no installed copy (`fde.config.toml` is user-owned, not generated).
- `test_spec_integrity::…::test_kernel_version_is_synced_everywhere`,
  `test_install_sync::TestGeneratedSurfaces::test_kernel_version_matches_the_spec_here_too`,
  `TestPluginDistribution::*` — **value** carriers (the same version or
  name in files of different shape and key), not file copies.
- `test_verify::TestSharedRangeResolution` — code duplication inside one
  module, not a file copy.
- `test_walkthrough.py`'s NOTE comment (lines ~850–866) — not an
  assertion, but it names D2 and D5 by test id as the place mirror
  identity is covered; it goes stale if those ids retire.

### Pairs with no protection today (observed, all currently in sync)

Verified on 2026-09-28 with `cmp`/`diff` against the working tree:

- G1 `agents/fde-walkthrough-evaluator.md` → `.claude/agents/` — identical,
  not asserted (D5's hard-coded list).
- G2 `templates/pre-commit` → `.githooks/pre-commit` — identical, **not
  asserted anywhere**. This is the file that runs the gate on every
  commit (`core.hooksPath = .githooks`).
- G3 `templates/fde-gate.yml` → `.github/workflows/fde-gate.yml` —
  identical except `{{TEST_COMMAND}}` filled; only needles asserted (D9).
- G4 `agents/fde-adversarial.md` → `.claude/agents/fde-adversarial.md` —
  identical except (a) the `FDE-KERNEL:GENERATED` marker block inserted
  after the frontmatter and (b) the final `## Attack order` section
  replaced by the concrete plan; only weight substrings asserted (D6).
- G5 `templates/AGENTS.md.template` → `AGENTS.md` — identical except the
  five `{{…}}` placeholders filled and the example id `DEM-042` →
  `FWD-002`; only three sections asserted (D10–D12) plus needles (D7/D8).
  Commands, Invariants prose, Roles, Voice, and Detail are unprotected.
- G6 Orphans under `.claude/skills/`, `.claude/agents/`, and any file
  type other than `.py`/`.toml` under `bin/fde/`/`.fde/spec/`.
- G7 `CLAUDE.md` first line `@AGENTS.md` (SETUP §8.3) — not asserted.
- G8 `.claude/settings.json` hook shape (SETUP §8.4) — no template file
  exists; the relation is prose-to-JSON.
- G9 `fde.config.toml [erosion].generated_paths` restates the mirror
  roots (`bin/fde/`, `.fde/`, `.claude/skills/`, `.claude/agents/`) as a
  second, independent declaration of the same fact.
- G10 `tests/support.py::make_project` enumerates which `spec/` files the
  fixture installs (and omits `spec/references/`), a third declaration of
  the install layout.

G1–G6 are in scope: they are exactly the pairs a single declared
mechanism covers for free, and closing them is the evidence the
mechanism is not just a rename of D1–D13. G7–G10 are named; their
disposition is under Boundaries.

## Amendment — 2026-09-28 (after ADR-0016)

The architecture step (`docs/adr/0016-one-manifest-for-every-mirror.md`,
`specs/FWD-020-mirror-drift/architecture.md`) resolved every "Ask first"
item below:
- the manifest is `tests/mirror.toml`;
- the mechanism is test-only, with no `verify.py` gate;
- `generated_paths` is cross-checked, not derived;
- G10 is neither derived nor checked;
- G7/G8 become ordinary content tests;
- value carriers stay out.

The architecture step also found live drift that contradicts the
inventory's "all currently in sync". G4's `## Attack order` lacks three
usability probes that `quality-attributes.toml` has carried since
FWD-017. This is FM-15, covered by R12. `acceptance.md` is amended to
match.

## Amendment — 2026-09-28 (after adversarial round 2, F9/F10/F12)

- **F12** (`reviews/FWD-020/findings.toml`): the original wording said a
  replaced section runs "to the next same-level heading or end of file".
  Taken literally, content added to the source after the section under a
  higher-level heading (`# Appendix …` after `## Attack order`) became
  part of the replaced span. It was never installed and never reported,
  and a literal SETUP §8.2 installer got a false red. The required rule
  is now: a replaced section ends at the next heading of the same or
  higher level (fewer or equal `#`), or at end of file. Boundaries and
  R3 are amended to match.
- **F9**: "the ignore rule never silences a tracked file" (Always) is now
  a checked requirement, not only a design intent. R7 adds it: no
  `[ignore]` entry may match a git-tracked file.
- **F10**: the gate-invocation pins (ADR-0016 Decision 9) protect by
  order plus forbidden strings, not by presence. This is recorded in
  `acceptance.md`, and no requirement text here changes.

## Amendment — 2026-09-28 (after adversarial round 3, F14/F15/F17)

Cites `reviews/FWD-020/findings.toml`, round 3.
- **F17**: "the next heading" was broader than the implemented rule.
  `#\tAppendix`, ` # Appendix` and a setext `Appendix\n========` were
  absorbed into the replaced span, so source content was never
  installed and nothing reported it. The definition is now exact: a heading is a CommonMark ATX heading (0–3 leading spaces, then 1–6
  `#`, then a space, a tab, or end of line; level = number of `#`) or a
  setext heading (a non-blank text line underlined by a line of only `=`
  for level 1 or only `-` for level 2, 0–3 leading spaces). Code fences
  are not tracked. A heading-shaped line inside a fence ends the span
  early, and the result is reported as a difference. That is the safe
  direction: a false red, never a silent green.
- **F14**: R7 now says an `[ignore]` entry is judged with the same
  predicate the walk uses. That covers every tracked file **and every
  ancestor directory** of a tracked file. The case this closes: a bare
  entry such as `dimensions`, which the walk applies to directories,
  silenced `spec/dimensions/` and `.fde/spec/dimensions/`, while the F9
  check tested only file paths and passed.
- **F15**: the git check in R7 fails closed when the root is not the
  work tree's top level, or when nothing is tracked. Before this, a
  checkout nested in an unrelated repo listed zero tracked files and
  passed vacuously.

## Boundaries

**Always**
- One manifest, one checker. Every source→copy pair in this repo is
  declared in a single versioned TOML file, parsed with stdlib `tomllib`,
  and checked by one checker. Adding a pair is adding manifest lines,
  with zero new test code.
- Declare relations from a closed vocabulary, each with exact semantics:
  - `identical` — byte-for-byte equal; copy must exist.
  - `identical-except` — equal after applying ONLY the declared,
    enumerated differences: literal placeholder fills (`{{NAME}}` →
    a value derived from a named source of truth), literal substitutions
    (exact `from` → exact `to`, with an expected occurrence count), an
    inserted block (exact text, at a declared anchor), or a replaced
    section (named by its exact heading, running to the next heading of
    the same **or higher** level, or to end of file; a `# Appendix`
    after a `## ` section ends it). Here a heading is a CommonMark ATX
    heading (0–3 leading spaces, then 1–6 `#`, then a space, a tab, or
    end of line; level = number of `#`) or a
    setext heading (a non-blank text line underlined by a line of only `=`
    for level 1 or only `-` for level 2, 0–3 leading spaces). Code fences
    are not tracked. A heading-shaped line inside a fence ends the span
    early, and the result is reported as a difference. That is the safe
    direction: a false red, never a silent green.
    See the amendments for review F12 (round 2) and F17 (round 3).
  - `absent` — the source MUST NOT have a copy (e.g. `skills/fde-init`).
  A replaced/generated region is not a wildcard: its content is verified
  against the source of truth it is derived from, at no less strength
  than today's assertions (D6–D8).
- Discover, never enumerate. A pair may be declared over a root
  (`runtime/` → `bin/fde/`, `skills/*/` → `.claude/skills/*/`) and the
  checker walks it in both directions: every source file has its copy
  (or an `absent` declaration), every file under a declared copy root
  has a source (no orphans). A root-level declaration covers every file
  type in the tree, not a suffix — D1–D4's `.py`/`.toml`/`SKILL.md`
  filters are the blind spots G6 names.
- Fail closed on the manifest itself: a declared pair whose source root
  is empty or missing, an exception that matches nothing in the file
  (stale), a substitution whose occurrence count differs from declared,
  an unknown relation name, or a malformed entry is red — never a
  silently vacuous pass (the same class of guard as D1's
  `assertIn("erosion.py", modules)`).
- Separate the pure core from the repo: the checker takes a root path
  and a parsed manifest and returns labeled violations
  (pair, relation, file, what differed), so it runs unmodified against
  the real repo and against a temp-dir fixture. Report every violation
  labeled by pair and relation, never a bare pass/fail, mirroring
  `erosion.check_budget`'s labeled-breach style.
- Ignore what is not a copy: gitignored runtime output
  (`.fde/guard-audit.jsonl`, `__pycache__/`, `*.pyc`) and agent worktrees
  (`.claude/worktrees/`, which hold full clones of every source and every
  copy) are never reported as orphans or sources. The ignore rule is
  explicit and narrow; it never silences a tracked file.
- Stdlib only, no framework component on the critical path (I6). The
  mechanism runs under the project's own runner
  (`python3 -m unittest discover -s tests`) with no network, no `claude`
  CLI, no kernel checkout outside the repo, and adds no dependency.
- Keep content assertions. Needles that pin what a file must *say*
  (FWD-019's table/sentence pins, the RULE paragraph's required phrases,
  `agent_transcript`, the scrum elements, the placeholders a template
  must carry) are not drift tests and are not deleted by this demand.
- Update every live reference to a retired test id in the same change
  (MNT-10: docs drift is drift): `fde.config.toml`'s `[gate]` and
  `[erosion]` comments, `observability.toml`'s maintainability line,
  `discovery/survey.md`, and `tests/test_walkthrough.py`'s NOTE. Closed
  historical artifacts (`reviews/`, `promotions/`, earlier `specs/`) are
  records and are not rewritten.

**Ask first**
- Where the manifest lives. This spec's recommendation, for ADR-0016 to
  confirm or reject: under `[gate].eval_paths` (e.g. `tests/`), because
  then dropping a pair is shrinking an eval file — visible to the
  `rule-lane` gate (FWD-019 R1(d) makes it RULE-ineligible) and to
  review. **Not** under `spec/`: `test_fde_spec_is_identical_to_spec`
  rglobs `spec/**` into `.fde/spec/`, but SETUP §6 step 2 installs an
  enumerated subset of `spec/` into client projects, so a
  kernel-self-hosting manifest in `spec/` would either ship to clients
  where it means nothing or open a new source/copy disagreement between
  SETUP and the suite (FM-9).
- Whether the checker is a unittest module only, or also a `verify.py`
  gate id. A gate would ship to every client, where no kernel source
  exists to compare against; if chosen, it must be silent (not red, not
  a report row) in a project with no manifest, and `KNOWN_GATES` changes
  must be pure additions.
- Whether `[erosion].generated_paths` (G9) and `tests/support.py`'s
  fixture layout (G10) are *derived from* the manifest or merely
  *checked against* it. The minimum this spec requires is the check
  (R8); derivation changes `erosion.py`'s config contract for clients
  and is a separate decision.
- Whether G7 (`CLAUDE.md` starts with `@AGENTS.md`) and G8
  (`.claude/settings.json` carries the guard hook and `worktree.baseRef`)
  join the manifest as a fourth relation (e.g. `contains`) or stay as
  ordinary content assertions. Neither is a file copy; neither is
  asserted today.
- Folding the value carriers (`kernel_version` in four files,
  plugin/marketplace name) into the same manifest. Out of scope by
  default: different relation (same value, different shape).

**Never**
- A regex or glob wildcard as an exception. D10's `` `[A-Z]+-\d+` ``
  normalization over a whole section is the anti-pattern: it would also
  hide a real id change anywhere in that section. Exceptions are
  literals with counts, or named sections whose replacement content is
  itself verified.
- A whole-file "skip" or "generated, don't compare" relation. A copy
  that cannot be described by `identical`/`identical-except`/`absent`
  is a finding to record, not a pair to exempt.
- Hard-coded per-file lists where a root can be declared (D5's failure).
- Weakening any protection to make the collapse fit: if a current
  assertion cannot be expressed by the manifest at equal or greater
  strength, it stays as its own test and the spec records why.
- Deleting or rewriting historical records (`reviews/**`,
  `promotions/**`, other demands' `specs/**`) that cite the old test ids.
- Any change to `runtime/verify.py::Gate.gate_eval_coverage`, or to what
  I1 counts as behavior/eval paths, as a side effect of this demand.

## Failure modes

Enumerated in `failure-modes.toml` (FM-1 … FM-15). Summary:
FM-1 pair silently dropped from manifest; FM-2 orphan copy; FM-3 new copy
nobody declares; FM-4 over-broad exception; FM-5 stale exception;
FM-6 vacuous pass on empty/missing root; FM-7 generated region
unverified; FM-8 protection lost in the collapse; FM-9 manifest itself
drifts between source and mirror / ships where it means nothing;
FM-10 I6 regression (non-stdlib, CLI, network, kernel checkout);
FM-11 ignored-path leak (worktrees, runtime output) — false red or false
green; FM-12 second declaration of the same fact (`generated_paths`,
fixture) disagrees with the manifest; FM-13 stale references to retired
test ids; FM-14 the checker's own bugs pass because it is only ever run
against a repo that is already in sync; FM-15 (amendment) a generated region silently stale against its source — observed live in the adversarial attack order.

## Requirements (EARS)

- R1: The repository MUST contain exactly one mirror manifest (TOML,
  stdlib-parseable) declaring every source→copy pair D1–D13 protect and
  G1–G6 name, each with a relation from the closed vocabulary
  (`identical`, `identical-except`, `absent`). An unknown relation or a
  malformed entry MUST fail the check.
- R2: WHEN the checker runs, for every pair it MUST verify both
  directions over the whole declared root, all file types: every source
  file has a copy satisfying the relation (or an `absent` declaration),
  and every file under a declared copy root maps to a declared source
  (orphan = red). `absent` MUST fail if the copy exists.
- R3: WHEN a pair is `identical-except`, the checker MUST apply only the
  declared differences, each a literal (placeholder fill from a named
  source, `from`→`to` substitution with an expected count, inserted block
  at an anchor, replaced section by exact heading, ending at the next
  heading of the same or higher level or at EOF, with "heading" as
  defined under Boundaries/Always: CommonMark ATX or setext h1/h2, per
  the F12 and F17 amendments), and MUST fail when
  any declared difference matches nothing or matches a count other than
  declared. Placeholder values and replaced sections MUST be verified
  against their source of truth: `AGENTS.md`'s invariant list against
  `spec/invariants.toml` (id, name, and statement), weights against
  `[weights]` in declared order, depths against `[derived.depths]` > 0,
  `{{PROJECT_NAME}}` against `[project].name`, `{{TEST_COMMAND}}`
  against `[stack].test_command`; the workflow's
  `{{TEST_COMMAND}}` against `[stack].test_command`; the adversarial
  `## Attack order` against `[weights]` (descending order, `rounds =
  max(1, round(w/10))`, `BLOCKS MERGE` iff w ≥ 15) and the probe lists
  against `quality-attributes.toml`. Strength MUST be ≥ D6–D9's today.
- R4: The checker MUST be a pure core over (root path, parsed manifest)
  returning labeled violations, plus a thin test that runs it against the
  real repo. It MUST fail closed on an empty or missing source root.
- R5: A mutation suite MUST exist that, for **every pair declared in the
  manifest** (iterated from the manifest, not a hand list), builds a
  temp copy of the pair's real files and proves red for at least: one
  byte changed in the copy; the copy deleted; an extra orphan file under
  the copy root; and, for `identical-except`, a change inside an
  un-excepted region and a declared exception made stale. Adding a pair
  to the manifest MUST extend the mutation suite with zero test-code
  change.
- R6: D1–D5 and D10–D13 MUST be retired into the mechanism, and D6–D9
  either retired into R3's verified regions or kept — never weakened.
  After the change, no test outside the mechanism's module may compare a
  source file to its declared copy for equality. Content assertions
  listed as "adjacent" in this spec MUST remain.
- R7: Ignored paths (gitignored runtime output, `.claude/worktrees/`,
  `__pycache__/`) MUST NOT produce orphans or sources; an untracked,
  non-ignored file under a copy root MUST be an orphan. (Amended
  2026-09-28, F9.) No `[ignore]` entry may match any git-tracked file.
  A test MUST check this against `git ls-files`, outside the pure
  checker core, and MUST fail closed (error, never skip) when the root
  is not a git work tree. (Amended 2026-09-28, round 3, F14/F15.) The
  check MUST use the same match predicate the walk uses, applied to
  every tracked file path and to every ancestor directory of a tracked
  file, each with that path's real kind (file or directory). It MUST
  also fail closed when the root is not the work tree's top level
  (`git rev-parse --show-toplevel` ≠ root) or when the tracked list is
  empty.
- R8: A test MUST assert agreement between the manifest and every other
  declaration of the same layout that remains — this is what catches a
  pair dropped from the manifest (FM-1), since the orphan walk cannot
  see a root nobody declares any more: each `[erosion].generated_paths`
  entry contains at least one declared copy root and no tracked,
  non-ignored file outside a declared copy root, and each declared
  `identical` copy root is under some `generated_paths` entry or
  explicitly listed as intentionally measured (G9); and each installed
  destination SETUP §6/§8 names
  (`bin/fde/`, `.fde/spec/`, `.githooks/pre-commit`,
  `.github/workflows/fde-gate.yml`, `AGENTS.md`, `.claude/agents/`,
  `.claude/skills/`) appears in the manifest.
- R9: The mechanism MUST run under `python3 -m unittest discover -s
  tests` with stdlib only (I6), and the whole mirror check MUST complete
  in under 2 s on this repo (baseline: `tests.test_install_sync`, 17
  tests, 0.72 s wall on 2026-09-28).
- R10: Every live reference to a retired test id MUST be updated in the
  same change (`fde.config.toml` comments, `observability.toml`,
  `discovery/survey.md`, `tests/test_walkthrough.py` NOTE).
- R11: `docs/adr/0016-*.md` MUST record the decision, including where the
  manifest lives and why, gate-vs-test, the G7–G10 dispositions, and the
  rejected alternatives: keep case-by-case tests; a generic "all copies
  identical" glob with a per-file skip list; generating the copies at
  test time instead of committing them.
- R12 (amendment 2026-09-28): WHEN this demand ships, the `## Attack
  order` section of `.claude/agents/fde-adversarial.md` MUST be
  regenerated from `fde.config.toml [weights]` and
  `spec/dimensions/quality-attributes.toml`, adding exactly the three
  missing usability probes. No other byte of any copy changes, and no
  source is edited to match the copy. A regression test MUST keep the
  pre-fix copy as a fixture and show the checker reports `differs` on
  it (FM-15).
