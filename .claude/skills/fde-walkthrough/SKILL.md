---
name: fde-walkthrough
description: First-contact experience review — two independent, blind agent runs explore a running target cold and report what the interface communicated; confronted against an architecture-compiled intended model, divergence between the two runs is evidence about the artifact, never about users. Use for an M/L demand with a UI surface and a running target, after the wireframe is built and before promotion. Use when the user asks whether the interface explains itself to a stranger, wants a cold read / first-contact review / blind usability check, or asks whether two people would understand the product the same way on first sight.
---

# fde-walkthrough

A planned journey (`fde-design`'s "Browser-executed journeys") proves a
KNOWN path holds together end to end — the agent already has the plan.
This skill answers an earlier, different question: does the interface,
on first contact, communicate to a stranger what this product IS, what
they can do, and what happens if they do it? A journey cannot probe
that; a walkthrough has no plan at all, explores cold, and measures
whether two independent blind interpretations of the whole first-contact
surface agree (ADR-0014). It never re-litigates journey coverage
(DOM-7, USE-13, USE-14) and never writes under `evals/journeys/**`.

It is subordinate to `fde-design`, not a phase inside it — the same
relationship the `adversarial` *role* has to the `fde-review` *skill*
that invokes it. `fde-walkthrough` orchestrates; the role it invokes
twice, in isolation, is `walkthrough-evaluator` (`spec/roles.toml`).

## When this applies

| size | applies | when |
|---|---|---|
| XS / S | never | no UI design phase exists at this size to have an intended model for (`fde-design`'s own table) |
| M | opt-in, via `[walkthrough]` in `fde.config.toml` | after the wireframe is approved and the build exists, before promotion |
| L | opt-in, via `[walkthrough]` | after the wireframe is approved and the build exists, before promotion |

Opt-in at every size, deliberately — no "every M/L UI demand runs this
before promotion" mandate exists yet. `fde-design`'s own precedent for
journeys: ship the narrow structural check now, defer a completeness
mandate until real client usage shows the gap is worth forcing
(ADR-0014, Consequences).

## The two-run protocol (structural independence)

Each run is a separate, freshly-invoked instance of the
`fde-walkthrough-evaluator` role — never a fork, a cloned session, or a
second turn inside an existing one. Concretely, in Claude Code: two
separate subagent invocations of `fde-walkthrough-evaluator`, each
starting its own isolated context from scratch. Sharing a session
between the two runs, or seeding the second run's prompt with anything
from the first run's transcript, does not satisfy independence — it
manufactures agreement instead of testing for it (FM-3).

Each run's initial instructions carry nothing beyond the target
URL/endpoint and generic first-contact framing ("explore this as a
first-time visitor; report what you understand"). No spec language, no
wireframe description, no glossary term, no persona name, and no
paraphrase of the intended model — the role's `tools:` allowlist blocks
tool-based reads; it does nothing to stop this second, prompt-based leak
channel (FM-4).

```
WRONG — shares run A's turns with run B, and hands B a paraphrase:
    run_a = invoke("fde-walkthrough-evaluator", url)
    run_b = invoke("fde-walkthrough-evaluator", url,
                    prior_context=run_a.transcript,
                    hint="the previous run thought this was a checkout flow")

RIGHT — two independent processes/sessions, identical minimal framing:
    run_a = invoke_fresh("fde-walkthrough-evaluator", url, FIRST_CONTACT_FRAMING)
    run_b = invoke_fresh("fde-walkthrough-evaluator", url, FIRST_CONTACT_FRAMING)
    # run_b never sees run_a's output, the intended model, or anything
    # beyond FIRST_CONTACT_FRAMING + url. Neither knows the other exists
    # beyond "you are one of two runs" (the role's own framing).
```

The isolation is enforced structurally, not by instruction:
`walkthrough-evaluator`'s `tools:` frontmatter allowlist contains only
browser-automation tools — no `Read`, `Grep`, `Glob`, `Bash`, `Edit`,
`Write`, `NotebookEdit`, `WebSearch`, or `WebFetch`. `runtime/guard.py`
enforces write-scope only, never read-scope, and this repository's own
FWD-010 review (`reviews/FWD-010/findings.toml`, F1) already proved that
telling a model not to read something in a prompt is not enforcement —
absence of the tool is checkable by inspecting one file; best-effort
blocking of its use is not (ADR-0014).

## The intended model — compiled first, by architecture

Before either run is issued, the `architecture` role compiles
`specs/<demand-id>/design/intended-model.md`, synthesized from that
demand's existing `spec.md`, `flow.md`, `ia.md`, wireframe(s), glossary,
and `acceptance.md` — what the team actually intended to communicate. A
demand missing the design artifacts needed to synthesize one owes that
groundwork first, the same uncovered-root discipline
`design/foundation.md` already applies.

Ordering is load-bearing, not procedural tidiness: a run that could see
the intended model before or during its own exploration cannot produce
independent evidence about the interface — it would be grading the
interface against what it was just told to expect. `runtime/graph.py`'s
`forbidden_orphans()` makes this an observable graph state, not a
documentation promise: a perceived model on record with no
`intended-model` counterpart for its demand is a forbidden orphan.

## Confrontation — intended vs. perceived-A vs. perceived-B

Once both runs are on record, `runtime/walkthrough.py` computes a
deterministic divergence score between perceived-A and perceived-B
(stdlib only — see "The divergence metric" below), and the confrontation
step reads all three documents side by side:

- Where a perceived model asserts something the intended model does not
  (or denies something it does), that is a candidate
  `functional_correctness` defect — the interface says something false
  about the system, independent of whether the two runs agree with each
  other.
- Where the two perceived models diverge from EACH OTHER on the same
  interface — different primary action, different implied consequence,
  different unclear point — that is a candidate `usability_accessibility`
  ambiguity: the interface sustains two reasonable, independently-arrived
  -at readings.

This confrontation is not itself a finding. It produces evidence
(`walkthroughs/<demand-id>/divergence.toml` plus the two raw perceived
models) that `fde-review`'s existing heuristic pass then classifies —
see "Handoff to review" below. Misattributing one kind of defect as the
other is a named failure mode (FM-6): a genuine implementation bug and a
genuine ambiguity in the same interface look similar from the outside,
and only reading against the intended model, not just against each
other, tells them apart.

## Refined synthetic-evidence admissibility (extends `fde-design`)

`fde-design`'s "User validation" section already holds two rules:
synthetic users generate hypotheses and tasks, never findings; and an
agent completing a planned journey proves the path exists, never that an
unprepared human finds it without hesitation (USE-14, the Suchman
limit). This capability adds a third, narrower category — read the
current text of that section before touching it; this table sits
adjacent to it, never replacing or reordering what is already there.

| synthetic claim | admissible? | why |
|---|---|---|
| "users will feel confused / prefer X" | No — unchanged | a population claim from a source that is not a population |
| "the agent completed the planned journey" | Not usability evidence by itself — unchanged (USE-14) | proves the path exists, never that an unprepared human finds it without hesitation |
| "two independent, blind runs sustain distinct interpretations of the same interface" | **Yes** — new | a claim about the artifact, demonstrated by blind replication, never a claim about a population; satisfied only by two genuinely independent runs — one run's confusion is an anecdote, not a finding |

## Artifact layout

`specs/<demand-id>/design/intended-model.md` sits with the rest of that
demand's design family (`flow.md`, `ia.md`, `alternatives.md`) —
authored with full context, by the role that already produces that
family. A new top-level `walkthroughs/<demand-id>/` holds the
**perceived** side — received, verbatim, from a role denied that same
context — plus the confrontation:

- `walkthroughs/<demand-id>/perceived-model-a.md`
- `walkthroughs/<demand-id>/perceived-model-b.md`

Neither labeled or ordered as more authoritative than the other.

```toml
# walkthroughs/FWD-018-first-contact-walkthrough/divergence.toml
demand = "FWD-018"
score = 0.222                       # [0, 1]
threshold = 0.30                    # copied from [walkthrough].divergence_threshold at compute time, if declared
intended_model = "specs/FWD-018-first-contact-walkthrough/design/intended-model.md"
perceived_model_a = "walkthroughs/FWD-018-first-contact-walkthrough/perceived-model-a.md"
perceived_model_b = "walkthroughs/FWD-018-first-contact-walkthrough/perceived-model-b.md"

[per_slot]
primary_actions       = { intersection = 1, union = 3, distance = 0.667 }
action_consequences   = { intersection = 2, union = 2, distance = 0.0 }
unclear_points        = { intersection = 2, union = 2, distance = 0.0 }
```

## The divergence metric (stdlib, deterministic — `runtime/walkthrough.py`)

Three enumerable slots are scored — `primary_actions`,
`action_consequences` (each pair canonicalized as
`"<action> -> <consequence>"` before comparison, so agreeing on the
action but not the consequence still counts as divergence on that pair),
and `unclear_points`. The free-prose "what this is" line is never fed to
the number.

Per phrase: `phrase.strip().lower()`, internal whitespace collapsed to
one space. Each slot becomes a `set[str]`. Per-slot distance, Jaccard-
class, stdlib set operations only:

```
d(A, B) = 0                      if A and B are both empty
d(A, B) = 1 - |A ∩ B| / |A ∪ B|  otherwise
```

Overall score is the unweighted mean of the three slot distances —
deterministic, symmetric, bounded to `[0, 1]`, never an embedding, never
an LLM call (mirrors ADR-0010's rejection of anything non-deterministic
on a gated path and ADR-0011's rejection of instructed-not-measured
quality). This is a first cut: equal weighting across the three slots is
a starting assumption with face validity, not calibration — the same
humility ADR-0011 named for this repo's own erosion numbers.

## The gate — opt-in, silent by default

```bash
python3 bin/fde/verify.py --gate walkthrough
```

`[walkthrough]` absent from `fde.config.toml` → silent. `enabled = true`
with no `divergence_threshold` declared → **"not measured,"** never a
vacuous pass — identical to `[erosion]`'s rule that a threshold checking
nothing has not been met. `enabled = true` with a threshold declared but
zero `divergence.toml` files anywhere in the repo → also **"not
measured"** — there is nothing yet to check the budget against.
Otherwise, every `walkthroughs/<demand-id>/divergence.toml` found is
checked; a `score` exceeding `divergence_threshold` is a breach.

## Handoff to review — evidence, not a verdict

`fde-walkthrough` produces evidence; it does not itself file findings.
`fde-review`'s existing heuristic pass, given `walkthroughs/**:read`
added to the `adversarial` role's `inputs`, is the step that classifies
each recorded divergence as EITHER:

- a `usability_accessibility` finding citing `USE-15` (interpretive
  divergence — the two independent, blind reads disagree on the
  interface's primary action, object, or consequence), OR
- a `functional_correctness` finding citing the `DOM-*` id that fits
  when the divergence traces to a demonstrable implementation bug rather
  than genuine ambiguity — most commonly `DOM-3` (the UI implies a
  capability the system does not have) or `DOM-6` (the implied
  consequence contradicts a de facto behavioral contract).

Never both for the same divergence; never silently dropped once the
configured threshold is crossed (I8 — judgment without a named principle
or probe is not a finding).

## Calibration — structural here, real in the client repo

This kernel repository has no UI (`user_facing = false`); what it proves
is structural: the role cannot reach the filesystem, the metric is
deterministic and bounded on constructed fixtures, the gate reports "not
measured" rather than a vacuous pass. Whether two blind runs against a
*real* interface produce a divergence score that actually tracks real
ambiguity is proven in the client projects where this skill runs against
a real target — the same honest limit `fde-design`'s journey section
already names for itself.
