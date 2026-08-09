---
name: fde-review
description: Runs the adversarial review in an isolated context, with attack order derived from the project's weights. Use before promoting any artifact, when the user asks for review, code review, red team, "try to break this", or asks whether something is secure/robust enough. The reviewer must NOT be the thread that built the code — isolate first.
---

# fde-review

## Build the probe plan (deterministic)

1. Read `[weights]` from `fde.config.toml`; sort attributes descending.
2. Per attribute: `rounds = max(1, weight/10 rounded)`; weight ≥ 15 means a
   confirmed finding there **BLOCKS MERGE**, below that it records.
3. Probes per attribute come from
   `.fde/spec/dimensions/quality-attributes.toml` (`adversarial_probes`).
4. Create `reviews/<demand-id>/findings.toml` from the kernel's
   `templates/findings.template.toml` (`rounds_planned` = total rounds).

## Non-negotiable rules

**Isolation (I2).** The reviewer receives the artifact and the
specification. It does not receive the context, the history, or the
reasoning of whoever built it. If you are in the same thread that produced
the code, you **cannot** be the reviewer:

- Claude Code: invoke the `fde-adversarial` subagent — it runs in an
  isolated worktree with Edit/Write denied.
- Any other tool: `git worktree add --detach ../.fde-review-<demand-id>`
  and run the review inside it, in a fresh session with no builder context.

**No fixing (I3).** The adversarial role records in
`reviews/<id>/findings.toml` and stops. Fixing belongs to the
implementation role. A reviewer who fixes what they found erases the record
of the finding.

**Success is findings.** The goal is not to approve. A review that found
nothing is suspicious before it is good news — declare how many rounds ran
and what was probed.

## Order

Derived from vector A weights, not from your intuition about what is
interesting. High weight attacks first and gets more rounds. A low-weight
attribute still gets at least one round — a floor, not zero.
