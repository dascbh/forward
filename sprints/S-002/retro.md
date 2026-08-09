---
sprint: S-002
date: 2026-08-09
---

# Retro — S-002

## 1. What cost more than it returned?

- Batching five demands into one adversarial round (rather than one per
  demand) worked: the reviewer found a cross-demand interaction (FWD-005 ×
  the allowlist) that per-demand review would likely have missed. Keep
  batch review for tightly coupled demands.
- Nothing else notably over-cost. The per-demand triage rule (FWD-003)
  immediately paid off: FWD-004 and FWD-007 sized XS instead of the M
  they would have floored at last sprint.

## 2. What did the gate catch — and what did it let through?

- Caught: the parity test (FWD-003) flagged a real divergence between the
  template and AGENTS.md on first run; the guard-scope regression
  (FWD-005) surfaced live in review, not in prod.
- Let through: nothing known. CI green every push.
- Gap noticed (became the next sprint): the traceability chain the kernel
  asserts in prose (goal → sprint → demand → spec → review → promotion)
  is not machine-checked end to end. DOM-5 is an orphan-sweep principle
  with no gate; FWD-007's `agent_transcript` was the first explicit edge
  with nothing consuming it.

## 3. What changes?

- The gap above, plus a research question ("is graph-based context the
  evolution of loops?"), converged into S-003's goal: make the latent
  artifact graph explicit and gate-consumed — evidence, not a database.
  The research (ADR-0010) is what turned an open enthusiasm into a scoped
  demand instead of a graph-DB detour.
- Process working as designed; no kernel-mechanism change this retro.
