# FWD-030 — fde backlog panel

cycle: C-5 · layer: back · meets: A1 · follows: ADR-0019 rules 9, ADR-0018

Skill fde-backlog: shows the backlog (ids) and cycles from `status.py --format json`; groups selected B-ids into a new draft (`cycles/C-<n>/plan.md` with `state: draft` and the items) or an open draft; opens a cycle's artifacts; `specify` runs the planner on a draft and stops at sign-off. The backlog stays readable by status.py after every edit.

Out of scope: anything not named above goes to backlog.md with origin (C-5).
