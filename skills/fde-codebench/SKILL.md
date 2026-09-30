---
name: fde-codebench
description: Code-quality view over the history: complexity, functions over CC 10, structural erosion, clones, and the hotspots that grew. Use when asked how code quality is trending, where complexity piles up, or for an erosion benchmark.
---

# fde-codebench

```bash
python3 bin/fde/codebench.py                 # 6 snapshots + install + HEAD
python3 bin/fde/codebench.py --points 10 --top 20
python3 bin/fde/codebench.py --format json
```

It reports; it never gates. The gate with a budget is `fde-erosion`, and
both read the same measures, so they cannot disagree.

Show the output as it is. Then say, in two or three lines, what moved
between the FORWARD install and HEAD, and name the top hotspot that grew.
Do not turn a hotspot into a fix unasked: a refactor is a demand like any
other; offer it as a backlog item.

## What each column means

- **files, LOC** — the project's own source: `[gate]` roots minus
  `[erosion] generated_paths`, tests out, byte-identical copies once.
- **fns, CC avg, p90, max** — Python functions (identical bodies once)
  and their cyclomatic complexity, counted as Radon does.
- **CC>10** — functions over the complexity cutoff.
- **erosion** — the share of complexity mass (CC × √SLOC) in those
  functions. Read it with CC>10: the share falls when a lot of simple code
  lands even while complex functions keep growing.
- **clones%** — the clone ratio (6-line windows that recur).
- **human ref.** — 473 open-source Python repositories average about
  0.34 structural erosion.
- **hotspots** — the functions with the most mass at HEAD, with their CC
  at the FORWARD install (or the first snapshot): `CC a → b` grew,
  `new` appeared since.

Limits: complexity is Python only; other languages count in size and
clones. Snapshots are committed trees, not the working copy.
