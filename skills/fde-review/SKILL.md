---
name: fde-review
description: Runs the adversarial review in an isolated context, with attack order derived from the project's weights. Use before promoting any artifact, when the user asks for review, code review, red team, "try to break this", or asks whether something is secure/robust enough. Use ALWAYS in an isolated worktree — a reviewer who sees the builder's reasoning agrees with itself.
---

# fde-review

```bash
python bin/review.py <demand-id> --plan-only    # see the plan
python bin/review.py <demand-id> --isolate      # isolated worktree + skeleton
```

## Non-negotiable rules

**Isolation (I2).** The reviewer receives the artifact and the specification. It does not receive the context, the history, or the reasoning of whoever built it. If you are in the same thread that produced the code, you **cannot** be the reviewer — create the worktree and run there.

**No fixing (I3).** The adversarial role records in `reviews/<id>/findings.toml` and stops. Fixing belongs to the implementation role. A reviewer who fixes what they found erases the record of the finding.

**Success is findings.** The goal is not to approve. A review that found nothing is suspicious before it is good news — declare how many rounds ran and what was probed.

## Order

Derived from vector A weights, not from your intuition about what is interesting. High weight attacks first and gets more rounds. A low-weight attribute still gets at least one round — a floor, not zero.
