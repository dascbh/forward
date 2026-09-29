# FWD-027 — status cycle states

cycle: C-5 · layer: back · meets: A3 · follows: ADR-0019 rules 9, 10, ADR-0018

status.py reads cycle directories (`cycles/C-<n>/plan.md`) and the old single files, shows the states draft/planned/running/closed (a `state:` header line, else `closed:` → closed, else running), shows backlog ids `B-<n>`, and prints `--format json` with the same content.

Out of scope: anything not named above goes to backlog.md with origin (C-5).
