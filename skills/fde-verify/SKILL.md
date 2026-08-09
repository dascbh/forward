---
name: fde-verify
description: Runs the invariant gate — exactly the same verifier that the pre-commit and CI run. Use before any commit, before opening a PR, when a commit gets rejected by the hook, or when the user asks whether something "is ready", "can ship", "is production-grade". Also use to explain why a gate failed.
---

# fde-verify

The gate is code, not agent judgment — it is the one part of the kernel
that stays a script, because pre-commit and CI run where no agent exists.

```bash
python3 bin/fde/verify.py --staged           # pre-commit (fast)
python3 bin/fde/verify.py --all              # CI (complete)
python3 bin/fde/verify.py --gate eval        # a single gate
python3 bin/fde/verify.py --format json      # machine-readable
```

## When explaining a failure

Say which invariant, why it exists, and what the fix is. Do not suggest
working around it — there is no bypass key, and looking for one is the
behavior the framework exists to prevent.

| gate | what was missing | fix |
|---|---|---|
| I1 | behavior change without an eval entry | write the failure mode and the evaluator |
| I2 | adversarial review did not run isolated | run `fde-review` isolated; findings.toml declares `artifact_only` |
| I3 | adversarial role touched code | revert; the finding goes in `reviews/`, fixing belongs to another role |
| I4 | acceptance criteria missing or undated | declare before building; `specs/<id>/acceptance.md` with a `date:` line |
| I5 | declared attribute without a signal | instrument it or reduce what was declared |
| I6 | gate does not run without the FDE | `fde-sync` re-copies the runtime |
| I7 | handoff without an artifact on disk | create the structure; do not pass context by conversation |
