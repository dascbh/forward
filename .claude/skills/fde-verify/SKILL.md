---
name: fde-verify
description: Runs the invariant gate, the same verifier the pre-commit hook and CI run. Use before any commit or PR, when the hook rejects a commit, when asked whether something "is ready" or "can ship", or to explain a failed gate.
---

# fde-verify

The gate is code, not agent judgment — it is the one part of the kernel
that stays a script, because pre-commit and CI run where no agent exists.

```bash
python3 bin/fde/verify.py --staged           # pre-commit (fast)
python3 bin/fde/verify.py --all              # CI (complete)
python3 bin/fde/verify.py --gate eval        # a single gate
python3 bin/fde/verify.py --format json      # machine-readable
```

A ⚠ line never blocks: it names what to look at (a draft outside git, a
stale doc path, a spec repeating its plan, a cycle that cannot be
checked). Gates added in 0.29 (owner direction, from a client cycle's lessons):

- `UNTRACKED` — a review, promotion, cycle review or ADR outside git
  fails (I7); a spec or plan/board/deploy outside git warns.
- `BL-LEN` — a NEW backlog line over `[backlog] max_item_words`
  (default 60) fails; `--gate backlog-length` lists every open one.
- `PROC-DUP` ⚠ — a demand spec repeating 6+ lines of its plan or ADRs.
- `DOC-REFS` ⚠ — a repo path named in CLAUDE.md, README.md or AGENTS.md
  that no longer exists.
- `DOCS` — a cycle closed from 2026-10-01 needs `docs:` in promotion.md.
- `CYCLES` — running cycles touching the same files without `depends:`
  fail (kernel ADR-0024); one that declares no `files` warns.

## When explaining a failure

Say which invariant, why it exists, and what the fix is. Do not suggest
working around it — there is no bypass key, and looking for one is the
behavior the framework exists to prevent.

## Suite discipline — what makes I1 worth anything

- A bug fix starts with the failing eval that reproduces it — that eval
  IS the I1 entry. A fix without a first-observed-failing test is
  unproven.
- A test that passes on its first run proves nothing: watch it fail
  before you make it pass.
- Assert state, not interactions — a suite that checks which methods were
  called breaks under refactor while behavior is unchanged.
- Double preference: real > fake > stub > mock; mock only slow or
  non-deterministic boundaries.
- A flaky test gets fixed or understood, never re-run until green.
- Fix the lint, don't disable the rule; fix the test, don't skip it.

## Known bluntness, kept on purpose (FWD-004, decided 2026-08-09)

I1 matches files, not diff content: a comment-only or prose-only edit
inside a behavior root trips the gate. Deliberate. In this kernel,
instructions ARE behavior (kernel ADR-0001) — a prose edit to a skill changes
what agents do, and the drift-detector tests are its legitimate eval.
For code, inspecting diff content to exempt "harmless" edits would make
the wall guess. The cost is one touched eval; the alternative is a wall
that argues. Re-decide only with field evidence that the cost is real
(the backlog carries the standing item).

## The bypass that is not one

Never recommend `git commit --no-verify` — not even as one option among
others. A bypassed commit does not escape: CI runs this same verifier on
push and fails there, publicly, later. When I1 blocks a change in a root
that has **no suite at all** (common in brownfield adoption), the demand
grew: it now includes bootstrapping the minimal suite for that root — one
runner, one smoke eval covering the change. That is the one-time cost of
an uncovered root surfacing, not this demand's fault — and it is paid
now, not deferred.

| gate | what was missing | fix |
|---|---|---|
| I1 | behavior change without an eval entry | write the failure mode and the evaluator |
| I2 | adversarial review did not run isolated, or a demand was promoted without one | run `fde-review` isolated; findings.toml declares `artifact_only`; every demand promoted by `cycles/C-<n>/promotion.md` (or the old `promotions/<id>/decision.md`) has `reviews/<id>/findings.toml` |
| I3 | adversarial role touched code | revert; the finding goes in `reviews/`, fixing belongs to another role |
| I4 | acceptance criteria missing or undated | declare before building: dated criteria in `cycles/C-<n>/plan.md` (a `date: YYYY-MM-DD` header line and a `## Acceptance [criteria]` section with at least one criterion id, `- **A1 — …**`, that is not the template's placeholder), which every demand of the cycle inherits — through the plan's `## Demands` table (first cell: any `<PREFIX>-<n>` id) or its spec's `cycle: C-<n>` line; the old `specs/<id>/acceptance.md` with a `date:` line still counts. Declared limit: the gate does not check that the date precedes the first demand commit |
| I5 | declared attribute without a signal | instrument it or reduce what was declared |
| I6 | gate does not run without the FDE | `fde-sync` re-copies the runtime |
| I7 | handoff without an artifact on disk | create the structure; do not pass context by conversation |
| I8 | finding cites neither probe nor principle | name the probe that broke it or the catalog principle it violates; naked opinion is not a finding |
