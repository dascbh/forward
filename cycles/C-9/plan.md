# C-9

state: draft
objective: gates and runtime hardening: robust path handling, validation, CI range and the cycle-layout journey check

## Items

- B-12 C-1#2 usage-data — I1's changed() lists files with git diff-tree --name-only without -z, so git-quoted paths (non-ASCII, tab) may miss behavior_paths
- B-14 C-1#6 usage-data — erosion.py:242 emits a DeprecationWarning (re.split maxsplit positional) during the suite
- B-15 C-1#14 usage-data — a workflow merge-base for new-branch pushes, so one red commit already on main does not keep full-history runs red (touches ADR-0016's pinned run line)
- B-16 C-1#15 usage-data — validate() rejecting non-list [gate] paths for every client
- B-17 C-1#16 usage-data — support for a project in a git subdirectory (I1 requires the git top level)
- B-20 C-2#2 usage-data — erosion counts cycles/ churn in clients that declare no [gate] roots (review note)
- B-27 (C-5) usage-data — I1-REQS reads journey R# tokens only from per-demand acceptance.md; a front demand in the cycle layout (A# criteria in plan.md) is not traced to evals/journeys/ — needs a follow-up in verify.py (FWD-032 note)
- B-28 (C-5) usage-data — runtime messages still cite bare kernel ADR ids a client cannot resolve: guard.py LEGACY_NOTE "only for a cycle opened before ADR-0019" (pinned by tests/test_coherence.py); instruction texts now say "kernel ADR-00NN" (RECON-C5-TEXT, reviews/C-5 F3)
