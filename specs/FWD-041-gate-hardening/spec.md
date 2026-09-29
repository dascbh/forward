# FWD-041 — gate hardening

cycle: C-14 · layer: back · meets: A7 · follows: ADR-0019

verify.py/erosion.py/fde_lib.py/guard.py: `-z` NUL-separated file lists (B-12); erosion re.split keyword maxsplit (B-14) and cycles/ excluded from erosion when no [gate] roots (B-20); validate() rejects non-list [gate] paths (B-16); I1-REQS traces a front demand's plan criteria to evals/journeys/<id>/ (B-27); runtime messages say 'kernel ADR-…' (B-28). Each red-before test; headlabs read-only green.

Review: code review (kind = code), kernel ADR-0021.
