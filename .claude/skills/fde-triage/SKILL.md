---
name: fde-triage
description: Sizes a demand and decides which roles and how many adversarial rounds activate. Use ALWAYS before starting any implementation work in a project under the kernel — a one-line change or a whole feature. Use when the user says the process feels too heavy for the size of the task, or asks to "skip steps". It is the legitimate path to reduce ceremony without relaxing criteria.
---

# fde-triage

If the full flow runs on a three-line change, the framework gets turned off
in week two. That is why sizing is a rule table, not common sense. Apply the
table; do not negotiate it, and do not interview the user about the formula
— estimate the inputs from the demand yourself and, if torn between two
sizes, take the larger.

## Inputs — all four judged for THIS demand

- `surfaces` — how many of the four surface kinds (UI/frontend, API,
  data/schema, infra) **this demand** touches — never the project's
  fixed count from install
- `loc` — estimated lines changed by this demand
- `sensitive` — **this demand** touches data of the class declared in
  `[triage].data_class`. The declaration is a ceiling: in a
  public/internal project, sensitive is always false; in a
  personal/financial/health project, judge whether the demand's paths
  read or write that data. Unsure → true.
- `irreversible` — **this change** is hard to undo once shipped: schema
  migration, deletion, external side effect, published artifact.
  `[triage].reversibility` sets the posture (a reversible project's
  demand is false unless the demand itself creates irreversibility).
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

| score | size | active roles | adversarial rounds | ADR |
|---|---|---|---|---|
| ≤ 1 | XS | implementation, adversarial | 1 | no |
| 2–3 | S | spec, implementation, adversarial | 1 | no |
| 4–6 | M | spec, implementation, adversarial, promotion | 2 | yes |
| ≥ 7 | L | all five | 3 | yes |

Announce the result in one line — size, roles, rounds — and start. The
table is deterministic; the reasoning behind the score does not belong in
chat.

## Cycle — declared scope (when [cycle] is on)

With `[cycle] enabled = true` in `fde.config.toml`, work runs in cycles
(ADR-0017). A cycle is one declared piece of work, started by one
request: `cycles/C-<n>.md` at the repository root, numbered like
`sprints/S-<n>`. It names the demand(s) it executes, each with the size
triaged above; a round of several demands is one cycle listing them all.
The orchestrating thread writes it. The `cycle` gate checks form and git
ordering only — never whether an item is true; review and promotion
judge that.

**Open — commit it before the first behavior change.** Write the
objective, the tasks and the done criteria, and commit the file before
any `[gate].behavior_paths` change; the gate checks that every behavior
commit's parent tree holds exactly one open, well-formed cycle. For an S+
demand the done list points at `specs/<id>/acceptance.md` (never restates
it), and that file must already be committed too. One cycle is open at a
time and it is the highest-numbered file ("no closure, no next cycle").
Commit the cycle on its own: a behavior commit may not add a cycle file.
Its done items start unmarked (`- [ ]`). A commit needs no cycle only
when it declares `FORWARD: RULE — <reason>` as its first message line
and is verified RULE-eligible; an eligible commit without the claim is
red. Every commit is judged by its parent's configuration, and once the
first cycle file exists every later commit is examined, whatever the
flag says.

A demand's `spec.md` declares its size in a header line before its
first `## ` section — `size: M` — and it must equal the size declared in
`demands:`; a missing `size:` is red. Ids compare normalized (`fwd-050` = `FWD-50` = `FWD-050`).

Schema — each `<…>` is a placeholder, and the gate rejects any field
left as one:

```
cycle: <C-n, equal to the file name>
objective: <one verifiable sentence: what is true when this cycle closes>
opened: <YYYY-MM-DD>
demands: <id (XS|S|M|L), comma-separated>

## Tasks
- <one line per task this cycle executes>

## Done when
- [ ] <one line per profile key the table below requires>
- [ ] <the acceptance.md path of each S+ demand>
- [ ] <one checkable criterion per XS demand>

## Next cycle
- <anything discovered and not acted on, appended while open>

## Intake
- <one line per item of the previous cycle: taken, deferred, or dropped with a reason>
```

`## Intake` is needed only when the previous cycle closed with items
and `[scrum]` is off. `## Next cycle` starts empty.

Done profile — computed from the declared sizes and `[cycle].stages`,
never hard-coded. Each required key is one done item, exactly once:

| key | required for | resolved by |
|---|---|---|
| `declared-before` | every size | the gate itself; listing it is informational |
| `regression-proven` | every size | the test id, or "red on `<sha>`, green on `<sha>`", or `n/a — <reason>` |
| `review-rounds` | every size | `reviews/<id>/findings.toml`, the size's rounds, no open blocking finding |
| `promotion` | M, L | `promotions/<id>/decision.md` |
| `live` | only when `stages` declares `live` | the live-check evidence the project names |
| `published` | only when `stages` declares `published` | the publication evidence the project names |
| `residuals` | every size | the cycle's own `## Next cycle` list |

Then the demand-specific part: the `acceptance.md` path of each S+
demand, and at least one inline, checkable item for each XS demand.
A declared size must equal the size on the demand's `spec.md` Triage
line when that line states one.

Minimal valid cycle for one XS demand, no stages:

```
cycle: C-12
objective: validate() rejects a [cycle] section that is not a table
opened: 2026-10-02
demands: FWD-030 (XS)

## Tasks
- reject a non-table [cycle] in fde_lib.validate()

## Done when
- [ ] declared-before
- [ ] regression-proven
- [ ] review-rounds
- [ ] residuals
- [ ] `[cycle] = 1` yields a CYCLE-TYPE violation

## Next cycle
```

**Scope freeze — during execution.** Anything discovered goes to
`## Next cycle` and is not acted on in this cycle: an adjacent bug, a
cleanup, an improvement (MNT-9 — adjacent improvements are noted for
later, never fixed in-band). This includes a RULE-sized fix: RULE
commits stay outside every cycle, and the gate cannot tell a planned one
from a discovered one (owner decision A9), so review judges it under
MNT-9. The declaration is frozen from the opening commit. The only
allowed changes while open are appends to `## Next cycle` and
`- [ ] amended YYYY-MM-DD: <text>` appends to `## Done when`; the header,
`## Tasks`, `## Intake` and every existing item stay byte-for-byte. A
wrong declaration is fixed by `git commit --amend` only while the opening
commit is still HEAD; otherwise close the cycle with the items marked not
met and open the next.

**Close.** In one commit: add `closed: YYYY-MM-DD` and resolve every done
item — `[x]` met or `[-]` not met, then ` — <evidence or reason>`
appended to the unchanged text. Carry each not-met item into
`## Next cycle`; if nothing is left, the list is the single item
`- none` (one next-cycle item per not-met item, starting with its text).
The gate judges the closed cycle once, here, against the closing commit's
parent configuration; a later change to `stages` or to a spec never
re-opens it. Then present the next-cycle list in the closing report: it
is domain content, and the Voice rule's one status line does not
suppress it. A closed file never changes again.

**Feed the next cycle.** Item *k* of cycle *n*'s list is the token
`C-<n>#<k>`; `--gate cycle` prints each one. With `[scrum]` on, each
item becomes a backlog item citing its token with an evidence label, in
the closing commit itself; the backlog is groomed freely afterwards, and a
later cycle pulls a captured item with `C-<n>#<k> taken` in its
`## Intake`. With it off, the next cycle's `## Intake`, in its opening
commit, lists each item of its predecessor exactly once as
`C-<n>#<k> taken` (a task cites the token), `C-<n>#<k> deferred` (its own
`## Next cycle` cites it) or `C-<n>#<k> dropped — <reason>`.

**Ways out.** Every red names its next step; the usual ones:
- a wrong declaration while the opening commit is still HEAD: amend that
  commit;
- otherwise: close the cycle with `[-]` items and reasons, and open the
  next;
- `stages` or a spec changed: nothing to do for closed cycles; for the
  open one, fix the spec's `size:` or append an `amended` done item;
- `--since` does not resolve: re-run with a known base
  (`--since <merge-base>`, or fetch full history);
- code and a new cycle in one commit: split the commit before push —
  cycle first, then the code.

## What never scales

The invariants. At XS and at L, all eight apply equally. What varies is the
**boundary covered**, not the **criteria applied**.

When the user complains about process weight: apply the table and show the
reduced plan. When they ask to turn off the gate: explain that no key
exists, and that the path is shrinking the delivery scope until it fits the
standard — not the other way around.
