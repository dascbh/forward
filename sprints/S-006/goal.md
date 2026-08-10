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
| FWD-014 plugin distribution | XS | the owner is starting a new project and needs `/forward:fde-init` to exist; the repo already shipped `.claude-plugin/plugin.json`, `skills/` and `agents/` in the right places, so the gap was one file (`marketplace.json`) making the repo its own marketplace. Does not serve the sprint goal — recorded here, surfaces at the retro |
