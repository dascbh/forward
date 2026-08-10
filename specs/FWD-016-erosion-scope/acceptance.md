---
date: 2026-08-09
demand: FWD-016
---

# Acceptance — FWD-016 erosion measures one codebase, not two

Context: the erosion gate fired on the kernel (add/delete 15.11 vs a
declared 12.0) and the decomposition showed the two metrics disagree
about what they measure. Duplication counts only code files, with
generated mirrors and vendor trees excluded; add/delete, largest change
and everything else count every tracked file — so 3,289 lines of review
findings, specs and retros (with 7 lines ever deleted) are read as
accretion. An audit trail that never shrinks is not decay; it is the
record the kernel exists to produce.

This is a correction made while the gate is red, so the bar is higher,
not lower:

- `erosion.py` measures add/delete and largest-change over the SAME file
  set the duplication metric already uses: tracked code files, mirrors
  and vendor excluded. One definition of "the codebase", used by every
  metric.
- The report states the scope it measured and the count of files
  excluded, so a reader can see what was left out rather than trusting
  the number.
- Tests: a fixture where documentation-only commits dominate must not
  move the ratio; a fixture where code grows by accretion must; the
  excluded-scope count is asserted.
- The kernel's own numbers are reported before and after in the commit,
  and the `[erosion]` budget is NOT raised — if the corrected code-only
  ratio still breaches, the answer is consolidation, not a bigger
  ceiling.
- One isolated adversarial round in `reviews/FWD-016/`, prompted
  explicitly to check whether this correction is rationalisation: the
  reviewer must decide whether the scope change is defensible on its own
  merits or is a threshold bump wearing a disguise.
