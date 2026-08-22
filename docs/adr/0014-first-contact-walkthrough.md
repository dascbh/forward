# ADR-0014 — First contact is blind, not scripted

date: 2026-08-22
status: accepted

## Context

FWD-017 (ADR-0013) gave the kernel a way to prove a *known* path holds
together: an agent drives a real browser along a planned route, and the
committed script is the evidence. That technique cannot answer an
earlier question — does the interface, on first contact, communicate to
a stranger what this product IS, what they can do, and what happens if
they do it? A planned journey cannot probe that; the agent already knows
the plan. FWD-018 adds the missing capability: two independent agents,
each told nothing about this project beyond a running target, explore
cold and report what they perceived. An `architecture`-compiled
**intended model**, synthesized before either run starts from the design
artifacts `fde-design` already produces, is confronted against both
**perceived models**. Divergence between the two independent, blind
reads of the *same* interface is evidence about the artifact — never a
claim about real users — the third, narrower admissibility category this
ADR adds to `fde-design`'s synthetic-evidence doctrine.

Two facts force the access shape, not a preference for it. First,
`runtime/guard.py` enforces write-scope only; it has never intercepted a
read, and its own module docstring admits the role branch is
honesty-dependent on the harness sending an identity. Second, this repo
already paid for the alternative once: FWD-010's adversarial review
(`reviews/FWD-010/findings.toml`, F1, severity critical) fabricated an
M-sized UI demand with no HMW reframe, no alternatives, no recorded
discard, shipped it through the full suite and `verify.py --all`, and
both went green — the demand's own founding argument had asserted the
fix was "structural," and it was, in the sense of being written down,
not in the sense of being checked by anything. Telling a model not to do
something in a prompt is not enforcement; this repository has the
receipt.

The spec (`specs/FWD-018-first-contact-walkthrough/spec.md`) deliberately
left six concrete calls to architecture: the role's exact
`spec/roles.toml` schema, the `tools:` allowlist contents, the artifact
layout, the divergence-metric formula, whether a gate ships now, and
whether `[walkthrough]` belongs in `fde.config.toml`. This ADR makes all
six, and is the design record implementation builds from — this role
writes nothing to `spec/roles.toml`, `agents/**`, `skills/**`, or
`runtime/**` itself; those paths are `implementation`'s territory in
this self-hosted repo (`CLAUDE.md`'s role-scope mapping), and every
concrete block below is copy-ready text for that role to place, not a
description of a change this ADR itself performs.

One numbering note, named rather than papered over: ADR-0013's own
Consequences section predicted "the next demand, FWD-018" would be a
field proof of journeys against a minimal fixture UI. That demand did
not happen under this id — the owner assigned FWD-018 to this materially
different capability instead. The prediction was simply wrong about
which work would claim the number; it is not a defect in ADR-0013 and
this ADR does not amend it.

## Options considered

**Isolation mechanism.**
- *Prompt instruction alone* ("do not read the spec") — rejected. FWD-010
  F1 is this repository's own proof that an instruction the model can
  ignore under pressure is not enforcement; the same failure would
  reproduce here, and would be worse, because the entire evidentiary
  claim ("two runs that could not have seen the intended model
  diverged") collapses the moment either run's blindness is merely
  requested rather than structural.
- *Extend `guard.py` with read-interception* — rejected. Best-effort
  blocking of every read path the model might attempt is weaker than a
  tool the model does not have; a new denylist for `Read`/`Grep`/`Glob`
  content is one more hand-maintained surface (exactly `guard.py`'s
  existing `ALLOWED` dict problem, FM-5, doubled) and inherits the same
  identity-honesty dependency already named above. Decided by the owner
  directly; not reopened here.
- *A `tools:` frontmatter allowlist naming only browser-automation tools*
  — accepted. Absence of a capability is checkable by inspecting one
  file; best-effort blocking of its use is not. This is the only option
  that turns "cannot read the spec" from a claim about behavior into a
  claim about the tool list.

**Role vs. a mode of an existing role (ADR-0012's razor).** Every
existing role reads `src/**`/`specs/**`/`evals/**` with full access,
including `adversarial`, which already judges `usability_accessibility`
in isolation. None can be parameterized into "structurally cannot see
the repository at all" — that is a different access shape, ADR-0012's
own admission test for a new role, not a title added for flavor.
Rejected: giving `adversarial` a "blind mode" flag — a flag toggling
`inputs` at runtime is exactly the kind of un-auditable branch
`spec/roles.toml`'s own header (`spec/roles.toml:4-19`) exists to
prevent; the schema is the enforcement surface, and a role that
sometimes has full read access and sometimes has none is one role, one
allowlist, doing two contradictory jobs.

**Metric or stay qualitative.** Rejected staying purely qualitative: the
project owner confirmed real production cases exist to calibrate a
numeric divergence score against, right now — unlike FWD-017's situation,
where this repo genuinely had no UI and ADR-0013 named that as an honest
limit. A capability with calibration data available and declined is a
choice this ADR does not make. The formula below is stdlib-only,
deterministic, and bounded, matching ADR-0010's rejection of anything
non-deterministic on a gated path and ADR-0011's rejection of
instructed-not-measured quality.

**Fold into `fde-design`'s `SKILL.md`, or a new subordinate skill.**
FWD-017 folded its technique in because it really was one more item on a
list "Design QA" already kept — Playwright execution, added to a section
that already named Playwright. This demand is not that. It introduces a
genuinely new access pattern (`tools:`-restricted, zero-filesystem, two
fresh isolated invocations) that no existing section of `SKILL.md`
already half-describes, and `SKILL.md` is already long. Folding it in
would bury a structurally distinct mechanism inside a file organized
around a different one. Rejected; `fde-walkthrough` is its own skill
file, subordinate to `fde-design` (it consumes `fde-design`'s artifacts
and never runs before a wireframe exists) the same way `fde-review`'s
`adversarial` role is a role distinct from the skill that invokes it —
precedent already in this repo, not an invention.

**Gate now, or defer.** FWD-017's own precedent: ship the narrow
structural check now (does the artifact shape parse, does the token
match hold on its boundary case), defer any *mandatory-before-promotion*
completeness policy until real usage shows the gap (the R#-coverage rule
ADR-0013 deferred). This ADR draws the identical line, on a different
axis: the opt-in `[walkthrough]` budget gate (does a declared
`divergence_threshold` hold, is a demand's `divergence.toml`
well-formed) ships now, exactly as `[erosion]` did in ADR-0011. A
mandatory "every M/L UI demand runs `fde-walkthrough` before promotion"
policy is explicitly **not** added — no usage evidence yet justifies
forcing it, and this repo has no UI to generate that evidence from
(named again in Consequences).

**Tool allowlist contents.** `WebSearch`/`WebFetch`: rejected, per the
spec's own instruction — no clean, narrow argument surfaced, and both
risk a "blind" run discovering this product's own public docs, marketing
copy, or support pages, reconstructing intended-model-equivalent
information through a side channel the allowlist exists to close. The
same reasoning, applied by architecture beyond the two tools the spec
named, rejects five more browser-automation tools that were technically
available:
- `javascript_tool` — executes arbitrary JS in the page's own context;
  it can read `window` internals, embedded JSON payloads, and source
  content no visual visitor ever sees. That is implementation-level
  introspection, not first-contact perception.
- `read_console_messages`, `read_network_requests` — same failure by a
  different door: API route names, error stack traces, and internal
  field names leak the builder's vocabulary straight into a run that is
  supposed to arrive with none of it. A cold visitor never opens
  DevTools.
- `file_upload`, `upload_image` — both take a local filesystem path as
  an argument (their own descriptions scope this to files "the user has
  shared with this session," but the interface still asks the run to
  name local paths at all). "Structurally cannot touch the local
  filesystem" is a much easier claim to defend, and to have an
  adversarial round probe (acceptance.md's own calibration question),
  when the allowlist contains zero path-taking tools rather than one
  scoped-safe one.
- `gif_creator` — its export path writes a file to disk (`download:
  true`). Same reasoning as above: no tool with a local-write side
  effect belongs on a role whose `write_scope` is `[]` by design.
- `list_connected_browsers`, `select_browser`, `switch_browser` — these
  select *which physical browser or device* to drive, not which page
  within one. `list_connected_browsers`'s own description requires
  routing the choice through a human (`AskUserQuestion`), which breaks
  the "fresh, unassisted, cold" premise on its own; more importantly, a
  developer's own Chrome profile may have this project's spec, GitHub
  repo, or Figma file open in another tab of the *same* browser —
  granting device/browser selection is a materially worse leak channel
  than `WebSearch`, because it does not require the model to guess a
  URL, only to look sideways.
- `browser_batch` — a composite dispatcher that runs a sequence of other
  tool calls in one round trip. Whether its per-item permission check is
  independently enforced against this same allowlist is not something
  this ADR can verify from the tool's description alone; excluding it
  costs nothing (every atomic action it could batch is already
  individually available) and removes a real question the adversarial
  round would otherwise have to chase down.

The ten tools that remain — `navigate`, `computer`, `find`,
`form_input`, `get_page_text`, `read_page`, `resize_window`,
`tabs_context_mcp`, `tabs_create_mcp`, `tabs_close_mcp` — cover
navigating, clicking, typing, scrolling, screenshotting, locating
elements by description, filling forms, reading rendered text and the
accessibility tree, testing responsive states, and managing the run's
own tab lifecycle. `tabs_context_mcp` is confirmed scoped to the
session's own MCP tab *group*, not the browser's other tabs — it is
plumbing the run needs to get a valid `tabId`, not a leak.

**Where `walkthroughs/**` write access lands.** Accepted, as the spec
proposed: `architecture`. It already synthesizes the intended model and
already treats filing a synthesis artifact under `specs/<demand-id>/design/`
as mechanical, not judgment (the same class of act `alternatives.md`
already is). Filing the two runs' verbatim returned text and the
computed score is the identical class of act, one directory over.
Rejected: `implementation` (it is denied `specs/**/acceptance.md` and
`reviews/**` specifically because it cannot rewrite what it will be
judged by — a walkthrough is exactly that kind of judging evidence, and
handing it to the role being judged defeats the isolation the mechanism
exists to provide) and `adversarial` (it reads `walkthroughs/**` to
classify divergences into findings — R9 — and a role that both files the
raw evidence and judges it collapses I2's separation on this one
artifact class specifically).

## Decision

### 1. `spec/roles.toml` — the sixth role

```toml
[[role]]
id = "walkthrough-evaluator"
label = "Walkthrough evaluator"
purpose = """
Explore a running target cold, as a first-time visitor, and report what
the interface communicates it is, what it implies you can do, and what
happens if you do it. Never told the spec, the wireframe, the glossary,
the code, or the builder's intent — structurally incapable of seeing any
of it. Two independent instances of this role produce two perceived
models; where they diverge on the same interface, that divergence is
evidence about the artifact, never a claim about real users.
"""
inputs = ["target-url (supplied at invocation; not a repository artifact)"]
outputs = ["perceived-model (returned as the run's own final message; nothing written to disk by this role)"]
write_scope = []
denied_paths = ["src/**", "tests/**", "evals/**", "infra/**", "specs/**",
                "discovery/**", "docs/**", "reviews/**", "promotions/**",
                "walkthroughs/**"]
isolation = true
isolation_mode = "fresh-agent"
context_policy = "blind"
tools = ["mcp__claude-in-chrome__navigate", "mcp__claude-in-chrome__computer",
         "mcp__claude-in-chrome__find", "mcp__claude-in-chrome__form_input",
         "mcp__claude-in-chrome__get_page_text", "mcp__claude-in-chrome__read_page",
         "mcp__claude-in-chrome__resize_window", "mcp__claude-in-chrome__tabs_context_mcp",
         "mcp__claude-in-chrome__tabs_create_mcp", "mcp__claude-in-chrome__tabs_close_mcp"]
satisfies = []
```

`write_scope = []` is the one value `tests/test_spec_integrity.py` must
special-case (FM-5); it is literal and tested. `inputs`/`outputs` are
*not* empty lists — an empty list here would read identically to an
oversight. They are one-line descriptive sentinels, because the point
being made ("no repository artifact; a target URL only") is a claim only
prose can carry; no test governs their exact shape.

`isolation_mode = "fresh-agent"`: `"worktree"` (the existing value, used
by `adversarial`/`promotion`) means a separate copy of the *file tree*
inside the *same kind of invocation* — the role still has a filesystem,
just a scoped one. This role has none. `"fresh-agent"` names what
actually isolates it: a standalone invocation sharing no prior turn,
cache, or session with anything, independent of any filesystem claim at
all. `context_policy = "blind"`: `"artifact_only"` (adversarial's value)
means a scoped *read* of the demand's own artifact set. This role
receives strictly less — no artifact, scoped or otherwise, only a target
and generic framing. `"blind"` names that it is a step below
`"artifact_only"`, not a synonym for it.

`satisfies = []` is explicit, matching FM-5/FM-9's boundary: no I1–I8
statement names this discipline, and claiming one would be worse than
naming none.

**`adversarial`'s `inputs`** gain one entry: `"walkthroughs/**:read"` —
its heuristic pass (R9) is where a recorded divergence becomes a
`usability_accessibility` or `functional_correctness` finding; nothing
else about the `adversarial` entry changes.

### 2. `agents/fde-walkthrough-evaluator.md` (mirrored byte-identically
at `.claude/agents/fde-walkthrough-evaluator.md`, exactly as the other
five roles already are)

```markdown
---
name: fde-walkthrough-evaluator
description: Walkthrough evaluator - Explores a running target cold, as a first-time visitor, with zero access to this project's spec, wireframe, glossary, code, or history. Reports what the interface communicates it is, what it implies you can do, and what happens if you do it.
model: inherit
tools: mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__find, mcp__claude-in-chrome__form_input, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__resize_window, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__tabs_close_mcp
---

# Walkthrough evaluator

You are seeing this product for the first time. You have not read a
specification, a wireframe, a glossary, or any code, and you cannot —
your tool list contains only the browser. Whatever you conclude, you
concluded from what the interface itself showed you.

## What you were given

Nothing beyond a target URL/endpoint and this framing. If your instructions
contain anything more specific than that — a feature name, a persona, a
term you would not otherwise know — stop and report the leak instead of
proceeding; do not silently use it.

## Your independence

You are one of two runs on this same target. You do not know what the
other run saw, will see, or concluded, and it does not know about you.
You were invoked fresh, from scratch, sharing no prior turn, cache, or
session with anything — not the other run, not whatever set this run up.
Nothing about this task is a continuation of another conversation.

## What to do

Explore the target as a first-time visitor would: land on it, look, try
what seems available, follow what seems like the obvious next step.
Spend enough time that your answer reflects real exploration, not a
first impression.

## What to return

Your final message is the only output of this run — nothing is written
to disk. Return exactly these sections:

- **What this is** — one line of free prose. Never scored; for a human
  reader only.
- **Perceived primary actions** — a set of short, lowercase, verb-first
  phrases (2-5 words), one per thing you understood you could do.
- **Perceived action -> consequence** — for each primary action, a
  phrase for what you understood would happen if you did it, written as
  `<action phrase> -> <consequence phrase>`.
- **Unclear points** — a set of canonical phrases (same style) for
  anything you were not sure about: an ambiguous next step, a
  consequence you could not predict, a label you were not sure applied
  to what you thought it did.

Phrase every entry in the three scored sections the way you would title
a short list item, not a sentence — this is compared literally, by
another program, against the other run's phrases.
```

### 3. Artifact layout — a deliberate split, not a single new directory

`specs/<demand-id>/design/intended-model.md` (existing `architecture`
write scope, alongside `flow.md`/`ia.md`/`alternatives.md`) holds the
**intended** model — synthesized, with full context, by the role that
already produces that whole family of artifacts. A new top-level
`walkthroughs/<demand-id>/` holds `perceived-model-a.md`,
`perceived-model-b.md`, and `divergence.toml` — the **perceived**
models and their confrontation.

These are not the same kind of artifact and must not share a directory
that could imply one is a draft or revision of the other. `intended`
is authored with full context and full intent; `perceived` is received,
verbatim, from a role that was denied both. Filing them side by side in
`specs/<demand-id>/design/` would blur exactly the distinction this
whole capability exists to keep sharp.

`walkthroughs/` also fits this repository's own existing pattern better
than nesting does. `discovery/`, `specs/`, `reviews/`, and `promotions/`
already give each distinct stage of the demand loop its own top-level
directory; `runtime/verify.py`'s `gate_artifact_handoff` already checks
for exactly this shape (`expected = ["specs", "docs/adr", "evals",
"reviews"]`, tolerant of one missing). `walkthroughs/` is structurally
closer to `reviews/` — both hold output from an isolated role that never
touches `specs/**` — than to anything inside `specs/design/`, which
holds artifacts an unisolated role writes with full context. It is not
added to `gate_artifact_handoff`'s expected list, for the same reason
`discovery/` already is not: both are opt-in, demand-specific artifact
kinds, not part of the always-present core handoff surface every demand
uses.

`divergence.toml` shape:

```toml
demand = "FWD-018"
score = 0.222                       # [0, 1], see formula below
threshold = 0.30                    # copied from [walkthrough].divergence_threshold at compute time, if declared
intended_model = "specs/FWD-018-first-contact-walkthrough/design/intended-model.md"
perceived_model_a = "walkthroughs/FWD-018-first-contact-walkthrough/perceived-model-a.md"
perceived_model_b = "walkthroughs/FWD-018-first-contact-walkthrough/perceived-model-b.md"

[per_slot]
primary_actions       = { intersection = 1, union = 3, distance = 0.667 }
action_consequences   = { intersection = 2, union = 2, distance = 0.0 }
unclear_points        = { intersection = 2, union = 2, distance = 0.0 }
```

### 4. The divergence metric (`runtime/walkthrough.py`)

Each perceived-model `.md` file is a plain heading-and-bullet document
(shown in full in §2's `agents/` body above), parsed with stdlib string
splitting — no markdown library, matching I6. Three slots are scored:
`primary_actions`, `action_consequences` (each pair canonicalized as
`"<action> -> <consequence>"` before set membership, so agreeing on the
action but not the consequence still counts as disagreement on that
pair — that is a real divergence, not noise), and `unclear_points`. The
free-prose "what this is" line is parsed and returned to callers for
human reading but never touches the score (R7).

Normalization, per phrase: `phrase.strip().lower()`, internal whitespace
collapsed to one space via `re.sub(r"\s+", " ", ...)`. Each slot becomes
a Python `set[str]` of normalized phrases.

Per-slot distance, a Jaccard-class formula over stdlib set operations
only:

```
d(A, B) = 0                          if A and B are both empty
d(A, B) = 1 - |A ∩ B| / |A ∪ B|      otherwise
```

Both-empty scores 0 deliberately: two runs that each report *no* unclear
points agree with each other on that slot, not "cannot be compared."

Overall score is the unweighted mean of the three slot distances:

```
score = (d(primary_actions) + d(action_consequences) + d(unclear_points)) / 3
```

Deterministic (pure string/set ops, no randomness), symmetric (`A ∩ B`
and `A ∪ B` do not care which run is "first"), bounded to `[0, 1]`
(every `d` term is), and never reads the prose slot — all four of R7's
requirements are structural properties of this formula, not properties
that need separate proving.

Worked boundary cases (the fixtures `tests/test_walkthrough.py` must
assert, per R12):
- **Identical sets on all three slots** → each `d = 0` → `score = 0`.
- **Fully disjoint, non-empty sets on all three slots** → each `d = 1`
  → `score = 1`.
- **Partial overlap** — e.g. `primary_actions` A = `{"buy product", "view
  cart"}`, B = `{"buy product", "checkout now"}` (intersection 1, union
  3, `d = 0.667`), the other two slots identical (`d = 0` each) →
  `score = 0.667 / 3 = 0.222`. This is the exact value in §3's example
  `divergence.toml`.

**This is a first cut, not a final claim.** Equal weighting across the
three slots is a starting assumption with nothing behind it yet but
face validity — mirroring ADR-0011's own humility about this
repository's erosion numbers ("a partial datapoint, not proof").
Calibration against the project owner's real production cases is what
would tell us whether the weights, or the formula shape itself, need to
change; that calibration is explicitly out of scope for this repository
(Consequences, below).

### 5. Gate: opt-in, structural, no completeness mandate

`runtime/verify.py`'s `KNOWN_GATES` gains `"walkthrough"`, and a
`gate_walkthrough(self, explicit: bool = False)` method following the
exact `gate_erosion`/`gate_survey`/`gate_scrum` shape:

- `[walkthrough]` absent from `fde.config.toml` → silent, unless invoked
  explicitly (`--gate walkthrough`), which reports "walkthrough mode off."
- `enabled = true` but `divergence_threshold` undeclared → **"not
  measured,"** never a vacuous pass — identical to `[erosion]`'s rule
  that a threshold measuring nothing is not a pass (ADR-0011's
  amendment, quoted directly: *"a threshold that measured nothing is not
  a pass"*).
- `enabled = true`, `divergence_threshold` declared, but **zero**
  `walkthroughs/**/divergence.toml` files exist anywhere in the repo →
  also **"not measured"** — there is nothing yet to check the declared
  budget against. This is the same doctrine applied one step earlier:
  a budget with no artifact to measure is exactly as unmeasured as a
  budget with no threshold.
- Otherwise, every `walkthroughs/<demand-id>/divergence.toml` found is
  checked against `divergence_threshold`; any `score` that exceeds it is
  a breach (`divergence_threshold` is a maximum-tolerable ceiling, the
  same semantics as `[erosion]`'s `max_*` keys, kept as the literal name
  the spec already fixed).

No mandatory "every M/L UI demand runs `fde-walkthrough` before
promotion" policy is added, for the reason given under Options
considered: FWD-017's own precedent is to defer a completeness mandate
until real usage shows the gap, and this repository cannot generate that
usage evidence (no UI). A future demand is free to add that policy once
a client project's experience justifies it.

`runtime/graph.py`'s `forbidden_orphans()` gains the matching checks
(§8), so the shape-level guarantee the gate needs (an intended model
exists before either run, both runs are on record before a divergence
score is trusted) is enforced by the graph, not re-implemented inside
the gate.

### 6. `[walkthrough]` in `fde.config.toml` / `templates/fde.config.template.toml`

Commented out by default, placed after `[erosion]`:

```toml
# [walkthrough]
# optional first-contact divergence budget (fde-walkthrough skill) — the
# gate enforces only the keys you declare, and is silent when this
# section is absent
# enabled = true
# divergence_threshold = 0.30
```

Exactly two keys, deliberately. `run_count` is **not** a config key —
the two-run protocol is not a ceremony dial, it is the load-bearing part
of the admissibility claim itself (R5, category 3): the argument is
specifically that *two* independently-arrived-at readings diverged.
`run_count = 1` cannot produce a divergence at all; `run_count = 3+`
would need a genuinely different aggregation formula (this ADR's
pairwise Jaccard mean does not generalize to N runs without redesign).
Making it configurable would let a client silently reinterpret what the
metric means without anyone having to say so. A demand that wants N-way
divergence someday is free to open one and redesign the formula — not to
turn a knob on this one.

### 7. Write scope and `guard.py`

`architecture`'s `write_scope` becomes `["docs/adr/**", "specs/**",
"walkthroughs/**"]` (`denied_paths` unchanged — `walkthroughs/**` was
never denied to it). `runtime/guard.py`'s `ALLOWED` dict gains the
matching entry in the same change:

```python
ALLOWED = {
    "fde-spec": ("specs/", "discovery/"),
    "fde-architecture": ("docs/adr/", "specs/", "walkthroughs/"),
    "fde-adversarial": ("reviews/",),
    "fde-promotion": ("promotions/",),
}
```

This closes FM-1/FM-5's own named risk for this path specifically:
`ALLOWED` is hand-maintained, not derived from `spec/roles.toml`, so the
schema change and the guard change ship in the same commit or the write
scope is unenforced.

### 8. `runtime/graph.py`

Three new node kinds, reusing the file's own two existing id-keying
conventions rather than inventing a third: `intended-model` and
`divergence` are single-per-demand, keyed by `did` (the same convention
`spec`/`acceptance`/`architecture`/`promotion` already use);
`perceived-model` is multi-per-demand, keyed `f"{did}#a"` / `f"{did}#b"`
(the same convention `finding`'s `f"{did}#{i}"` already uses).

Edge kinds: `modeled_by` (`demand -> intended-model`, continuing the
past-participle family `specified_by`/`accepted_by`/`designed_by`/
`promoted_by`/`reviewed_by`), `walked_by` (`intended-model ->
perceived-model`, one edge per run — two per demand), `confronted_by`
(`perceived-model -> divergence`, one edge per run — a `divergence`
node's in-degree of exactly 2 is the structural signature of "two
independent runs," directly checkable). For divergence reaching a
finding, this ADR reuses the existing `cites` edge kind but keeps its
existing direction — `finding -> cites -> divergence` — rather than the
spec's own sketch of the reverse. Every existing `cites` edge is
finding-sourced (a finding cites *its own justification*: a principle or
a probe); reversing the direction for one artifact type alone would
silently redefine what `cites` means everywhere else in the graph for a
convenience that isn't worth that cost.

`forbidden_orphans()` gains three checks, each an impossible state
(never an incomplete one, matching `design.py`'s own stated discipline):
1. a `divergence.toml` whose `perceived_model_a`/`perceived_model_b`
   pointer names a file that does not exist on disk;
2. a `perceived-model-*.md` present under `walkthroughs/<demand-id>/`
   with no `specs/<demand-id>/design/intended-model.md` counterpart —
   this makes R4's ordering requirement (intended model compiled
   *before* either run) an observable graph failure, not a documentation
   promise (FM-4, FM-9, and the fixture R12 requires);
3. a `divergence.toml` whose node has fewer than two incoming
   `confronted_by` edges — the graph-level form of FM-3 (the two runs
   were not, in fact, both on record).

### 9. `spec/dimensions/quality-attributes.toml` — `USE-15`

The full `USE-1..14` text was read in this session before this addition
was proposed, per R9's own discipline. None of them cover this judgment:
`USE-3` (consistency) is a static, same-screen-vs-screen check; `USE-13`
(hesitation) and `USE-14` (agent completion is not evidence) both
concern a single agent executing a single planned journey, not two
independent blind reads of the same unplanned first contact. This is a
distinct judgment and earns the next free id:

```
USE-15 interpretive divergence is evidence about the artifact: two
independently isolated, blind runs disagreeing on the primary action,
the primary object, or the expected consequence of the same
first-contact surface is an ambiguity finding in the interface itself —
never a claim about how real users would read it, and never satisfied
by one run alone
```

No new `functional_correctness` (`DOM-*`) id is minted preemptively.
R9's routing allows citing an *existing or new* id when a divergence
traces to a demonstrable bug rather than genuine ambiguity — most such
cases will likely fit `DOM-3` (the UI implies a capability the system
does not actually have) or `DOM-6` (the interface's implied consequence
contradicts a de facto behavioral contract). ADR-0012's recurrence
discipline governs catalog growth: a new id is earned by a pattern of
findings that do not fit, not declared in advance of any.

### 10. `skills/fde-design/SKILL.md` — "User validation"

One sentence, placed immediately after the existing FWD-017 Suchman
sentence, never replacing or reordering what is already there:

> A narrower claim IS admissible from a synthetic source: not "users
> will feel X" (still inadmissible) and not "the agent completed the
> plan" (still not evidence by itself, USE-14) — but "this interface
> sustains two reasonable, independently-arrived-at interpretations,"
> demonstrated by `fde-walkthrough`'s two isolated, blind runs reading
> the same first-contact surface and diverging. This is a claim about
> the artifact via demonstrated blind replication, never a population
> claim, and it is satisfied only by two genuinely independent runs —
> one run's confusion is an anecdote, not a finding.

### 11. Calibration: structural here, real in the client repo

This repository declares `data_class = "public"` (`fde.config.toml`
`[triage]`) — an open Apache-2.0 repository. Embedding even a
"sanitized" real production case here risks carrying some client's
product specifics into a public repo regardless of how carefully it is
scrubbed; that risk is not worth taking to save a client-repo step.
Calibration against the project owner's real production cases is
therefore a client-repo activity, not something this ADR builds a
fixture for. What this repository proves is structural only:
`tests/test_walkthrough.py` builds constructed, fabricated interfaces
(never derived from any real product) to exercise the metric's boundary
cases (§4) and the gate's silent/measured/breach states (§5) — the same
honest limit ADR-0013 already named for journeys, applied here to a
different mechanism.

## Consequences

**What ships.** A sixth role with zero filesystem access, enforced
structurally rather than by instruction; a subordinate skill file; a
stdlib, deterministic divergence metric with a named first-cut weighting;
an opt-in gate that reports its own absence of measurement honestly; a
new top-level artifact directory that fits this repo's existing
directory-per-stage pattern without extending its mandatory handoff
check; one new heuristic principle, added only after confirming it does
not restate an existing one; and one sentence extending, never
rewording, `fde-design`'s synthetic-evidence doctrine.

**What is deferred, and why.** A mandatory pre-promotion completeness
policy — deferred exactly as ADR-0013 deferred the analogous rule for
journeys, until a client project's real usage shows the gap is worth
forcing. Real-case metric calibration — deferred to client repos, on a
public-repo data-class argument this repo did not previously need to
make explicitly. A configurable run count — rejected outright, not
merely deferred, because it is load-bearing to the admissibility claim
itself, not a ceremony knob.

**The honest scope limit.** This repository's own kernel work has no UI
to run a walkthrough against — `user_facing = false` in its own
`fde.config.toml`, the identical limit ADR-0013 already named for
journeys. What this ADR and the demand behind it can prove here is that
the mechanism is structurally sound: the role cannot reach the
filesystem, the metric is deterministic and bounded on constructed
fixtures, the gate reports "not measured" rather than a vacuous pass,
and the graph has no orphan states for the new artifact kinds. Whether
two blind runs against a *real* interface produce a divergence score
that actually tracks real ambiguity — the question the project owner's
production cases exist to answer — is proven in the client projects
where `fde-walkthrough` actually runs against a real target, not here.
