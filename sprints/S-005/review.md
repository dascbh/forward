---
sprint: S-005
date: 2026-08-09
---

# Review — S-005

**Goal**: reached. Design diverges before it converges, and UI choices
stand on a curated base instead of the first idea.

**Increment**

Divergence is enforced, not requested: the problem is reframed ("How
might we", ≥2 framings), alternatives come from distinct named lenses
(subtract, invert, analogous, constraint-first, object-first — sharing a
lens counts as one), and the discard is recorded with what it traded, in
`specs/<id>/design/alternatives.md`. The `DIVERGE` gate fails any M/L
demand with a design surface that skips it; XS/S stay exempt.

UI choices stand on a base of 55 entries in five kinds: 18 design systems
(including DSGov, PO UI and Nimbus, which carry the pt-BR and LatAm
conventions no global system does), 21 interaction patterns, 8 page
archetypes, 4 frameworks and 4 directories. Frameworks are a separate
kind on purpose — they scaffold layout and decide no job — and each
declares `does_not_decide` plus a maintenance verdict measured against
the repository, not the project's marketing page.

**Evidence**: 173 tests (145 at sprint start), 16 gate lines green,
erosion within the declared budget (duplication 1.0% against a 6.0 ceiling,
add/delete 5.59 against 12.0) — the sprint did not degrade the repository.
Three demands, 41 findings, 17 blocking, 2 critical, all fixed in commits
separate from the reviews (I3).

**Owner's decision**: accept as delivered; nothing reopened. The two
candidates raised and declined for now — splitting the base file, and
lightening the divergence ceremony — are recorded here rather than lost:
revisit if the base keeps growing or if the alternative count proves
expensive in practice.

**Backlog**: empty of selectable items since S-002 consumed all five.
S-006 takes the verification discipline that this sprint's reviews forced
into the open (see the retro).
