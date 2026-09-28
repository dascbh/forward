---
demand: FWD-020
date: 2026-09-28
decision: promote-with-conditions
---

# Promotion decision: one declared mechanism for mirror drift

This decision checks `specs/FWD-020-mirror-drift/acceptance.md` against the artifact. The acceptance file is dated
2026-09-28 and was amended three times on that date. The decision also
uses `spec.md`, `failure-modes.toml`, `architecture.md`,
`docs/adr/0016-one-manifest-for-every-mirror.md` and
`reviews/FWD-020/findings.toml`: four isolated rounds, F1–F22.

The artifact is the uncommitted working tree on top of HEAD 4891da7. The
promotion worktree was at 4891da7 without the artifact (`git log -1`), so
the changed and untracked files were copied into it. `diff -rq` against
the main checkout then showed no difference apart from the gitignored
`.fde/guard-audit.jsonl`. Every mutation below ran on a fresh copy of a
scratch repository, never on the real tree. Hashes of the evaluated files
(sha1, first 12 characters):

| file | sha1 |
|---|---|
| `tests/mirror.py` | `0cfbec7eb8fe` |
| `tests/mirror.toml` | `fe054a813ee8` |
| `tests/test_mirror.py` | `92e7d6e7f1f9` |
| `tests/test_install_sync.py` | `bdda03e610d5` |
| `.claude/agents/fde-adversarial.md` | `e1649b034acd` |

## Evidence run for this decision

- `python3 -m unittest discover -s tests`: 407 tests, OK (21.1 s).
- `python3 bin/fde/verify.py --all`: all gates passed, exit 0.
- `test_mirror.py` alone: 50 tests in 1.0–1.55 s over repeated runs. The
  checker core `mirror.check_with_counts` took 0.008 s on the promotion
  worktree. On the real main checkout, which has 33 agent worktrees under
  `.claude/worktrees/` and `.fde/guard-audit.jsonl` on disk, it took
  0.02 s with **0 violations**. That run was read-only. Counts:
  runtime 9, spec 5, skills 12, skills-init 1, agents 5, and 1 for each
  file pair.
- `git diff --stat` against 4891da7 shows 10 tracked files. The only
  file under a copy root is `.claude/agents/fde-adversarial.md`, with
  +3 lines. Nothing changed under `runtime/`, `spec/`, `skills/`,
  `agents/`, `templates/`, `bin/fde/`, `.fde/spec/`, `.claude/skills/`,
  `.githooks/`, `.github/workflows/` or `AGENTS.md`. `tests/support.py`
  did not change. In `fde.config.toml` only comments changed, and the
  `behavior_paths`, `eval_paths` and `generated_paths` values are the
  same.
- Mutation probes. Each ran on a fresh copy of a scratch git repository
  that holds the artifact:

  | probe | result |
  |---|---|
  | pre-fix copy (the three probe lines removed) | `differs` at line 90, inside `### 4. Usability & accessibility`; 7 failures |
  | the same fixture compared with the bytes of `4891da7:.claude/agents/fde-adversarial.md` | byte-equal |
  | `chmod 644 .githooks/pre-commit` (F21) | red: `test_installed_pre_commit_is_executable` |
  | multi-line setext heading appended to the source role, copy drops the rule line (F19a) | red: `stale-exception`, "unmodelled heading form … the span is not computed" |
  | lazy-continuation setext heading (F19c) | red, same result |
  | block-quoted heading `> # Appendix`, source only (F19d) | red, same result |
  | `#\tAppendix` appended to the source only (F17) | red: `differs` at line 117 |
  | heading-shaped line inside a code fence, source only | red: `differs` at line 117 |
  | `workflow` pair dropped from the manifest | 5 failures and 1 error: agreement, INVENTORY, marker, new-pair |
  | orphan `.claude/agents/fde-rogue.md` | red: `orphan` |
  | orphan `.claude/skills/fde-verify/notes.txt`, a non-md type | red: `orphan` |
  | `mirror.check` patched to `return []` | 166 failures |
  | AGENTS.md invariant statement "never" changed to "rarely" | red: `differs` at line 29 |
  | two weights edited without regenerating | red on `adversarial-role` and `agents-md` |
  | ignore entry `dimensions` (bare) plus the matching `.gitignore` line | red: both `TestIgnoreNeverSilencesATrackedFile` tests |
  | regex-shaped substitute `[A-Z]+-\d+` | red: `stale-exception` |
  | `exit 0` before `exec` in the pre-commit template and its copy | red: 2 failures |

  The scratch baseline's one red test, `test_survey`'s dogfood check,
  comes from the scratch repository: it has one commit, so the survey
  anchor `e42bb87` does not resolve there. The same test passes in the
  real tree.
- A grep for each retired test id, outside `reviews/`, `promotions/` and
  `specs/`, returns nothing, with two exceptions. D9's test is kept on
  purpose (Decision 7). `TestGeneratedSurfaces` is the class that still
  holds D9 and the gate pins.

## Criteria

| criterion | evidence | met |
|---|---|---|
| **One manifest, closed vocabulary (R1)** | `tests/mirror.toml` is parsed with `tomllib`. It is under `tests/` (eval_paths), not under `spec/`. There is no copy under `.fde/`, and `find` shows a single copy. `SETUP.md` does not mention it. Tests: `TestRealRepo.test_manifest_lives_once_under_eval_paths_and_is_never_installed`, and `TestFailClosed.test_unknown_relation`, `test_unknown_exception_kind`, `test_extra_keys_are_malformed` and `test_schema_shape_rules_are_malformed` | yes |
| **No protection lost (R6, FM-8)** | The mapping table below is the live `INVENTORY` dict in `tests/test_mirror.py`. `TestInventoryMapping` requires every D1–D13 and G1–G10 row to exist, every home pair to be declared and every home test to exist. Round 1 probed "find any D1–D13 protection with no live equivalent" and found none. | yes |
| **Gaps closed (G1–G6)** | G1 is discovered by the `agents` pair (count 5, which includes `fde-walkthrough-evaluator.md`). G2 is the `pre-commit` pair. G3 is the whole-file `workflow` identical-except pair. G4 is `adversarial-role` outside two declared regions. G5 is `agents-md` outside 5 placeholders and 1 substitution. For G6, orphans of any type are red (probe above, `.txt` under `.claude/skills/`). | yes |
| **Bidirectional, all file types (R2, FM-2, FM-3)** | `TestFailClosed.test_missing_copy_and_orphan_all_file_types` and `test_files_beside_a_file_pair_copy_are_orphans`. Orphan probes are red. | yes |
| **Exceptions literal, counted, fresh (R3, FM-4/5/7), span per F12/F17** | The manifest has no regex, glob or skip. A regex-shaped `from` is stale (probe). There are `test_stale_placeholder` and `test_wrong_count`. The span fixtures cover `# Appendix` (`test_replace_section_ends_at_a_higher_level_heading`) and `#\tAppendix`, ` # Appendix` and setext `=`/`-` (`test_replace_section_ends_at_every_commonmark_heading_spelling`). Verified regions: invariant statement, weights and probe lines are red (probes and `test_verified_regions_catch_plausible_wrong_values`). The attack order comes from `fde_lib.probe_plan` (`TestAttackOrderIsTheKernelsPlan`). The code-fence case is red when the copy is CommonMark-correct (probe). See Observation 1. | yes |
| **Fail closed (R4, FM-6, FM-14)** | `test_empty_source_root`, `test_missing_source_root`, `test_zero_checked_when_nested_pairs_govern_everything` and `test_checker_errors_propagate_never_pass`. When the checker is patched to return `[]`, 166 tests fail. | yes |
| **Mutation evidence, driven by the manifest (R5)** | `TestMutationSuite.test_every_manifest_pair_goes_red_on_every_mutation` iterates `real_manifest()`. `test_a_new_pair_needs_zero_test_code` runs a new fixture pair through `assert_clean`, the mutations, agreement, `drop_unnoticed`, INVENTORY and marker checks. Round 2 verified F1 on the real suite: a real new pair with only manifest lines gives 397 OK. | yes |
| **Dropped pair is caught (R8, FM-1, FM-12)** | `TestAgreement.test_dropping_any_one_pair_goes_red`, `test_manifest_agrees_with_generated_paths_and_setup` and `test_erosion_measured_is_exclusive`. The workflow-drop probe is red. `generated_paths` is unchanged (diff). `tests/support.py` is unchanged. | yes |
| **G7/G8 as ordinary content tests** | `test_install_sync.TestNativeLayerShape.test_claude_md_imports_agents_md_on_its_first_line` and `test_settings_run_the_guard_hook_and_branch_worktrees_from_head`, which parses with `json` and checks the exact command and `baseRef == "head"`. The relation set has 3 entries and no `contains`. | yes |
| **Ignore is explicit and narrow (R7, FM-11, F9, F14, F15)** | Real checkout with worktrees and the audit log: 0 violations. `TestIgnore` has two fixtures (runtime output and worktrees ignored; an untracked file under `.claude/skills/` is an orphan). `TestIgnoreNeverSilencesATrackedFile` covers the real `git ls-files` check, a tracked-entry fixture, one shared predicate, and fail-closed behavior outside the work-tree top and on an empty index. The bare `dimensions` probe is red. Git is called in the test, never in `mirror.py`. | yes |
| **Gate-invocation pins: ordering plus forbidden strings (F10)** | `test_pre_commit_runs_the_staged_gate_first` and `test_ci_gate_step_is_the_last_step_and_cannot_be_made_advisory` run on both template and copy. The `exit 0` probe is red. The residual YAML spellings are named in Decision 9 (below). | yes |
| **Only one place compares copies (R6)** | By inspection, no test outside `test_mirror.py`/`mirror.py` compares a source with its copy. The rewritten tests in `test_instructions`, `test_scrum`, `test_references` and `test_install_sync` assert content on each surface on its own. | yes |
| **I6 holds (R9, FM-10)** | `mirror.py` imports only stdlib modules plus this repository's `runtime/fde_lib.py`, and spawns no process. It is test-only: `KNOWN_GATES`, `runtime/` and `bin/fde/` are unchanged. Timing is 0.008–0.02 s for the core and ≤1.55 s for the module, under the 2 s limit (`test_whole_check_runs_under_two_seconds`). | yes |
| **References follow (R10, FM-13)** | The `fde.config.toml` `[gate]`/`[erosion]` comments, the maintainability line in `observability.toml`, `discovery/survey.md` and the NOTE in `test_walkthrough.py` all name `tests/test_mirror.py`/`tests/mirror.toml`. The retired-id grep is clean (above). | yes |
| **Regression: stale attack order (FM-15)** | `TestStaleAttackOrder.test_pre_fix_copy_is_reported_inside_the_usability_block`. Its fixture is byte-equal to the copy at 4891da7 (checked). This decision's own probe gives `differs` at line 90, inside the usability block. | yes |
| **The one regenerated region** | The diff is exactly `+- ambiguous next action with multiple plausible controls`, `+- irreversible action taken with no confirmation or undo` and `+- state change with no visible feedback`, right after `- loading and failure states visible to the user`. The checker reports 0 violations, so the section equals `render:attack_order` byte for byte. The source is unchanged. | yes |
| **Untouched (amended)** | The only copy-root change is the 3 lines above. No source root changed. `gate_eval_coverage`, `KNOWN_GATES`, `erosion.py`, `tests/support.py` and the three path lists are unchanged. The acceptance phrases this check as `git diff --stat <base>..<closing>`, and no closing commit exists yet, so it is measured against the working tree. See Condition 1. | yes, on the working tree |
| **ADR (R11)** | ADR-0016 is accepted and dated 2026-09-28. It records the manifest location (Decision 1), test-only with no gate (Decision 2), G7/G8 as content tests (Decision 6), G9 cross-checked (Decision 4) and G10 neither (Decision 5). It rejects case-by-case tests, a blanket glob with a skip list, and test-time generation. The build follows these decisions. | yes |
| **Gate** | 407 tests OK. `verify.py --all` passes all gates and none regressed. This is on the working tree, because the acceptance names the closing commit and none exists yet. See Condition 1. | yes, on the working tree |
| **Review** | Four isolated rounds (I2, `context_policy = "artifact_only"`, one transcript per round). Round 1's `probed` answers every named prompt: drop a pair, undeclared file under each root, wildcard smuggling, concretized-region edit, stale probe, closing diff exactly three lines, broken checker, worktree present, D1–D13 without an equivalent. Rounds 2–4 re-probed each earlier finding (`[[verification]]`). | yes; see the note on the review |

## Protection mapping: D1–D13 and G1–G6 (from `INVENTORY`, checked live)

| row | old guard | new home | strength |
|---|---|---|---|
| D1 | `runtime/*.py` → `bin/fde/`, glob plus `erosion.py`/`graph.py` pin | `runtime` pair, discovered; `test_empty_source_root`; `test_every_declared_pair_holds_on_this_repo` | ≥. All file types. The pin becomes empty-source and zero-checked fail-closed rules. |
| D2 | `spec/**/*.toml` → `.fde/spec/` | `spec` pair, discovered | > (all file types) |
| D3 | orphans in `bin/fde/*.py`, `.fde/spec/**/*.toml` | `runtime`/`spec` orphan walk; `test_missing_copy_and_orphan_all_file_types` | > (all types) |
| D4 | `skills/*/SKILL.md` identical, `fde-init` absent | `skills` pair plus `skills-init` `absent` pair; `test_absent_pair` | > (every file in each skill dir, orphan dirs) |
| D5 | four-role hand list | `agents` pair, discovered | > (no hand list, G1 included) |
| D6 | `weight W, R round` / `BLOCKS MERGE` substrings | `adversarial-role` identical-except: marker insert plus `## Attack order` = `render:attack_order`, byte-exact; `test_verified_regions_catch_plausible_wrong_values` | > (the whole file and the probe lists; caught the live FM-15 drift) |
| D7 | `**<id> <name>**` needles | `agents-md` `render:invariants_list` (id, name, statement) | > (the statement text too) |
| D8 | test command plus `- attr: w` needles | `agents-md` `render:weights_list`, `render:depths_list`, `config:stack.test_command` | > (order and depths) |
| D9 | workflow needles | `workflow` pair (whole-file identity) plus kept `test_workflow_runs_tests_and_a_ranged_gate_on_full_history` plus Decision 9 pins | > |
| D10 | `## Demand loop` equal after the `[A-Z]+-\d+` normalization | `agents-md` whole file; `DEM-042`→`FWD-002` as one counted literal; needles kept in `test_demand_loop_states_the_per_demand_rule` | > (no wildcard) |
| D11 | byte-identical RULE paragraph plus needles | `agents-md` whole file; needles on both surfaces in `test_rule_paragraph_says_what_r5_requires` | ≥ |
| D12 | byte-identical `## Scrum mode` section | `agents-md` whole file; section exists on both surfaces in `test_both_agents_surfaces_carry_a_scrum_section` | ≥ |
| D13 | `ui-patterns.toml` byte-identical | `spec` pair (redundant with D2, retired) | = |
| G1 | `fde-walkthrough-evaluator.md` unguarded | `agents` pair, discovered | new |
| G2 | `templates/pre-commit` → `.githooks/pre-commit` unguarded | `pre-commit` pair (`erosion_measured = true`), plus the ordering pin and the executable-bit test (F21) | new |
| G3 | workflow beyond needles | `workflow` pair, whole file | new |
| G4 | adversarial role outside its regions | `adversarial-role` pair, whole file outside the 2 declared regions | new |
| G5 | AGENTS.md outside placeholders | `agents-md` pair, whole file outside the 5 placeholders and 1 substitution | new |
| G6 | orphans under `.claude/skills/`, `.claude/agents/`, any type | `runtime`/`spec`/`skills`/`agents` orphan walks; `test_untracked_file_under_claude_skills_is_an_orphan`; mutation suite | new |

G7 and G8 are content tests (Decision 6). G9 is cross-checked (Decision 4).
G10 is neither derived nor checked (Decision 5).

## Declared residuals (accepted, not defects)

- **ADR-0016 Decision 9: an exception can legalize drift.** A literal,
  counted `[[pair.except]]` can excuse a behavior change in a copy, and
  such a commit can qualify for the RULE lane. Only the two files that
  run the gate are pinned: the ordering pins and the forbidden-string
  list, on both the template and the copy, plus the executable bit on
  the installed hook. The pins close only the literal spellings they
  list. Other YAML spellings of `if` or of a trigger (`if : false`,
  `? if`, `"i\x66"`, `? !!str if`, flow mappings, anchors) are still
  open (F20), and so is an earlier step that overwrites
  `bin/fde/verify.py`. Isolated review remains the backstop. As the ADR
  says, the pins do not establish that the gate runs unconditionally.
- **ADR-0016 Decision 10: git is used in the test layer.** The
  ignore-list validator needs `git ls-files`. It fails closed outside the
  work-tree top and on an empty index. A source export with no `.git`
  fails this test, and it already fails the rest of the suite. `verify.py
  --all` does not run the unit suite, so an ignore-list silencer goes red
  in CI's Tests step, not in the gate (round 4 records this).
- **SETUP rounding.** SETUP says "weight/10 rounded". `probe_plan` uses
  Python's `round()`, which rounds half to even, so weight 25 gives 2
  rounds where half-up gives 3. The renderer follows `probe_plan`, so
  this demand changes no behavior. No declared weight here ends in 5.
  The ADR records this as kernel feedback and does not resolve it.
- **A new pair's destination.** A new pair that no parent pair,
  `generated_paths` entry or orphan walk would notice being dropped must
  name its destination in a SETUP §6 `→` line. That is a documentation
  edit, not test code (ADR Consequences, F1).

## On the amendments (I4)

Every amendment is dated 2026-09-28, states its reason inline in
`acceptance.md`, and appears in the `amended:` header.

1. **After the architecture step, before any code.** This is legitimate.
   The architect found a live drift (the stale attack order) that the
   original "Untouched" criterion said did not exist. The amendment
   loosens "Untouched" by exactly one section, and only to regenerate
   that section from sources that did not change, which is SETUP's rule
   for a generated file. In the same step it adds a stricter
   regression criterion (FM-15). It also binds the criteria to ADR-0016's
   answers to the spec's Ask-first items. None of this was written after
   the builder had anything to fit it to.
2. **After round 2 (F9, F10, F12)** and 3. **after round 3 (F14, F15,
   F17).** These are legitimate. Each amendment turns an adversarial
   finding into a declared obligation that the build then had to meet.
   None relaxes a criterion that was already declared, and none was
   made to fit a result the builder already had. F9, F14 and F15 add the
   ignore validation and its fail-closed cases. F10 replaces presence
   needles with ordering pins plus forbidden strings. F12 and F17 state
   the section extent, which the original criterion ("`## Attack order`
   replaced") left undefined. Defining it gives the section fixed edges
   and does not widen what is excused. The fence sentence in F17 records
   a known simplification openly, and it is checked in Observation 1.

   Nothing is committed yet, so git cannot show the order of amendments
   and code. The `I4` gate passes ("14 demand(s) with dated criteria"),
   and the round records put each amendment at the right point: rounds
   2–4 each review "the spec as amended after" the round before.

## Note on the review

- **Rounds.** M sizing planned two rounds and four ran. Rounds 1, 2 and 3
  each had one blocking finding, so each earned the next round:
  - F1 (round 1): "zero test code" was false for a real pair.
  - F9 (round 2): an ignore entry could silence tracked, executed
    content.
  - F14 (round 3): the one-character variant of F9 got past the
    validator's different match model.

  F9 followed by F14 is the recurring-class signal. The fix in round 3
  is structural: one predicate, `mirror.hidden`, for the walk and the
  validator, pinned by `test_the_walk_and_the_validator_share_one_predicate`.
  It is not another variant patch. Round 4 confirmed the fix against the
  bare, slash, anchored and skill-name spellings. It closed with 0
  blocking findings and 4 low ones (F19–F22).
- **The review bound.** `skills/fde-review/SKILL.md` sets a hard bound of
  "three review cycles, then escalate to the user". Round 4 is the
  fourth cycle, and no artifact on disk records the owner's go-ahead.
  FWD-019's decision, by contrast, records one. This is a process gap,
  not a defect in the artifact. See Condition 2.
- **Round-4 lows fixed after the last review round, with no further
  isolated round.** A fifth round would itself need the owner's go-ahead
  under the same bound. This decision therefore re-ran each fix instead
  of taking the reconciliation on trust.
  - **F19** added new checker code, `_unmodelled_heading`. This is the
    one post-review change to the checker, so it got the most scrutiny.
    - It can only add a `stale-exception` and skip the span. It never
      removes a violation and never computes a span.
    - All three of F19's constructs are red on the real role file
      (probes) and in fixtures, both with and without the copy
      following.
    - Its scan runs from the replaced heading to EOF, so it can also
      false-red on something like a two-line list followed by `---`
      later in the file. That is the fail-closed direction. It is an
      observation, not a defect.
  - **F21** added `test_installed_pre_commit_is_executable`. The
    `chmod 644` probe is red.
  - **F20** and **F22** are record fixes. Decision 9 now states that
    the list closes only its literals, and the round-3 revision no
    longer contradicts itself. Both were checked by reading the ADR.

## Observations (not conditions)

1. **Code fences.** The acceptance says a heading-shaped line in a fence
   "makes the check report `differs`. It never goes silently green."
   That holds for a CommonMark-correct copy: the probe is red at line
   117. But a copy produced by the checker's own simplified split, which
   keeps the in-fence `#` line and the closing fence and drops the
   opening fence, is green. No source text goes missing from the copy
   in that case, so this is the "safe direction" `architecture.md`
   describes, and no fence follows `## Attack order` today. The suite has
   no fixture for the fence case. Round 4 and this decision executed it,
   but no test keeps it. A one-fixture follow-up would fix that, and the
   acceptance wording should read "for a CommonMark-correct copy".
2. `python3 -m unittest tests.test_mirror` (module-path form) fails to
   import. Other modules behave the same way (`tests.test_verify`,
   `tests.test_survey`). The runner the project declares is `discover -s
   tests`, which works. This is an existing convention, not a regression.
3. This decision's probe driver was written to the session scratchpad
   the reviewers also used, and it overwrote a file there named
   `probes.py`. The review record in `reviews/FWD-020/findings.toml` is
   the evidence of record and is unaffected.

## Rollout, rollback, and the first hour

The change is test-only, plus three regenerated lines in the in-repo
adversarial role. Nothing ships into clients: `runtime/`, `bin/fde/`,
`KNOWN_GATES` and `spec/` are untouched. The deploy here is the merge to
`main` and the push that runs `fde-gate`.

- **Rollback plan, written before the deploy.**
  - Primary path: `git revert <closing>` plus a push. The target is
    under 5 minutes, and CI runs the full suite.
  - There is no feature flag. The mechanism is a test module, so the
    revert is the flag.
  - There is no data to restore. The only non-test content, the three
    probe lines, is correct against the unchanged source and should
    survive a revert of the test machinery. To keep it, revert
    everything except `.claude/agents/fde-adversarial.md`, in the same
    5 minutes.
- **Staged rollout.** This is a single-repository change with no
  population to stage across. Each threshold below is a rollback
  trigger:
  - The `fde-gate` Tests step is red on `main` at the closing commit.
    Error rate vs baseline: any red where 4891da7 was green.
  - `test_mirror` takes 2 s or more in CI (p95 against the 2 s budget).
  - `test_mirror`/`mirror.py` raises an exception type not seen here,
    for example `ModuleNotFoundError` from the `runtime/` import on the
    CI runner.
  - Business guardrail: a false red on a legitimate `fde sync` or a
    kernel-version bump that only a manifest edit would clear, meaning a
    correct copy change is blocked.
- **First hour, verified and recorded** in the promotion commit's
  follow-up or the S-006 review:
  - The CI run on the push is green, with the Tests step and
    `verify.py --all` both passing.
  - The CI log has no new error types.
  - The `test_mirror` duration in the CI log is flat against the local
    1.0–1.5 s.
  - One manual pass of the critical flow: edit one probe line in
    `.claude/agents/fde-adversarial.md` locally, see
    `python3 -m unittest discover -s tests` go red on `adversarial-role`,
    then restore.

## Decision

**Promote with conditions.**

Every criterion in `acceptance.md` is met, based on the runs above
rather than on the review's word:

- The artifact's key behavior was executed against the real tree and
  against mutated copies. The one manifest is green on the real checkout
  with 33 agent worktrees present. It goes red on the three drift
  classes the demand exists for (a dropped pair, an orphan of any type,
  a wrong value inside a verified region). It caught the live FM-15
  drift at the base commit.
- The mutation suite is driven by the manifest, and a checker that
  always returns `[]` turns 166 tests red.
- Every D1–D13 protection has a live home of equal or greater strength,
  and G1–G6 are closed.
- The residuals of Decisions 9 and 10 and the rounding note are
  disclosed. They are not left out.

Conditions:

1. **Commit the closing state as evaluated.** The acceptance's Gate and
   Untouched criteria name "the demand's closing commit", and none exists
   yet. The closing commit must hold the evaluated tree (the hashes
   above). At that commit, `python3 -m unittest discover -s tests` and
   `python3 bin/fde/verify.py --all` must be green. `git diff --stat
   4891da7..<closing>` over the copy roots must show only
   `.claude/agents/fde-adversarial.md | 3 +`. Any byte change after this
   decision voids it.
2. **The owner acknowledges the fourth review round.** This is the
   fourth cycle past `fde-review`'s three-cycle bound, and so far it is
   unrecorded. Record the acknowledgment in the S-006 retro or in
   `[meta]` of the findings file. It does not change the artifact's
   verdict. It is the escalation the bound asks for, and it belongs to
   the owner.
