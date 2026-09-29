# FWD-040 — sync clients

cycle: C-14 · layer: back · meets: A6 · follows: ADR-0019

SETUP/fde-sync install the kernel ADRs read-only at `.fde/adr/` (B-32, mirror pair); sync rewrites the old 'backlog + sprints' config comment (B-38); sync says up front it writes permissions and to leave auto mode if blocked (B-42); a fixture shows 0.21.0 ignores `.fde/adr/` and `[backlog]` (downgrade).

Review: code review (kind = code), kernel ADR-0021.
