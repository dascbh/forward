---
name: fde-erosion
description: Measures and gates long-term decay of AI-built code: clone ratio, add/delete ratio, batch size. Use when the user worries the codebase will rot, asks about debt, bloat or duplication, sets an erosion budget, or the erosion gate fired.
---

# fde-erosion

Decay is measured, not prompted: instruction alone does not stop it
(the evidence is kernel ADR-0011).

```bash
python3 bin/fde/erosion.py --report            # the stdlib signals
python3 bin/fde/verify.py --gate erosion       # enforce the [erosion] budget
```

## The signals (stdlib, language-agnostic)

- **duplicate-block %** — the clone ratio, via normalized line-window
  hashing. Byte-identical files kept in several places (a shared module
  copied into each deploy package) count once; the report says how many
  groups it found, to declare in `generated_paths`.
- **structural erosion** (Python and TypeScript/JavaScript; `jscc.py`
  for the front, calibrated on ESLint) — each function's mass is cyclomatic
  complexity × √SLOC; erosion is the share of the mass in functions with
  CC > 10 — new logic patched into functions already complex. Tests
  excluded, identical bodies once, docstrings out of SLOC; other
  languages report `n/a`. Read it with its count of complex functions:
  a share falls when much simple code lands. Human repositories average
  about 0.34.
- **add/delete ratio** — growth by accretion; a codebase that only grows
  never consolidates.
- **largest change (lines)** — batch size.
- **dependency count** — reinvent-or-import bloat.
- **process-only commits** (`process_only_ratio`) — the share of commits
  in the window that touch only the merge rule's process records
  (`reviews/`, `cycles/`, `promotions/`, `backlog.md`). `specs/` is not
  one: a demand's spec is part of its change. It reads the last N commits
  on HEAD (the window), not the population below, and the report line
  says so; it is a report line only: no budget key, never gated. A high
  share is what the squash at merge (`fde-review`) removes from main's
  history, so after squash merges the ratio falls without the overhead of
  the work itself having fallen.

## What is measured — one population, and you declare it

Every metric reads the **same** set of files.

The population is `[gate] behavior_paths + eval_paths` — the roots you
already declared for I1 — minus `[erosion] generated_paths`, minus vendor
trees (`node_modules/`, `.venv/`, `vendor/`, …). Nothing else is
hardcoded: if your generated tree is `gen/`, `target/`, `.terraform/` or
`third_party/`, name it in `generated_paths` and it stops being counted.

**Retargeting `[gate]` retargets your erosion measurement**: an
`[erosion]` budget is only as live as the roots `[gate]` declares.

Two consequences the report prints rather than hides:

- A root that matches **no tracked file** (stale, misspelled, or declared
  before the code exists) is named in the output. It does not fail the
  gate — a typo and a greenfield root look identical from outside, and
  `[gate]` is written at install time while `[erosion]` is opt-in.
- When the window changed nothing inside the population, the churn
  metrics read `n/a` and the verdict says **"not measured"**, never
  "within budget". A threshold that checked nothing has not been met.

Declaring **no** `[gate]` roots is not an error: churn is then measured
over everything tracked except `cycles/`, the cycle records. A project
that declared nothing is measured whole, never narrowed to kernel
defaults it never asked for.

Deeper metrics (other languages' complexity, exact tool metrics) need
per-language tools (lizard, radon, jscpd): wire them into your eval suite
(I1), never into the gate's path (I6).

## The budget (opt-in, declared — never universal)

Erosion tolerances are project-specific, so thresholds are DECLARED in
`fde.config.toml`, versioned like acceptance criteria (I4). The gate
enforces only the declared keys and is silent when `[erosion]` is absent:

```toml
[erosion]
window = 50                  # commits analyzed
max_add_delete_ratio = 6.0
max_duplication_pct = 8.0
max_dependencies = 40
max_change_lines = 600       # largest NON-ROOT commit; root/scaffold excluded
max_structural_erosion = 0.6 # Python and TS/JS; other languages unmeasured
generated_paths = ["bin/generated/"]   # copies, not organic growth
```

`generated_paths` is the one non-numeric key: the paths this project
generates rather than writes. Excluding a byte-identical, drift-tested
copy is not a carve-out — counting it doubles every change and makes the
mirror read as duplication. Excluding a path you also *edit* is: the
exclusion is in the config diff so a reviewer can see it and contest it.

`max_change_lines` measures the largest non-root commit — a root or
scaffold commit (a bulk import) is excluded, so the budget is safe to
declare on a young repo. An undeclared budget is measured, not gated —
never a false wall. A non-numeric threshold fails the config gate (a typo
must not silently disarm the check).

## Judgment

The review cites MNT-11 (reuse over clone), MNT-12 (deletion is a
feature), MNT-13 (AI output is a draft — reviewed and understood or it
does not merge) and COST-1..3. Never add a graph DB, a metrics service,
or a per-language dependency to the gate's path.

When reporting: read the change in the domain's terms. If the erosion
gate fired, name the metric and the declared budget it breached — and if
duplication is rising, the fix is MNT-11 (consolidate), not a threshold
bump.

## The ratchet and the bounded loop

The budget identifies a deviation and blocks it; the agent corrects it;
nothing loops. Never raise a budget by hand.

- **Blocked at commit**: with the add/delete ratio over its budget, the
  pre-commit refuses a commit that makes it worse (`erosion.py
  --staged`, under a second). A commit that consolidates, or carries 10
  lines or fewer, always passes. Duplication and structural erosion
  block at the merge, where `verify.py --all` must be green.
- **Correct, at most twice**: run `codebench.py`, take the change
  hotspots and clones among the files the work touched, and consolidate
  (MNT-11, MNT-12) in one change of about 300 lines or fewer. Measure
  again. Each attempt must lower the measure; an attempt that does not
  ends the attempts.
- **Then one debt**: still over after two attempts, write the
  consolidation as a backlog line and as the next cycle's first demand,
  and register the debt — `erosion.py --debt C-<n> B-<n>`. It holds the
  breach measured now as the budget's room, so work goes on. A second
  debt is refused while one is open.
- **Due in two closes**: each cycle close runs `erosion.py --close
  C-<n>`. A paid debt is cleared; one unpaid at its second close is
  overdue, `EROSION` fails, and it is a replan for the owner — the only
  time the owner hears of erosion.
- **At every close**: `--close` drops each budget to the measured value
  plus 5% when it improved, never raises one, and glides duplication
  toward 3% and structural erosion toward 0.5 (each close, a tenth of
  the gap). The add/delete ratio has no target — a young product grows
  by addition — only the ratchet.
