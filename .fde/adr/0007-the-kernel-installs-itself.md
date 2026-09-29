# ADR-0007 — The kernel installs itself

date: 2026-08-09
status: accepted

## Context

The kernel preached I1/I4 with a bare repo: no committed eval suite (all
release testing was scratchpad-ephemeral), no gate on its own CI, no
acceptance criteria before construction. Field bugs it shipped — the
template invariants list drifting from the spec — were of exactly the
class its own review would have caught at release time.

## Options considered

- **No self-hosting** — rejected: a kernel that does not practice what it
  enforces has no answer to "why should my repo bear this".
- **Partial (tests + CI only)** — rejected: leaves I4 and adversarial
  review unpracticed; the proof stays incomplete. The ceremony objection
  is answered by the kernel's own triage: a public, reversible repository
  floors at XS/S — the lightest track that exists.
- **Full install per SETUP.md, kernel as client** — accepted.

## Decision

FORWARD runs under FORWARD: fde.config.toml (public, reversible; weights
led by correctness 30 and maintainability 22, both blocking), gate paths
covering `runtime/`, `spec/`, `skills/`, `agents/`, `templates/`, and
`SETUP.md` — per ADR-0001 the instructions ARE the runtime, so they are
behavior. The eval suite is stdlib `unittest`: gate/guard/lib behavior
plus structural integrity of the instruction files (catalog prefixes,
role/skill cross-references, template placeholders, version sync).
Changes flow as demands: triage, spec with dated acceptance, isolated
adversarial review recorded in `reviews/`.

## Consequences

The repo doubles as a living example of an installed project. Friction
felt here (e.g. I1's bluntness on prose-only edits) is felt by the
maintainer first and fixed for every client. CI now blocks what the
kernel merely preached.
