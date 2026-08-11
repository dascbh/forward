---
name: fde-erosion
description: Measure and gate the long-term decay of AI-built code — erosion, verbosity, efficiency. Use when the user worries an AI-built codebase will rot, asks about technical debt / bloat / duplication / maintainability over time, wants to set an erosion budget, or invokes the thesis that AI applications are doomed long-term. Also use to read the erosion signals or explain why the erosion gate fired.
---

# fde-erosion

The thesis this answers: *every application built with generative AI is
destined to fail in the long term.* Four long-horizon studies give it
teeth — coding agents degrade **monotonically**: SlopCodeBench (arXiv
2603.24755) measures erosion in 80% of trajectories, verbosity in 89.8%,
complexity 10×, agent code 2.2× more verbose than maintained repos, while
humans stay stable. The decisive finding is negative: **prompts do not
fix it** — "anti-slop" prompts cut initial verbosity a third but
degradation resumed at the identical rate at higher cost. So this is
measurement, not instruction (ADR-0011).

```bash
python3 bin/fde/erosion.py --report            # the stdlib signals
python3 bin/fde/verify.py --gate erosion       # enforce the [erosion] budget
```

## The signals (stdlib, language-agnostic)

- **duplicate-block %** — the clone ratio the papers measure, via
  normalized line-window hashing.
- **add/delete ratio** — growth by accretion; a codebase that only grows
  never consolidates (the reuse inversion the papers name).
- **largest change (lines)** — batch size; large batches carry DORA's
  instability.
- **dependency count** — reinvent-or-import bloat.

## What is measured — one population, and you declare it

Every metric reads the **same** set of files. Two definitions of "the
codebase" inside one tool is how a number stops meaning anything.

The population is `[gate] behavior_paths + eval_paths` — the roots you
already declared for I1 — minus `[erosion] generated_paths`, minus vendor
trees (`node_modules/`, `.venv/`, `vendor/`, …). Nothing else is
hardcoded: if your generated tree is `gen/`, `target/`, `.terraform/` or
`third_party/`, name it in `generated_paths` and it stops being counted.

**Retargeting `[gate]` retargets your erosion measurement.** That is the
point — decay is measured where you said behavior lives — and it is the
one operational fact to carry over from install: an `[erosion]` budget is
only as live as the roots `[gate]` declares.

Two consequences the report prints rather than hides:

- A root that matches **no tracked file** (stale, misspelled, or declared
  before the code exists) is named in the output. It does not fail the
  gate — a typo and a greenfield root look identical from outside, and
  `[gate]` is written at install time while `[erosion]` is opt-in.
- When the window changed nothing inside the population, the churn
  metrics read `n/a` and the verdict says **"not measured"**, never
  "within budget". A threshold that checked nothing has not been met.

Declaring **no** `[gate]` roots is not an error: churn is then measured
over everything tracked. A project that declared nothing is measured
whole, never narrowed to kernel defaults it never asked for.

Deeper metrics — exact cyclomatic complexity, the SlopCodeBench
structural-erosion measure (complexity mass in high-CC functions) — need
per-language tools (lizard, radon, jscpd). Wire them into your eval suite
(I1), as the kernel delegates the eval framework; the kernel keeps I6.

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

## The doctrine — why measured, not prompted

The judgment half lives in the catalogs a review cites (I8): MNT-11
(reuse over clone), MNT-12 (deletion is a feature), MNT-13 (AI output is
a draft — reviewed and understood or it does not merge), and COST-1..3
(efficiency and spend). But the papers prove judgment-in-a-prompt is not
enough: what stops the monotonic decay is the boring governance the
kernel already is — I1 (tests as the anchor), I2/I3 (isolated review), I7
(handoff by artifact, no conversation) — plus this trend measurement. Do
not add a graph DB, a metrics service, or a per-language dependency to
the gate's path; the language-agnostic subset is stdlib and I6-pure, and
the rest is the client's to wire into their own eval.

When reporting: read the change in the domain's terms. If the erosion
gate fired, name the metric and the declared budget it breached — and if
duplication is rising, the fix is MNT-11 (consolidate), not a threshold
bump.
