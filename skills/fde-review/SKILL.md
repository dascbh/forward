---
name: fde-review
description: Runs the isolated review sized by risk: code, adversarial, plan or cycle. Use before promotion, or when the user asks for review, code review, red team, "try to break this", or whether something is secure or robust enough.
---

# fde-review

## Build the probe plan (deterministic)

1. Read `[weights]` from `fde.config.toml`; sort attributes descending.
   Weight orders the attack — nothing else. It does not add rounds and it
   does not make a finding blocking (kernel ADR-0018). A low-weight attribute is
   still probed in the full round.
2. Probes per attribute come from
   `.fde/spec/dimensions/quality-attributes.toml` (`adversarial_probes`).
3. Read `plan.md`'s `## Threat model`: who the cycle must contain, and
   what is declared out of scope. It bounds every probe. A demand review
   attacks first what the plan already names as risk — its failure
   modes, the threat model, an irreversible or `[prod]` step the demand
   touches — and only then the probe list. The deploy plan itself is
   judged by the plan review, `preflight.py` and the cycle review, never
   by a demand review.
4. Code or adversarial mode: create `reviews/<demand-id>/findings.toml`
   from `.fde/templates/findings.template.toml`, with its `kind`. Plan
   mode: `reviews/C-<n>/findings-plan.toml`, `kind = "plan"`. Cycle
   mode: write `cycles/C-<n>/review.md`.

## Mode — review by weight (kernel ADR-0021)

A coding demand inside a signed-off plan: isolated code review (diff ×
demand spec, ADR conformance, tests, the layer's check; `kind = "code"`;
~10 minutes; no scratch repositories or probe hunt). A sensitive or
irreversible demand, or a real diff over ~300 production lines:
adversarial review. An M/L plan, before sign-off: adversarial plan
review (`kind = "plan"`). The cycle review is unchanged.
The risk rule wins: a demand that is sensitive or irreversible, or whose
real diff overruns ~300 production lines, gets adversarial review even
inside a signed-off plan, and `plan.md`'s demand table marks it
(`adversarial` in its row).

Every mode stays isolated (I2), every finding cites a probe or a
principle (I8), blocking follows `## What blocks`, and a code review's
record satisfies the promotion gate like any review.

- **Code** (~10 minutes): the diff against the demand spec, plus
  conformance to the cycle ADRs it cites, plus the tests and its layer's
  check (`back` unit + contract tests, `front` design QA against the
  approved wireframe, `infra` plan diff + policy check). No scratch
  repositories, no probe hunt; the heuristic pass still runs. 1 round.
  Its core question is the **verification gap**: for each behavior the
  diff changes, if it broke where it is used, would a test fail? Trace
  the changed behavior to its callers and consumers, name the smallest
  realistic regression each would see, and read the test that should
  catch it. Evidence rules: read a test before claiming what it covers;
  search the repository by the symbol before claiming no test exists;
  say how far you looked; never file what you did not verify.
- **Adversarial**: the code review's scope, then the probe plan above,
  scratch repositories allowed (`kind = "adversarial"`). 1 round.
- **Plan**: attack `plan.md`'s criteria, threat model and demand split,
  and the cycle's ADRs. At M/L, the adversarial plan review (kernel
  ADR-0021) runs before the sign-off: the owner signs the plan that
  answered its findings. 1 round.
- **Cycle** (kernel ADR-0019 rule 12, `kind = "cycle"`): the objective
  on the integrated result; it never re-reviews a demand. *Functioning*:
  every `plan.md` criterion shown end to end (integration for back,
  usability for front, live checks for infra).
  *Readiness*: `deploy.md` complete with each step's verification and
  rollback exercised where the project allows, the signals the criteria
  declare (I5), runbook and README current, and no path the docs name
  gone stale (`DOC-REFS`). `fde-walkthrough` runs here,
  only when the cycle has a `front` demand. Rounds: the budget below.

## Budget — cycle rounds come from the cycle's size, and they end

| size | rounds | kinds |
|---|---|---|
| XS, S | `[review] cycle_rounds_small` (default 1) | full |
| M, L | `[review] cycle_rounds_large` (default 2) | full, delta |

A demand review is always 1 round: no second or third round is ever
launched on a demand. Its blocking finding is fixed inside that demand
and proven by its regression test, which is the re-check; the reviewer
confirms it (`fixed_in`) at the cycle review. Two client demands ran
three rounds each and took 7–9 h against a 1.1 h median (2026-10-01;
`REVIEW-ROUNDS` ⚠ names a demand file with `R2-` ids). The owner
is asked only when the fix changes a criterion or an ADR, which is a
replan. A non-blocking finding is triaged by the builder (`## Triage`):
fixed in the demand as a patch, deferred to `backlog.md`, or dropped; one
that shows a plan criterion unmet is fixed by the cycle. The reviewer closes a
blocker fixed inside its demand by recording the fixing commit on it,
`fixed_in = "<sha>"`, in a commit of its own (I3), in the cycle review's
pass and within its budget, never as an extra round. A demand merges only
if main stays deployable with it (kernel ADR-0027): its migration only
expands and its new behavior is dark — a flag off, a route not linked —
as its plan row's `dark` note says. The code review asks "if the cycle
stopped here, would main deploy and behave as today?"; a no blocks the
merge. A demand merges rebased
onto main, with `python3 bin/fde/verify.py --all` green and no blocking
finding open. A rebase is a new SHA: when main moved since the demand's
recorded suite, the suite runs once more at the rebased tree
(`verify.py --all --record-suite`) before the merge — two demands with
disjoint files can still collide (a key declared twice, a shared
registry), and main must not be where that shows. Main unmoved: the
recorded run stands. `EROSION` red at the merge is corrected by the
bounded loop of `fde-erosion` (two attempts, then one debt), never by a
budget raised. A demand merges only with its review record
(`reviews/<id>/findings.toml`), and its merge line on `board.md` names it.
After the merge its worktree is removed (`git worktree remove`, then
`git worktree prune`) and its branch deleted: a worktree left inside the
repository is a full copy that every tool walking the root sweeps up —
one client's CDK asset copied 95 of them into an 11 GB `cdk.out` and
filled the disk.
On the demand's branch, process records (`reviews/`, `cycles/`,
`promotions/`, `backlog.md`) stay in commits of their own, so no commit
mixes findings with behavior (I3); the merge to main squashes the branch
into one commit, or fast-forwards when the branch has a single commit.

- **Full** (round 1): the whole artifact against the whole spec. A full
  round with no blocking finding ends the review: the delta round runs
  only to check a blocker's fix.
- **Delta** (every later round): the prior findings plus the diff that
  answered them. The reviewer verifies each prior finding, then attacks
  only the changed lines. A new defect in untouched code goes to the
  backlog (`blocking = false`, `backlog = true`) — it never reopens the
  demand.
- **No extension; the safer path is taken without asking.** When a
  cycle review's budget is spent with a blocking finding open — or a
  blocker or a new risk turns up while closing — the agent narrows on
  its own: it cuts the part the finding lives in, ships the rest, and
  the cut becomes the next cycle's first demand. It never grows the
  cycle (no new demand after the last merge) and never accepts a risk
  outside the signed threat model; a risk that adds to an open backlog
  finding on the same component weighs as one. Recorded on `board.md`,
  marked in `promotion.md` at close; `plan.md` is not edited (kernel
  ADR-0019). The owner hears it in the closing message, after.
  Only the larger path asks the owner, once, with the narrowed cycle
  already moving: to declare the finding an accepted limit (a dated,
  named risk), or to grow the cycle. When what the blocker hits is the
  objective's core — narrowing would ship nothing it was for — the
  agent pauses the deploy (nothing ships, the backlog keeps the record)
  and that is the one question. "One more round" is not an option
  (kernel ADR-0018).

## Test runs — once per SHA

A suite green at a SHA is a fact on disk; no role runs it again at that
SHA.

- **Builder**: while building, only the tests of the files touched; the
  full suite once, at the commit handed to review, and once more at the
  rebased tree when main moved before the merge. Its command, result
  and SHA go on the demand's board line. `verify.py --all --record-suite`
  runs the gate and the configured `test_command` once and records both
  in `.fde/runs/<key>.json` (the key is the index's code — every path but
  `reviews/`, `cycles/`, `promotions/`, `backlog.md`, `specs/`,
  `discovery/` — so a board or promotion commit keeps the record; the
  directory is gitignored).
- **Code review**: reads that record and the tests in the diff; never
  reruns the suite. `verify.py --status` prints the record for the current
  tree, from any worktree of the repository, or "no record for this
  tree" — then the board line is the record. One targeted test only to
  prove a suspected finding.
- **Adversarial review**: probes are targeted executions, never a
  full-suite rerun.
- **Deploy**: the recorded suite of the code being deployed stands —
  a promotion or board commit does not change its key. The suite is
  recorded in a checkout where nothing else runs: a client's deploy saw
  a red that two other jobs writing in the same directory caused, and
  ran the suite three times. A red record lists its failing tests
  (`--status`); no rerun just to find them.
- **Promotion**: `verify.py --all` once at the promoted commit; the
  evidence per criterion is the review record and the builder's run,
  not a red→green reproduction per criterion.
- **Mutation testing** as evidence runs only where `plan.md` declares it
  for a criterion. Apart from that, the cycle review measures the suite's
  effectiveness on what the cycle changed, unasked:
  `codebench.py --tests --changed-since <the commit before the cycle's
  first merge>` (10-minute budget, report only). A surviving `if`,
  comparison or `and`/`or` in a changed module is one backlog line;
  `--format json` keeps the numbers for the next cycle. No module with
  tests found, or no runner found: say so in one line and declare
  `[codebench] test_file_command` yourself — never ask the owner.

CI runs the full suite on every push; locally, a suite already green at
the same SHA is not run again.

## Closing is a rail

After the last demand merges, the cycle review runs within its budget,
then the preflight, one promotion decision, the deploy and the close —
each once (`fde-backlog`). What the cycle review finds that does not
block is a backlog line, not a new round.

The cycle review also reads `deploy.md` as an artifact: each step has
its rollback, a time target for it, and numeric triggers (error rate,
latency, a new error, a business guard) that decide it. A plan that
passed three cycle-review rounds without them reached production
without them.

## Before the cycle review

The demand reviews are committed before the cycle review starts, so the
cycle reviewer reads them, not a stale tree. A change to a reader or a
gate is proven read-only against a real client before the cycle review,
not only against this repository's layout.

## What blocks

`blocking = true` only when all three hold: severity `critical`/`high`;
the path is reachable inside the plan's threat model; it breaks a declared
acceptance criterion or failure mode of `plan.md`. Anything else records,
and a non-blocking finding is triaged (`## Triage`). A defect reachable only by
an actor or sequence the threat model excludes is a declared limit. No
threat model in the plan → that is the first finding.

## Cap

At most `[review] max_findings` (default 5) `[[finding]]` entries per
round, the most severe. Every
other observation is one line in `[meta].notes`.

## How to run it

- **Isolate (I2).** The thread that produced the code cannot review it.
  Claude Code: invoke the `fde-adversarial` subagent (isolated worktree;
  the guard hook blocks its writes outside its scope). Any other tool:
  `git worktree add --detach ../.fde-review-<demand-id>` and review there
  in a fresh session.
- **Record, never fix (I3).** Findings go in `reviews/<id>/findings.toml`;
  fixing belongs to the implementation role.
- **Pass the SHA, verify the SHA.** Put the commit SHA under review in
  the reviewer's prompt; its first step is `git log -1`, which must match
  (isolation tooling can pin an older base; install sets
  `worktree.baseRef: "head"`). If not, check out the right commit first.
- **Record provenance (FWD-007).** `[meta]` carries the rounds run, what
  was probed, and `agent_transcript = "agent-<id>"` (the reviewer's
  worktree directory name). In chat, the findings speak.

## The heuristic pass (same reviewer, same isolation)

After probing, judge the attributes whose `verified_by` includes
`heuristic` (`.fde/spec/dimensions/quality-attributes.toml`) against
their `heuristic_principles`. A heuristic finding cites `principle` and
severity (I8): "USE-3: the same filter is called 'Period' on one screen
and 'Range' on another — medium".

## Triage — reviewer output is data, not a verdict

Reviewers find; the builder triages, once every review result is in.
Recall belongs to the reviewer, precision to the triage.

1. **Verify each claim** at its evidence: does the bad outcome happen?
   Read past the changed lines (callers, guards upstream). Verdict:
   `real` (the reviewer's severity stands), `false` (write what disproves
   this claim; a true fact about nearby code does not), or `unsure`
   (write what would settle it).
2. **Route each real finding by where the defect lives:**
   - `intent` — the plan does not say what the owner wants: this demand
     stops and the owner gets one question with a recommended answer, as
     a plain message and a board line (`<demand> asks …`), never a
     blocking question box while other agents run. Only this demand
     waits; the orchestrator keeps dispatching the rest. A question box
     once held a client's five fronts for 6 hours over one demand's
     question (2026-10-01). An answer that
     changes a criterion is the replan; any other answer is one board
     line and the demand continues.
   - `plan` — the demand spec was unclear or wrong: revert the demand's
     code, fix the spec, rebuild from it. No patch on patch.
   - `patch` — a **high** finding whose smallest fix is trivial, adds no
     public surface and no new guard: fixed inside the demand now, with a
     regression test when behavior changes. This is the one in-band fix
     MNT-9 allows besides a blocker. A medium or low finding is never
     patched in the demand: it is `defer`. Patching non-blocking findings
     (and the scope they widened) made the slow tail of two client
     projects, where 79–84% of findings were medium or low.
   - `defer` — the finding stays where it is, in `findings.toml`: that
     file is its record (I7), and `fde-graph` surfaces the ones that
     recur. It becomes a backlog line only when it is worth a piece of
     work of its own — medium or higher, with the value it would bring —
     and a cycle adds at most 5 such lines (`BL-CYCLE` ⚠). A low
     finding is never a backlog line. Copying every finding into the
     backlog buried one client's under 79 lines from a single cycle.
3. **Record** one board line: `<date> <demand> decided triage F1
   real/patch <sha>; F2 false — <refutation>; F3 real/defer`. The
   reviewer's file is never edited (I3). A blocking finding is never
   triaged away: it is fixed (`fixed_in`) or its refutation goes on the
   board for the cycle review to decide. The cycle review audits every
   `false`.

One commit per triage: the patches, their evals, and — only when a
decision changed — the ADR edit. A fix that rewrites far more than the
finding's evidence spans is the wrong design for this scope: narrow
(Budget, option 1) instead of rebuilding under review.

## Change sizing

One ceiling: a demand is split at planning to fit ~300 production lines,
never at review; an overrun is posted on the board and the review
proceeds (`fde-triage`). A dependency bump is a behavior change: read the
changelog, diff the lockfile, one package per change.
