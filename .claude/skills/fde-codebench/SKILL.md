---
name: fde-codebench
description: Code-quality view over the history: complexity, functions over CC 10, structural erosion, clones, and the hotspots that grew. Use when asked how code quality is trending, where complexity piles up, whether the tests catch bugs, or for a benchmark.
---

# fde-codebench

```bash
python3 bin/fde/codebench.py                 # 6 snapshots + install + HEAD
python3 bin/fde/codebench.py --points 10 --top 20
python3 bin/fde/codebench.py --format json
python3 bin/fde/codebench.py --tests        # the suite's effectiveness instead
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

**Change (since the FORWARD install):** change hotspots — commits
touching a file × its lines (Tornhill): complex code that keeps changing
is where a refactor pays. Change coupling — two files changed together
in at least 5 commits and 70% of the less-changed one's: plan them in
one cycle or the foundation (kernel ADR-0024), never in parallel slices.

**Process:** beside the code, read from git and files only: test lines
against production lines, the last suite run recorded by
`verify.py --all --record-suite` (seconds, exit), cycle time, lead time
and wait for sign-off as medians over closed cycles, each running
cycle's age, and each objective (cycles joined by `depends:`) with its
lead time or how long it has been open (`status.py --flow`). Delivery,
DORA's measures with a closed cycle as the deployment: deployment
frequency, lead time for changes (commit → first close after it),
change failure rate (reverts of commits already deployed) and failed
recovery time (close → revert). A backlog origin `(C-<n>)` is no defect
signal — it marks follow-ups and debt too. Reviews: findings per demand,
the blocking share, the share that passed in one round with no blocker. The suite's
effectiveness runs tests, so it is not here: `--tests`.

**Hotspots:** the functions with the most complexity mass at HEAD, their
CC at the install (`a → b` grew, `new` appeared since), marked ◆ when
their file is a controller touching data.

The population is the project's own source: `[gate]` roots minus
`[erosion] generated_paths`, tests out, byte-identical copies once.

Limits: complexity and function measures are Python only; other languages count in size, SQL, layers and
clones. Snapshots are committed trees, not the working copy.

## The suite's effectiveness (`--tests`)

Time says what a suite costs and coverage what ran; a mutation score
says what the tests would catch. The cycle review runs it unasked
(`fde-review`); run it by hand the same way:

```bash
python3 bin/fde/codebench.py --tests                       # 10-minute budget
python3 bin/fde/codebench.py --tests --changed-since <ref> # what changed since
```

Nothing to choose. Modules: the project's own Python modules with tests
— named after them (`test_<stem>.py`) or importing them. Runner: pytest
when `[stack] test_command` names it or a conftest.py exists, unittest
when it names unittest or nothing; otherwise, or when the project's
command is a CI script, find the one-file command yourself and declare
it once (`[codebench] test_file_command = "<cmd> {test}"`) — never ask
the owner. Size: the budget is split across modules by their baseline
time; `--minutes M`, or `--mutants N` per module.

Each module's tests run once unchanged (the baseline and its seconds; a
failing baseline is skipped, not scored), then on the sampled mutants —
a comparison flipped, `and`/`or` swapped, an `if` negated, an integer
+ 1, a returned boolean inverted. Killed is caught; a survivor is a
defect every test of the module lets through, listed with its line.
Also shown: test lines against production lines.

It runs in a temporary worktree at HEAD and never writes the working
copy (other sessions may be committing there); what the tests need and
git ignores — build output, node_modules, a venv — is linked in.

Read the survivors, not the score alone: an integer + 1 on a default or
a limit is often harmless; a surviving `if` or comparison is logic no
test pins. High score with a large suite: consolidation is safe there.
Low score: the tests to strengthen, as a backlog item.
