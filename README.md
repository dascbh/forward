# FORWARD

A delivery kernel for forward-deployed engineering. Treats **empirical review**
and **adversarial review** as gate invariants, not as methodology phases.

Portable across agentic tools: Claude Code, Codex, Cursor, Copilot, Kiro,
Gemini CLI, Windsurf, Aider. The instruction layer uses standards governed by
the Agentic AI Foundation (AGENTS.md, Agent Skills); the enforcement layer
lives in the repository, not in the IDE.

> FORWARD is the project name; `fde` remains the technical prefix — from
> forward-deployed engineering — in commands (`fde doctor`), skills
> (`fde-review`), and configuration (`fde.config.toml`).

---

## The problem

The FDE model has dense organizational analysis and **no technical acceptance
criteria**. The canonical playbook offers seven org-design lessons — hire the
engineer-diplomat, embed with the client, deliver on day one, treat discovery
as engineering, build the client's ontology, route feedback through the FDE,
refuse the integrator role — and zero definition of "production-ready".

Without that, FDE is sales with a fast PoC, and the criticism that it produces
lock-in and limited functionality stands.

This kernel claims no pioneering in empirical review nor in adversarial
review. Both have lineage: eval-driven development on one side; debate as
supervision, red teaming, and challenger/solver architectures on the other.
The claim is narrower and defensible: **no FDE framework today treats both as
delivery gates, and without that a PoC never becomes production.**

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

## The seven invariants

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

Zero external dependencies. Python 3.11+ (`tomllib` is stdlib). Runs in the
client's repo with nothing to install.

```bash
# 1. parameterize (detects the stack; asks only what cannot be inferred)
python bin/init.py
#    or non-interactive:
python bin/init.py --yes --data-class personal --reversibility irreversible

# 2. compile the native artifacts for the tool in use
python bin/compile.py
git config core.hooksPath .githooks

# 3. see what is actually enforced
python bin/fde/doctor.py

# 4. on demand
python bin/triage.py --surfaces 2 --loc 120     # sizing
python bin/review.py DEM-001 --isolate          # isolated adversarial review
python bin/fde/verify.py --all                  # the gate (same one CI runs)
```

### Commands as skills

Each command has a corresponding skill in `skills/` in the Agent Skills
format — portable, read by ~30 tools. `commands/` is not used: it is a legacy
Claude Code format, not an open standard.

The logic lives in `bin/` as deterministic scripts, never in prompts. Three
reasons: it runs in CI with no agent at all, it does not vary across tools or
across runs of the same model, and it is testable. Stack detection inside a
prompt is different every Tuesday.

---

## Configuration

`fde.config.toml` is the single declarative source, versioned. Auditable
diffs, idempotent recompilation, new projects parameterized by copy,
non-interactive mode for CI.

Two natures, deliberately separated: **parameterizable** (build and test
commands, paths, data class, weights, depths) and **fixed** (the invariants).
Fixed is not a field in the file — the key does not exist.

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
- Adapters covered: Claude Code (`loop`), Codex and Cursor (`commit`).
  Copilot, Kiro, Gemini CLI, and Windsurf work via AGENTS.md in `advisory`
  until they get their own adapter.
- "Adversarial" in ML already means adversarial examples and GANs. Here it
  means process-level adversarial review. Worth disambiguating on first
  mention to anyone coming from ML.

## License

Apache-2.0.
