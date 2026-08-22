# ADR-0013 — Journeys are executed, not narrated

date: 2026-08-22
status: accepted

## Context

An agent driving a real browser (Claude Code, Codex, the `claude-in-chrome`
tool family) can author an executable journey that traces to a demand's
EARS `R#` requirements end to end, and can probe UX friction through real
execution instead of a static screenshot. The question this demand answers
is not whether that capability is worth having — it is whether it needs a
new place to live.

It does not, on the kernel's own precedent. Two sockets already claim this
ground:

- `fde-design`'s "Design QA" section is already named as "the empirical
  pillar of UI (I1)" and already lists Playwright `toHaveScreenshot()` per
  route as one of its checks. A browser-executed journey is the member
  missing from a list this section already keeps, not a new discipline
  next to it.
- `fde-design`'s "User validation" section already carries, inherited from
  the absorbed prancheta suite (ADR-0004), the sentence "Synthetic users
  generate hypotheses and tasks, never findings — stamp their artifacts
  '[synthetic — not evidence]'." The limit an agent-driven journey needs is
  the same conclusion, not a competing one: a persona simulated in text and
  an agent executing a real DOM are both a plan run without an unprepared
  human at the wheel.

Two more facts bound the decision. `finding-discipline` (I8) already
rejects any finding under `usability_accessibility` that does not cite a
`probe` or a `principle` — it already rejects a finding backed only by
"the agent got through." And `usability_research` already exists as a
Vector B domain (`spec/dimensions/technical-domains.toml`), currently the
only one of the nine domains with no `min_depth_when` field.

`fde-review` is not in scope for any of this. It is deliberately
attribute-agnostic — it derives probe order from `[weights]` and never
hardcodes one attribute's method — so wherever the journey technique lives,
it is not there.

## Options considered

- **A new dedicated skill (`fde-journey`)**, following the `fde-X` ↔
  `runtime/X.py` convention `fde-erosion`/`fde-graph`/`fde-design` already
  use — rejected. ADR-0004 rejected porting prancheta's thirteen skills
  wholesale for the same reason it names outright: it "bloats a
  deliberately thin kernel with method the model already carries." That
  reasoning applies here without adjustment. `fde-design` already names
  Playwright inside "Design QA" — a browser session that authors an
  executable journey is a sharper version of a check that section already
  owns, not a different discipline needing its own file, its own frontmatter
  trigger, and a fourth thing for `fde-sync` to keep consistent with the
  UI method it already documents next door.
- **A new domain in Vector B** (e.g. `browser_journey_verification`,
  sibling to `usability_research`) — rejected. Every existing domain's
  `derived_from` names a signal external to the domain's own artifacts —
  `has_database`, `exposes_api`, `has_frontend`, `data_class`. The only
  honest `derived_from` a new domain here could declare is "journey
  manifests exist under `evals/journeys/**`" — circular, because the
  artifact the domain would require to reach depth is the same artifact
  that would trigger requiring it. `usability_research` already covers
  this ground and derives from `has_frontend`/`user_facing`, signals that
  do not depend on whether anyone has authored a journey yet.
- **Treat a completed agent-driven journey as usability evidence in
  itself** — rejected, on Suchman's situated-action critique: an agent
  that completes a journey by following a plan demonstrates that the path
  exists, never that an unprepared human would find it without hesitation.
  Plan-execution and situated, moment-to-moment improvisation are
  different cognitive acts; success at the former proves nothing about the
  latter. Accepting "the agent succeeded" as a closed finding would let a
  synthetic run outrank the doctrine `fde-design` already states for a
  synthetic persona — the mechanism would quietly become stronger evidence
  than the thing it is built on top of, by virtue of clicking real pixels
  instead of narrating them. `finding-discipline` (I8) already forecloses
  this: a finding must cite a `probe` (demonstrated friction) or a
  `principle`, and neither is "the run finished."
- **Extend the two existing sockets, sharpen the one gate that already
  polices requirement-to-eval traceability, add principle/probe entries
  where genuinely uncovered** — accepted.

## Decision

No new role, skill file, invariant, gate id, Vector B domain, or
`fde.config.toml` section. Journey verification is scope-derived per
demand — from an existing design surface plus the `R#` criteria that
demand already declares in `acceptance.md` — never a project-level toggle.

**`skills/fde-design/SKILL.md`.** "Design QA" gains a paragraph
documenting a manifest at `evals/journeys/<demand-id>/<slug>.journey.toml`
paired with a committed Playwright script: `id`, `demand_id`,
`requirements` (the `R#` tokens from that demand's `spec.md` the journey
verifies), `script` (the client-runnable artifact CI executes), and
`authored_with` (the tool that discovered the flow). The paragraph states
without hedging that `authored_with` is never on the gated critical path —
CI runs `script`; an agent session never runs during promotion or CI (I6).
"User validation" gains one sentence placed adjacent to — never replacing
or rewording — the existing synthetic-user sentence, naming the Suchman
limit: an agent completing a journey along a planned path proves the path
exists, never that an unprepared human finds it without hesitation;
"the agent succeeded" does not by itself close a `usability_accessibility`
finding, only a demonstrated friction (probe) or a cited principle does.

**`spec/dimensions/quality-attributes.toml`.** `usability_accessibility`
gains 2–3 `heuristic_principles`, `USE-13` onward (the catalog runs
`USE-1..12` today, so the sequence is free) — checked first against the
full existing text to confirm no restatement: ambiguity or hesitation as a
finding in itself even on a journey that completes, and the Suchman limit
stated as a principle rather than left as prose only in the skill.
`USE-4` ("error prevention and recovery: destructive paths confirm; every
error names a way out; typed input is never lost") already covers
confirm/undo on destructive action — the new probe phrases about
irreversible action sit under `USE-4`, not a new id, because the judgment
is the same, only the technique that surfaces it (execution instead of
inspection) is new. It gains 3–4 `adversarial_probes` phrases, unnumbered
(matching the catalog's own convention: probes are bare phrases, ids exist
only on `heuristic_principles`), covering an ambiguous next action, an
irreversible action with no confirmation or undo, and a state change with
no visible feedback. `functional_correctness` gains a `DOM-7` if a probe
turns out to be empirically demonstrable and visible only across a
multi-step execution rather than one static screen — `USE-3` ("the same
concept has the same name and behavior everywhere") already owns static
cross-screen consistency and is not duplicated.

**`spec/dimensions/technical-domains.toml`.** `usability_research` gains
`"journey manifest under evals/journeys/** tracing to R#"` in `artifacts`
and `min_depth_when = "user_facing and has_frontend => >= 1"` — the same
trigger `design_system` already uses, unrelated to whether any journey
manifest has been authored, so the addition is documentary parity with the
other eight domains (all of which already declare the field) and not new
enforcement: no gate reads `min_depth_when` automatically today, on this
domain or any other.

**`runtime/verify.py`, `gate_eval_coverage()`.** Sharpened, not renamed:
for a demand with a design surface (`design.has_design_surface()`) whose
`acceptance.md` declares one or more whole-token `R\d+` criteria, every
such token must also appear, as a whole token, under that demand's own
evals namespace (a path containing `<demand-id>` under `evals/**`) — `R1`
is not satisfied by `R10` or `R11`. A demand with no design surface, or a
design surface declaring zero `R#` tokens, is untouched; existing
`eval-coverage` behavior for it does not change. No id is added to
`KNOWN_GATES`; `--gate eval-coverage` remains the only invocation surface.
This closes a real gap rather than an anticipated one: `eval-coverage`
today checks file-level granularity ("some eval was touched"), never
criterion-level granularity. Leaving that gap to the heuristic catalog
alone (`DOM-5`, "no orphans") would rank heuristic judgment ahead of an
empirical check for something a whole-token substring match can already
decide — the inverse of the primacy `verified_by` itself declares
(empirical before heuristic).

## Consequences

This repository has `user_facing = false` in its own `fde.config.toml`
and no real UI anywhere in it. What FWD-017 can prove here is structural
only: the manifest shape parses, the gate's token match is correct on its
boundary case, the catalog gains no collision. It cannot prove that a
journey catches real human friction, because there is no real screen in
this repository for an agent to be confused by — the same limit named in
the Options above applies reflexively to the kernel's own proof of itself.
That field proof is out of scope here and is named, the way
`discovery/survey.md` names its own unknowns rather than paper over them:
it is the next demand, FWD-018, against a minimal fixture UI, the first
time a script under `evals/journeys/**` actually drives a browser in CI
instead of being parsed by a fixture test.

Two sockets carry more weight than before without changing shape:
"Design QA" documents one more artifact kind it already had room for, and
"User validation" states a boundary that was already true of its
synthetic-user doctrine, now written down instead of left implicit. The
`eval-coverage` gate starts checking a granularity it always should have,
silently, for demands that never claimed a UI surface. Nothing is added
that a fourth demand would need to keep in sync by hand: no new file for
`fde-sync` to regenerate, no new toggle for a client to discover missing.
