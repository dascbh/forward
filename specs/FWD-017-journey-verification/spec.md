# FWD-017 — Journeys are verified by execution, not narrated

Triage: surfaces 3 (skill doc, quality/domain catalogs, runtime gate) capped
to 3 · public · reversible · ~350-450 LOC → score 4 → **M** (spec, impl,
adversarial 2 rounds, promotion, ADR-0013).

## Problem

An agent driving a real browser (Claude Code, Codex, or the
`claude-in-chrome` tool family) can author an executable journey that
traces to a demand's EARS `R#` requirements end to end, and can probe UX
friction through real execution instead of a static screenshot. That
capability has no home in this kernel yet — but not because the kernel
lacks the sockets for it. Two already claim exactly this ground:

- `fde-design`'s **"Design QA"** section already names Playwright and
  already treats it as the empirical pillar of UI (I1) — an executable
  journey is the member missing from a list this section already has,
  not a new discipline.
- `fde-design`'s **"User validation"** section already carries the
  doctrine "synthetic users generate hypotheses and tasks, never
  findings", inherited from the absorbed `prancheta` suite. The limit an
  agent-driven journey needs — that completing a planned path proves the
  path exists, never that an unprepared human finds it without hesitation
  (Suchman's situated-action boundary) — is the same conclusion in the
  same doctrine, not a competing one.
- The adversarial role's heuristic pass already judges
  `usability_accessibility` against a principle catalog (`USE-*`), and
  `finding-discipline` (I8) already rejects any finding that cites only a
  persona instead of a `probe` or `principle` — it already rejects a
  finding that cited only "the agent got through" as evidence.
- `usability_research` already exists as a Vector B domain (depth 0 in
  this project's own `[derived.depths]`, `user_facing = false`).

The decision this demand makes is not "build something new" — it is
sharpen two existing sockets and the one gate that polices whether a
declared requirement has a matching eval (I1), instead of opening a sixth
role, a new skill file, or a new invariant. `fde-review` stays untouched:
it is deliberately attribute-agnostic (it derives probe order from
`[weights]` and never hardcodes one attribute's method), so the technique
lives where the UX method already lives — inside `fde-design`.

This repository has no real UI (`user_facing = false` in its own
`fde.config.toml`). What this demand can prove here is structural: the
manifest shape parses, the gate's token match is correct, the catalog
stays free of collisions. It cannot prove a journey catches real human
friction, because there is no real screen in this repository for an agent
to be confused by. That field proof is out of scope for FWD-017 and is
named, not hidden — it is the next demand (FWD-018), against a minimal
fixture, the first time a script under `evals/journeys/**` actually
drives a browser in CI rather than being parsed by a fixture test.

## Boundaries

**Always**
- Read the full current text of `USE-1..12` and `DOM-1..6`
  (`spec/dimensions/quality-attributes.toml`) before cutting any new
  principle id; a new id is used only for judgment none of them already
  cover.
- Keep the committed Playwright `script` the only artifact the gate or CI
  ever executes; `authored_with` documents technique and is never a
  dependency of a passing gate (I6).
- Extend the existing "synthetic users generate hypotheses and tasks,
  never findings" sentence — never delete, reword, or weaken it.
- State, in the sharpened gate's pass/fail message, which demand and
  which `R#` tokens were checked, so a reader sees what was measured
  instead of trusting a boolean.

**Ask first**
- If reading `USE-1..12`/`DOM-1..6` in full shows genuine overlap with a
  proposed new principle (most likely candidate: `USE-4`, error
  prevention/recovery, against a reversibility-flavored probe) — narrow
  to an `adversarial_probes` phrase under the existing id instead of
  forcing a new one to look "different enough".
- If walking `specs/**` inside a staged/pre-commit-tier check turns out
  costly at scale, ask whether the sharpened check belongs at the CI tier
  instead — a speed regression on `--staged` is a cost this demand did
  not budget.

**Never**
- A new skill file (e.g. `fde-journey`), following the `fde-X` ↔
  `runtime/X.py` convention `fde-erosion`/`fde-graph` use.
- A new entry in `spec/roles.toml`, a new invariant in
  `spec/invariants.toml`, a new domain in
  `spec/dimensions/technical-domains.toml`, a new gate id in
  `runtime/verify.py`'s `KNOWN_GATES`, or a new `[journey]` section in
  `fde.config.toml`.
- Treating "the agent completed the journey" as a closed
  `usability_accessibility` finding by itself.
- Claiming this repository proved the mechanism "in the field" — it has
  no real UI; the proof here is structural (fixtures) only.

## Failure modes

- FM-1: the gate sharpening false-positives — it flags a demand with no
  design surface, or a design surface whose `acceptance.md` declares no
  `R#` tokens at all, as if it owed journey coverage, reintroducing
  ceremony on demands that never claimed a UI surface.
- FM-2: the new `fde-design` text on agent-driven journeys contradicts,
  instead of extends, the existing synthetic-user-never-evidence
  doctrine — e.g. by phrasing the addition so a completed agent run reads
  as a finding rather than a hypothesis.
- FM-3: a new `heuristic_principles` id under `usability_accessibility`
  collides with or restates an existing `USE-*`/`DOM-*` entry (most
  likely `USE-4`, already covering error prevention/recovery, or `USE-1`,
  already covering status visibility) instead of covering genuinely
  uncovered judgment.
- FM-4: the interactive agent session that authors or drives the journey
  becomes what the gate actually depends on — instead of the committed,
  deterministic Playwright script — putting a framework component (the
  agent, the browser-driving tool) on the critical path CI runs. This is
  an I6 violation by definition: the deliverable must be runnable without
  the FDE present.
- FM-5: `usability_research`'s `min_depth_when` derivation becomes
  circular — deriving the domain's required depth from "journey manifests
  exist" would make the artifact the gate is supposed to require also the
  signal that triggers requiring it.
- FM-6: the demand grows past what the two existing sockets need — a new
  skill, role, invariant, gate id, or config section — repeating the
  bloat ADR-0004 already rejected once when the design suite was
  absorbed.

## Requirements (EARS)

- R1: WHEN `fde-design`'s "Design QA" section documents browser-executed
  journeys, it MUST describe a manifest at
  `evals/journeys/<demand-id>/<slug>.journey.toml` paired with a
  committed Playwright script, carrying at minimum `id`, `demand_id`,
  `requirements` (the `R#` tokens from that demand's `spec.md` the
  journey verifies), `script` (the client-runnable artifact CI executes),
  and `authored_with` (the tool used to discover the flow) — and MUST
  state explicitly that `authored_with` is never on the gated critical
  path: CI runs `script`, never an agent session (FM-4).
- R2: WHEN `fde-design`'s "User validation" section is extended for
  agent-driven journeys, the addition MUST sit adjacent to, and MUST NOT
  replace or reword, the existing "synthetic users generate hypotheses
  and tasks, never findings" sentence. It MUST state the Suchman
  boundary: an agent completing a journey along a planned path
  demonstrates the path exists, never that an unprepared human finds it
  without hesitation. "The agent succeeded" MUST NOT by itself close a
  `usability_accessibility` finding — only a demonstrated friction
  (probe) or a cited principle closes one (FM-2).
- R3: WHEN `spec/dimensions/quality-attributes.toml` gains new
  `heuristic_principles` under `usability_accessibility` for judging
  executed journeys, each new id MUST be checked against the full
  existing text of `USE-1..12` first and MUST NOT duplicate or restate an
  existing principle's coverage. New ids continue the sequence from
  `USE-13`. The judgment they cover, if genuinely uncovered, includes:
  ambiguity or hesitation as a finding in itself even when the journey
  completes, and the Suchman limit that agent success is not usability
  evidence (FM-3).
- R4: WHEN `spec/dimensions/quality-attributes.toml` gains new
  `adversarial_probes` under `usability_accessibility` for
  browser-executed journeys, they MUST be bare phrases — no id, matching
  the catalog's existing convention — covering at minimum: an ambiguous
  next action, an irreversible action taken with no confirmation or
  undo, and a state change with no visible feedback. A probe that only
  surfaces by executing a multi-step flow (not visible on one static
  screen) and is empirically demonstrable belongs to
  `functional_correctness` as a new `DOM-*` id (continuing from `DOM-7`)
  instead of `usability_accessibility` — `USE-3` already covers static
  cross-screen consistency and MUST NOT be duplicated.
- R5: WHEN `spec/dimensions/technical-domains.toml`'s `usability_research`
  domain is extended, its `artifacts` list MUST add "journey manifest
  under evals/journeys/** tracing to R#", and it MUST gain a
  `min_depth_when` field bringing it to parity with the other 8 domains
  that already declare one. The trigger MUST stay
  `user_facing and has_frontend => >= 1` — unrelated to whether journey
  manifests have been authored yet — so the derivation is not circular
  (FM-5).
- R6: WHEN `runtime/verify.py`'s `gate_eval_coverage()` runs and a demand
  under `specs/<id>/` has a design surface (`design.has_design_surface()`)
  whose `acceptance.md` declares one or more whole-token `R\d+` criteria,
  the gate MUST additionally require every such token to appear, as a
  whole token (`R1` MUST NOT be satisfied by `R10` or `R11`), somewhere
  under that same demand's own evals namespace — paths containing
  `<demand-id>` under `evals/**` (e.g. `evals/journeys/<demand-id>/`). A
  token present only under an unrelated demand's evals tree MUST NOT
  satisfy the check. WHEN a demand has no design surface, or has one but
  zero `R\d+` tokens in `acceptance.md`, the sharpened check MUST add
  nothing — existing `eval-coverage` behavior for that demand is
  unchanged (FM-1). No new id is added to `KNOWN_GATES`.
- R7: WHEN this sharpening ships, `tests/test_verify.py` MUST cover at
  least: green (every `R#` of a design-surface demand's `acceptance.md`
  is present under that demand's own evals tree), red (at least one `R#`
  declared but absent), silent for a demand with no design surface,
  silent for a design surface with zero `R#` tokens declared, and the
  token-boundary case (`R1` declared, only `R10` present, still red).
  `tests/test_spec_integrity.py` MUST continue to pass unmodified — no
  code change in that file — against the new catalog entries (FM-1,
  FM-3).
- R8: The implementation MUST NOT add a new skill file, a new entry to
  `spec/roles.toml` or `spec/invariants.toml`, a new domain to
  `spec/dimensions/technical-domains.toml`, a new gate id to
  `KNOWN_GATES`, or a new section to `fde.config.toml`. Journey
  verification is scope-derived per demand — from an existing design
  surface plus declared `R#` criteria — never a project-level toggle
  (FM-6).
