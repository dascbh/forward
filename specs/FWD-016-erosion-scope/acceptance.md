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

---

## Amendment — 2026-08-10, after the adversarial round (F6)

The criteria above stand as declared on 2026-08-09. This note records
what happened to them, because the alternative — editing them to match
what shipped — is the failure I4 exists to prevent, and the reviewer
caught it happening once already: `spec.md`, which restated the target as
the declared roots and thereby made the code conformant, was committed
**after** the implementation (`f4af1fb` 20:26:32 against `8b30405`
20:25:54). That ordering was wrong. It is not repeated here.

**The first criterion was declared under a hypothesis that proved
false.** "Churn measured over the SAME file set the duplication metric
already uses: tracked code files, mirrors and vendor excluded" assumed
the audit trail sat outside that set. It did not — `.md` and `.toml` are
in `CODE_SUFFIXES` — so the criterion as written targets 16.15, worse
than the 15.11 it was meant to correct. The criterion was measurable and
it was wrong.

**What it asked for is now met, in the other direction.** The demand's
real requirement was one population, not two, and the first
implementation shipped a third (47 churn files against 116 duplication
files). Both metrics now read the same set: declared roots, minus
declared generated copies, minus vendor. One definition of "the
codebase", used by every metric — the criterion's actual sentence,
reached by moving duplication to churn's population rather than the
reverse.

**Two items were absent and are now built**: the report states the count
of tracked code files excluded (`files_excluded`), and a test asserts it
(`test_one_population_for_both_metrics`).

**One item is superseded**: "mirrors and vendor excluded" is no longer
the kernel's decision. The mirrors are excluded because
`fde.config.toml` declares them in `[erosion] generated_paths`; vendor
because it is code this project did not write. The number that exclusion
is worth — 12.13 without it, 11.06 with — is published in the config
comment and in `spec.md`.

The budget was not raised (R4): `max_add_delete_ratio` is still 12.0.
