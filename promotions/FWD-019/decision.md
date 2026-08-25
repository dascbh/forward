---
demand: FWD-019
date: 2026-08-25
decision: promote
---

# Promotion decision — RULE is not a smaller XS

Confronting `specs/FWD-019-rule-lane/spec.md` and `acceptance.md` (dated
2026-08-25, amended in place 2026-08-25 after F13) against the
accumulated history d26cc3f (original implementation) through 64c0960
(round-5 F13 reconciliation) — 9 commits, five isolated adversarial
rounds (planned 2 for M sizing, escalated to 5, each escalation past
round 3 explicitly authorized by the project owner per the review
doctrine's own hard bound).

| criterion | evidence | met |
|---|---|---|
| `runtime/triage.py` pure eligibility core + git-aware wrapper + `--report` + `--check`, mirrored to `bin/fde/triage.py` | `runtime/triage.py:94-174` (`check_eligibility`, no git/fs access), `:333-367` (`eligibility_for_commit`), `:415-480` (`--check`/`--report` CLI); mirrored via the existing install-sync sweep (`tests/test_install_sync.py`) | yes |
| R1 eligibility: 4 mechanical criteria, project-level axes resolved once, merge/binary/git-failure categorically ineligible (never "0 lines") | `runtime/triage.py:94-174` — data_class/reversibility checked first (`:119-134`), `is_merge`/`is_binary` block before loc (`:136-150`), loc then eval_paths-shrink (`:152-169`); `tests/test_triage.py` `TestPureCore`/`TestMechanicalUncertaintyDefaultsToNever` cover all branches including the boundary case | yes |
| `gate_rule_lane` + `rule-lane` in `KNOWN_GATES`, CI-tier only, per-commit isolation, silent/explicit reporting, blocking on a false claim | `runtime/verify.py:40-43` (`"rule-lane"` appended last, pure addition), `:797-878` (`gate_rule_lane`), dispatch at `:1071` inside the CI-only block; `tests/test_verify.py::TestRuleLaneGateMergeAndGitFailure` and sibling classes; live-confirmed this session: `--gate rule-lane` (default and `--all`) → explicit pass "no commit in range claims RULE — nothing to re-verify" | yes |
| `gate_eval_coverage`'s body unmodified — zero lines added/removed/reordered; gate is never RULE-aware | `runtime/verify.py:281-380` read in full — no reference to `triage`/RULE anywhere in the function body; `tests/test_verify.py::TestGateEvalCoverageBodyUnmodifiedR6`; round 5's own byte-level `diff`/`cmp` against both bd4e9ff and the demand's true pre-FWD-019 origin (389cf88) confirmed identical | yes — see amendment note below for the one narrowed clause |
| `[triage].rule_lane_max_loc` in `fde.config.toml`/template, plain key, this repo's own value `10` | `fde.config.toml:24` (`rule_lane_max_loc = 10`), `templates/fde.config.template.toml:20` (`{{RULE_LANE_MAX_LOC}}` placeholder), both alongside the section's existing keys, not a new opt-in section | yes |
| `skills/fde-triage/SKILL.md` RULE paragraph before the table, categorical distinction, 4 criteria, usage loop, primacy-ordering justification | `skills/fde-triage/SKILL.md:31-77` — "RULE — a lane below the table, not a row in it", states "categorically distinct... not a smaller XS", lists all 4 criteria plus the 3 categorical exclusions, `--check`/self-declare loop documented | yes |
| `AGENTS.md`/`templates/AGENTS.md.template` byte-identical RULE paragraph; pre-existing XS/S/M/L text unchanged | `AGENTS.md:88-108` (RULE paragraph, before `score ≤ 1 → **XS**`, `:110`), `templates/AGENTS.md.template` mirrored; `tests/test_instructions.py::test_rule_paragraph_is_byte_identical_between_agents_and_template` green in this session's 361-test run | yes |
| `tests/support.py` fixture extended (`reversibility`, `rule_lane_max_loc`); `tests/test_triage.py` covers all 8 R7 cases | `tests/support.py:47-61`; `tests/test_triage.py` 38 test methods across `TestPureCore`/`TestGitWrapper`/`TestMechanicalUncertaintyDefaultsToNever`/`TestFallbackDefault`/`TestReport`/`TestGate` — all 8 minimum cases present by name (trivial-eligible, loc-ineligible, ceiling-ineligible-at-1-line, eval_paths shrink/delete, falsely-tagged blocking, silent-vs-explicit, default-10-fallback, per-commit isolation) | yes |
| Full suite + `verify.py --all` green, 15 pre-existing gates unregressed, `rule-lane` a 16th | This session, fresh at 64c0960: `python3 -m unittest discover -s tests` → 361 tests, OK; `python3 bin/fde/verify.py --all` → all gates green (`KNOWN_GATES` has 16 entries, `rule-lane` last); `--gate rule-lane` directly → explicit pass | yes |
| `docs/adr/0015-*.md` cites Kahneman/*Noise*, kernel's own `verified_by` primacy, rejects diluting-XS/round-reduction/semantic-detector | `docs/adr/0015-rule-is-not-a-smaller-xs.md:20-52` (both citations, primacy ordering), "Options considered" (`:61-127`) — all three rejections present with named reasoning | yes |
| Two (planned)/five (actual) isolated adversarial rounds test the seven named questions; `finding-discipline` (I8) holds | `reviews/FWD-019/findings.toml` (round 5, current) plus rounds 1-4 preserved in git history at b481563/426148c/2a3055f/6a66a39 — all seven acceptance-named questions answered across the five rounds (mapped in the note below); I8 checked explicitly each round, zero undisciplined findings | yes |

## Note on the review

**Why five rounds, not two.** M sizing budgeted 2 rounds; 5 ran, each
escalation past round 3 explicit per the review doctrine's own hard
bound (`skills/fde-review/SKILL.md` caps at three before requiring the
project owner's go-ahead) rather than an agent deciding unilaterally to
keep going. The escalation was earned, not padding: round 1 found F1
(binary-file numstat rows silently dropped, evading the eval_paths-shrink
check), F2 (merge commits invisible to `commit_files()` — a 500-line
merge tagged `FORWARD: RULE` would have read as "0 lines, eligible"),
F3 (a structural clone of the range-resolution fallback chain, kept in
sync only by memory), F4 (`_git()` swallowing every git failure into
empty output — the unsafe default, directly contradicting ADR-0015's own
"default to never"), and F5 (a per-commit subprocess spawn, non-blocking).
Round 2 found F6: the F4 fix was narrowly scoped to one wrapper, and
`gate_rule_lane`'s own path through `_commits_in_range` still routed
through the old, unhardened `Gate._git` — reproduced end-to-end
(`chmod 000` on `.git/objects` let an over-threshold RULE-tagged commit
pass silently). Round 3 found F9: the identical defect class a *third*
time, one call further upstream (`_resolve_range` → `_rev_ok`), reproduced
against the real CI invocation. Three recurrences of one class is what
triggered the structural response named in the task: inverting
`Gate._git`'s default contract to fail-safe, with every existing call
site individually re-audited (`GitOpFailure`'s own docstring at
`runtime/verify.py:50-86` names each: `changed()` and `gate_adversarial`
needed the strict default; only `gate_observability`'s telemetry fallback
correctly keeps the lenient opt-in, because a failure and a legitimate
empty result there already produce the identical, safe verdict). Round 4
found F10 (the round-3 fix had put a 16-line `try/except` inside
`gate_eval_coverage`'s own body, violating R6's letter even though the
safety intent was sound) and F12 (a narrower-than-needed `OSError`
catch); fixed by moving the catch to a generic dispatch-level `run_gate`
wrapper in `main()` instead, restoring the function's body to byte-
identical rather than patching around the violation. Round 5 came back
clean except F13 (non-blocking): R6's own second clause ("nothing about
`gate_eval-coverage`'s behavior... changes as a side effect of this
demand") had gone textually false the moment F9 landed — not because
the function's body moved, but because it inherited stricter, safer
behavior for free through the now-strict shared `_git`/`_resolve_range`
helper under a git-failure condition specifically. Reconciled the same
day by narrowing R6's second clause and the matching Boundaries/Never
text to exempt that one condition, with the ADR amendment naming why the
narrowing is correct rather than a violation.

**(a) Is the final mechanism genuinely sound, or a pile of patches that
happened to stop failing the specific reproductions found so far?**
Genuinely sound. The tell is in what round 3 forced versus what rounds 1
and 2 tried first: F4 and F6 were each a *local* fix — harden the one
call site the round's own repro hit. Both were reopened by the next
round finding the identical defect one layer further out, which is
exactly the signal that local patching does not converge for this class
of bug. Round 3's fix is categorically different in kind: it inverts
`Gate._git`'s own *default* contract (`GitOpFailure` raised on any
genuine failure, never collapsed into "found nothing"), and the
commit's own record (and `GitOpFailure`'s docstring, `runtime/
verify.py:50-86`) shows every pre-existing caller was individually
re-examined against that new default — not blanket-wrapped to keep the
file compiling. Two callers needed the strict default (`changed()`,
`gate_adversarial`); exactly one earned an explicit, named, justified
exception (`_git_lenient`, used only by `gate_observability`, whose own
comment states why leniency there is safe — a failure and a legitimate
empty result already produce the same blocking verdict for I5). That is
a decision rule applied consistently, not a location-specific patch.
Round 5's fresh, unprompted sweep (task item 4, `findings.toml`
`[meta].probed`) grepped every `subprocess.run` call site in both files
and every gate method that can reach `GitOpFailure`, and found the
dispatch-level `run_gate` wrapper (F10's fix) correctly covers both
current call sites with no third gap — the sweep was not required to
find anything and came back clean apart from F13, which is a spec-text
staleness finding, not a code defect. F10 itself is worth naming as
evidence of soundness rather than fragility: it was a real regression (a
non-negotiable requirement's literal text became false), but the fix
that closed it did not touch the safety property F9 established — it
relocated *where* the exception is caught, preserving *that* it is
caught. The F13 amendment is the same discipline applied to prose: it
does not weaken the guarantee (clause (a), the mechanically-checkable
"zero lines in the body," is untouched and re-confirmed independently
this round against both round 2's checkpoint and the demand's true
origin commit) — it corrects an overbroad sentence to match a real,
demonstrated, and *safer* behavior change that the sound part of the
mechanism produced as a side effect. A pile of unrelated patches does
not produce that shape: one coherent default (fail-safe git handling),
one audited exception list, and a documentation correction that admits
exactly what changed and why, in a dated amendment rather than silently.

**(b) Does the demand's own core promise hold — does a genuinely trivial
change actually skip the ceremony now?** Yes, and the evidence is
structural, not just narrated. `gate_rule_lane` (`runtime/verify.py:
797-878`) is a pure git-diff and config check: it reads a commit's
numstat and two project-level TOML values, and its only interaction with
the rest of the demand loop is a pass/fail gate result — it does not
invoke, require, or check for a `specs/<id>/` directory, an ADR, or a
`reviews/<id>/` artifact anywhere in its code path (confirmed by reading
the full method and its two helpers, `triage.eligibility_for_commit` and
`_commits_in_range`). This matches the spec's own declared working
assumption (`spec.md` "Ask first," first bullet): a RULE-tagged commit
gets no demand-id and no spec/ADR/review artifacts at all — the
commit-message convention is the only artifact, and `runtime/graph.py`
and the traceability gate stay untouched by design (confirmed: `git
diff --stat` between the demand's origin and HEAD touches no
`runtime/graph.py` line). This project's own `fde.config.toml`
(`data_class = "public"`, `reversibility = "reversible"`,
`rule_lane_max_loc = 10`) clears both project-level checks today, so the
lane is live here, not merely designed. `tests/test_triage.py::
TestGate::test_gate_passes_a_genuinely_eligible_declared_commit` and
`TestPureCore::test_a_genuinely_trivial_diff_is_eligible` demonstrate by
execution, not narration, that a small, text-only diff under the
declared threshold clears eligibility and the live gate. What a RULE
commit does still owe, correctly and by design: I1's `gate_eval_coverage`
stays fully in force (confirmed unmodified above) — RULE recognizes I1's
sufficiency, it does not create a second, weaker path around it. The
velocity this demand exists to restore is specifically the isolated
adversarial round and the spec/ADR ceremony XS still spent even at score
0; that is what a qualifying commit now skips, verified by inspection of
what `gate_rule_lane` does and does not touch, not merely asserted by
the spec.

**The honestly named residual (FM-1).** Neither the spec, the ADR, nor
any review round claims the semantic-gaming gap is closed. A diff that
clears all four mechanical criteria while hiding a disproportionate
change (a flipped comparison operator, a widened default) is not
detectable by a loc/path check at any threshold, including one far
below 10 — the ADR states this plainly rather than papering over it, and
five rounds of adversarial pressure did not find a way to close it,
because the design itself states it cannot be closed mechanically
without reintroducing the judgment layer RULE exists to remove. What the
mechanism does provide against that gap — I1 remaining fully intact, a
low default threshold, and live re-verification catching anything that
turns out bigger or different in kind than self-declared — is real and
verified; what it does not provide is honestly disclosed as a permanent
limit, not a defect this promotion is overlooking.

## Decision

**Promote.** Every criterion in `acceptance.md` traces to evidence on
disk and to a fresh run of the actual gate and suite at HEAD (64c0960):
361 tests green, `verify.py --all` green across 16 gates including
`rule-lane`, and `--gate rule-lane` both silent under default/`--all`
and explicitly passing when invoked directly, matching the declared
contract exactly. `gate_eval_coverage`'s body is confirmed byte-identical
to its pre-FWD-019 state by direct inspection, not by trusting the
commit history — the one narrowing this demand made to its own
non-negotiable requirement (R6's second clause, via the F13 amendment)
is honestly recorded, correctly scoped to a real and safer behavior
change the demand did not cause and could not have avoided without
either reverting a genuine safety fix or forking a duplicate, less-safe
helper, and does not touch the clause that actually does the guarding
work (the function's own body, mechanically verified unmodified). Five
rounds of isolated adversarial review — three beyond the planned budget,
each escalation explicitly authorized — converge on zero open blocking
findings, having forced the mechanism through exactly the kind of
recurring-defect-class response (fail-safe-by-default, individually
audited exceptions) this kernel's own doctrine expects rather than
settling for three successive local patches. The demand's own reason for
existing — a genuinely trivial, mechanically bounded change skipping
spec/ADR/adversarial ceremony without skipping I1 — is verified
structurally: `gate_rule_lane` touches nothing but a commit's own diff
and two already-declared config values, and this project's own
configuration clears the lane today. The one open item (FM-1's semantic-
gaming gap) is a disclosed, permanent design limit, not a withheld
defect, and is the isolated adversarial round's own named probe for any
future RULE-tagged commit to face.
