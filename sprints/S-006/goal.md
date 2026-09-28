---
goal: A claim the kernel makes about the world names its source, its date, and is verified against the artifact — and goes red when it ages.
date: 2026-08-09
---

# Sprint S-006

| demand | size | serves the goal because |
|---|---|---|
| FWD-013 verification discipline | M | five factual errors in two demands, each one a confident claim about an external source that no test could falsify, is the sprint's measured evidence that the kernel needs a rule for how it makes claims — a catalog principle plus a gate that fails on undated or expired claims, applying to the whole kernel and not only to the UI reference base |

Closes when: FWD-013 passes the gate with two adversarial rounds and a
promotion decision, and the owner runs the review + retro sitting.

## Unplanned

| demand | size | why it bypassed the backlog |
|---|---|---|
| FWD-015 brownfield survey | M | the owner is taking over an undocumented project and the kernel had nothing for it: fde-init classifies a stack to configure the gate and never reads architecture or history. The `discovery/` slot has been declared as the spec role's input since day one and never written to. Does not serve the sprint goal — second unplanned this sprint, which the S-005 retro said to watch |
| FWD-020 one mirror-drift mechanism | M | backlog item 8, pulled forward by the owner on 2026-09-28 (optimization pass): the graph ranks MNT-1 at 28.0 severity-weighted at intake, more than twice the next principle (OBS-1, 12.0), because every source/copy pair carries its own bespoke drift test. Does not serve the sprint goal — surfaces at the retro |
| FWD-021 declared cycle scope | M | backlog item 9, pulled forward by the owner on 2026-09-28 right after FWD-020 closed: long agent loops drift into side tasks and burn tokens; the owner reports a round file with a declared definition of done visibly improved agent behavior, and chose gate enforcement. Does not serve the sprint goal — surfaces at the retro |
| FWD-022 declared cycle, as instruction | S | successor of FWD-021 after ADR-0018 (review is a budget, not a loop): the first slice ships the cycle practice as text in AGENTS.md, no gate. Does not serve the sprint goal — surfaces at the retro |
| FWD-014 plugin distribution | XS | the owner is starting a new project and needs `/forward:fde-init` to exist; the repo already shipped `.claude-plugin/plugin.json`, `skills/` and `agents/` in the right places, so the gap was one file (`marketplace.json`) making the repo its own marketplace. Does not serve the sprint goal — recorded here, surfaces at the retro |

## Owner decisions

- 2026-09-28 — FWD-020 ran a 4th adversarial round past fde-review's
  three-cycle bound (rounds 1–3 each closed on a blocking finding: F1,
  F9, F14; round 4 closed with 0 blocking). The owner accepted the 4th
  round and authorized the closing commit — condition 2 of
  promotions/FWD-020/decision.md.
- 2026-09-28 — FWD-021 owner decisions: RULE commits stay outside every
  cycle, the in-band-fix gap is a declared limit (A9); `[cycle]` ships
  commented out in the client template (A10); this repo declares no extra
  stages (A11); the declaration freezes at the opening commit, and a
  declaration error found after push costs a close-and-reopen (ADR-0017).
- 2026-09-28 — FWD-021 after review round 2: merges are judged against
  their first parent, rebase is the way out (fallback: linear history if
  round 3 finds a merge hole); `declared-before` and `residuals` stay
  required done items (F30 declined); a cumulative cap on claimed RULE
  commits with no cycle stays a declared limit (F7, A9 unchanged).
- 2026-09-28 — FWD-021 after review round 3 (3 blocking open: F31 merge
  first-parent hole, F32, F33): the owner applied the declared fallback —
  linear history in any examined range — and authorized a 4th review
  round past fde-review's three-cycle bound.
- 2026-09-28 — FWD-021 after review round 4 (2 blocking: F41 disarm via
  the checked commit's own flag, F42 second open cycle caught only at the
  tip): the owner authorized a fix and a 5th, final round; a blocking
  finding in round 5 pauses FWD-021 unpromoted.
- 2026-09-28 — FWD-021 round-4 decision (ADR-0017 R4): once the first
  cycle file exists the mode is permanent for that history; leaving costs
  one deliberately merged red commit. The owner accepted this over a
  declared opt-out commit, which would reopen F41.
- 2026-09-28 — FWD-021 paused unpromoted after review round 5 (F47
  force-push disarm, F48 never-opted clients red). The owner chose to
  revert the gate from main and keep the record: spec, ADR-0017 (paused),
  five review rounds, cycle C-1 closed with its items captured in
  backlog.md. Nothing was pushed before the revert.
- 2026-09-28 — the owner asked for the delivery process to be reconfigured after FWD-021 (ADR-0018) and authorized carrying FWD-022 to closure under it.
