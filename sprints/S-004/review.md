---
sprint: S-004
date: 2026-08-09
---

# Review — S-004

**Goal**: reached. Entropy is measured, not assumed.

**Increment**: FWD-009 (M). `runtime/erosion.py` measures the decay four
long-horizon papers predict — clone ratio, add/delete ratio, batch size,
dependency count — in stdlib over the git history; the opt-in `[erosion]`
budget gates it (declared thresholds, I4 pattern; silent when undeclared).
Catalogs grew MNT-11..13 and `operational_cost`'s first, COST-1..3. The
README manifesto answers the thesis with the evidence, and the kernel
declares its own budget: it gates its own decay, within budget.

Adversarial (2 rounds): 5 findings, 2 blocking — `max_change_lines` was a
false wall on any repo younger than the window (root commit dominated the
batch metric), and the install-drift test omitted the two newest
CI-executed copies. Both fixed. The sharpest, non-blocking: the manifesto
over-read its own metric ("Exhibit A / decay did not happen"), corrected
to a precise partial datapoint — the directive against overclaiming
caught overclaiming. Suite 115 → 130; 15 gate lines green.

**Owner's backlog decision**: next direction selected from an external
design-architecture proposal, confronted against kernel doctrine — its
11-role structure rejected by the roles razor, but two real gaps
accepted: no divergence step, and no pattern-selection discipline. Both
enter S-005 as FWD-010, extended by the owner with creative method
(Design Thinking / Double Diamond) and a curated UI reference base.
