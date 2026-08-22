---
demand: FWD-017
date: 2026-08-22
decision: promote
---

# Promotion decision — FWD-017 journeys are verified by execution, not narrated

Confronting evidence against `specs/FWD-017-journey-verification/acceptance.md`
(dated 2026-08-22, amended 2026-08-22 after F6) against the accumulated
history bcbb734 (spec + ADR-0013 + implementation) through 3683342 (round
4 adversarial close) — 7 commits, four isolated review rounds.

| criterion | evidence | met |
|---|---|---|
| R1: Design QA gains browser-executed-journey paragraph — manifest shape, `authored_with` never on the gated critical path | `skills/fde-design/SKILL.md:269-293` — manifest fields `id`/`demand_id`/`requirements`/`script`/`authored_with`, states plainly "CI runs `script`, always; an agent session never runs during promotion or CI (I6)" | yes |
| R2: User validation gains Suchman sentence adjacent to, not replacing, the synthetic-user sentence | `skills/fde-design/SKILL.md:295-309` — original "Synthetic users generate hypotheses... not evidence" sentence intact verbatim, new sentence follows it in the same paragraph | yes |
| R3: `usability_accessibility` gains USE-13/14, checked against full existing text, no restatement | `spec/dimensions/quality-attributes.toml:203-204` — USE-13 (hesitation as finding), USE-14 (agent completion ≠ evidence); round 1 explicitly diffed these against USE-1..12 and found no collision | yes |
| R4: 3-4 new `adversarial_probes`; execution-only findings filed as `DOM-7` under `functional_correctness`, not duplicating `USE-3` | `spec/dimensions/quality-attributes.toml:210-212` — 3 probes added (ambiguous action, irreversible/no undo, no feedback); `:47` DOM-7 exists and distinguishes itself from USE-3 by verification method, not scope | yes — R1 finding F4 (DOM-7 mischaracterized USE-3's own text) fixed in ea1822d, wording now accurate |
| R5: `usability_research` gains `artifacts` entry + `min_depth_when`, trigger non-circular | `spec/dimensions/technical-domains.toml:57-62` — trigger `"user_facing and has_frontend => >= 1"`, derived from the domain's own pre-existing `derived_from`, not from journey-manifest existence | yes — the ADR/acceptance's wrong precedent citation (F6, `design_system`'s trigger) corrected by amendment; the shipped trigger itself was always right |
| R6: `gate_eval_coverage()` sharpened — token-boundary, manifest-parsed (not grepped), containment against escape (parent traversal, absolute path, symlinked script/manifest/intermediate dir, symlinked demand-id root) | `runtime/verify.py:94-318`, `_journey_coverage`/`_no_symlink_descendant` — closes F1 (substring aliasing), F2 (narration), F10 (leaf escape), F13 (root-directory symlink) with one categorical per-component walk | yes |
| R7: `tests/test_verify.py` covers green/red/silent×2/token-boundary; `tests/test_spec_integrity.py` unmodified | `tests/test_verify.py:144-310`+ — all required cases present plus 8 additional escape-route tests (F1/F2/F10/F13 fixtures); `git log --oneline bcbb734..HEAD -- tests/test_spec_integrity.py` empty, 11/11 green against the new catalog entries | yes |
| R8: no new skill file, role, invariant entry, Vector B domain, gate id, or config section | Vector B still 9 domains; `spec/roles.toml` untouched; `spec/invariants.toml`/`fde.config.toml` diffs are version-bump only (`0.12.2`→`0.13.0`); `KNOWN_GATES` unchanged; no `skills/fde-journey/` | yes |
| ADR-0013 records rejected alternatives, discloses no-real-UI limit honestly, amendment records F5/F6 | `docs/adr/0013-journeys-are-executed-not-narrated.md` — 3 rejected options named with reasoning; Consequences section states the mechanism is proven structurally only here, field proof deferred to FWD-018; Amendment section (2026-08-22) records both F5 and F6 without rewriting the original Decision | yes |
| Full suite + `verify --all` green; adversarial rounds confront the four named questions; `finding-discipline` holds | 232 tests OK; 17/17 gates green (`I8` 102 findings, every one probe- or principle-cited); rounds 1-4 in `reviews/FWD-017/findings.toml` explicitly tested all four named questions plus escape-route search beyond them | yes |

## Note on the review

Two rounds were planned (M sizing); four ran, on the review doctrine's
own three-cycle escalation bound plus the project owner's explicit
go-ahead, because the same defect class recurred three times running,
each time one layer further out: F1/F2 (demand-id aliasing, narration)
in round 1; F10 (the `script` leaf escaping containment) in round 2;
F13 (the demand-id directory itself as a symlink, defeating containment
at its root) in round 3. Round 3's escalation note is explicit that this
was a recurring pattern, not three unrelated bugs. f4c6445 replaced the
resolve()-and-compare approach entirely with a categorical per-component
symlink walk (`_no_symlink_descendant`) — closing the class rather than
patching another instance of it. Round 4 verified that fix against 10
further symlink-chain variants (including cases the shipped tests do not
cover: a symlinked manifest leaf, a two-hop chain, a dangling symlink, a
self-referential loop) plus two non-symlink escape attempts (hard link,
FIFO); zero new findings, F9-F12 re-verified clean. Round 4's `probed`
log also records one accepted, deliberately-not-filed limit: the passing
message's wording ("traces to a real, EXECUTED journey") is imprecise —
the check confirms the script exists, never that it runs — a defect two
prior rounds examined and consciously declined to file as its own
ticket, since the mechanism's declared boundary (existence, not
originality or execution, ADR-0013's own words) already discloses this.

Two non-blocking, honest corrections shipped alongside the fixes rather
than being smoothed over: F4 (DOM-7's own justifying text
mischaracterized the USE-3 principle it distinguished itself from) and
F6 (the ADR/acceptance cited the wrong domain's trigger as precedent).
Neither changed a decision; both are recorded as amendments rather than
silently rewritten history.

## Decision

**Promote.** Every R1-R8 criterion traces to evidence on disk, the ADR
names its rejected alternatives and discloses its own proof limit
without hedging (this repository has no real UI; FWD-017 proves the
mechanism structurally, not in the field), and four rounds of isolated
adversarial review — the last two beyond the planned budget, on a
recurring defect class the review doctrine's own escalation rule covers
— converge on zero open findings. Full suite (232 tests) and the client
gate (17/17) are green at 3683342. The one disclosed residual limit
(the passing message overstates "executed" when the check only confirms
existence) is accepted as a declared boundary, not a defect, consistent
with what ADR-0013 and `acceptance.md` both stated the check would and
would not prove. Field proof of the mechanism against a real UI — the
one thing this demand explicitly could not test here — is out of scope
by the ADR's own words and is already named as FWD-018.
