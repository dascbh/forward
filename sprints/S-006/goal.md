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
