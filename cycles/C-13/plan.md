cycle: C-13
state: planned
date: 2026-09-29
size: S
objective: review by weight — a coding demand gets a code review; adversarial review is for M/L plans before sign-off and for sensitive, irreversible or oversized demands
signed-off:

<!-- Triage: surfaces 1 (instruction layer) · public · reversible ·
~150 lines → 1 + 0 + 0 + 1 = 2 → S. Planner with kernel ADR-0021; one
demand, reviewed under the rule it ships (code review, kind = code);
cycle review 1 round. -->

## Items

- B-44 owner direction — review by weight: code review for coding demands; adversarial for specifications and larger changes

## Threat model

Contained: a cooperative agent choosing the wrong review depth, either
too heavy (cost) or too light (a risky change slipping through). Out of
scope: an agent that skips review altogether; the gate already catches
a promoted demand with no review record.

## Acceptance criteria

- **A1 — Code review is the default for coding demands.** AGENTS.md step
  5 and fde-review state it: a front, back or infra demand inside a
  signed-off plan gets one isolated code-review pass (diff × demand spec,
  ADR conformance, tests, the layer's check), recorded with
  `kind = "code"`.
- **A2 — Adversarial where the risk is.** The same texts send a demand
  to adversarial review when it is sensitive or irreversible, or when its
  real diff overruns ~300 production lines. They also send an M/L cycle's
  plan to an adversarial plan review before sign-off (`kind = "plan"`).
- **A3 — Invariants hold.** A code review stays isolated (I2) and cites
  a principle or a probe (I8). Its record satisfies the promotion gate.
  The findings template carries `kind`.
- **A4 — The reviewer knows its mode.** fde-adversarial (and its
  installed copy) has three modes (code, adversarial, plan) plus the
  cycle mode, each with its budget: about 10 minutes for code review.
- **A5 — Terse.** AGENTS.md stays at or under 1,600 words; every
  description stays at or under 40.
- **A6 — Ships.** The full suite and `verify.py --all` are green, the
  version is 0.21.0, and the change is pushed.

## Failure modes

- **FM1:** the texts disagree on which review a demand gets. Detected by
  verbatim pins of the same rule in AGENTS.md, fde-review and
  fde-adversarial. Meets A1, A2.
- **FM2:** a `kind = "code"` record fails the gate. Detected by a gate
  test on a code-review fixture. Meets A3.

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-036 | back | — | AGENTS.md step 5 (+ template), fde-review, agents/fde-adversarial.md (+ rendered copy), findings template `kind`, kernel ADR-0021 cited; pins and a gate test for kind = code | A1–A5 | ADR-0021 |
