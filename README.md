# FORWARD

A delivery kernel for forward-deployed engineering. Treats **empirical
review**, **adversarial review**, and **heuristic review** as gate
invariants, not as methodology phases.

Portable across agentic tools: Claude Code, Codex, Cursor, Copilot, Kiro,
Gemini CLI, Windsurf, Aider. The instruction layer uses standards governed by
the Agentic AI Foundation (AGENTS.md, Agent Skills); the enforcement layer
lives in the repository, not in the IDE.

> FORWARD is the project name; `fde` remains the technical prefix — from
> forward-deployed engineering — in the skills (`fde-review`, `fde-doctor`),
> the roles (`fde-adversarial`), and the configuration (`fde.config.toml`).

> **Are you a coding agent?** If you were asked to set this kernel up in a
> project, read [`SETUP.md`](SETUP.md) and execute it top to bottom. That
> file is the installer; you are its runtime.

---

## The problem

The FDE model has dense organizational analysis and **no technical acceptance
criteria**. The canonical playbook offers seven org-design lessons — hire the
engineer-diplomat, embed with the client, deliver on day one, treat discovery
as engineering, build the client's ontology, route feedback through the FDE,
refuse the integrator role — and zero definition of "production-ready".

Without that, FDE is sales with a fast PoC, and the criticism that it produces
lock-in and limited functionality stands.

This kernel claims no pioneering in empirical, adversarial, or heuristic
review. All three have lineage: eval-driven development; debate as
supervision, red teaming, and challenger/solver architectures; heuristic
evaluation and expert review. The claim is narrower and defensible: **no FDE
framework today treats them as delivery gates, and without that a PoC never
becomes production.**

---

## How rigor survives speed

"Deliver on day one" was never "production on day one" — it meant running on
real data instead of slides. The kernel's rule:

> **Rigor is constant. Surface varies.**

On day one you deliver something minimal but real: it runs on production data,
has an eval, has observability, could stand indefinitely. Scope shrinks; the
standard never does. That is what qualifies the demo instead of sacrificing
it — not "look what we could do", but "this already works in your
environment, and here is the measurement."

An assumed consequence: there are engagements the kernel **refuses**. A client
with no access to real data, no environment to promote to, no one to receive
operations. `fde doctor` and the gate make that visible before the contract.

---

## Three verification modes

Each pillar has a different oracle, and each reaches what the others
structurally cannot:

- **Empirical** — verdict by execution: an eval passes or fails. Reaches
  everything computable.
- **Adversarial** — verdict by demonstrated failure: a probe produces a
  broken outcome. Reaches what execution alone hides.
- **Heuristic** — verdict by judgment against a declared, versioned
  principle catalog. Reaches what can be bad while everything passes:
  usability, information architecture, craft.

Heuristic review is not licensed opinion. A finding cites the principle it
violates and a severity, or it is not a finding (I8). The catalogs live in
[`quality-attributes.toml`](spec/dimensions/quality-attributes.toml) — each
attribute declares `verified_by` and, where judgment applies, its
`heuristic_principles`.

## The eight invariants

Defined in [`spec/invariants.toml`](spec/invariants.toml). **They have no
configuration key.** Whoever needs to operate without one of them forks the
framework — the fork is visible; a silent exception would not be.

| id | invariant |
|---|---|
| I1 | No behavior change lands without a corresponding entry in the eval suite |
| I2 | Adversarial review receives artifact + spec, never the builder's reasoning |
| I3 | Adversarial success is findings, not approval — and it cannot fix |
| I4 | Promotion criteria declared, versioned, and dated **before** construction |
| I5 | What is not observable is not verifiable: an observability floor |
| I6 | The gate runs in the client's environment, without the FDE present |
| I7 | Handoff between roles is by artifact on disk, never by conversation |
| I8 | Every finding cites the probe that broke it or the principle it violates — naked judgment is not a finding |

---

## The two vectors

Quality attributes and technical domains are different things and do not share
a budget. Mixing them would make "low weight on QA" mean less testing, which
collides with I1.

**Vector A — quality attributes.** A **closed** budget of 100 points. It is
what the client allocates and signs; it becomes a dated record of what they
said mattered. If everything could be high, nobody chose anything.

It governs: adversarial attack order, rounds per dimension, suite sizing, and
what blocks merge above the floor.

**Vector B — technical domains.** Depth 0–3, **derived** from the stack +
triage. Override is *upward-only*: the client can raise, never reduce. Low
weight on data modeling in a data-heavy system is not a preference, it is an
error — and the framework must not allow erring by configuration.

Security appears in both on purpose: in A it is what the delivery
**guarantees**; in B it is **how much specialist work** goes in.

### Floors

Weight moves rigor upward or redistributes emphasis. It never goes below the
floor, and weight zero does not exist. Three floors are high: functional
correctness (it is the definition of delivered), observability (without it
nothing else is verifiable after deploy), and security — whose floor is
**escalated by the data class** set at triage and never lowered by weight. In
vector B, QA is never 0.

---

## The five roles

A role is not a job title. `spec/roles.toml` defines five because each one has
**different access** — tools, context, artifacts. A role running the same
model, in the same context, with the same tools as another is the same role in
a different hat, and the "architect" approves what they themselves designed.

What produces real separation: `denied_tools` (the role cannot), `isolation`
(the role does not see), artifact handoff (I7).

PM, PO, squad lead, and tech lead were deliberately collapsed. They exist in
human org charts because humans lack shared context. Agents have it.

---

## Enforcement: three tiers, declared

The instruction layer is agnostic. The enforcement layer is not and never will
be — hooks, tool restrictions, and worktrees are per-tool implementation with
unequal capability. That is why **the invariant lives in the repository**: git
hook + CI work with any agent, with human devs, and keep working after the FDE
leaves (I6).

| tier | meaning |
|---|---|
| `loop` | hook + per-role restriction. Blocks before the write. |
| `commit` | no hook, but subagents/worktrees exist. Real roles, gate in git. |
| `advisory` | instruction only. Roles are convention, the gate is CI. |

`fde doctor` declares the tier and separates what is actually **enforced**
from what is merely **suggested**. Promising parity and delivering theater in
three out of five tools is what burns an open framework.

---

## Usage

### Install — one prompt

Tell your coding agent — Claude Code, Cursor, Codex, Kiro, whatever reads a
repository — inside the project you want under the kernel:

> Clone https://github.com/dascbh/forward and set it up for this project.
> Follow the kernel's SETUP.md top to bottom: detect the stack from my
> files, interview me only for what files cannot say, allocate the weight
> vector with me, install the gate into the repo, and emit the native
> layer for the tool you are. Finish by running the gate and reporting
> honestly what is enforced versus merely suggested.

The agent executes [`SETUP.md`](SETUP.md); the install ends with the gate
auditing the agent's own work. On a fresh project, I2/I4/I5 red is the
designed result — those turn green when the first demand completes its
cycle, not before.

### Update — one prompt

When this repository gains a new version, in the installed project:

> Update FORWARD: git pull the kernel clone (or re-clone
> https://github.com/dascbh/forward) and re-run SETUP.md steps 6–8 from
> the current sources — runtime and spec into `bin/fde/` and `.fde/spec/`,
> AGENTS.md regenerated, roles and skills re-copied. Overwrite only files
> carrying the FDE-KERNEL:GENERATED marker; merge user-owned files, never
> clobber them. Close with `python3 bin/fde/verify.py --all` and report
> what changed in one status line.

Installed projects pin nothing: updating is re-emitting from current
sources, and drift shows up as a diff in generated files.

### Day-to-day

Each step is a skill in `skills/` (Agent Skills format, portable across
tools; installed into the project for Claude Code):

- `fde-triage` — sizes the demand: which roles enter, how many rounds
- `fde-design` — the design discipline for UI demands: foundation, flow,
  IA, wireframe, design QA, user validation — proportional to size
- `fde-review` — two-pass review, isolated: adversarial probes, then
  heuristic judgment citing the principle catalogs
- `fde-debug` — stop-the-line, six-step triage to root cause, and the
  guard eval that turns the fix into an I1 entry
- `fde-scrum` — optional cadence layer: evidence-labeled backlog, sprints
  with dated goals, review and retro as the user's two sittings
- `fde-verify` — the gate: `python3 bin/fde/verify.py --all` (same as CI)
- `fde-doctor` — what is actually enforced vs. merely suggested
- `fde-sync` — regenerate after config, stack, or tool changes

### The agent is the runtime

There is no CLI to install and no dependency to add. Interaction lives in
instructions (`SETUP.md` + `skills/`), executed by whatever agent is in use.
What remains code is the one thing that must run where no agent exists: the
gate — `runtime/verify.py` and `runtime/guard.py`, copied into the client
repo at `bin/fde/` and called by pre-commit and CI with plain Python 3.11+
stdlib (`tomllib`), zero external dependencies.

The determinism argument did not go away — it moved. The agent executes
procedures; the gate audits outcomes with exit codes. A wrong weight sum, a
floor violation, an unisolated review: caught by code, not by convention.

---

## Configuration

`fde.config.toml` is the single declarative source, versioned. Auditable
diffs, idempotent recompilation, new projects parameterized by copy,
non-interactive mode for CI.

Two natures, deliberately separated: **parameterizable** (build and test
commands, the gate's behavior/eval roots, data class, weights, depths) and
**fixed** (the invariants). Fixed is not a field in the file — the key does
not exist. The gate can be retargeted to the repo's real layout, never
emptied.

Generated files carry `FDE-KERNEL:GENERATED` at the top. Editing them by hand
is guaranteed loss on the next `sync`; the fix belongs at the source.

---

## Known limits

- `evals/` is the expected interface, but the kernel does not impose an eval
  framework. Inspect AI, promptfoo, DeepEval, and a homegrown suite all work
  the same.
- In the `advisory` tier, roles are convention. The gate still holds, at
  commit and in CI.
- `git worktree` is a requirement for forced isolation outside the `loop`
  tier.
- Native layers scripted in `SETUP.md` step 8: Claude Code (`loop`), Cursor
  and Codex (`commit`). Copilot, Kiro, Gemini CLI, and Windsurf work via
  AGENTS.md in `advisory` until they get their own section.
- "Adversarial" in ML already means adversarial examples and GANs. Here it
  means process-level adversarial review. Worth disambiguating on first
  mention to anyone coming from ML.

## License

Apache-2.0.
