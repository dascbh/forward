---
date: 2026-08-22
demand: FWD-018
---

# Acceptance — FWD-018 first contact is blind, not scripted

Context: FWD-017 sharpened two existing sockets so a planned journey can
be executed and gated. This demand adds a capability those sockets cannot
provide — first-contact interpretation with no plan at all — as a new
role (`walkthrough-evaluator`), a new subordinate skill (`fde-walkthrough`),
a new stdlib divergence metric, and the artifact surface that connects
them, without re-litigating FWD-017's already-shipped work.

- `spec/roles.toml` gains a sixth `[[role]]`, `id = "walkthrough-evaluator"`,
  with `inputs` documented as no repository artifact (a target
  URL/endpoint only, supplied at invocation), `outputs` documented as a
  structured perceived-model returned as the run's final message (nothing
  written to disk by the role itself), `write_scope = []` declared
  intentionally, `denied_paths` covering every top-level directory,
  `isolation = true`, `isolation_mode` a value distinct from `worktree`,
  `context_policy` a value distinct from `artifact_only`, and
  `satisfies = []` explicit (no I1–I8 statement names this discipline).
  The file's header comment reads "Six roles." The role also declares a
  `tools` allowlist: browser-automation tools only, explicitly excluding
  `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, `NotebookEdit`,
  `WebSearch`, and `WebFetch`.
- `agents/fde-walkthrough-evaluator.md` and
  `.claude/agents/fde-walkthrough-evaluator.md` mirror that same `tools:`
  allowlist in their frontmatter — the first agent files in this
  repository to declare one. Both state, in the body, that both runs are
  separate fresh invocations sharing no prior context, and that their
  initial instructions carry only a target and generic first-contact
  framing — no spec, wireframe, glossary, or persona language.
- `skills/fde-walkthrough/SKILL.md` documents: trigger conditions
  (M/L demand, UI surface, running target, after the wireframe is built,
  before promotion — subordinate to `fde-design`); the two-run
  independence protocol; that the `architecture` role compiles
  `specs/<demand-id>/design/intended-model.md` from that demand's
  existing spec/flow/IA/wireframe/glossary/acceptance artifacts strictly
  before either run is issued; the confrontation of intended vs.
  perceived-A vs. perceived-B; and a refined admissibility table sitting
  adjacent to — never replacing or rewording — `fde-design`'s "User
  validation" section's existing "Synthetic users generate hypotheses and
  tasks, never findings" sentence and its FWD-017 Suchman addition. The
  table names three categories: synthetic-preference claims
  (inadmissible, unchanged), agent journey completion (not usability
  evidence by itself, USE-14, unchanged), and two independent blind runs
  sustaining distinct interpretations of the same interface (admissible —
  a claim about the artifact via demonstrated blind replication, never a
  population claim). The skill states, in one sentence, the distinction
  from FWD-017: a journey executes a known planned path; a walkthrough
  has no plan and explores cold.
- The perceived-model schema (documented in the skill, consumed by
  `runtime/walkthrough.py`) declares named, enumerable slots — perceived
  primary actions, perceived action→consequence pairs, unclear points
  noticed — each entry a short, lowercase, verb-first canonical phrase
  (2–5 words), plus one free-prose "what this is" slot that is never fed
  to the numeric metric.
- `runtime/walkthrough.py` computes a deterministic, symmetric, `[0, 1]`-
  bounded divergence score from only the enumerable slots, via stdlib
  string normalization and a set-difference/Jaccard-class formula — no
  embedding, no LLM call. Unit-verified against constructed fixtures:
  identical canonical-phrase sets score 0; fully disjoint sets score 1;
  a partial-overlap fixture scores the hand-computed intermediate value.
- A new top-level `walkthroughs/<demand-id>/` directory (or architecture's
  chosen alternative, recorded in the ADR if different) holds
  `perceived-model-a.md`, `perceived-model-b.md` (raw, verbatim, neither
  labeled as more authoritative) and `divergence.toml` (score, per-slot
  breakdown, pointers to the intended-model and both perceived-model
  files). Whichever role's `write_scope` architecture extends to cover
  this path also gets a matching entry added to `runtime/guard.py`'s
  `ALLOWED` dict in the same change.
- The `adversarial` role's `inputs` gain `walkthroughs/**:read`. Its
  existing heuristic pass classifies each recorded divergence as either a
  `usability_accessibility` finding — citing a new `heuristic_principles`
  id continuing from `USE-15` in
  `spec/dimensions/quality-attributes.toml`, added only after the full
  existing `USE-1..14` text is read and confirmed not to already cover
  this judgment — or a `functional_correctness` finding citing a `DOM-*`
  id when the divergence traces to a demonstrable implementation bug.
  Never both; never silently dropped once the configured threshold is
  crossed.
- `fde.config.toml` and `templates/fde.config.template.toml` gain a
  `[walkthrough]` section, commented out by default, with `enabled` and
  `divergence_threshold` keys, following `[erosion]`'s exact silence
  discipline (absent → gate adds nothing; enabled with no threshold →
  "not measured," never a vacuous pass). `runtime/verify.py`'s
  `KNOWN_GATES` gains a `walkthrough` id following the
  `gate_erosion`/`gate_survey`/`gate_scrum` `explicit`-parameter pattern.
- `runtime/graph.py` gains node kinds for the intended model, each
  perceived model, and the divergence artifact, and edge kinds tracing
  demand → intended-model → perceived-model (×2) → divergence → finding,
  surfaced by `fde-graph --demand <id>` and `--central`.
  `forbidden_orphans()` gains the matching impossible-state checks: a
  `divergence.toml` pointing at a perceived-model file that does not
  exist, or existing with no `intended-model` counterpart, is a forbidden
  orphan.
- Tests: `tests/test_spec_integrity.py::test_five_roles_with_write_scope`
  is updated (not deleted, not weakened for the other five) to assert six
  role ids and to permit exactly `walkthrough-evaluator`'s `write_scope`
  as empty — the other five roles' non-empty assertion still fails on
  regression. A new `tests/test_walkthrough.py`, in `test_divergence.py`'s
  on-disk-fixture style, asserts: the three metric boundary cases from
  above; the `walkthrough` gate's silent/measured/breach states; and a
  fixture where an intended-model is absent, proving that case is an
  observable failure, not a silent pass.
- Nothing this demand adds writes under `evals/journeys/**`, reuses the
  `*.journey.toml` shape, or restates coverage already held by DOM-7,
  USE-13, or USE-14 — verified by inspection of the diff and by R13's
  one-sentence distinction actually appearing in the skill text.
- `docs/adr/0014-*.md` records: the role-vs-mode-of-existing-role decision
  (ADR-0012's razor, applied), the `tools:` allowlist over a `guard.py`
  read-interception mechanism (decided by the owner, alternatives named
  and rejected), the write-scope-for-`walkthroughs/**` resolution
  (whichever role architecture chose, and why), the `walkthroughs/<demand-id>/`
  directory placement (or its alternative), and the calibration question
  (real production case as a repo fixture vs. structural-only proof here,
  same honesty FWD-017 already modeled) — each with rejected alternatives
  named, per `MNT-4`.
- Full suite (`python3 -m unittest discover -s tests`) and
  `python3 bin/fde/verify.py --all` green at the demand's closing commit.
  Two isolated adversarial rounds in `reviews/FWD-018/`, specifically
  prompted to test: can the `tools:` allowlist be bypassed by anything
  short of removing the tool from the agent file (an orchestrator-level
  override, a prompt-injected filesystem path, a `WebSearch`/`WebFetch`
  side channel)? does the divergence metric read as degenerate against a
  constructed near-identical pair and a constructed maximally-divergent
  pair? does anything let a walkthrough run see the intended model,
  directly or via the orchestrator's own prompt to it? does the
  confrontation step correctly separate a planted implementation bug from
  a planted genuine ambiguity in the same review fixture? does this
  capability write, anywhere, under `evals/journeys/**`? `finding-
  discipline` (I8) continues rejecting any divergence finding that cites
  neither a probe nor a principle. `promotions/FWD-018/decision.md`
  confronts this list.
