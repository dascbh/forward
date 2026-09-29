# C-7

state: draft
objective: clients sync without surprises: kernel ADRs reachable, open sprints and old comments migrated, auto mode handled

## Items

- B-32 (C-5) usage-data — clients read "kernel ADR-00NN" but never receive the kernel ADRs; ship them read-only or link them (reviews/C-5 F3 partial)
- B-35 (C-5) usage-data — a client syncing with a sprint still open loses it from every view; fde-sync's migration should carry an open sprint's demands into backlog.md (reviews/FWD-031 F2)
- B-38 (C-5) usage-data — clients keep the old config comment "backlog + sprints" across syncs (headlabs fde.config.toml:196) (reviews/FWD-031 F5)
- B-42 usage-data — under Claude Code auto mode, the classifier blocks the sync's permission merge (SETUP §8.4) and the sync stops half way (kernel_version and permissions left undone); fde-sync should say up front that it writes permissions and tell the user to leave auto mode if blocked (owner report, 2026-09-29)
