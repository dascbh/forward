---
date: 2026-08-25
demand: FWD-019
---

# Acceptance — FWD-019 a rule lane below XS

Context: `fde-triage` has no floor below XS, and XS already spends a full
isolated adversarial round — paid even by a one-line label fix. This
demand adds RULE: a categorically distinct, zero-judgment mechanical
lane, eligible only when checked post-hoc against the actual committed
diff, never estimated a priori and never a smaller XS. I1's
`eval-coverage` gate is unchanged; RULE recognizes when it already
suffices, it does not exempt anything from it.

- `runtime/triage.py` (mirrored to `bin/fde/triage.py` by the existing
  install-sync sweep) exposes a pure eligibility core plus a git-aware
  wrapper: eligible only when `[triage].data_class` is `public` or
  `internal`, `[triage].reversibility` is `reversible`, the commit's own
  `added + deleted` is under the declared `[triage].rule_lane_max_loc`
  (default `10` when undeclared), and no `eval_paths` file was deleted or
  shrunk in that commit. A failed check names which criterion failed. A
  `--report` prints RULE usage over a window (self-declared, passed,
  would-have-blocked counts), never silent. A `--check` mode previews
  eligibility against the currently staged diff, advisory only.
- `runtime/verify.py` gains `gate_rule_lane` and a `rule-lane` id in
  `KNOWN_GATES`, running only outside `--staged` (CI/full-gate tier,
  alongside `gate_erosion`/`gate_divergence`/`gate_scrum`'s
  `explicit`-parameter pattern). It resolves the examined commit range
  via the existing `--since`/`HEAD~1`/empty-tree fallback chain, checks
  each commit in that range individually (never the range's aggregate
  diff) for a first message line matching `FORWARD: RULE`, and
  re-verifies each match against that commit's own actual diff. Silent
  (no report row) when no commit in range claims RULE under `--all`/
  default; an explicit pass message only under `--gate rule-lane`
  directly. Blocking, naming the commit and the failed criterion, when a
  claimed-RULE commit does not actually qualify. `gate_eval_coverage`'s
  body is unmodified — zero lines added, removed, or reordered.
- `[triage]` in `fde.config.toml` and `templates/fde.config.template.toml`
  gains a plain, uncommented `rule_lane_max_loc` key (template:
  `{{RULE_LANE_MAX_LOC}}` placeholder) alongside the section's existing
  keys — not a new opt-in section. This repo's own `fde.config.toml`
  declares `rule_lane_max_loc = 10` directly (ADR-0007 self-hosting,
  matching `[erosion]`'s "Exhibit A" posture already in that file), with
  the reasoning recorded in `spec.md`: comfortably covers the motivating
  trivial-change case with 5× headroom below S tier's `loc < 50`
  boundary, and no lower value would close the semantic-risk gap a 1-2
  line change already carries, so there is no safety case for a smaller
  default.
- `skills/fde-triage/SKILL.md` introduces RULE in its own paragraph,
  positioned immediately before the existing `## Score and size` table,
  never as a row inside it: categorically distinct from XS (XS runs
  judgment in reduced form; RULE runs none), the four criteria in plain
  language, mechanically checked post-hoc against the real diff — never
  claimed a priori, I1 unchanged and fully applying, and the internal
  justification citing `spec/dimensions/quality-attributes.toml`'s
  `verified_by` primacy ordering (empirical, adversarial, heuristic).
  It documents the usage loop (`triage.py --check` before committing,
  self-declare `FORWARD: RULE — <one-line reason>` in the message, a
  wrong guess only costs redoing the demand normally) alongside the
  existing `FORWARD: M — ...` example.
- `AGENTS.md` and `templates/AGENTS.md.template` carry the same RULE
  paragraph, positioned immediately before the existing
  `score ≤ 1 → **XS**...` sentence in the Triage step, byte-identical to
  each other across the new material — enforced by a suite test. The
  pre-existing XS/S/M/L table rows (SKILL.md) and the pre-existing
  score-boundary sentence (AGENTS.md / template) are byte-identical to
  their current text — enforced by the same or an adjacent test.
- `tests/support.py`'s shared fixture gains a `reversibility` override
  and a `rule_lane_max_loc` value so `tests/test_triage.py` can exercise
  the project-level-ceiling boundary cases without duplicating a parallel
  config builder.
- `tests/test_triage.py` covers, at minimum: a genuinely trivial diff
  eligible; ineligible purely from the loc threshold; ineligible from the
  `data_class`/`reversibility` ceiling even at 1 line; ineligible from an
  `eval_paths` file deleted or shrunk even under the loc threshold;
  `gate_rule_lane` blocking a falsely-tagged commit; `gate_rule_lane`
  silent with no claimed-RULE commit in range, explicit only when
  directly invoked; the `10`-line fallback applying when the config key
  is absent; and per-commit isolation — a RULE-tagged trivial commit
  unaffected by a large unrelated sibling commit in the same range.
- Full suite (`python3 -m unittest discover -s tests`) and
  `python3 bin/fde/verify.py --all` green at the demand's closing commit,
  with the 15 pre-existing gates unregressed and `rule-lane` a 16th.
- `docs/adr/0015-*.md` records the decision, citing Kahneman
  (*Thinking, Fast and Slow*) and Kahneman/Sibony/Sunstein (*Noise*), the
  kernel's own `verified_by` primacy ordering as internal justification,
  and explicitly rejects: diluting XS itself instead of shrinking what
  enters the judged lane; further reducing XS's round count; and a
  per-file/per-line semantic detector as part of eligibility (accepting
  FM-1's residual gameability as a named, only-mitigated risk rather than
  a closed one).
- Two isolated adversarial rounds in `reviews/FWD-019/`, specifically
  prompted to test: can the eligibility checker be gamed by a diff that
  clears all four criteria but hides a disproportionate semantic change
  (a security-check operator flip, a widened default) within a few
  lines? does `gate_rule_lane` actually block a commit whose message
  claims RULE but whose diff exceeds any one of the four criteria — each
  criterion tested independently? does the gate evaluate a bundled
  commit's own diff in isolation, or does it leak size/risk from an
  unrelated sibling commit in the same push either direction? does any
  part of this change touch, weaken, or add a RULE-aware branch inside
  `gate_eval_coverage`? does the documentation, read cold, ever suggest
  RULE is "a smaller XS" or license to skip review rather than a
  categorically distinct mechanical lane? are `AGENTS.md` and
  `templates/AGENTS.md.template` actually byte-identical across the new
  material, and is the pre-existing XS/S/M/L text actually unchanged?
  `finding-discipline` (I8) continues rejecting any finding citing
  neither a probe nor a principle. `promotions/FWD-019/decision.md`
  confronts this list.
