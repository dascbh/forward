cycle: C-13
date: 2026-09-29
commit: 9368d1d
round: 1 of 1 (S)
reviewer: fde-adversarial, cycle mode, agent-a08dd8b509eb4ce7d
record: reviews/C-13/findings.toml

## Functioning

- **A1 — met.** AGENTS.md step 5, fde-review `## Mode` and fde-adversarial `## Mode` carry the same sentence: "A coding demand inside a signed-off plan: isolated code review (diff × demand spec, ADR conformance, tests, the layer's check; `kind = "code"`; ~10 minutes; no scratch repositories or probe hunt)." Case *one-line front demand in a signed-off S plan*: code review, the layer check is design QA against the wireframe. The rule is unambiguous.
- **A2 — met to the letter, with gaps (F1, F2).** Same three texts: "A sensitive or irreversible demand, or a real diff over ~300 production lines: adversarial review. An M/L plan, before sign-off: adversarial plan review (`kind = "plan"`)." Case *diff over 300 lines*: decided (adversarial). Case *back demand in a sensitive project*: two rules match, no precedence is stated, and sensitivity is triaged on the cycle, not the demand (F2). Case *M plan before sign-off*: the rule lives in step 5, after step 3 Sign-off. fde-triage's announce line and fde-spec's "stop at the sign-off" never schedule the plan review, so a cold agent reaches sign-off without it (F1).
- **A3 — met.** fde-review: "Every mode stays isolated (I2), every finding cites a probe or a principle (I8) … a code review's record satisfies the promotion gate". The template carries `kind = "{{REVIEW_KIND}}"`. FM2 probe on a scratch fixture: a promoted FWD-121 with the installed template filled as `kind = "code"` passes I2, TRACE and I8. Without `context_policy`, it still fails I2. A plan record is read by I8 but not by I2 (already B-50).
- **A4 — met.** agents/fde-adversarial.md (and the .claude copy, which differs only in the generated header and the rendered attack order) lists code (~10 minutes, 1 round), adversarial, plan and cycle, each with a budget. Case *cycle review*: "The cycle review is unchanged". The cycle mode text matches fde-review.
- **A5 — met.** AGENTS.md is 1,599 words (limit 1,600). The longest descriptions are 40 words (fde-verify, fde-backlog, fde-walkthrough, fde-status), fde-review 38, fde-adversarial 39.
- **A6 — not yet (expected before release).** The suite passes 629 tests and `verify.py --all` is green at 9368d1d. `kernel_version` is still 0.20.0 and nothing is pushed. These are deploy.md step 1.

## Readiness

- deploy.md: one back step with verification (suite, `verify --all`, CI) and a rollback (`git revert --no-commit a9d37f8..<release sha>`). The range starts at C-12's close and covers all C-13 commits. It is irreversible: no. The step is complete. Release is pending: bump to 0.21.0, then push.
- Suite and gate: green (629 OK; all gates passed).
- Signals (I5): the criteria are instruction text and a gate test. No production signal is declared, and none is owed.
- README: stale. README.md:300 still describes fde-review as "adversarial probes, then heuristic judgment" and names neither code nor plan mode (F4). There is no runbook change.
- Demand review record: reviews/FWD-036/ is missing, although the plan says the demand is reviewed as a code review (F3). It must exist before promotion cites it.

## Findings

- **F1 — high, non-blocking (MNT-4).** The M/L plan review is placed after sign-off in AGENTS.md (step 5 of 8). fde-triage's M announce line and fde-spec's stop at sign-off never schedule it, so a cold agent skips it. A2's letter holds. FM1's pins do not cover fde-triage or fde-spec. Backlog (extends B-52).
- **F2 — medium (probe: case the spec does not cover).** A "sensitive demand" is undefined, because sensitivity is judged on the cycle, and code review versus adversarial has no stated precedence when both match. Backlog.
- **F3 — medium (MNT-13).** FWD-036 is on main with no reviews/FWD-036/findings.toml and no review line on the board. This repeats C-12 F2 (B-39). Backlog, and the record is owed before promotion.
- **F4 — medium (MNT-10).** The README's fde-review line predates ADR-0021. Backlog.

No blocking finding.
