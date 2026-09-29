---
name: fde-triage
description: Sizes a cycle (XS/S/M/L), bounds its demands, and recognizes the RULE commit lane. Use ALWAYS before planning work under the kernel, when the process feels too heavy, or when asked to "skip steps".
---

# fde-triage

Sizing is a rule table, not common sense. Apply the table; do not
negotiate it, and do not interview the user about the formula — estimate
the inputs yourself and, if torn between two sizes, take the larger.
Rationale: ADR-0019 rule 3.

## What gets sized

Size is set on the cycle, never on a demand. The size sets the depth of
the planner and the number of cycle review rounds.

A demand is at most about 300 production lines and has exactly one
layer: `front`, `back` or `infra`. A change that spans layers is always
split, however small. Splitting happens at planning, in `plan.md`'s
demand list, not at review.

## Inputs — all four judged for THIS cycle

- `surfaces` — how many of the four surface kinds (UI/frontend, API,
  data/schema, infra) **this cycle** touches — never the project's
  fixed count from install
- `loc` — estimated lines changed by this cycle
- `sensitive` — **this cycle** touches data of the class declared in
  `[triage].data_class`. The declaration is a ceiling: in a
  public/internal project, sensitive is always false; in a
  personal/financial/health project, judge whether the cycle's paths
  read or write that data. Unsure → true.
- `irreversible` — **this change** is hard to undo once shipped: schema
  migration, deletion, external side effect, published artifact.
  `[triage].reversibility` sets the posture (a reversible project's
  cycle is false unless the cycle itself creates irreversibility).
  Unsure → true.

## RULE — a lane below the table, not a row in it

RULE is categorically distinct from XS/S/M/L, not a smaller XS: XS still
runs full judgment in reduced form (implementation, one isolated
adversarial round); RULE runs no judgment at all. Where the table is an
agent's a-priori estimate of `surfaces`/`loc`/`sensitive`/`irreversible`,
made before any code exists, RULE is the opposite on every axis — it is
never estimated, only computed, and only after the fact, directly from
the commit's own diff. This is *Noise*'s (Kahneman/Sibony/Sunstein)
rule-vs-standard distinction: a high-volume, low-stakes decision becomes
a deterministic rule with zero judgment, while deliberate, multi-
perspective judgment stays reserved for what is genuinely risky or
novel — never a lighter version of the judgment lane itself.

A commit is RULE-eligible only when ALL four hold, checked mechanically,
post-hoc, against the actual committed diff — never claimed a priori:
`[triage].data_class` is exactly `public` or `internal`; `[triage].
reversibility` is exactly `reversible`; the commit's own `added +
deleted` is strictly under the declared `[triage].rule_lane_max_loc`
(default `10`); no file under `[gate].eval_paths` was deleted or shrunk
in it. Three further conditions make a commit categorically ineligible
regardless of loc, because its real diff cannot be mechanically known at
all — never merely counted as zero (reviews/FWD-019 round 1, F1/F2/F4):
a merge commit (2+ parents — its diff depends on a parent choice this
check refuses to make), a commit touching a binary file (git reports no
line count for it), and any git subprocess failure while determining
either (a bad SHA, git missing, a permission or object error) — RULE
defaults to never whenever mechanical certainty is unavailable, the same
posture ADR-0015 states for the gate itself. **I1's `eval-coverage`
gate is completely unchanged and still fully applies** — RULE is not
an exemption from it, it is the recognition that when empirical
verification already covers everything
there is to verify for a change this small, adversarial and heuristic
review on top of it verify nothing further. That is the kernel's own
declared justification: `spec/dimensions/quality-attributes.toml`
orders its three verification pillars by primacy — `verified_by =
["empirical", "adversarial", "heuristic"]`, execution first — so
stacking judgment on top of a change I1 already fully covers adds no
information that ordering did not already rule out.

Usage loop: before committing a change that looks trivial, run
`triage.py --check` against the staged diff — advisory, it gates
nothing by itself. If it looks eligible, self-declare it as the commit's
first message line: `FORWARD: RULE — <one-line reason>` (the same
announcement discipline as `FORWARD: M — spec + impl + adversarial(2r) +
promotion`). The `rule-lane` gate then re-verifies the claim against
what was actually committed, every time — a wrong guess costs nothing
but redoing the demand through the normal table below, so there is no
incentive to game it.

## Score and size

```
score = min(3, surfaces)
      + (sensitive ? 2 : 0)
      + (irreversible ? 2 : 0)
      + (loc < 50 ? 0 : loc < 300 ? 1 : 2)
```

| score | size | active roles | adversarial rounds | ADR | timebox |
|---|---|---|---|---|---|
| ≤ 1 | XS | implementation, adversarial | 1 full | no | 30 min |
| 2–3 | S | spec, implementation, adversarial | 1 full | no | 1 h |
| 4–6 | M | spec, implementation, adversarial, promotion | 1 full + 1 delta | yes | 3 h |
| ≥ 7 | L | all five | 1 full + 2 delta | yes | 1 day |

Announce the result in one line — size, roles, rounds — and plan:
`plan.md` comes first (AGENTS.md `## Cycle`), and the planner stops at the
sign-off. The table is deterministic; the reasoning behind the score does
not belong in chat. The rounds are the cycle review's budget, not a
minimum to extend: `fde-review` says what happens when it is spent.

## Re-size on the real diff — the estimate is not a contract

A demand's `loc` is an estimate made before code exists; the diff is the
fact. Before its review round, count the behavior + eval lines actually
changed (specs, reviews and ADRs excluded). If the count is more than
twice the estimate, or above ~800 lines, stop: the demand is split, not
reviewed. Cut it into demands that each fit ~300 lines and one layer,
enter them in the demand list, and post the split on the board. The same
holds when the timebox runs out: work at its timebox is re-sized, never
granted more time in place.

## Smallest mechanism first

When the demand is a new rule or policy, its first slice ships it as an
instruction (skill text, a heuristic principle the review cites). It
becomes a mechanical gate only in a later demand, with usage-data showing
the instruction was not enough. A gate is an enforcement boundary; the
review will attack it as one, and every bypass it finds is a round.

## Spec budget

The cycle's `plan.md` carries the `## Threat model` (who the change must
contain, what is out of scope — three to five lines) and at most ten
failure modes. A demand's `spec.md` fits one page (~800 words) and cites
the plan's ids. A plan that needs more is a cycle that needs splitting.

## What never scales

The invariants. At XS and at L, all eight apply equally. What varies is the
**boundary covered**, not the **criteria applied**.

When the user complains about process weight: apply the table and show the
reduced plan. When they ask to turn off the gate: explain that no key
exists, and that the path is shrinking the delivery scope until it fits the
standard — not the other way around.
