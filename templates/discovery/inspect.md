# Inspection — <feature or job> — <YYYY-MM-DD>

<!-- fde-inspect starts here (.fde/spec/product-pipeline.md, "What an
inspection delivers"). Every claim is labeled [observed] (read in code or
measured, with its source), [inferred] (reasoning, may be wrong) or
[to confirm] (a question for the owner). Read-only: nothing written to
production; a write the inspection would need is a proposal below. -->

- Commit inspected: `<sha>` · Production: <where>
- Scope: <the job, from where to where> · Out of scope: <what>

## Baseline and real use

<!-- usage over a window (records, users, errors, latency), the recorded
suite of this code (`verify.py --status`, never a fresh run), what is
already in the backlog -->

## Product map

<!-- docs/map/<slug>.md, generated now when missing (fde-map): screens,
calls, handlers, rules, events, columns. Its coverage limits. -->

## UI — the five measures

| measure | how it was measured | value | evidence | verdict |
|---|---|---|---|---|
| Information density | | | | |
| Semantic economy | | | | |
| Action topology | | | | |
| Visual hierarchy alignment | | | | |
| Interaction friction | | | | |

## UX — journeys

| journey | task effectiveness | cognitive economy | journey topology | expectation/feedback | effort and recovery |
|---|---|---|---|---|---|
| <journey> | | | | | |

## Design-system adherence (a separate verdict)

| check | verdict (pass/fail/unknown/n.a.) | evidence |
|---|---|---|
| Tokens and kit | | |
| Semantics (glossary, status, actions) | | |
| Rendered parity | | |
| Interaction and accessibility | | |
| Adoption (consumers, debt) | | |

## Findings

<!-- ordered by impact on the user's job; each cites the measure above or
the named principle (I8) it breaks, with severity -->

## Contracts to preserve

## Coverage limits

## Backlog generated

<!-- lines worth work of their own, each pointing here; `[kernel]` for an
item about FORWARD itself -->

## Questions for the owner

<!-- none blocks the inspection; each with a recommended answer -->
