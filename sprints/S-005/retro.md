---
sprint: S-005
date: 2026-08-09
---

# Retro — S-005

## 1. What cost more than it returned?

Nothing structurally, but two of the three demands (FWD-011, FWD-012)
were added mid-sprint. Both justified themselves against the goal, which
is the documented path — and both were XS, so the cost was small. Worth
naming anyway: a sprint that keeps absorbing new work is on its way to
being a bucket rather than a goal. Watch it; no change yet.

## 2. What did the gate catch — and what did it let through?

The gate caught nothing of substance this sprint. **The isolated review
caught everything**, and the pattern is about the builder, not the tools:

- **FWD-010 (critical)**: the demand whose founding argument is
  "instruction does not hold" shipped as instruction. The skill claimed
  "the kernel enforces the second diamond structurally" while nothing
  did.
- **FWD-011 (critical)**: component.gallery's numbers are counts of
  EXAMPLES, cited as counts of design systems (accordion: 101 examples,
  ~74 distinct systems). Material cited as canonical for an accordion it
  does not ship.
- **FWD-012**: dormancy measured against `foundation-sites` while the
  entry recommends `foundation-emails`, which is maintained; "the one
  thing nothing else covers" false (MJML); Tailwind Plus described as a
  per-seat subscription when it is a one-time purchase.

Five factual errors about external sources in two demands — and in every
case **the tests written alongside were tautologies**: they asserted that
a claim existed, never that it was true. A test that reads the file back
to itself cannot fail on a false claim.

The counter-signal is that the review pillar is doing exactly its job: 41
findings, 17 blocking, and without it all five errors would have shipped
as authoritative reference material that clients act on.

## 3. What changes?

**Verification discipline becomes a kernel rule (S-006, FWD-013).** The
countermeasure emerged on its own during the sprint and currently lives
only inside the UI reference base:

- verify against the primary artifact (the repository, the spec), never
  against a project's own marketing page;
- every volatile claim names its source and the date it was verified;
- the suite goes red when a claim ages past its useful life — the
  staleness signal is the point of the date.

That is a general rule about how this kernel makes claims, so it belongs
in the catalog and in a gate, not in one TOML file's header.

**Second signal, recorded not acted on**: the graph, mining the kernel's
own review history, ranks **MNT-1 (single source of truth) at 25.0
severity-weighted — three times the next principle**. The kernel keeps
creating parallel copies (source, installed mirror, template, generated
surface) and defends each with a bespoke drift test. That is a structural
observation about the kernel's own shape, not this sprint's work; it goes
to the backlog as a candidate, and the S-005 review already declined to
open it now.
