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

## What it shows

**Now (HEAD), each with the reference it is read against:**
- lines of code per language; files over 1000 lines (Pylint);
- Python functions: CC average, p90 and max, Radon ranks (A 1-5 … F
  41+), functions over CC 10 (McCabe; NIST SP 500-235), and Pylint's
  limits for statements (50), arguments (5), branches (12), nesting (5);
- structural erosion: the share of complexity mass (CC × √SLOC) in the
  functions over CC 10 — human repositories average about 0.34. Read it
  with the count over CC 10: the share falls when a lot of simple code
  lands even while complex functions keep growing;
- clones: recurring 6-line windows (SonarQube's gate is 3% on new code);
- SQL: statements embedded in source, and lines in .sql files;
- controllers: how many hold SQL or call the database or storage
  directly — the model's work done in the controller (MVC; MNT-2).
  Declare which paths are controllers:

  ```toml
  [codebench]
  controller_paths = ["backend/lambdas/", "api/routers/"]
  ```

  Undeclared, common names (handler, routers, views, controllers) are
  detected and the report says so.

**Trend:** snapshots spread over the history, the FORWARD install commit
and HEAD: LOC, functions, CC, over CC 10, erosion, clones, SQL, and
controllers touching data.

**Hotspots:** the functions with the most complexity mass at HEAD, their
CC at the install (`a → b` grew, `new` appeared since), marked ◆ when
their file is a controller touching data.

The population is the project's own source: `[gate]` roots minus
`[erosion] generated_paths`, tests out, byte-identical copies once.

Limits: complexity and function measures are Python only; other languages count in size, SQL, layers and
clones. Snapshots are committed trees, not the working copy.
