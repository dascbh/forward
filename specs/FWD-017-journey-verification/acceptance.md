---
date: 2026-08-22
demand: FWD-017
---

# Acceptance — FWD-017 journeys are verified by execution, not narrated

Context: `fde-design` already names Playwright inside "Design QA" and
already carries the synthetic-user-never-evidence doctrine inside "User
validation"; the adversarial role's heuristic pass already judges
`usability_accessibility` against a principle catalog, and
`finding-discipline` already rejects a finding backed only by a persona.
This demand sharpens those existing sockets and the `eval-coverage` gate
that already polices requirement-to-eval traceability (I1) — it does not
open a new role, skill, invariant, or config surface.

- `skills/fde-design/SKILL.md`'s "Design QA" section gains a paragraph
  documenting `evals/journeys/<demand-id>/<slug>.journey.toml` paired
  with a committed Playwright script. The manifest shape carries `id`,
  `demand_id`, `requirements` (the `R#` list from that demand's
  `spec.md`), `script` (the client-runnable artifact CI executes), and
  `authored_with` (the tool that discovered the flow — `claude-code`,
  `codex`, `claude-in-chrome`, or similar). The paragraph states, without
  hedging, that `authored_with` is never on the gated critical path: CI
  runs `script`, an agent session never runs during promotion or CI
  (I6).
- "User validation" gains one sentence, placed adjacent to — never
  replacing or rewording — the existing "Synthetic users generate
  hypotheses and tasks, never findings — stamp their artifacts
  '[synthetic — not evidence]'" sentence. The new sentence states the
  Suchman limit: an agent completing a journey along a planned path
  proves the path exists, never that an unprepared human finds it without
  hesitation; "the agent succeeded" does not by itself close a
  `usability_accessibility` finding — only a demonstrated friction
  (probe) or a cited principle does.
- `spec/dimensions/quality-attributes.toml`'s `usability_accessibility`
  gains 2–3 new `heuristic_principles`, numbered `USE-13` onward, each
  verified — by reading the full existing text of `USE-1..12` first —
  to cover judgment none of them already do (candidates: ambiguity or
  hesitation as a finding even on a completed journey; the Suchman
  limit that agent success is not usability evidence). None restates
  `USE-4` (error prevention/recovery) or any other existing id. It also
  gains 3–4 new `adversarial_probes` phrases (no id, matching the
  catalog's existing convention): an ambiguous next action, an
  irreversible action taken with no confirmation or undo, a state change
  with no visible feedback. Any probe that only surfaces via a multi-step
  execution and is empirically demonstrable is filed under
  `functional_correctness` as a new `DOM-*` id (from `DOM-7`) instead,
  not duplicating `USE-3`.
- `spec/dimensions/technical-domains.toml`'s `usability_research` domain
  gains `"journey manifest under evals/journeys/** tracing to R#"` in its
  `artifacts` list and `min_depth_when = "user_facing and has_frontend
  => >= 1"` — bringing it to parity with the other 8 domains that
  already declare the field. The trigger is unchanged from what
  `design_system` already uses: not derived from whether journeys exist,
  so the addition is documentary consistency, not new enforcement (no
  gate reads `min_depth_when` automatically today, same as every other
  domain).
- `runtime/verify.py`'s `gate_eval_coverage()` is sharpened: for any
  demand with a design surface (`design.has_design_surface()`) whose
  `acceptance.md` declares one or more `R\d+` tokens, every such token
  must also appear, as a whole token, under that demand's own evals
  namespace (a path containing `<demand-id>` under `evals/**`). A demand
  with no design surface, or a design surface declaring zero `R#`
  tokens, is untouched by the new check — verified both directions. No
  id is added to `KNOWN_GATES`; `--gate eval-coverage` remains the only
  invocation surface.
- Tests: `tests/test_verify.py` asserts green (every `R#` present under
  the demand's own evals tree), red (at least one `R#` missing), silent
  for no design surface, silent for a design surface with zero `R#`
  tokens, and the token-boundary case (`R1` declared, only `R10` present
  under evals, still red — no prefix false-positive).
  `tests/test_spec_integrity.py` passes unmodified — no code change in
  that file — against the new catalog entries, exercising its existing
  prefix-to-attribute mapping and id-uniqueness checks.
- Nothing else changes: no new skill file, no new entry in
  `spec/roles.toml` or `spec/invariants.toml`, no new domain in
  `spec/dimensions/technical-domains.toml` (Vector B stays 9 domains), no
  new gate id, no new `fde.config.toml` section, `fde-review` untouched.
- `docs/adr/0013-journeys-are-executed-not-narrated.md` records the
  decision and names the rejected alternatives (a dedicated `fde-journey`
  skill; a new Vector B domain derived from journey manifests; treating
  agent completion as usability evidence) and states honestly that this
  repository has no real UI (`user_facing = false`) — the mechanism is
  proven structurally here (fixtures), never in the field, until a real
  client project with a UI surface adopts it. That field proof —
  a fixture UI plus a journey script actually driving a browser in CI —
  is out of scope for FWD-017 and named as the next demand (FWD-018).
- Full suite (`python3 -m unittest discover -s tests`) and
  `python3 bin/fde/verify.py --all` green at the demand's closing commit.
  Two isolated adversarial rounds in `reviews/FWD-017/` (M sizing),
  specifically prompted to test: does the sharpened gate false-positive
  on a demand with no design surface or no `R#` tokens? does the new
  `fde-design` text contradict — instead of extend — the synthetic-user
  doctrine? does any new catalog id collide with or restate an existing
  `USE-*`/`DOM-*` entry? can the gate be satisfied by an agent session
  instead of the committed script? `finding-discipline` continues
  rejecting any finding backed only by a synthetic persona without
  `probe`/`principle` — a regression there is a blocking finding.
  `promotions/FWD-017/decision.md` confronts this list.
