# FWD-021 — Declared cycle scope and a next-cycle list

size: M

Triage: surfaces 2 (gate runtime + instruction layer) · public ·
reversible · ~300+ LOC → surfaces 2 + loc 2 = score 4 → **M** (spec, impl,
adversarial 2 rounds, promotion, ADR).

Input: `backlog.md` item 9, "Declared cycle scope and a next-cycle list
(FWD-021)". Evidence: usage-data, owner-reported. It was pulled forward on
2026-09-28 as an unplanned demand in `sprints/S-006/goal.md`. The owner
chose gate enforcement over an instruction-only rule on 2026-09-28.

## Problem

Long agent loops drift into side tasks. The agent finds something along
the way, fixes it, finds something else, and the tokens go to work nobody
asked for. The owner reports that one practice visibly kept an agent on
task: a round file that declared seven done criteria before execution.
The owner asks for three things:

1. Every request (cycle) declares its tasks, its objective and its
   definition of done (DoD) **before** execution.
2. Anything discovered during execution is **not** acted on in the
   current cycle. It goes to a list.
3. That list is presented at the close, and it is the input of the next
   cycle.

The seven criteria the owner used:

1. Spec + ADR (M/L) committed before code.
2. Tests fail on the old code and pass on the new code, with no new
   failures in the suite.
3. The size's review rounds are done, and no blocking finding is open.
4. Promotion for M/L.
5. Live in production, with live checks passing.
6. Published.
7. Residuals declared.

Criteria 5 and 6 do not apply to every project. This repository deploys
nothing. So the DoD must be **project-aware**, not seven hard-coded items.

## What the kernel has today (verified 2026-09-28)

Each claim is labeled `[observed]` (read or run in the repo for this
spec) or `[inferred]`.

**Gap (a): no DoD below S, and none for a multi-demand round.** Confirmed.
- `[observed]` AGENTS.md step 2 is "Spec (unless XS)". `acceptance.md`
  exists only from S up.
- `[observed]` RULE is defined as zero-judgment and post-hoc (ADR-0015).
  It declares nothing before the commit.
- `[observed]` Nothing in `runtime/`, `skills/`, `templates/` or
  `spec/` names a round or cycle that groups several demands.

**Gap (b): no scope-freeze rule outside `[scrum]`.** Partly confirmed.
The principle exists, but only as judgment after the fact.
- `[observed]` `spec/dimensions/quality-attributes.toml` carries
  MNT-9: "scope discipline: adjacent improvements are noted for later,
  never fixed in-band". It is a heuristic principle. Review checks it
  after the fact, and nothing states it as a rule during execution.
- `[observed]` MNT-9 is cited in exactly one skill, `fde-debug` (line 48).
- `[observed]` `fde-scrum`'s "Execute" section covers two cases: ideas
  that come up in conversation ("Capture") and demands added in the
  middle of a sprint ("must justify itself against the goal or wait").
  Neither covers something discovered inside a demand while it runs.

**Gap (c): no mandatory next-cycle list at the close.** Confirmed.
- `[observed]` Three promotions carry a "Declared residuals" section by
  practice: FWD-017, FWD-019 and FWD-020. The promotion role does not
  require it (`agents/fde-promotion.md` has no "residual").
- `[observed]` Promotion exists only at M/L. XS and S close with no
  residual record at all.
- `[observed]` No residual is routed anywhere. Nothing turns it into the
  next cycle's input. The scrum retro's question 3 routes only process
  friction.

**Finding F-A: I4's "declared before construction" is not verified
mechanically. Owner criterion (1) is not met by this repository's own
history.**
- `[observed]` `Gate.gate_promotion_criteria` checks two things. Every
  `specs/*/` directory has an `acceptance.md`, and a `date:` string
  appears in its first 400 characters. It never checks ordering.
- `[observed]` In each of the last five demands, the commit that first
  added `acceptance.md` also changed behavior paths:

  | demand | commit | behavior files in the same commit |
  |---|---|---|
  | FWD-016 | `8b30405` | 2 |
  | FWD-017 | `bcbb734` | 4 |
  | FWD-018 | `c3f130f` | 9 |
  | FWD-019 | `d26cc3f` | 6 |
  | FWD-020 | `d744170` | 17 files in total: spec, ADR, tests and copies |

  "Before" held in the working session. It does not hold in git. This
  demand cannot keep the declaration requirement and leave ordering
  unverifiable. The history is a record and is not rewritten. The gate
  must not go red on history from before it was switched on (R9).

**Other constraints read for this spec**
- `[observed]` `gate_promotion_criteria` requires `acceptance.md` in
  **every** directory under `specs/`. `graph.forbidden_orphans` rule 1
  forbids an `acceptance.md` without a `spec.md`. Suppose an XS cycle file
  lived in `specs/<id>/`. XS would then have to write `acceptance.md` and
  `spec.md`, which is exactly the S ceremony XS exists to skip (FM-8).
- `[observed]` The implementation role is denied
  `specs/**/acceptance.md`, "cannot rewrite the criteria it will be judged
  by" (`spec/roles.toml`). The cycle DoD needs the same protection. The
  next-cycle list, however, has to be appended during execution.
- `[observed]` `[scrum]`, `[erosion]` and `[walkthrough]` already set the
  opt-in pattern. A missing section means the gate is silent under
  `--all`, and `--gate <id>` prints an explicit "not in force" pass. The
  `enabled` check is strictly boolean (`gate_scrum`).
- `[observed]` `triage.eligibility_for_commit` already decides RULE
  eligibility for one commit against its real diff, and it fails closed on
  a merge, a binary file, or a git failure.
- `[observed]` `Gate._resolve_range` picks the commit range. It uses
  `--since`, then `HEAD~1..HEAD`, then everything. CI passes `--since`
  with the PR or push base (`.github/workflows/fde-gate.yml:17`).
- `[observed]` `python3 bin/fde/verify.py --all` took 5.11 s wall on this
  repo on 2026-09-28 (one run, 0.74 s user). That is the baseline for R11.
- `[observed]` Commit subjects are prefixed `FWD-NNN:` by this
  repository's practice (62 of 99). The kernel does not make this a rule
  anywhere, and client repos may follow other conventions.

## Definitions (settled here)

**Cycle.** The unit of execution scope. It is one declared piece of agent
work, started by one request, that has an objective, at least one task, a
DoD, a next-cycle list and a closure. A **demand** is the unit of sizing
and artifacts: triage, spec, review, promotion, joined by demand id. The
two are related like this:

- A cycle names the demand(s) it executes, each with its triaged size.
  The common case is one cycle with one demand. A multi-demand round (the
  owner's "round file") is one cycle that lists N demands.
- A demand whose DoD is not met when its cycle closes continues in a later
  cycle. It is carried over through the next-cycle list, never by leaving
  the cycle open. So a demand may appear in more than one cycle.
- A **sprint** (with `[scrum]` on) contains cycles. The sprint goal is not
  a cycle, and a cycle does not replace the sprint's `goal.md`.
- A **RULE** commit is outside every cycle. RULE stays zero-judgment
  (ADR-0015). A commit that is actually RULE-eligible needs no cycle,
  checked with `triage.eligibility_for_commit` against its real diff and
  never on its claim (R3).

**Open / closed.** A cycle is open from the commit that adds its
well-formed file. It is closed from the commit that adds its `closed:`
header. Both states are read mechanically from the file in a given git
tree, never from chat.

**Declared before execution.** Every commit that changes a
`[gate].behavior_paths` file must have an open, well-formed cycle already
present in its **parent** tree. For each S+ demand that cycle names, the
demand's `specs/<id>/acceptance.md` must also be in that parent tree. This
is pure git ordering with no content judgment. It uses the same behavior
paths that I1 uses (MNT-1). It also closes Finding F-A for every commit
made after opt-in.

**Project-aware DoD.** A cycle's DoD has three parts:
- (i) **Profile items.** The kernel derives these from each demand's size
  and from the project's declared delivery stages. They are stable keys,
  not free text.
- (ii) **Demand-specific criteria.** For S+ this is a reference to
  `specs/<id>/acceptance.md`, and the criteria are never restated. For XS,
  where no `acceptance.md` exists, the items are written inline in the
  cycle file.
- (iii) Nothing else is required.

Profile, by the owner's criteria:

| key | owner criterion | required for | resolved by |
|---|---|---|---|
| `declared-before` | (1) | every size | the gate itself (R3). Listing it is informational |
| `regression-proven` | (2) | every size that changes behavior | evidence named in the closure (test id, or "red on `<sha>`, green on `<sha>`"), or `n/a — <reason>` |
| `review-rounds` | (3) | every size | `reviews/<id>/findings.toml` with the size's rounds and no open blocking finding |
| `promotion` | (4) | M, L | `promotions/<id>/decision.md` |
| `live` | (5) | only when the project declares the `live` stage | the live-check evidence the project names |
| `published` | (6) | only when the project declares the `published` stage | the publication evidence the project names |
| `residuals` | (7) | every size | the cycle's own next-cycle list (see below) |

Stages are declared once per project in `fde.config.toml` (R2). A project
that declares no stage gets a DoD profile of five keys at most. This
repository deploys nothing, so `live` never applies here (see Ask first
for `published`).

**Next-cycle list.** This is one section of the cycle file. There is one
list, not a "discovered" list plus a "residuals" list plus a "next cycle"
list (MNT-1). During execution, items are only ever appended. At the
close it holds two kinds of entry: everything discovered and not acted
on, and every DoD item not met, each with its reason. A closed cycle must
carry at least one item or the literal `none`. That list is criterion (7).

## Boundaries

**Always**
- One gate id, `cycle`, added to `KNOWN_GATES` as a pure addition. It
  runs at the CI/full-gate tier (outside `--staged`), next to
  `gate_scrum` and `gate_rule_lane`, and follows the same
  `explicit`-parameter silence pattern.
- Opt-in by `[cycle] enabled = true` in `fde.config.toml`, checked as a
  strict boolean like `[scrum]`. With the section absent or not strictly
  `true`, the gate adds zero result rows under `--all` or the default.
  Under `--gate cycle` it adds one explicit "not in force" pass. An
  existing client project that does not opt in sees no change at all.
- The gate judges **form and ordering only**: which headers and sections
  exist, whether they are empty, which profile keys are present, git
  parent-tree ordering, and whether the DoD stayed unchanged after open.
  It never judges whether an objective is good or whether a checked box is
  true. Truth is verified where the kernel already verifies truth: the
  size's isolated adversarial round, and promotion at M/L (I8, ADR-0003).
- Reuse, never clone (MNT-11):
  - behavior paths come from the same `gate_paths(cfg.raw)` I1 uses;
  - the commit range comes from `Gate._resolve_range`;
  - RULE eligibility comes from `triage.eligibility_for_commit`;
  - git failures follow the `GitOpFailure`/`run_gate` fail-closed
    contract;
  - header-line parsing follows `gate_scrum`'s "first 30 lines,
    non-empty `key:`" rule, or reuses it.
- One DoD per cycle. For S+ demands it **points to** `acceptance.md` and
  never restates it (MNT-1). `acceptance.md` stays I4's artifact,
  unchanged in format and still required by `gate_promotion_criteria`.
- Fail closed whenever mechanical certainty is unavailable: an unreadable
  file, a malformed header, a git failure, or a merge commit whose own
  diff would need a parent choice. Such cases are red with a labeled
  reason, never a vacuous pass (ADR-0015's posture).
- Label every breach by check and file (C1–C6 in R4–R8), in the style of
  `erosion.check_budget`. Never a bare pass/fail.
- The instruction layer lands in the same change (MNT-10):
  - `templates/AGENTS.md.template` and `AGENTS.md` get the
    open-the-cycle step and the closing rule. The FWD-020 manifest pair
    `agents-md` keeps them identical-except;
  - `skills/fde-triage` gets the cycle schema, the profile table, and the
    scope-freeze rule;
  - `skills/fde-scrum` gets how the list feeds `backlog.md`;
  - `fde.config.toml` and `templates/fde.config.template.toml` get the
    `[cycle]` section;
  - the mirrored copies (`bin/fde/`, `.claude/skills/`) are regenerated
    and checked by `tests/mirror.toml`, with no new drift test.
- Stdlib only. No network, no `claude` CLI, and no framework component on
  the critical path (I6).

**Ask first** (for architecture unless it says owner)
- **A1: attribution.** How does the gate know which cycle a behavior
  commit belongs to? The spec's minimum (R3) is "some open cycle exists in
  the parent tree", which needs no commit-message convention.
  Alternatives:
  - a git trailer (`Cycle: C-7`);
  - the `<demand-id>:` subject prefix this repo uses. Clients do not
    follow it, and the kernel never made it a rule.

  Recommendation: the minimum, plus A2's serial rule. Together they make
  "some open cycle" mean "the one open cycle".
- **A2: one open cycle at a time.** Recommended: a cycle can open only
  once the numerically previous one is closed ("no closure, no next
  cycle", mirroring "no retro, no next sprint"). This closes the omnibus,
  never-closed cycle (FM-5). The cost is that parallel agent worktrees
  cannot each hold their own cycle. Architecture decides whether that
  cost is acceptable or whether numbering has to be per worktree or
  branch.
- **A3: location and id.** Recommended: `cycles/C-<n>.md` at the repo
  root, ordered numerically like `sprints/S-<n>`. Not under `specs/`: see
  the `[observed]` constraint on `gate_promotion_criteria` and graph rule
  1. Not under `sprints/`: the cycle must work with `[scrum]` off.
- **A4: who writes `cycles/`.** No role's `write_scope` covers it today.
  Recommendation: the orchestrating thread, which already writes
  `backlog.md` and `sprints/`. Implementation must not be able to edit
  the DoD it is judged by. R6 enforces this mechanically whoever writes
  the file, so a guard-hook scope change is optional. It is not required.
- **A5: the graph.** Does `runtime/graph.py` gain a `cycle` node
  (cycle → demand, cycle → next-cycle item → backlog item or next cycle)?
  Is a new `forbidden_orphans` rule added? Recommendation: add the node
  (traceability is the point) and no new orphan rule, because the `cycle`
  gate already owns the checks. The graph stays evidence derived from
  files (ADR-0010).
- **A6: pre-commit feedback.** Should C1 also run under `--staged`
  (HEAD as parent tree, cheap, and the agent learns before committing)?
  `--staged` today allows only `config`/`eval`/`eval-coverage`. The spec
  requires only the CI tier. Adding `--staged` changes a stated posture
  ("pre-commit stays fast").
- **A7: `fde-sync` and version bumps.** These commits rewrite
  `bin/fde/`, `.fde/` and `.claude/`, which are behavior paths. Under R3
  they need an open cycle. Recommendation: they do, and `fde-sync`
  opens a minimal cycle whose objective is the sync. The alternative is a
  named exemption, which R3's "no exemption by path" forbids unless this
  item overturns it.
- **A8: amendments.** The DoD cannot change after open (R6). The
  alternative is to allow append-only lines marked `amended: <date> —
  <reason>`, as FWD-020 did to `acceptance.md`. Recommendation: append-only
  additions allowed; removal or rewording is never allowed.
- **A9 (owner): RULE during an open cycle.** The gate exempts
  RULE-eligible commits (R3), because RULE is zero-judgment. The owner
  wants discovered items never acted on in the current cycle. So the
  instruction layer forbids using a RULE commit to act on something
  discovered while a cycle is open: it goes to the list. The gate cannot
  tell a planned RULE commit from a discovered one without judgment. This
  gap is declared as a residual, not closed. The owner confirms or
  overrides.
- **A10 (owner): default for new installs.** Should
  `templates/fde.config.template.toml` ship `[cycle] enabled = true` (on
  for new projects) or ship it commented out (opt-in everywhere)? Existing
  clients stay silent either way (R9). Recommendation: commented out, and
  `fde-init` states the choice in one line. The owner chose enforcement
  for this repository, not necessarily as the default for every client.
- **A11 (owner): this repo's stages.** Does this repository declare
  `published`? "Published" could mean the push to the public repository,
  or the plugin marketplace entry. Recommendation: `stages = []`, because
  the push is the gate's own CI and there is no separate publish step. The
  owner decides.
- **A12: format of the list items.** How does an item get a stable
  reference that the next cycle or `backlog.md` can cite mechanically?
  Examples: `C-7#3`, or a slug. R8 needs *some* stable token. Architecture
  chooses the token.

**Resolved — 2026-09-28.** The architecture items are resolved by
`docs/adr/0017-a-cycle-is-declared-in-git-before-it-runs.md`. The build
contract is `architecture.md`. The owner answered A9–A11 on 2026-09-28.
The items above are kept as asked. Their answers:
- **A1:** attribution is structural. A behavior commit belongs to the one
  open cycle in its parent tree. There is no trailer and no subject
  convention.
- **A2:** adopted. At most one cycle is open, it is the highest-numbered
  file, and every lower-numbered cycle is closed. Per-branch numbering is
  rejected, and the parallel-branch cost is accepted.
- **A3:** adopted. `cycles/C-<n>.md` at the repository root.
- **A4:** adopted. The orchestrating thread writes `cycles/`, and no role
  scope or guard changes. The adversarial and promotion roles gain
  `cycles/**:read` as an input.
- **A5:** adopted. A `cycle` node with `executes` and `carries` edges,
  and no new orphan rule.
- **A6:** rejected. No `--staged` participation, because RULE eligibility
  cannot be known before the commit exists.
- **A7:** no exemption. Client syncs touch no default behavior path. Here,
  syncs and version bumps run inside the demand's cycle.
- **A8:** append-only `- [ ] amended YYYY-MM-DD: <text>` done items while
  the cycle is open. Removal or rewording is never allowed.
- **A9 (owner):** confirmed. RULE commits stay outside every cycle, and
  discovered items go to the list even when RULE-sized. That the gate
  cannot tell a planned RULE commit from an in-band fix is a declared
  known limit, and review is the backstop. ADR-0015 is unchanged.
- **A10 (owner):** `[cycle]` ships commented out in the client config
  template. This repository enables it.
- **A11 (owner):** `stages = []` here. Done ends at promotion plus
  declared residuals.
- **A12:** positional, derived tokens `C-<n>#<k>`, stable because the
  list is append-only and frozen at close.

The ADR also changes three requirements. Each change is stricter or a
decision the requirement delegated, and none loosens a criterion:
- **R6:** the freeze starts at the **opening commit**, not at the first
  behavior commit's parent, so that every check compares one commit with
  its own parent. It covers the whole declaration: header values, Tasks,
  Intake, done items and next-cycle items. The only allowed changes are
  next-cycle appends, `amended` done-item appends while open, and the
  closing transition (`closed:` plus resolution marks). A deleted cycle
  file is red, and none of these checks is RULE-exempt.
- **R10:** a merge is examined on its own changes (`git diff-tree -c`).
  C1 and C4 must hold against every parent, and a merge with no change of
  its own is counted, not silently passed.
- **R1/R2:** a demand's declared size must equal the size on its
  `spec.md` Triage line when that line states one. This closes
  "declare M as XS" as a way to drop the `acceptance.md` and `promotion`
  requirements.

**Revised — 2026-09-28, after adversarial round 1.** See ADR-0017
"Revision — 2026-09-28" and `architecture.md` "Revision — round 1". Each
change below is stricter; none loosens a criterion.
- **R9:** a commit is examined when its parent tree enables the mode or
  holds any tracked cycle file (F1). History from before the first cycle
  file, and every client that never opts in, is still never examined.
- **R3:** every rule applied to a commit reads its parent's configuration
  (F8). The RULE exemption requires the `FORWARD: RULE` claim plus
  verified eligibility (F7). A behavior commit may not add a cycle file
  (F9).
- **R1/R2:** size agreement reads a `size:` header line in `spec.md`,
  compares normalized ids, and is red when the size is unreadable (F2).
  This spec now carries `size: M`.
- **R2/R5:** closed cycles are judged once, at their closing commit,
  against the configuration in force there (F3). Carrying a not-met item
  over is one-to-one (F12).
- **R8:** a disposition is checked at the transition where it happens.
  With scrum on, it is checked at close against that commit's
  `backlog.md`. With scrum off, it is checked at the next cycle's
  opening, against its `## Intake` (F5).
- **R10:** an unresolvable, non-zero `--since` is red. An all-zero
  `--since` examines the full history (F4).

**Never**
- Hard-code seven DoD items. The profile comes from size and from declared
  stages.
- Restate `acceptance.md`'s criteria in the cycle file, or create a second
  artifact that competes with I4 (MNT-1).
- Make XS write `spec.md` or `acceptance.md` to satisfy this gate, or
  place the cycle file anywhere that triggers `gate_promotion_criteria` or
  graph rule 1 for an XS demand (FM-8).
- Require a cycle for a commit that is actually RULE-eligible. Also never
  exempt a commit because of what its message claims, rather than its
  verified eligibility (ADR-0015).
- Judge DoD content: no word counts, no "is this objective specific", no
  model call. Content that only matches the template placeholder is form
  and may be rejected (R4). Anything beyond that is review's job.
- Go red on a commit whose parent tree did not have `[cycle] enabled =
  true`. History from before opt-in is never examined (R9).
- Rewrite history or older artifacts to satisfy the gate
  (`specs/FWD-0xx`, `reviews/`, `promotions/`, commits).
- Change `gate_eval_coverage`, `gate_promotion_criteria`, `gate_scrum` or
  `gate_rule_lane` behavior as a side effect.
- Allow a bypass key. `enabled = false` is opt-out of a mode, like
  `[scrum]`, and not an invariant switch. No invariant becomes
  configurable.

## Failure modes

Enumerated in `failure-modes.toml` (FM-1 … FM-14). Summary:
- FM-1: empty or boilerplate DoD passes.
- FM-2: DoD written after the fact.
- FM-3: DoD weakened mid-cycle.
- FM-4: a discovered item is acted on silently.
- FM-5: omnibus or perpetual open cycle.
- FM-6: the list is never presented, or never consumed.
- FM-7: the gate blocks legitimate RULE work.
- FM-8: ceremony inflation on XS.
- FM-9: a second DoD competes with `acceptance.md`.
- FM-10: the gate goes red for an existing client, or on pre-opt-in
  history.
- FM-11: a git failure or merge reads as a pass.
- FM-12: criteria 5/6 are forced on a project that deploys or publishes
  nothing, or skipped by one that does.
- FM-13: the instruction layer drifts from the gate (template, AGENTS.md,
  skills, copies).
- FM-14: a claimed-closed cycle has unresolved DoD items.

## Requirements (EARS)

- **R1 (schema).** A cycle file MUST carry these header lines within its
  first 30 lines, each non-empty: `cycle:` (its id), `objective:` (one
  line), `opened:` (a date), and `demands:` (one or more `<demand-id>
  (<size>)`, size in XS|S|M|L). It MUST carry three sections:
  - `## Tasks` with at least one list item;
  - `## Done when` with the profile keys R2 requires plus the
    demand-specific part (a path to `specs/<id>/acceptance.md` for each
    S+ demand, and at least one inline item for each XS demand);
  - `## Next cycle`.

  A closed cycle adds a `closed:` date header. Architecture may rename
  the headings. It MUST NOT add a required field beyond these.
- **R2 (profile).** The required profile keys for a cycle MUST be computed
  by one function, from the sizes of its demands and from
  `[cycle].stages`. These are the keys in the Definitions table.
  `[cycle].stages` is a list drawn from the closed set `live` and
  `published`. It is empty when absent. An unknown stage MUST be a config
  violation (`validate()`), never ignored. A missing required key MUST be
  red, and so MUST a `live`/`published` key present when not declared.
- **R3 (C1, declared before).** WHEN `[cycle] enabled = true` in a
  commit's parent tree, and the commit changes any
  `[gate].behavior_paths` file, and it is not a merge, and
  `triage.eligibility_for_commit` does not find it RULE-eligible, THEN
  its parent tree MUST contain an open cycle file that satisfies R1 and
  R2. For every S+ demand that cycle lists, the parent tree MUST also
  contain `specs/<id>/acceptance.md`. There is no exemption by path or by
  commit message.
- **R4 (C2, form).** The gate MUST reject, labeled per file, a cycle
  whose headers, sections or list items are missing or empty. It MUST
  also reject an item whose text is byte-identical to the placeholder
  text of the schema shipped in the skill.
- **R5 (C3, closure).** WHEN a cycle carries `closed:`, every `## Done
  when` item MUST be resolved. Resolved means marked met (for example
  `[x]` plus evidence text) or marked not met with a non-empty reason. The
  `## Next cycle` section MUST hold at least one item or the literal
  `none`. Every not-met DoD item MUST also appear as a `## Next cycle`
  item. A closed cycle file MUST NOT change in any later commit.
- **R6 (C4, frozen DoD).** Take the `## Done when` item set as it was in
  the parent tree of the cycle's first behavior commit. That set MUST
  still be present, unchanged, in every later version of the file:
  resolution marks may be added, and additions are governed by A8.
  `## Next cycle` items MUST only be appended, never removed or reworded,
  until closure.
- **R7 (C5, serial).** Subject to A2: a cycle MUST NOT be open in a tree
  where a numerically previous cycle is not closed.
- **R8 (C6, the list feeds the next cycle).** For every closed cycle, each
  `## Next cycle` item (except `none`) MUST have exactly one disposition,
  cited by its stable token (A12):
  - WHEN `[scrum]` is on, the token appears in `backlog.md` (captured with
    an evidence label, per `fde-scrum`), or in the next cycle's
    `## Intake` as taken or dropped with a reason.
  - WHEN `[scrum]` is off, the numerically next cycle carries an
    `## Intake` section listing every item of its predecessor as taken
    (it is among its tasks), deferred (it is re-listed in its own
    `## Next cycle`), or dropped with a non-empty reason.

  An item with no disposition is red once a next cycle opens (scrum off),
  or at the next gate run (scrum on).
- **R9 (compatibility).** With `[cycle]` absent or not strictly `true`,
  `verify.py --all` MUST produce byte-identical output with and without
  this change on a fixture client project. The gate MUST NOT examine any
  commit whose parent tree lacked `[cycle] enabled = true`. This repo's
  pre-FWD-021 history, including the five same-commit demands above, MUST
  stay green under `verify.py --all --since <root>`.
- **R10 (fail closed).** A git failure MUST be a labeled red result
  through the `run_gate` contract, never a pass. So MUST an unparseable
  cycle file or config. A merge commit MUST be neither silently passed
  nor red. The recommended treatment: its non-merge ancestors in the range
  are each checked individually, and the merge itself is examined only
  when it carries its own behavior diff against its first parent.
  Architecture decides and records this. Whatever it decides, the merge
  MUST NOT be silently passed.
- **R11 (cost).** The `cycle` gate MUST add at most 0.5 s wall to
  `verify.py --all` on this repository. Baseline: 5.11 s on 2026-09-28,
  one run. Promotion re-measures the median of 5 runs, before and after.
- **R12 (ceremony budget).** A valid cycle file for one XS demand in a
  project with no stages MUST fit in at most 20 lines. The skill MUST
  ship that minimal example, and a test MUST check that the example is
  both valid and within the limit.
- **R13 (instruction layer).** Four surfaces MUST state the same rule:
  `templates/AGENTS.md.template`/`AGENTS.md` (demand loop) and
  `skills/fde-triage`/`skills/fde-scrum`. The rule has four parts:
  - (a) open the cycle, with its objective, tasks and DoD, and commit it
    before the first behavior change;
  - (b) during execution, anything discovered goes to `## Next cycle` and
    is not acted on in this cycle. This includes a RULE-sized fix (A9)
    and cites MNT-9;
  - (c) at the close, resolve every DoD item and present the next-cycle
    list in the closing report. The list is domain content, so the Voice
    rule's one-status-line limit does not suppress it, and the Voice
    section says so;
  - (d) with `[scrum]` on, items become backlog items with evidence
    labels; with it off, they become the next cycle's intake.

  The mirrored copies MUST pass `tests/mirror.toml` with no new drift
  test.
- **R14 (evals, I1).** A test module MUST prove red and green for each
  check C1–C6 and for R2, R9, R10 and R12. The fixtures are temp git
  repos built with `tests/support.py`'s `make_project` (extended, not
  cloned). Each red case MUST show the labeled reason. There MUST be at
  least:
  - C1: a behavior commit whose parent has no cycle; one whose cycle has
    `closed:`; one whose S+ demand's `acceptance.md` arrives in the same
    commit (red); one where it arrives in an earlier commit (green); a
    RULE-eligible commit with no cycle (green); a commit that claims
    `FORWARD: RULE` but is not eligible and has no cycle (red);
  - C4: a DoD item reworded after the first behavior commit (red);
  - C5: a second cycle opened while the previous one is open (red,
    subject to A2);
  - C6: an item with no disposition, with scrum on and with scrum off;
  - R9: pre-opt-in history (green).
- **R15 (ADR).** `docs/adr/0017-*.md` MUST record the decisions on A1–A8
  and A12 and the owner's answers to A9–A11. It MUST also record the
  alternatives rejected, including: instruction-only (the owner rejected
  it); the cycle file under `specs/`; hard-coded seven criteria; and a
  per-cycle path-scope declaration to detect side tasks mechanically.
  That last one was rejected here as ceremony. FM-4 is covered by review
  against MNT-9 with the cycle file as the reference (MNT-4).

- **R16 (report).** WHEN run as `--gate cycle` (explicit), the gate MUST
  print, beyond pass/fail, a report of three things:
  - the open cycle's id, its `opened:` date, and the number of behavior
    commits since it opened;
  - for each closed cycle, its `## Next cycle` item count and the count of
    each disposition kind;
  - the number of behavior commits in range that were exempted as
    RULE-eligible.

  Under `--all` it prints only the pass/fail rows (OBS-1, OBS-3).

## Measurement notes

- **Unmeasured hypothesis, declared as a finding.** The owner's outcome
  ("fewer side tasks, fewer tokens burned") has no baseline in this repo.
  Token use per demand is not recorded anywhere. This demand does not
  claim that outcome as an acceptance criterion. It provides a proxy
  that the next retro can read: the explicit `--gate cycle` run reports,
  per closed cycle, the `## Next cycle` item count and the count of
  disposition kinds. Review findings that cite MNT-9 are already counted
  by `graph.py --recurring`. The S-006 retro, or a later one, judges the
  hypothesis on those numbers.
- The gate verifies ordering and form. It cannot verify that a checked
  DoD box is true, that the list was actually shown to the owner in chat,
  or that nothing discovered was acted on. Those three are verified by
  the isolated review (FM-4, FM-6) and promotion (FM-14), and they are
  named as residuals in `acceptance.md`, not claimed by the gate.
