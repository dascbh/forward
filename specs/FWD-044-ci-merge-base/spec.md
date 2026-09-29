# FWD-044 — ci merge base

cycle: C-14 · layer: infra · meets: A7 · follows: ADR-0016

The gate workflow (templates/fde-gate.yml and .github/workflows copy, pinned by ADR-0016's run line) uses a merge-base for new-branch pushes so one red commit already on main does not keep full-history runs red (B-15); mirror pair and pin updated.

Review: code review (kind = code), kernel ADR-0021.
