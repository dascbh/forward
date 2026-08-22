# FWD-018 — First contact is blind, not scripted

Triage: surfaces 2 (data/schema: new role entry + new artifact schemas;
infra: the tool-restriction enforcement mechanism, capped to 2) · public ·
reversible · large multi-file change → score 4 → **M** (spec, impl,
adversarial 2 rounds, promotion, ADR-0014).

## Problem

FWD-017 gave the kernel a way to prove a *known* path works: an agent
drives a real browser along a planned route and the committed script is
the evidence (I1), gated so that "the agent succeeded" alone never closes
a `usability_accessibility` finding (USE-14, the Suchman limit). That
technique answers "does this path exist and hold together end to end?"
It cannot answer a different, earlier question: **does the interface, on
first contact, communicate to a stranger what this product IS, what they
can do, and what happens if they do it?** A planned journey cannot probe
that — the agent already knows the plan.

This demand adds that missing capability: two independent agents, each
told nothing about this project beyond a running target to look at, each
explore cold and report what they perceived. Compiled *before* either run
starts, from the same design artifacts `fde-design` already produces
(spec, flow, IA, wireframe, glossary, acceptance criteria), is what the
team actually intended to communicate. Confronting the three — intended,
perceived-A, perceived-B — surfaces two different kinds of defect: the
interface says something the team didn't intend (an implementation bug,
`functional_correctness`), or the interface sustains two reasonable,
independently-arrived-at readings (an ambiguity in the artifact itself,
`usability_accessibility`) — never a claim about how real users would
feel, which stays inadmissible exactly as it already is.

**Why a new role, not a new mode of an existing one (ADR-0012's razor).**
`spec/roles.toml`'s header states the test directly: "a role exists
because it has DIFFERENT ACCESS... not a different title." Every
existing role — including `adversarial`, which is already isolated and
already judges `usability_accessibility` — runs with full read access to
`src/**`/`specs/**`/`evals/**`. The capability this demand needs is
qualitatively different: an evaluator that must be **structurally unable**
to see this project's spec, wireframe, glossary, code, or git history —
not instructed not to look, incapable of looking. No existing role's
access shape can be reused or parameterized into that; it needs its own
`tools:` allowlist. That is a different access shape, which is exactly
ADR-0012's admission criterion, not a title added for flavor.

**Why this is not a 6th competing top-level skill.** The skill this
demand adds, `fde-walkthrough`, is subordinate to `fde-design` the same
way `fde-review`'s adversarial pass is a *role* (`adversarial`) distinct
from the *skill* that invokes it (`fde-review`) — precedent already in
this repo, not an invention. `fde-walkthrough` orchestrates; the role it
invokes twice, in isolation, is `walkthrough-evaluator`. The intended
model it confronts against is not a new phase of `fde-design` — it is a
synthesis of artifacts `fde-design` (via the `architecture` role) already
produces, the same relationship `specs/<demand-id>/design/alternatives.md`
already has to the flow/IA/wireframe that precede it.

**Why the isolation mechanism is a `tools:` allowlist, not a guard-hook
extension.** `runtime/guard.py` enforces write-scope only; it has never
enforced read-scope, and FWD-010's own review (`reviews/FWD-010/findings.toml`
F1) already demonstrated that telling a model not to do something in a
prompt is not enforcement. The owner decided directly: the new role's
agent definition declares a `tools:` frontmatter allowlist containing
only browser-automation tools — no `Read`, `Grep`, `Glob`, `Bash`, `Edit`,
`Write`, `NotebookEdit`. This makes filesystem access **structurally
impossible**, not best-effort blocked, for exactly the reason `guard.py`'s
own module docstring admits its role branch is honesty-dependent on the
harness sending an identity. This is decided, not reopened here: no new
`guard.py` read-interception mechanism is built as an alternative.

## Boundaries

**Always**
- Read the full current text of `skills/fde-design/SKILL.md`'s "User
  validation" section before writing the new admissibility sentence(s) so
  the addition sits adjacent to — and never replaces or reworks — the
  existing "Synthetic users generate hypotheses and tasks, never
  findings" sentence and the FWD-017 Suchman sentence already appended to
  it.
- Declare the new role's `tools:` allowlist as the **only** enforcement
  mechanism for its filesystem incapacity; record that choice, and the
  rejected guard-hook alternative, in the ADR.
- Launch both `walkthrough-evaluator` runs as genuinely separate, fresh
  invocations — no fork, no cloned session, no shared prior turns between
  them or with whatever invoked them. State this explicitly in the skill
  text and in any orchestration example shipped with it.
- Give each run's initial instructions nothing beyond a target
  URL/endpoint and generic first-contact framing ("explore this as a
  first-time visitor; report what you understand"). No spec language, no
  wireframe description, no glossary term, no persona name, no paraphrase
  of the intended model — the `tools:` allowlist blocks tool-based reads,
  it does nothing to stop this second, prompt-based leak channel.
- Compute the divergence score from stdlib operations only (string
  normalization, set operations) over the perceived-model's enumerable
  slots — never an embedding, never an LLM call scoring the two texts
  against each other. This mirrors ADR-0010's rejection of anything
  non-deterministic on a gated path and ADR-0011's rejection of
  instructed-not-measured quality.
- Keep the `[walkthrough]` config section's silence discipline identical
  to `[erosion]`'s, already stated in `AGENTS.md`: absent section, gate
  silent; `enabled = true` with no threshold declared reports "not
  measured", never a vacuous pass.
- Declare the new role's `write_scope = []` as an intentional, documented
  choice — not an omission — and update (never delete or weaken)
  `tests/test_spec_integrity.py::test_five_roles_with_write_scope` so the
  other five roles' non-empty check still fails if any of them regresses.

**Ask first**
- Which existing role's `write_scope` gains `walkthroughs/<demand-id>/**`
  to persist the two runs' raw returned text and the computed score,
  since `walkthrough-evaluator` itself can write nothing. This spec
  proposes `architecture` (it already owns `specs/**`, already
  synthesizes the intended model, and the persistence step is mechanical
  filing, not judgment requiring isolation) — but this is a real
  access-design decision for `architecture` to make and record, not
  mine to fix.
- If reading the full `USE-1..14` text shows the new
  interpretive-divergence judgment overlaps `USE-13`/`USE-14` closely
  enough to become an `adversarial_probes` phrase under one of them
  instead of a new id — the same discipline FWD-017 already applied to
  itself.
- Whether a real, sanitized production case (the owner confirmed these
  exist) can be embedded as a versioned calibration fixture in *this*
  repository, which declares `user_facing = false` and has no real UI —
  or whether calibration is necessarily a client-repo activity and this
  repo proves only the metric's boundary behavior structurally, the same
  honest limitation FWD-017 named for journeys. Do not build a fixture UI
  here to force the question closed.
- The exact string values for the new role's `isolation_mode` and
  `context_policy` (this spec proposes `fresh-agent` and `blind`
  respectively, specifically because `worktree` and `artifact_only`
  already carry a different, narrower meaning for `adversarial`/
  `promotion` — a role with zero filesystem access is not "isolated in a
  worktree" and receives less than "the artifact only").

**Never**
- A new `guard.py` read-interception mechanism as an alternative or
  supplement to the `tools:` allowlist for this role. Decided; not
  re-litigated by this demand or its review.
- `WebSearch` or `WebFetch` in the new role's tool allowlist by default.
  No clean, narrow argument surfaced for either — both risk letting a
  "blind" run discover this product's own public docs, marketing, or
  support pages, leaking intended-model-equivalent information through a
  side channel the `tools:` allowlist was supposed to close.
- Writing under `evals/journeys/**` or reusing the `*.journey.toml`
  manifest shape for any artifact this demand produces — that shape
  belongs to FWD-017's planned-path verification, a different question
  from cold first-contact interpretation (FM-7 below).
- Treating agreement OR disagreement between the two runs as a claim
  about real users, a population, or how "users" in general would react.
  The admissible claim is narrower and stays about the artifact: these
  two independently-arrived-at readings of THIS interface diverged (or
  converged) — never "users will."
- A new invariant, or a reworded I1–I8 statement, to formally fold in
  this role's isolation. Out of scope for an M demand; if the isolation
  discipline someday needs its own named invariant, that is a separate,
  larger decision this demand does not make.
- Claiming this repository proves the mechanism "in the field." This
  repo has no real UI (`user_facing = false`); the metric's boundary
  behavior is proven structurally (constructed fixtures) here, exactly as
  FWD-017 already named for journeys.

## Failure modes

- FM-1: the `tools:` allowlist is bypassed through an indirect channel —
  an orchestrating invocation hands the evaluator a tool beyond its
  declared allowlist (a harness that lets a parent override a subagent's
  tool list), or `WebSearch`/`WebFetch` (if ever included) surfaces this
  product's own public pages, reintroducing exactly the access the
  allowlist exists to deny.
- FM-2: the divergence metric is gameable or degenerate — a
  perceived-model schema coarse enough that two runs on any interface
  always match (score pinned at 0, ambiguity never caught), or granular
  enough (full free sentences, compared by literal string/embedding-free
  match) that two runs on the same unambiguous interface never fully
  agree (score pinned near 1, every interface reads as ambiguous).
- FM-3: the two runs are not genuinely independent — an orchestration
  bug forks or clones one running instance instead of issuing two fresh
  invocations, or state (cache, session, prior turn) leaks between them.
- FM-4: the intended model is compiled or consulted after a walkthrough
  run instead of strictly before, or a run gains access to it — either
  through a tool (closed by the allowlist) or through the orchestrator
  pasting spec/wireframe/glossary language into the run's own initial
  prompt (a channel the allowlist does nothing to close).
- FM-5: a role with `write_scope = []` breaks assumptions three existing
  mechanisms make about every role writing somewhere —
  `tests/test_spec_integrity.py::test_five_roles_with_write_scope`
  (hardcodes 5 ids, asserts every role's `write_scope` truthy),
  `runtime/guard.py`'s `ALLOWED` dict (hand-maintained, not derived from
  `spec/roles.toml` — silently permissive for a new role's path unless
  someone remembers to add it), and any future tooling that assumes
  "every role has an output."
- FM-6: the confrontation step misattributes a genuine implementation bug
  as an interpretive-ambiguity finding, or the reverse — scope confusion
  between `functional_correctness` (the interface says something false
  about what the system does) and `usability_accessibility` (the
  interface is honest but supports two reasonable readings).
- FM-7: scope creep — this capability re-litigates or duplicates
  FWD-017's already-shipped journey-eval work (planned-path execution,
  `evals/journeys/**`, DOM-7, USE-13/USE-14) instead of sitting cleanly
  after it as a distinct, earlier question (no plan at all, vs. a known
  plan executed).
- FM-8: the `[walkthrough]` config section drifts from the `[erosion]`
  silence discipline `AGENTS.md` already declares — the gate fails loudly
  when the section is merely absent, or passes vacuously when
  `enabled = true` but nothing was ever actually measured, instead of
  reporting "not measured."
- FM-9: `graph.py`'s new node/edge kinds create an orphan class the
  gate never checks (a `divergence` artifact pointing at a
  `perceived-model` that was never persisted, or existing with no
  `intended-model` counterpart) — the same "impossible states, never
  incomplete ones" discipline `design.py`'s docstring already states,
  unenforced for the new kinds.

## Requirements (EARS)

- R1: WHEN `spec/roles.toml` gains its sixth `[[role]]` entry, its `id`
  MUST be `walkthrough-evaluator` (distinct from the skill name
  `fde-walkthrough`, mirroring the existing `adversarial` role /
  `fde-review` skill split already in this repo) and it MUST declare, at
  minimum: `inputs` documented as receiving no repository artifact at
  all — only a target URL/endpoint supplied at invocation; `outputs`
  documented as none on disk — a structured perceived-model returned as
  the run's own final message; `write_scope = []`, declared, not omitted;
  `denied_paths` covering every top-level directory a role could
  plausibly write to; `isolation = true`; an `isolation_mode` value
  distinct from `worktree` (proposed: `fresh-agent`); a `context_policy`
  value distinct from `artifact_only` (proposed: `blind`); `satisfies =
  []`, explicit — none of I1–I8's literal statements name this role or
  this discipline, and inventing a claim to one is worse than declaring
  none (FM-5, FM-9 boundary "Never" on new invariants). The file's header
  comment updates from "Five roles" to "Six roles."
- R2: WHEN `spec/roles.toml`'s schema is extended with a `tools` field
  for `walkthrough-evaluator`, it MUST be a positive allowlist containing
  only browser-automation tools, and MUST explicitly exclude, by name:
  `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, `NotebookEdit`,
  `WebSearch`, `WebFetch`. The mirrored agent files —
  `agents/fde-walkthrough-evaluator.md` and
  `.claude/agents/fde-walkthrough-evaluator.md` — MUST carry this same
  allowlist in their `tools:` frontmatter, making this the first agent
  file in the repository to declare one (FM-1).
- R3: WHEN the orchestration protocol for the two runs is documented (in
  `skills/fde-walkthrough/SKILL.md` and in any workflow-script example
  shipped with it), it MUST state explicitly: each run is a separate,
  freshly-invoked agent instance sharing zero prior context with the
  other run or with the orchestrating step; a fork, clone, or session
  reuse does not satisfy independence. It MUST also state that each
  run's initial instructions carry nothing beyond the target
  URL/endpoint and generic first-contact framing — no spec text,
  wireframe description, glossary term, persona name, or paraphrase of
  the intended model (FM-3, FM-4).
- R4: WHEN a demand's intended model is compiled, the `architecture` role
  MUST produce it — as `specs/<demand-id>/design/intended-model.md`,
  synthesized from that demand's existing `spec.md`, `flow.md`, `ia.md`,
  wireframe(s), glossary, and `acceptance.md` — and it MUST exist on disk
  before either `walkthrough-evaluator` invocation is issued. A demand
  missing the design artifacts needed to synthesize one owes that
  groundwork first, the same uncovered-root discipline
  `design/foundation.md` already applies (FM-4).
- R5: WHEN `skills/fde-walkthrough/SKILL.md` is written, it MUST state:
  the trigger conditions (an M/L demand with a UI surface and a running
  target, invoked after the wireframe is approved and the build exists,
  before promotion — subordinate to, not a phase inside, `fde-design`);
  the two-run protocol from R3; the confrontation procedure (intended vs.
  perceived-A vs. perceived-B); and a refined synthetic-evidence
  admissibility table that extends — sitting adjacent to, never
  replacing or reording — `fde-design`'s "User validation" section. The
  table MUST distinguish three categories: (1) "users will feel/prefer
  X" from a synthetic source — inadmissible, unchanged; (2) an agent
  completing a planned journey — not usability evidence by itself
  (USE-14), unchanged; (3) two independent, blind runs sustaining
  distinct interpretations of the SAME interface — admissible, because it
  is a claim about the artifact demonstrated by blind replication, never
  a claim about a population (FM-6, FM-7).
- R6: WHEN a `walkthrough-evaluator` run returns its perceived model, the
  returned text MUST follow a declared, structured schema with named,
  enumerable slots — at minimum: a one-line "what this is" (prose, never
  fed to the numeric metric), a set of perceived primary actions, a set
  of perceived action→consequence pairs, and a set of unclear points the
  run itself noticed. Every entry in an enumerable slot MUST be phrased
  as a short, lowercase, verb-first canonical phrase (2–5 words)
  specifically so a literal stdlib set comparison is meaningful without
  embeddings or NLP (FM-2).
- R7: WHEN `runtime/walkthrough.py` computes the divergence score for a
  pair of perceived models, it MUST be deterministic (same two inputs,
  same score, every time), symmetric (order of the two runs does not
  change the score), bounded (e.g. `[0, 1]`), computed only from stdlib
  string/set operations (normalization plus a set-difference/Jaccard-class
  formula) over the enumerable slots from R6, and MUST NOT read the
  prose "what this is" slot into the number. No embedding, no LLM call,
  matching ADR-0010's and ADR-0011's rejection of nondeterministic,
  un-gateable measures (FM-2).
- R8: WHEN this demand's artifacts are located, a new top-level
  `walkthroughs/<demand-id>/` directory (proposed; architecture makes the
  final call) MUST hold the two runs' raw, verbatim, unranked perceived
  models (`perceived-model-a.md`, `perceived-model-b.md` — neither
  labeled or ordered as more authoritative) and a `divergence.toml`
  carrying the computed score, the per-slot breakdown, and pointers to
  the intended-model file and both perceived-model files. Whichever
  existing role's `write_scope` is extended to cover this path (proposed:
  `architecture`) MUST have `runtime/guard.py`'s `ALLOWED` dict updated
  in the same change — that dict is hand-maintained, not derived from
  `spec/roles.toml`, and a role granted write scope there without a
  matching guard entry is silently unenforced for that path (FM-1, FM-5).
- R9: WHEN a demand's divergence score crosses the declared
  `[walkthrough].divergence_threshold` (or, absent a declared threshold,
  whenever a `divergence.toml` exists), the `adversarial` role's
  existing heuristic pass — given `walkthroughs/**:read` added to its
  `inputs` — MUST be the step that classifies each recorded divergence as
  EITHER a `usability_accessibility` finding, citing a new
  `heuristic_principles` id continuing the sequence from `USE-15` (added
  to `spec/dimensions/quality-attributes.toml` only after the full
  existing `USE-1..14` text is read and shown not to already cover this
  judgment — the same discipline FWD-017's own R3 applied), OR a
  `functional_correctness` finding citing an existing or new `DOM-*` id
  when the divergence traces to a demonstrable implementation bug rather
  than a genuine interpretation gap. A divergence MUST NOT be filed under
  both, and MUST NOT be silently dropped when the threshold is crossed
  (FM-6, FM-2).
- R10: WHEN `fde.config.toml` and `templates/fde.config.template.toml`
  gain a `[walkthrough]` section, it MUST be commented out by default,
  carrying at minimum `enabled` and `divergence_threshold` keys, and MUST
  follow `[erosion]`'s exact silence discipline: absent section, the
  gate adds nothing; `enabled = true` with no `divergence_threshold`
  declared reports "not measured," never a vacuous pass. A new gate id
  (proposed: `walkthrough`) is added to `runtime/verify.py`'s
  `KNOWN_GATES`, following the `explicit`-parameter pattern
  `gate_erosion`/`gate_survey`/`gate_scrum` already use (FM-8).
- R11: WHEN `runtime/graph.py` is extended for this capability, it MUST
  add node kinds for the intended model, each perceived model, and the
  divergence artifact, and edge kinds connecting demand → intended-model
  → (walked_by) → perceived-model (×2) → (confronted_by) → divergence →
  (cites) → finding, so `fde-graph --demand <id>` and `--central` surface
  the chain. `forbidden_orphans()` MUST gain the matching impossible-state
  checks: a `divergence.toml` referencing a perceived-model file that was
  never persisted, or existing with no `intended-model` counterpart, is a
  forbidden orphan — exact node/edge naming left to architecture,
  consistent with `design.py`'s "impossible states, never incomplete
  ones" discipline (FM-9).
- R12: WHEN this capability ships, `tests/test_spec_integrity.py`'s
  `test_five_roles_with_write_scope` MUST be updated — not deleted, not
  weakened for the other five — to assert six role ids, and to special-
  case only `walkthrough-evaluator`'s `write_scope` as the one
  permitted-empty value; every other role's non-empty assertion MUST
  still fail if any of them regresses. A new `tests/test_walkthrough.py`,
  built on-disk-fixture-and-assert-on-the-gate in `test_divergence.py`'s
  style (never a tautological grep-for-a-word test, the exact lesson
  FWD-010's own review recorded), MUST cover: the R7 metric's three
  boundary cases (identical canonical-phrase sets → 0, fully disjoint →
  1, partial overlap → a hand-computed intermediate value); the R10
  gate's silent/measured/breach states; and a fixture proving the R4
  ordering requirement — an intended-model absent MUST be a failure the
  test can observe, not a silent pass (FM-2, FM-5, FM-8).
- R13: The implementation MUST NOT write under `evals/journeys/**`, MUST
  NOT reuse the `*.journey.toml` manifest shape for any artifact this
  demand produces, and MUST NOT add or restate coverage already held by
  DOM-7, USE-13, or USE-14. `skills/fde-walkthrough/SKILL.md` MUST state,
  in one sentence, the distinction from FWD-017: a journey executes a
  KNOWN planned path and measures completion/drift/hesitation on it; a
  walkthrough has no plan, explores cold, and measures whether two
  independent blind interpretations of the whole first-contact surface
  agree (FM-7).
