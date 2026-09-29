# ADR-0021 — Review by weight

date: 2026-09-29
status: accepted with C-13's sign-off
realized by: FWD-036

## Context

Every demand got an adversarial review: a probe hunt with scratch
repositories, which takes 5 to 15 minutes and many tokens. That cost is
spent even on one-line coding changes inside a plan the owner already
signed off. The owner saw that happen on a card change in another project
and asked for the adversarial pass to be reserved for specifications and
larger changes. C-5 and C-12 give the evidence:
- code reviews of coding demands found real defects in under a minute;
- the costly catches came from the cycle review and from reviewing the
  plan-level text.

## Decision

Review is sized by what is at risk.

| What | Review |
|---|---|
| A coding demand (front, back or infra) inside a signed-off plan | **code review**: one isolated pass that checks the diff against the demand spec, conformance with the ADRs it follows, the tests passing, and the layer's check; `kind = "code"` in findings.toml |
| A demand that is sensitive or irreversible, or whose real diff overruns ~300 production lines | **adversarial**, as before |
| The plan of an M/L cycle, before sign-off | **adversarial plan review**: attacks the criteria, the threat model, the demand split and the ADRs; `kind = "plan"` |
| The cycle review | unchanged: the objective, functioning and readiness |

- A code review is still isolated (I2): artifact plus spec, never the
  builder's thread.
- Every finding cites a principle or a probe (I8).
- Blocking follows the same rule as before.
- A code review's record satisfies the promotion gate like any review.

## Rejected

- **No review for small demands.** It loses I2's second look, which is
  cheap at code-review depth.
- **Adversarial review everywhere.** That is the cost the owner rejected.
