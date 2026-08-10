# Survey — FORWARD

commit: e42bb87e23054e025a42a30a4a2de1e533ab1d8a
date: 2026-08-09

The kernel surveying itself: the dogfood for FWD-015, and the worked
example of the format. Every claim carries how it was obtained.

## How it runs

- `[observed]` No build, no install, no dependency: Python 3.11+ stdlib
  only. `python3 -m unittest discover -s tests` runs the suite;
  `python3 bin/fde/verify.py --all` runs the gate (`fde.config.toml`,
  `[stack]`).
- `[observed]` CI is one workflow, `.github/workflows/fde-gate.yml`: full
  history checkout, tests, then the gate with `--since` on the push range.
- `[observed]` Nothing deploys. The delivery is the repository — consumed
  either as a Claude Code plugin (`.claude-plugin/marketplace.json`, this
  repo is its own marketplace) or as a clone whose `runtime/` and `spec/`
  are copied into a client project.
- `[observed]` A pre-commit hook (`.githooks/pre-commit`) runs the fast
  half of the gate; `git config core.hooksPath .githooks` arms it.

## Shape

- `[observed]` Four layers, and the boundary between them is the whole
  design: `spec/` declares (invariants, roles, quality/domain vectors, the
  UI reference base); `runtime/` enforces (verify, guard, graph, erosion,
  design, survey, fde_lib); `skills/` + `agents/` + `SETUP.md` instruct;
  `templates/` is what gets emitted into a client.
- `[observed]` `runtime/fde_lib.py` is the only shared module — every
  other runtime file imports it and nothing else of the kernel's.
  Dependency direction is one-way and flat.
- `[observed]` The repo is installed on itself (ADR-0007): `bin/fde/` and
  `.fde/spec/` are byte-identical copies of `runtime/` and `spec/`,
  enforced by `tests/test_install_sync.py`.
- `[inferred]` That mirroring is the single biggest source of structural
  risk here — four parallel copies of the same facts (source, mirror,
  template, generated surface). Inferred from the review history, not from
  a failure: the graph ranks MNT-1 (single source of truth) as the most
  cited principle at 25.0 severity-weighted, 3x the next.

## History

- `[observed]` 15 demands (FWD-001..015) across 6 sprints, all in one
  day's working session — this is a young repository with a dense history,
  not a long-lived one.
- `[observed]` Churn hotspots over the last 80 commits:
  `.claude-plugin/plugin.json` (24), `spec/invariants.toml` (22),
  `templates/fde.config.template.toml` (21), `README.md` (15),
  `templates/AGENTS.md.template` (14), `SETUP.md` (13).
- `[inferred]` The top three are not design churn: they are the version
  carriers, touched by every release bump. The real behavior churn is
  `runtime/verify.py` (11) — the file every new gate lands in.
- `[observed]` Erosion signals at this commit: add/delete ratio 6.08,
  duplicate blocks 1.1%, largest change 2854 lines, zero dependencies —
  within the declared `[erosion]` budget.
- `[observed]` The 2854-line change is the root commit (a bulk import),
  excluded from the batch-size metric by `--min-parents=1`.
- `[observed]` Every demand since FWD-001 carries an isolated adversarial
  review in `reviews/`, and the fixes always land in a commit separate
  from the findings (enforced by I3).

## Seams

- `[observed]` `runtime/` ↔ `bin/fde/`: not a boundary but a mirror. CI
  executes the `bin/fde/` copy while the suite imports `runtime/`; only
  the identity test keeps them the same file.
- `[observed]` `spec/` → everything: the gates, the roles, the AGENTS
  surface and the skills all derive from it. A spec edit propagates to
  four places, none automatically.
- `[observed]` `verify.py` → the gate modules (`graph`, `erosion`,
  `design`, `survey`): each gate imports its module inside the method and
  catches Exception, so a broken module degrades to a red gate line
  instead of taking the verifier down.
- `[inferred]` The instruction layer (`skills/`, `AGENTS.md`) is coupled
  to the runtime only by convention — a skill can name a flag that does
  not exist and nothing catches it except a test written on purpose.
  Inferred from the FWD-010 review, where exactly that happened.

## Undocumented decisions

- `[observed]` Twelve ADRs cover the structural decisions (0001 the agent
  as runtime … 0012 divergence and references), so this repo is unusually
  well covered. What follows is what they do NOT record.
- `[to confirm]` Why `fde-` prefixes every skill: the README states it is
  the technical prefix from forward-deployed engineering, and FWD-014
  found a second reason (collision with Claude Code's built-in `/init`
  and `/review`). Neither is in an ADR — candidate for a retroactive one.
- `[to confirm]` Why TOML over YAML/JSON for the spec: `tomllib` being
  stdlib since 3.11 is the likely reason (it would preserve the zero-
  dependency rule), stated in `fde_lib.py`'s docstring but never as a
  decision.
- `[inferred]` The choice to keep gate thresholds opt-in (`[erosion]`,
  `[survey]`, `[scrum]`) rather than defaulted comes from the invariant
  rule — an invariant has no configurable key, so anything needing a
  threshold cannot be one. Stated across ADR-0011 and the scrum ADR, never
  as a rule of its own.

## Risk

- `[observed]` `runtime/verify.py` is the single point of failure: every
  gate lives there, CI runs it, the hook runs it. It is also the most
  churned behavior file.
- `[observed]` Distribution is unverifiable from inside the repository:
  the plugin install path is exercised by `claude plugin validate` only
  where the CLI exists, and the suite skips it otherwise. Nothing tests
  that a real `/plugin install` in a clean environment works.
- `[inferred]` The reference base (`spec/references/ui-patterns.toml`)
  carries claims about external projects that drift — maintenance
  verdicts, licences, counts. A staleness test exists, but it goes red on
  a schedule, not on the world changing.
- `[to confirm]` No project other than this one has completed an install
  end to end. AGROMETA is several versions behind and its update has not
  been run, so the client path is proven by construction, not by use.

## Unknown

- `[to confirm]` Whether the plugin's hooks work: the guard is installed
  at project level, and whether a plugin can ship it is undocumented
  upstream. Untested.
- `[to confirm]` Whether the divergence lenses actually produce better
  designs, or only more artifacts. There is no measurement, only a gate.
- `[to confirm]` How the kernel behaves in a large brownfield repository —
  every signal here (erosion, graph, survey) has only been exercised on
  this repo and on scratch fixtures.
- `[to confirm]` Whether an agent other than the one that wrote the skills
  reads them the same way. The whole instruction layer is unvalidated
  across tools: Codex, Cursor and Kiro paths exist in SETUP and have never
  been run.
