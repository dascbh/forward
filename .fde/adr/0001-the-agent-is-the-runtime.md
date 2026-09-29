# ADR-0001 — The agent is the runtime

date: 2026-08-08
status: accepted

## Context

v0.1 shipped a Python CLI (init, compile, adapters per tool). The owner
wants installation to be one sentence to any coding agent: "clone
https://github.com/dascbh/forward and set it up for this project".

## Options considered

- **install.py orchestrator** — rejected: still a CLI; agents improvise
  around it, and script + instructions become two sources of truth.
- **Pure instruction, zero Python** — rejected: pre-commit and CI run
  where no agent exists; without an executable gate, invariants degrade
  to suggestions.
- **SETUP.md as the installer, executed by the agent; only the gate
  payload stays Python** — accepted.

## Decision

Interaction lives in instructions (SETUP.md + skills), executed by
whatever agent is in use. `runtime/` (verify, guard, lib) is the only
code, copied into the client repo at `bin/fde/` (I6). Per-tool adapters
became SETUP step 8 sections.

## Consequences

Determinism moved: the agent executes procedures; the gate audits
outcomes with exit codes (budget sum, floors, isolation, structure).
Setup variance is caught by the wall, not prevented by code. Generated
files carry a marker so drift is diffable.
