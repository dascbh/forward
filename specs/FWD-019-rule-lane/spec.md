# FWD-019 — A rule lane below XS

Triage: surfaces 3 (runtime/ + skills/ + templates/docs, capped) · public ·
reversible · ~300+ LOC → score 5 → **M** (spec, impl, adversarial 2 rounds,
promotion, ADR-0015).

## Problem

`fde-triage`'s table has no floor below XS. The lowest possible score
(0) still lands on XS, and XS already spends a full isolated adversarial
round — a fresh subagent, its own git worktree, an attack order derived
from vector A, a written `findings.toml`, the isolation gate checked.
A one-line label fix pays that entire bill. The skill's own description
promises "reduce ceremony without relaxing criteria," and the table
cannot keep that promise for the genuinely trivial case, because XS **is**
the floor and XS is already heavy. In the field this cost a user real
velocity — they moved a change to another tool rather than pay it, which
is exactly the failure mode Kahneman/Sibony/Sunstein's *Noise* names: if
the cheapest path *inside* the process is still expensive, the truly
cheapest path becomes leaving the process.

*Noise*'s rule-vs-standard distinction is the fix, not "a lighter
XS": a high-volume, low-stakes decision should become a **rule** — a
deterministic checker decides, no judgment applied at all — while
deliberate judgment (multiple perspectives, adversarial pressure) stays
reserved for what is genuinely risky or novel. That is a categorical
difference in KIND, not degree. XS already sits at the judgment end of
that line, in reduced form; the missing tier sits at the rule end, with
none.

**The kernel already declares its own justification.**
`spec/dimensions/quality-attributes.toml` orders the three verification
pillars by primacy — `verified_by = ["empirical", "adversarial",
"heuristic"]` — execution first, adversarial proof second, heuristic
judgment last, reserved for what the first two cannot reach. When
empirical verification (I1's `eval-coverage` gate) already covers
everything there is to verify for a given change, stacking adversarial
and heuristic review on top of it is not additional rigor. It is
ceremony that primacy ordering already told us was unnecessary.

**RULE, not "XS with score 0."** The current XS/S/M/L score is an
agent's **a-priori estimate** of `surfaces`/`loc`/`sensitive`/
`irreversible`, made before any code exists, and it fixes the ceremony
level for the demand's entire life with no re-check against what
actually got committed. RULE inverts every one of those properties: it
is never estimated, only computed, and only after the fact, directly
from the commit's own diff; it does not use the score formula's four
inputs at all; and it is re-verified live, against what was **actually**
committed, every time. This is the "surprise/conflict" escalation trigger
*Noise* asks a rule-governed system to keep — except deterministic and
always-on, not a fallible human noticing something felt off. A commit
that turns out bigger, riskier, or different in kind than its own
self-declaration claimed is caught mechanically, not trusted.

### How eligibility resolves the sensitive/irreversible axes

The plan behind this demand asks eligibility to reuse "the same signals
`[triage].data_class`/`reversibility` already declare, applied
mechanically, never estimated." No per-file sensitivity signal exists
anywhere in this codebase — `fde_lib.py` and `erosion.py` were read in
full for this spec, and the only signals that exist are exactly those
two **project-level** TOML values. FWD-003 already establishes what they
mean: `data_class` is a ceiling ("in a public/internal project, sensitive
is always false"); `reversibility` sets a posture with an exception
clause ("a reversible project's demand is false unless the demand itself
creates irreversibility") that, in general, requires judging what a
specific diff *does* — content-level judgment RULE cannot perform by
definition.

The only mechanically consistent resolution, and the one this spec
adopts: **RULE checks these two axes once, at the project level, never
per file.** `data_class` must be exactly `public` or `internal` — the two
values where FWD-003's own ceiling already makes `sensitive` unconditionally
false for every demand in the project, with no file-by-file exception
possible or needed. `reversibility` must be exactly `reversible`. Any
other declared value on either axis makes RULE categorically unavailable
for **every** commit in that project — not "unavailable for commits that
touch risky-looking files," unavailable outright, full stop. This is
FWD-003's own "unsure → true" tiebreak taken to its strictest reading:
where mechanical certainty is unavailable, RULE default to never, not to
a heuristic guess about which files "look" sensitive.

One consequence worth naming plainly: because this project
(`data_class = "public"`, `reversibility = "reversible"`) clears both
project-level checks, RULE eligibility here reduces entirely to the
per-commit checks — loc threshold and eval-paths-not-shrunk. A project
declaring `personal`/`financial`/`health` or `difficult`/`irreversible`
never gets a RULE lane at all under this design, regardless of how small
any individual commit is. That is intentional, not an oversight to fix
later.

## Boundaries

**Always**
- Design the eligibility check as a pure function over (the two declared
  project-level config values, one commit's own file list and numstat,
  the declared `eval_paths`) — no git or filesystem access inside the
  pure core — reusable, unmodified, by both `runtime/triage.py`'s own CLI
  and `runtime/verify.py`'s new gate. Mirror `erosion.py`'s existing
  split between pure cores (unit-tested without git) and git/fs wrappers
  (MNT-11 — do not clone a second copy of numstat/rename/quoted-path
  parsing; reuse or import `erosion`'s existing `numstat_path`/
  `_unquote`/`parse_numstat` rather than re-implementing them).
- Resolve `sensitive`/`irreversible` at the project level only, exactly
  as reasoned above — never by inferring content-level sensitivity from
  a touched file's path or contents.
- Define a commit's size as `added + deleted` from its own numstat — the
  same definition `erosion._largest_change` already uses for "the size
  of a change in lines" (MNT-1: one definition of "how big is this
  diff," not two).
- Re-verify eligibility against the commit's **actual** diff (via
  `git show`/`git diff-tree` scoped to that one commit), never against
  anything the commit message claims about itself.
- Run `gate_rule_lane` at the CI/full-gate tier only (outside
  `--staged`), in the same `if not args.staged:` block as
  `gate_erosion`/`gate_divergence`/`gate_scrum` — a commit's message and
  full diff exist only after `git commit` completes; pre-commit inspects
  staged changes, not commits, and stays fast per I1's own doctrine.
- Report a blocked commit's reason labeled by criterion (which of the
  four failed), mirroring `erosion.check_budget`'s labeled-breach style
  — never a bare pass/fail.
- Fall back to the documented default (`rule_lane_max_loc = 10`) when the
  key is absent from an out-of-date `fde.config.toml`, instead of
  crashing or silently disabling the gate.
- Add the `rule-lane` gate id to `KNOWN_GATES` as a pure addition — no
  existing id renamed, removed, or reordered.
- Extend `tests/support.py`'s `BASE_CONFIG`/`make_project` (a
  `reversibility` override parameter; a `rule_lane_max_loc` key) rather
  than hand-writing a parallel config-building helper inside the new test
  file (MNT-11).
- Document, in `skills/fde-triage/SKILL.md`, the practical usage loop for
  an agent: when a change looks trivial, run `triage.py --check` against
  the staged diff before committing (advisory, not gated), self-declare
  `FORWARD: RULE — <reason>` in the commit message if it looks eligible,
  and understand that a wrong guess costs nothing but redoing the demand
  through the normal table — there is no incentive to game it.

**Ask first**
- Whether a RULE-tagged commit is assigned a demand-id at all. This
  spec's working assumption, needed to keep `runtime/graph.py` and the
  traceability gate untouched, is that it is **not**: the commit-message
  convention is the only artifact — no `specs/<id>/` directory, no
  demand-id threading through the provenance graph. If a real need
  surfaces later for `fde-graph` to see RULE commits without a spec,
  review, or promotion artifact behind them, that is a separate design
  call to make and record, not settled here by assumption.
- The concrete default window/range `runtime/triage.py --report` scans
  with no arguments. This spec requires the report exist and be
  non-silent (auditable by sampling, mirroring `erosion.py --report`'s
  shape: how many commits in the window self-declared RULE, how many
  passed re-verification, how many would have been blocked) but leaves
  the exact default commit count to implementation, the same way
  `erosion.py`'s `DEFAULT_WINDOW = 50` was implementation's call.
- Whether an informational (non-blocking) config-gate nudge is worth
  adding when `rule_lane_max_loc` is raised well past its default —
  mirroring `CFG-VER`'s informational drift notice. This spec does not
  require one (see "Never," below, and the reasoning under R4) but does
  not forbid it either, if implementation judges it earns its keep
  without becoming an unprincipled magic number.

**Never**
- A per-file or per-line semantic detector — keyword matching on
  "security"/"auth"/"guard," AST inspection, or any other content-aware
  heuristic — as part of RULE eligibility. The design point is a
  bright-line rule with zero judgment; a semantic detector is judgment
  wearing a regex, and is exactly the kind of thing a small adversarial
  diff is best at slipping past. The residual gameability this leaves
  open (FM-1, below) is accepted, named, and handed to the isolated
  adversarial round to probe — not "solved" by a second, weaker judgment
  layer smuggled into the lane whose whole premise is having none.
- A hardcoded kernel-level ceiling on `rule_lane_max_loc`'s permitted
  value. Every other declared threshold in this kernel — `[erosion]`'s
  budgets, `[walkthrough]`'s `divergence_threshold` — is type-checked by
  `fde_lib.validate()` but never magnitude-checked; the project's own
  declared, versioned, diffable value already carries the audit trail.
  A magnitude ceiling on this one key alone, and no other, would be an
  unexplained inconsistency, not added rigor.
- Any change to `gate_eval_coverage`'s code path, call signature, or
  reported message shape. It must not read, branch on, or otherwise know
  that the RULE commit-message convention exists.
- Consuming the existing `surfaces`/`loc`/`sensitive`/`irreversible`
  agent-estimated inputs, or the formula's `score` value, for any part of
  RULE eligibility. RULE's criteria come from the actually-committed diff
  plus two already-declared project-level values — never from an
  a-priori estimate. That is what makes it categorically distinct from
  "XS scoring 0," not a smaller version of the same thing.
- Documentation that adds RULE as a row, a `score ≤ -1`, or any entry
  inside the existing `| score | size | active roles | adversarial
  rounds | ADR |` table. It is a paragraph that precedes the table, never
  a line inside it.
- Weakening XS's existing round count, isolation protocol, or any part
  of its ceremony as a side effect of shipping RULE. The rejected
  alternative — diluting XS itself instead of shrinking what enters the
  judged lane — is named and closed; it is not reopened by this demand
  or its review.

## Failure modes

- FM-1 (gameable eligibility, only partially mitigated): a diff can
  clear all four mechanical criteria — genuinely `< rule_lane_max_loc`
  lines, touching no project-level-sensitive/irreversible class,
  shrinking no `eval_paths` file — and still carry a disproportionate
  semantic change: a flipped comparison operator in a security-relevant
  check, a widened default, a changed permission. No mechanical check
  this spec proposes closes that gap, and no threshold value closes it
  either — a one-line operator flip is 2 lines of churn, so even
  `rule_lane_max_loc = 1` would not stop the paradigm case. What DOES
  apply: I1 still requires a corresponding eval entry for anything under
  `behavior_paths` regardless of the RULE tag, so an unevaled
  security-relevant change already fails the unchanged I1 gate on its
  own; the low default threshold caps how much any single such diff can
  hide; and the live re-verification gate still catches a commit that
  turns out to exceed any of the four criteria. What is genuinely open:
  a small, path-innocuous, eval-covered change that is still
  substantively wrong. This is not resolved here — it is the isolated
  adversarial round's specific probe, named directly in this demand's
  acceptance criteria, and the honest position (matching the plan's own
  framing) is that RULE's accepted risk is a false positive slipping
  through, mitigated but never fully closed by the live gate; a false
  negative — something trivial wrongly landing in the heavy lane — stays
  safe, only costly.
- FM-2 (falsely tagged commit): a commit's message claims
  `FORWARD: RULE` but its actual diff does not qualify. This is the
  entire reason `gate_rule_lane` exists — R3 requires it be caught,
  blocking, every time.
- FM-3 (gate weakens I1 instead of recognizing its sufficiency): a
  future edit teaches `gate_eval_coverage` to special-case a RULE-tagged
  commit, turning "empirical verification already covers everything"
  into "empirical verification is optional here." R3/R6 require
  `gate_eval_coverage`'s body to gain zero lines referencing the RULE
  convention, verifiable by inspection of the diff.
- FM-4 (misread as "skip review"): an agent, a human skimming the docs,
  or a future maintainer reads RULE as license to skip judgment in
  general, rather than the narrower claim — this specific, mechanically
  bounded class needs no *additional* judgment because execution already
  proves what there is to prove. R5 requires the documentation to state
  the narrower claim explicitly, every place RULE is introduced.
- FM-5 (threshold creep): `rule_lane_max_loc` gets raised carelessly —
  "bumped to make more things qualify" — silently expanding what bypasses
  judgment well past "genuinely trivial." The only mitigation this spec
  proposes is transparency: the change is a visible, versioned, one-line
  diff to `fde.config.toml`, the same audit trail every other declared
  threshold in this kernel already relies on instead of a hardcoded
  ceiling (see Boundaries/Never and the reasoning under R4).
- FM-6 (documentation drift): `skills/fde-triage/SKILL.md`, `AGENTS.md`,
  and `templates/AGENTS.md.template` describe RULE as "a lighter XS"
  instead of a categorically distinct, zero-judgment mechanical lane, or
  the three files diverge from each other — the same I8-template-drift
  class FWD-003's own FM-1 already named once for the triage inputs. R5
  requires byte-identical text across the two AGENTS.md files and a
  parity test.
- FM-7 (fixture drift produces weak tests): `tests/support.py`'s shared
  fixture does not currently expose `reversibility` or
  `rule_lane_max_loc` as parameters. Left unextended, `test_triage.py`
  either duplicates a parallel config-builder (an MNT-11 violation) or
  silently exercises only the fixture's hardcoded defaults, missing the
  project-level-ceiling boundary cases R7 requires.
- FM-8 (per-commit vs. per-range confusion): a push bundles a RULE-tagged
  commit together with other, larger commits. If `gate_rule_lane`
  evaluates the aggregate range diff instead of each claimed commit's
  own diff in isolation, a small innocuous RULE commit can be wrongly
  blocked by a sibling commit's unrelated size (false block), or a
  sibling's changes can be wrongly absorbed into a RULE commit's
  apparent size in the other direction. R3 requires per-commit isolation
  specifically to close this.

## Requirements (EARS)

- R1: WHEN eligibility is computed for one commit's diff, it MUST return
  ineligible (labeled with which criterion failed) UNLESS ALL of: (a)
  `[triage].data_class` is exactly `public` or `internal`; (b)
  `[triage].reversibility` is exactly `reversible`; (c) `added + deleted`
  over that commit's own numstat is strictly less than the declared
  `[triage].rule_lane_max_loc` (default `10` when the key is absent);
  (d) no file matching `[gate].eval_paths` was deleted, or has
  `deleted > added` for that file alone, within that commit's numstat.
  The function MUST take the two project-level values, the commit's file
  list/numstat, and `eval_paths` as inputs — never re-derive them from
  git itself — so it stays the pure, unit-testable core described under
  Boundaries/Always.
- R2: WHEN this demand ships, `runtime/triage.py` MUST exist (mirrored,
  via the existing generic `runtime/` → `bin/fde/` install-sync sweep
  `tests/test_install_sync.py` already asserts — no separate manual copy
  step), exposing R1's eligibility function as an importable pure core
  plus a git-aware wrapper that resolves one commit's numstat/file list
  and calls it, mirroring `erosion.py`'s pure-core/git-wrapper split. It
  MUST provide a `--report` CLI (mirroring `erosion.py`'s
  `--report`/`--gate`/`--window`/`--format` shape) printing, over a
  window of recent commits: how many self-declared RULE via the
  commit-message convention, how many passed re-verification, how many
  would have been blocked — never silent, auditable by sampling like
  `erosion.py --report` already is. It MUST also provide a `--check`
  mode (mirroring `design.py`'s existing `--check` flag) that previews
  eligibility against the currently staged diff (`git diff --cached`),
  advisory only — it does not gate anything itself — for an agent to run
  before self-declaring RULE in a commit message.
- R3: WHEN `runtime/verify.py` is extended, it MUST gain a `gate_rule_lane`
  method and a `rule-lane` entry in `KNOWN_GATES`, called only inside the
  existing `if not args.staged:` block (alongside
  `gate_erosion`/`gate_divergence`/`gate_scrum`), following the same
  `explicit: bool = False` parameter pattern those gates already use.
  It MUST determine the commit range under examination using the same
  `--since` → `HEAD~1..HEAD` → empty-tree fallback chain
  `Gate.changed()`/`_rev_ok()` already implement, and MUST evaluate each
  individual commit in that range separately — never the range's
  aggregated diff (FM-8) — checking each commit's own first
  message line against the `^FORWARD:\s*RULE\b` convention. WHEN no
  commit in the examined range matches, it MUST add nothing to the
  report under `--all`/default and, only when explicitly invoked
  (`--gate rule-lane`), report an explicit "no commit in range claims
  RULE" pass. WHEN a matching commit fails R1's eligibility, re-verified
  against that commit's actual diff, the gate MUST fail (blocking),
  naming the commit's short SHA, the specific criterion that failed, and
  the fallback instruction (run the demand through the normal XS/S/M/L
  table). It MUST NOT alter `gate_eval_coverage`'s logic, call signature,
  or output in any way (FM-3, R6).
- R4: WHEN `fde.config.toml` and `templates/fde.config.template.toml` are
  updated, `[triage]` MUST gain a plain (uncommented) `rule_lane_max_loc`
  key alongside its existing `data_class`/`reversibility`/`user_facing`/
  `has_agent_loop` keys — never inside a new opt-in section like
  `[erosion]`/`[walkthrough]`, because this is a correction to default
  behavior every project already owes, not an additional discipline a
  project opts into. The template uses a `{{RULE_LANE_MAX_LOC}}`
  placeholder matching that file's existing convention. This repo's own
  `fde.config.toml` (ADR-0007 self-hosting) MUST declare a concrete value
  directly, not rely on the runtime default alone — the same "Exhibit A"
  posture `[erosion]`'s own comment already takes in this file. Decided
  value: **10**. Reasoning, for the record: it comfortably covers the
  motivating case (a label changed in several places, a comment fix, a
  config-value or version bump — all well under 10 lines of churn)
  without approaching S tier's `loc < 50` boundary (5× headroom); and, as
  FM-1 establishes, no threshold value — including one far lower than 10
  — closes the semantic-risk gap a 1-2 line change can already carry, so
  there is no safety argument for picking a smaller number, only a usability
  one for not picking a larger one.
- R5: WHEN `skills/fde-triage/SKILL.md`, `AGENTS.md`, and
  `templates/AGENTS.md.template` are updated, RULE MUST be introduced in
  its own paragraph positioned immediately before the existing
  `## Score and size` table (SKILL.md) and immediately before the
  existing `score ≤ 1 → **XS**...` sentence (AGENTS.md / template step 1)
  — never as a table row, never as a new column, never altering a single
  byte of the table or sentence it precedes (R6). The paragraph MUST
  state, at minimum: RULE is categorically distinct from XS, not a
  smaller version of it (XS still runs full judgment in reduced form;
  RULE runs none); the four eligibility criteria in plain language;
  that eligibility is checked mechanically, post-hoc, against the actual
  committed diff, never claimed a priori; that I1's `eval-coverage` gate
  is completely unchanged and still fully applies; and the internal
  justification — `spec/dimensions/quality-attributes.toml`'s
  `verified_by` primacy ordering (empirical, then adversarial, then
  heuristic) — RULE recognizes when empirical verification already
  covers everything there is to verify, it is not an exemption from it.
  SKILL.md MUST additionally document the practical usage loop from
  Boundaries/Always (`--check` before committing, self-declare in the
  message, a wrong guess only costs redoing the demand normally) and the
  `FORWARD: RULE — <one-line reason>` commit convention, alongside the
  existing `FORWARD: M — ...` example. `AGENTS.md` and
  `templates/AGENTS.md.template` MUST remain byte-identical to each
  other across this new material, and a new or extended suite test MUST
  enforce that parity plus the pre-existing XS/S/M/L text staying
  byte-identical to its current state (FM-6).
- R6 (non-negotiable): `runtime/verify.py::Gate.gate_eval_coverage` MUST
  be unmodified by this demand's diff — zero lines added, removed, or
  reordered inside its body, verifiable by direct inspection. Nothing
  about `--gate eval`/`--gate eval-coverage`'s behavior, output, or code
  path changes as a side effect of this demand. The existing XS/S/M/L
  table rows in `skills/fde-triage/SKILL.md` and the existing
  `score ≤ 1 → **XS**...`/`≥ 7 → **L**...` sentence in `AGENTS.md` and
  `templates/AGENTS.md.template` MUST remain byte-identical to their
  current text. `KNOWN_GATES`' insertion of `"rule-lane"` MUST be a pure
  addition — no existing id renamed, removed, or reordered in a way that
  changes `--gate <id>` behavior for any id that exists today.
- R7: WHEN this demand ships, `tests/test_triage.py` MUST exist,
  following `tests/test_erosion.py`'s split between pure-core unit tests
  (no git) and on-disk-fixture git-backed tests using the extended
  `tests/support.py` fixture (FM-7), and MUST cover at minimum: (1)
  eligible=true for a genuinely trivial diff (a comment/text change, a
  few lines, project-level ceilings clear); (2) eligible=false purely
  from exceeding the declared `rule_lane_max_loc`; (3) eligible=false
  when `data_class`/`reversibility` don't clear the project-level
  ceiling, even for a 1-line diff — proving the project-level check, not
  the loc threshold, is what stops it; (4) eligible=false when an
  `eval_paths` file is deleted or shrunk, even under the loc threshold;
  (5) `gate_rule_lane` blocking a commit whose message claims RULE but
  whose actual diff fails re-verification (FM-2); (6) `gate_rule_lane`
  passing silently (no report row) when no commit in range claims RULE,
  and reporting explicitly only under `--gate rule-lane`; (7) the
  fallback default of `10` applying when the config key is absent from
  the fixture's config; (8) a fixture proving per-commit isolation — a
  RULE-tagged trivial commit's eligibility is unaffected by a large,
  unrelated sibling commit in the same examined range (FM-8).
