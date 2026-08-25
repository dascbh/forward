---
demand: FWD-018
date: 2026-08-25
decision: promote
---

# Promotion decision — first contact is blind, not scripted

Confronting `specs/FWD-018-first-contact-walkthrough/acceptance.md` (dated
2026-08-22) against the accumulated history c3f130f (spec + ADR-0014 +
original implementation) through ca57bc1 (fresh-cycle round-2 close) —
14 commits, six isolated review rounds across two structurally different
implementations of the same declared capability.

| criterion | evidence | met |
|---|---|---|
| `spec/roles.toml` sixth role, full schema (`write_scope=[]`, `denied_paths`, `isolation_mode="fresh-agent"`, `context_policy="blind"`, `satisfies=[]`, `tools:` allowlist) | `spec/roles.toml:117-143` — every field present as specified; header reads "Six roles." (`:4`); `tools` list is exactly the ten browser-automation tools, no `Read`/`Grep`/`Glob`/`Bash`/`Edit`/`Write`/`NotebookEdit`/`WebSearch`/`WebFetch` | yes |
| `agents/fde-walkthrough-evaluator.md` + `.claude/` mirror carry the same `tools:` allowlist; body states fresh-invocation independence and minimal initial framing | Both files byte-identical (`diff` confirmed); frontmatter `tools:` line matches `spec/roles.toml` exactly; "Your independence" and "What you were given" sections state both requirements verbatim | yes |
| `skills/fde-walkthrough/SKILL.md` documents trigger conditions, two-run protocol, architecture-compiled `intended-model.md` strictly before either run, confrontation procedure, admissibility table adjacent to (not replacing) `fde-design`'s existing text | `skills/fde-walkthrough/SKILL.md` — all sections present; "The intended model" section states ordering is load-bearing and cites `forbidden_orphans()` as the structural enforcement; admissibility table's own footnote correctly scopes the "structural" claim to the `loop` tier (see review note below) | yes |
| Perceived-model schema: named enumerable slots, canonical short phrases, one free-prose slot never scored | `agents/fde-walkthrough-evaluator.md`'s "What to return" — seven required TOML keys, each typed; `primary_actions`/`action_consequences`/`unclear_points` required to be short canonical phrases "compared literally, by another program" | yes |
| `runtime/walkthrough.py` computes deterministic/symmetric/`[0,1]`-bounded score from stdlib only; fixtures for identical/disjoint/partial-overlap | `runtime/walkthrough.py:361-401` (`slot_distance`, `compute_divergence`) — pure set/string ops, no embedding, no LLM call; `tests/test_walkthrough.py::TestComputeDivergence` — identical scores 0.0, disjoint scores 1.0, partial overlap scores exactly 0.222 with per-slot intersection/union/distance matching the ADR's own worked example | yes |
| `walkthroughs/<demand-id>/` directory holds both perceived models + `divergence.toml`; the role granted write scope there gets a matching `runtime/guard.py` entry in the same change | `spec/roles.toml:50-54` grants `architecture` `write_scope` including `walkthroughs/**`; `runtime/guard.py:40` — `"fde-architecture": ("docs/adr/", "specs/", "walkthroughs/")` present. No `walkthroughs/**` directory exists on disk yet — no demand has actually run the mechanism against a real target (see review note) | yes, mechanism; not yet exercised |
| `adversarial`'s `inputs` gain `walkthroughs/**:read`; heuristic pass classifies each divergence as `USE-15` or a `DOM-*` finding, never both, never dropped | `spec/roles.toml:88` — `"walkthroughs/**:read"` present; `spec/dimensions/quality-attributes.toml:205` — `USE-15` added after the full `USE-1..14` text was read (ADR-0014 §9); `skills/fde-walkthrough/SKILL.md`'s "Handoff to review" states the either/or/never-both/never-dropped rule | yes |
| `[walkthrough]` in `fde.config.toml`/template, commented out, `[erosion]`'s silence discipline; `KNOWN_GATES` gains `walkthrough` | `fde.config.toml:93-99` — commented out, with the disabled reason stated ("this kernel repo has no UI to run a walkthrough"); `runtime/verify.py:43` — `"walkthrough"` in `KNOWN_GATES`; `gate_walkthrough` (`:551-564`) follows the `gate_erosion` shape exactly; confirmed live: `python3 bin/fde/walkthrough.py --gate` → "no [walkthrough] budget declared — walkthrough mode off", exit 0 | yes |
| `runtime/graph.py` gains `intended-model`/`perceived-model`/`divergence` nodes and `modeled_by`/`walked_by`/`confronted_by`/`cites` edges; `forbidden_orphans()` gains the three impossible-state checks | `runtime/graph.py:262-324` (node/edge construction), `:424-466` (the three orphan checks: dangling pointer, perceived-model with no intended-model counterpart, divergence with <2 `confronted_by` edges) — all present, matching R11/FM-9; mirrored byte-identically in `bin/fde/graph.py` | yes |
| `test_spec_integrity.py` asserts six role ids, permits only `walkthrough-evaluator`'s empty `write_scope`; new `tests/test_walkthrough.py` in `test_divergence.py`'s on-disk-fixture style | `tests/test_spec_integrity.py:106-130` — `test_six_roles_with_write_scope`, five roles' non-empty assertion intact, `walkthrough-evaluator` the one named exception; `tests/test_walkthrough.py` — 869 lines, 14 test classes covering the three boundary cases, gate silent/measured/breach states, the R4 ordering fixture, and (added across the review) unexpected-key rejection, the `_REQUIRED_FIELDS` single-source-of-truth in both directions, `target_unreachable`, `observed_text` | yes |
| Nothing writes under `evals/journeys/**` or reuses `*.journey.toml`; no restated DOM-7/USE-13/USE-14 coverage; one-sentence FWD-017 distinction in the skill | `grep -rn "evals/journeys\|\.journey\.toml"` across `runtime/walkthrough.py`, `skills/fde-walkthrough/`, `agents/fde-walkthrough-evaluator.md` — zero hits; `skills/fde-walkthrough/SKILL.md:8-16` states the journey/walkthrough distinction in one paragraph, explicitly disclaiming re-litigation of DOM-7/USE-13/USE-14 | yes |
| `docs/adr/0014-*.md` records the role-vs-mode decision, the `tools:`-allowlist-over-guard-hook decision, write-scope resolution, directory placement, and the calibration question, each with rejected alternatives named | `docs/adr/0014-first-contact-walkthrough.md` — full "Options considered" section covers all five, each with named rejected alternatives (guard-hook read-interception, blind-mode flag, staying qualitative, folding into `fde-design`, mandatory-gate-now); two dated amendments (2026-08-22 F4, 2026-08-25 F12) correct rather than silently rewrite | yes |
| Full suite + `verify.py --all` green at closing commit; two isolated adversarial rounds test the five named questions; `finding-discipline` (I8) holds; this document confronts the list | `python3 -m unittest discover -s tests` → 298 tests, OK (re-run fresh, this session, at ca57bc1); `python3 bin/fde/verify.py --all` → 17/17 gates green including I8 ("105 finding(s), every one cites a probe or a principle"), TRACE, DIVERGE, SURVEY; the five named questions are answered across the six actual rounds (see note below) | yes |

## Note on the review

This demand's review history is longer and structurally different from
what M-sizing (2 rounds) names, and that difference is worth stating
plainly rather than folding into the table above.

**What actually happened, in order.** The original implementation
(c3f130f) parsed a `walkthrough-evaluator` run's returned perceived model
out of free markdown prose, by heuristically matching section headings.
Four consecutive review rounds against that implementation each found a
new, reproducible way to misclassify a block of that prose: F2/F3 (round
1, alias matching too fragile), F8 (round 2, the positional fallback
assumed a fixed heading order), F11 (round 3, unconditional priority
between the positional and content-based guesses was itself wrong), F12
(round 4, the one branch F11's fix deliberately left untouched was exactly
as fragile as every branch the prior three rounds had each closed). Three
of those four rounds' fixes were blocking. This is the review doctrine's
own recurring-pattern signal (`skills/fde-graph/SKILL.md`, `--recurring`)
firing on itself — the same `functional_correctness` weakness, in the same
function, four rounds running — and it produced a structural response, not
a fifth patch: ADR-0014 was amended (cad7947) to replace the entire
heuristic-parsing mechanism with structured TOML output carrying seven
required, fixed-type keys (b3b1cba). This eliminates the category of
defect (guessing which of four fields a block of free text belongs to),
not one more instance of it — the same class of move FWD-017's own F13 fix
made for its symlink-containment class, and the ADR says so directly
rather than claiming novelty.

A second, fresh 2-round cycle then ran specifically against the rewrite —
the M-sizing budget this demand was always entitled to, now spent against
the artifact that actually ships. Round 1 (c039a95) found 4 findings, 2
blocking: F13 (stale `.md` filename declarations left over from the
rewrite) and F14 (unexpected keys silently dropped, reintroducing a
softer version of the exact "guess or reject" problem the rewrite existed
to remove). Both were fixed (b1519e1), independently re-verified by round
2 rather than trusted from the commit message — including a
repo-wide `grep` sweep for F13 and eight constructed documents beyond the
original repro for F14. Round 2 (5102d46) found 3 more findings, F17-F19,
none blocking: a new regression test that didn't test what its own
docstring claimed and duplicated pre-existing coverage (F17), a
single-source-of-truth dict that was authoritative for validation but not
for the returned dict's shape (F18), and a scoping-trap hint that fired
unconditionally instead of only on its actual signature (F19). All three
were fixed (ca57bc1) and this session's fresh run of the full suite and
`verify.py --all` confirms zero open findings at HEAD.

Net: six review rounds, nineteen findings (F1-F19), zero left open. Every
finding against the now-deleted heuristic parser is moot in the sense that
the code it describes no longer exists — but it is not wasted evidence:
it is the reason a categorically simpler, structurally rejecting (not
guessing) artifact format shipped instead. The mechanism that actually
promotes here — the TOML schema, `parse_perceived_model`, the divergence
formula, the gate, the graph checks — received its own full 2-round M-size
review, closed clean, in addition to inheriting the discipline that forced
its existence.

**The tier-scoping correction (F4/F9), specifically.** One review finding
is worth naming on its own because it is exactly the kind of overclaim a
promotion decision has to catch: round 1 found that "the isolation
mechanism is structural, not instruction-based" was stated in the ADR and
`spec.md` with no scope limit, when this kernel's own tier doctrine
(`fde-doctor`) already says tool-restriction enforcement is a `loop`-tier
property only. The ADR's 2026-08-22 amendment and the corresponding
paragraph in `skills/fde-walkthrough/SKILL.md` (the footnoted admissibility
table row) now state this correctly: structural on `loop` (this project's
own tier), degrades to instruction-based — the same class the ADR itself
rejects elsewhere — on `commit`/`advisory` tiers. This was found, not
missed, and corrected in the same review cycle rather than surviving to
promotion; it is exactly the kind of self-correction the process should
produce.

**Does the honest scope limit hold, checked directly.** This repository
has no real UI to run a walkthrough against — `user_facing = false`,
confirmed in `fde.config.toml`'s `[triage]`, and no `walkthroughs/**`
directory exists anywhere in the repo (confirmed by `find`/`ls` this
session). The mechanism is proven here only structurally: the schema
rejects malformed input rather than guessing (unit-tested), the divergence
formula is deterministic/symmetric/bounded on constructed fixtures
(unit-tested against the ADR's own worked numbers), the gate reports "not
measured" rather than a vacuous pass when nothing exists to check
(confirmed live: `--gate` prints "walkthrough mode off" because
`[walkthrough]` is commented out), and the graph has no orphan states for
the new node kinds (unit-tested in `tests/test_graph.py`). Whether two
blind runs against a *real* interface produce a divergence score that
tracks real ambiguity is explicitly **not** answered by anything in this
repository, and — checked against every place that could plausibly
overstate this — it is not claimed to be, three separate times, in three
separate documents: `docs/adr/0014-first-contact-walkthrough.md`'s
Consequences section ("Whether two blind runs against a *real* interface
produce a divergence score that actually tracks real ambiguity... is
proven in the client projects... not here"), `specs/FWD-018-first-contact-walkthrough/spec.md`'s
Boundaries ("Never... Claiming this repository proves the mechanism 'in
the field'"), and `skills/fde-walkthrough/SKILL.md`'s own "Calibration"
closing section, worded almost identically to the ADR's. The disclosure is
consistent, not just present in one place and silently dropped elsewhere,
and it is not hedged into vagueness either — each statement names
specifically what IS proven (structural boundary behavior on fixtures) and
what is NOT (real-world calibration), matching the honest-limit precedent
this repo's own FWD-017/ADR-0013 already set for journeys. This limit is
disclosed accurately, not overstated and not buried.

## Decision

**Promote.** Every criterion in `acceptance.md` traces to evidence on
disk or to a live, reproduced command run this session. The one criterion
marked "mechanism, not yet exercised" — the `walkthroughs/<demand-id>/`
directory and its guard entry — is a structural capability with no live
instance because this repository has never had a target to run it
against; that absence is itself declared, correctly, as the demand's
honest scope limit, not concealed as if the capability had been field-
proven. Full suite (298 tests) and the client gate (17/17, including I8's
105 cited findings) are green at ca57bc1, reproduced fresh in this
session, not taken on faith from a prior report. Six isolated adversarial
rounds — far beyond the two the M-sizing budget named — converge on zero
open findings; the excess is explained, not hidden: four of those rounds
found a genuine recurring defect in an implementation that has since been
deleted in its entirety and replaced by a structurally simpler one, which
then received its own full, clean 2-round cycle. A finding that could have
shipped as an overclaim (the unscoped "structural isolation" claim, F4/F9)
was caught and corrected within review, not left for promotion to catch.

No rollback plan or staged-rollout thresholds apply in the usual sense —
this is a framework capability addition to a kernel repository, not a
live service with traffic to cut over. The closest analogue is already
built in: `[walkthrough]` ships commented out in both `fde.config.toml`
and its template, so the capability is inert by default in every project
that installs this kernel version until a project owner deliberately
opts in; disabling it again, for a project that did opt in, is the same
one-line comment-out `[erosion]` already established the precedent for.
There is no first-hour-in-production check to run because nothing this
demand ships is on a path any existing gate, build, or runtime executes
by default.
