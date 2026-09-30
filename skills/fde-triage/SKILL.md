---
name: fde-triage
description: Sizes a cycle (XS/S/M/L), bounds its demands, and recognizes the RULE commit lane. Use ALWAYS before planning work under the kernel, when the process feels too heavy, or when asked to "skip steps".
---

# fde-triage

Apply the table; do not negotiate it or interview the user about the
formula. Estimate the inputs yourself; if torn between two sizes,
take the larger. Rationale: kernel ADR-0019 rule 3.

## What gets sized

An objective with more than one goal the owner would see working on
its own is several cycles, one per slice (`fde-spec`, kernel ADR-0024);
size each slice.

Size is set on the cycle, never on a demand. The size sets the depth of
the planner and the number of cycle review rounds.

A demand is one goal (kernel ADR-0022), at most about 300 production
lines (`[lanes] demand_max_loc` in `fde.config.toml`, default 300). Its
layer cell lists every layer it touches: `front` is screens, flows and
user-facing text; `back` is the API, domain logic and data access;
`infra` is IaC, roles, pipelines and runtime configuration. Two goals
that could each merge alone are two demands; a goal over the ceiling
splits into smaller goals, never into layers. Splitting happens at
planning, in `plan.md`'s demand list, not at review.

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

RULE is categorically distinct from XS/S/M/L, not a smaller XS: XS runs
judgment in reduced form; RULE runs none. It is never estimated, only
computed after the fact from the commit's own diff. Rationale: kernel ADR-0015.

A commit is RULE-eligible only when ALL four hold on the committed diff:
`[triage].data_class` is exactly `public` or `internal`;
`[triage].reversibility` is exactly `reversible`; the commit's own
`added + deleted` is strictly under `[triage].rule_lane_max_loc`
(default `10`); no file under `[gate].eval_paths` was deleted or shrunk.
A merge commit, a commit touching a binary file, and any failure while
checking either are ineligible regardless of loc: RULE defaults to never
when mechanical certainty is unavailable.

**I1's `eval-coverage` gate is completely unchanged and still fully
applies.** RULE exempts nothing from it: by the `verified_by` primacy of
`spec/dimensions/quality-attributes.toml` (empirical, adversarial,
heuristic), judgment on top of a change I1 fully covers adds nothing.

Before committing a change that looks trivial, run `triage.py --check`
on the staged diff (advisory). If eligible, the commit's first message
line is `FORWARD: RULE — <one-line reason>`. The `rule-lane` gate
re-verifies the claim against the real diff, every time; a wrong guess
only sends the change through the table below.

## Direct lane — no cycle

A change goes straight to code, with no cycle, plan or sign-off, when
ALL hold: exactly one goal; about 300 production lines at most
(`[lanes] direct_max_loc`, default 300); not
`sensitive`; not `irreversible`; it adds no acceptance criterion to a
plan and needs no ADR. Unsure on any → a cycle.

1. The request is the spec: the owner's words, one paragraph, in the
   first commit's message body.
2. The test comes first and is the declared criterion (I1, I4).
3. Build on a branch; the gate runs green (`verify.py --all`).
4. One isolated code review (I2, I3): the diff against the request,
   `reviews/<branch>/findings.toml`, `kind = "code"`, 1 round. Only a
   blocking finding stops the merge.
5. Merge rebased onto main. It ships with the project's next deploy.

Announce it in one line: `FORWARD: direct — <layers>, ~<loc> lines`. A
direct change that turns out to be two goals, overrun ~300 lines or
need a criterion stops and becomes a cycle.

## Score and size

```
score = min(3, surfaces)
      + (sensitive ? 2 : 0)
      + (irreversible ? 2 : 0)
      + (loc < 50 ? 0 : loc < 300 ? 1 : 2)
```

| score | size | planner (`fde-spec`, `plan.md`) | cycle review rounds | ADR | timebox |
|---|---|---|---|---|---|
| ≤ 1 | XS | minimal plan | 1 full | no | 30 min |
| 2–3 | S | plan | 1 full | no | 1 h |
| 4–6 | M | plan + ADRs | 1 full + 1 delta | yes | 3 h |
| ≥ 7 | L | full plan + ADRs | 1 full + 1 delta | yes | 1 day |

The round counts are the defaults of `[review] cycle_rounds_small` (XS/S)
and `cycle_rounds_large` (M/L); a project that tunes them uses its values.
The line ceilings above are the defaults of `[lanes]`. Tune numbers in
`fde.config.toml`, never in this text.

Every size: `fde-spec` writes `plan.md`, a demand review is 1 round, and
the cycle closes with a promotion by `fde-promotion`. M adds
architecture: `fde-architecture` writes the ADRs, so M and L run all
five roles. "All five roles" means the five working roles; the
walkthrough evaluator is a sixth role that writes nothing.

Announce the result in one line — size, roles, rounds — e.g.
`FORWARD: M — spec + plan review + architecture + impl + demand review(1r)
+ cycle review(full+delta) + promotion` (at L, `FORWARD: L — full spec +
plan review + architecture + impl + demand review(1r) + cycle
review(full+delta) + promotion`) — and plan:
`plan.md` comes first (AGENTS.md `## Cycle`). At M/L, the adversarial plan
review (kernel ADR-0021) runs before the sign-off: the owner signs the
plan that answered its findings. Then the planner stops at the
sign-off. The table is deterministic; the reasoning behind the score does
not belong in chat. The rounds are the cycle review's budget, not a
minimum to extend: `fde-review` says what happens when it is spent.

## Overrun on the real diff — a fact for the board

A demand's `loc` is an estimate made before code exists; the diff is the
fact. One ceiling: a demand is split at planning to fit ~300 production
lines (tests, evals, specs, reviews and ADRs not counted). A demand
whose real diff overruns its estimate or that ceiling is not re-split
at review: post the overrun on the board and the demand proceeds. Splitting happens at
planning only; the cycle replans only if a criterion or an ADR changes.
A timebox overrun is recorded the same way.

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

When the user complains about process weight: check the direct lane
first; otherwise apply the table and show the reduced plan. When they ask to turn off the gate: explain that no key
exists, and that the path is shrinking the delivery scope until it fits the
standard — not the other way around.
