# ADR-0012 — Divergence is structural; references are criteria, not components

date: 2026-08-09
status: accepted

## Context

Confronting an external "design operating system" proposal (11 specialist
agents, Double Diamond, JTBD, decision records) against the kernel showed
three of its ideas were already here — its decision record is the ADR
(MNT-4 already demands rejected alternatives), its "experience contract"
is the dated acceptance criteria (I4), its fixed-agenda critique is the
I8 heuristic pass with the USE catalog. Independent convergence on the
same ontology is evidence the design holds.

Two real gaps remained: the kernel has no divergence step (information
architecture goes straight to one wireframe), and no discipline for
choosing WHICH interaction pattern, so novelty enters by default. The
owner extended the scope: creative method strong enough to produce
extraordinary flows, and a curated design-system/reference base for UI.

The binding constraint comes from ADR-0011's research: instructing a
model toward quality does not hold — anti-slop prompts cut initial
verbosity while degradation resumed at the identical rate. "Be creative"
is the same class of intervention.

## Options considered

- **Adopt the 11 specialist roles** — rejected by the kernel's own razor
  (`spec/roles.toml`): a role exists because it has different ACCESS, not
  a different title. Strategist, researcher, experience architect,
  pattern curator, interaction designer, visual designer, and design
  system guardian all run the same model, with the same tools, over the
  same files — seven hats on one head, each costing tokens and one more
  point of intent degradation. The access-based split that matters
  already exists: who builds versus who judges in isolation and cannot
  fix (I2/I3).
- **Instruct creativity ("explore alternatives", "be bold")** —
  rejected: the failure mode ADR-0011 documents. Unmeasurable and
  unenforceable, it degrades exactly when pressure rises.
- **Bundle a component library / copy design-system code into the
  kernel** — rejected: copied components rot, bloat (MNT-11, MNT-12),
  drag licenses, and would need per-framework maintenance the kernel
  cannot honor (I6).
- **Structural divergence (distinct named lenses, recorded discards) plus
  a curated base of criteria and canonical pointers** — accepted.

## Decision

Creativity becomes structural. Before converging, the problem is reframed
at least twice (How Might We) and alternatives are generated from
DISTINCT named lenses — subtract, invert, analogous, constraint-first,
object-first — with alternatives sharing a lens counting as one; the
convergence records what each discard traded. Counts scale with triage
size (XS/S none, M 2, L 3), so the ceremony stays proportional.

`spec/references/ui-patterns.toml` curates decision criteria and
canonical sources only: which design systems are worth studying for what,
and for each recurring pattern its job, platform convention, canonical
implementations, fit/misfit criteria, mandatory states, and accessibility
pattern. It earns entries by recurrence, not completeness, and the client
extends it in `design/patterns.md` without editing the kernel's copy.
Judgment is citable through USE-10..12.

## Consequences

The choice between alternatives becomes an auditable artifact instead of
an invisible first draft, and pattern novelty becomes a declared cost
rather than a default. The kernel gains a reference surface that must be
curated — the discipline that keeps it from becoming an encyclopedia is
the same recurrence rule that governs the principle catalogs. No new
role, no dependency, no component code.
