---
name: fde-survey
description: Architectural reconnaissance of a system nobody documented — read the code, the structure and the git history and produce discovery/survey.md, the map a team needs when it takes over. Use when joining or inheriting an existing codebase, when the user asks what a project is, how it is structured, what the history says, where the risk is, or says the project is undocumented, legacy, or "we just got handed this".
---

# fde-survey

`fde-init` classifies a stack to configure the gate. This is the other
job: **understanding a system you did not build.** It produces
`discovery/survey.md` — an artifact, not an answer in chat (I7), and the
one that fills the `discovery/` input the spec role has always declared.

## The rule that makes it safe

A confident wrong map is worse than no map, because it gets acted on.
**Every claim carries how you obtained it:**

- `[observed]` — you read it in the code, or measured it. Cite the path.
- `[inferred]` — reasoned from evidence and could be wrong. Say from what.
- `[to confirm]` — a question for whoever remains. Do not guess it away.

Never present inference as observation. A survey with fifty `[observed]`
claims and no `[to confirm]` is not thorough, it is dishonest — nobody
inherits a system and understands all of it.

## Order of work

Breadth before depth. Do not start reading files at random.

1. **Run it.** How does it start, what does it need, what breaks first?
   README, Makefile, compose file, CI workflow, entrypoints. What the
   pipeline does is more truthful than what the README claims.
2. **Map the shape.** Top-level structure, then the real module
   boundaries — imports and calls across directories, not folder names.
   Where does data enter, where does it persist, what talks outward?
3. **Ask the history.** `bin/fde/erosion.py --report` for the decay
   signals, then git for the rest: `git log --format='%ad' --date=short |
   sort | uniq -c` for pace, `git log --name-only --format= | sort |
   uniq -c | sort -rn | head -30` for churn hotspots, `git log -1
   --format=%ad -- <path>` for frozen areas. Compose the tools; do not
   reimplement them.
4. **Find the seams.** Where is coupling real (shared schema, shared
   module, implicit contract) versus where the structure only claims
   separation? The seams are where a change will hurt.
5. **Recover the decisions.** What did the code decide that no document
   records — the ORM, the auth model, the multi-tenancy strategy, the
   thing that was clearly a workaround? Each is a candidate for a
   retroactive ADR.
6. **Name the risk and the ignorance.** What has no test, what is a
   single point of failure, what would you not touch on a Friday — and
   what you could not determine.

## The artifact

`discovery/survey.md`, with a header recording the commit surveyed and
the date (a survey is a snapshot; the gate uses this to tell you when it
has drifted), and these sections:

```
## How it runs        — start, deps, deploy, environment
## Shape              — real module boundaries and their dependencies
## History            — churn hotspots, frozen areas, pace changes, erosion signals
## Seams              — where coupling is real vs claimed
## Undocumented decisions — what the code decided, ADR candidates
## Risk               — no tests, single points of failure, do-not-touch
## Unknown            — the questions for whoever remains
```

Check it with `python3 bin/fde/verify.py --gate survey`.

## What this is not

Not an index, not a knowledge graph, not a retrieval layer — the kernel
refused those with evidence (ADR-0010). A survey is read once by a human
and by the next agent, then maintained like any artifact. If it drifts
far from HEAD, the gate says so; re-survey rather than patch a stale map.

Not a substitute for asking. `[to confirm]` items go to whoever remains
while they still remember — that window closes.
