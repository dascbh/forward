# C-5 board

One line per event: `<time> <demand> <claim|proposes|blocked-on|decided> <what>`.
Claims name the files a demand owns; a demand touching a file claimed by
another posts `blocked-on` and waits for its merge.

- 2026-09-29 C-5 decided plan signed off; FWD-026..029 start in parallel
- 2026-09-29 FWD-026 claim AGENTS.md, templates/AGENTS.md.template, templates/cycle/**, skills/fde-triage/**
- 2026-09-29 FWD-027 claim runtime/status.py, tests/test_status.py, skills/fde-status/**
- 2026-09-29 FWD-028 claim agents/**, spec/roles.toml, skills/fde-review/**, skills/fde-walkthrough/**, skills/fde-design/**
- 2026-09-29 FWD-029 claim runtime/verify.py, runtime/graph.py, runtime/fde_lib.py, tests/test_verify.py, tests/test_graph.py, tests/test_scrum.py
- 2026-09-29 C-5 decided tests/test_instructions.py: FWD-026 owns TestDeclaredCycle and loop sections; FWD-028 adds its own classes at the end; conflicts resolved at rebase
- 2026-09-29 C-5 decided mirror copies (.claude/**, bin/fde/**, .fde/spec/**) follow their source's owner
- 2026-09-29 FWD-027 decided merged 180548d (ff); main --all red only on I4 (per-demand acceptance.md), pre-existing since 4f25730, cleared by FWD-029
- 2026-09-29 FWD-030 claim skills/fde-backlog/**, tests/test_backlog_panel.py; contract: status.py --format json (FWD-027)
- 2026-09-29 FWD-028 decided merged 181ed34 (rebased); guard: inside cycles/C-<n>/ each role writes only its file, board.md open to all; promotion also writes backlog.md
- 2026-09-29 FWD-028 proposes FWD-026: AGENTS.md ## Roles must match roles.toml scopes (cycles/**)
- 2026-09-29 FWD-028 proposes FWD-032/033: fde-review Budget still "never reopens the demand" / "the user picks one" (pinned by tests); walkthrough and design descriptions over 40 words; fde-design "Phases scale with triage size"
- 2026-09-29 FWD-026 decided merged (rebased onto 027+028); touched tests/test_mirror.py D10 row (unclaimed)
- 2026-09-29 FWD-029 decided merged; I4 inherits dated criteria from cycles/C-<n>/plan.md; SCRUM-GOAL/RETRO removed; SCRUM kept on backlog goal when [scrum] on; main --all green
- 2026-09-29 FWD-030 decided merged; README line (unclaimed) added; table `#` column becomes `id` when ids are assigned
- 2026-09-29 C-5 decided FWD-027 review F1–F4 fixed in-cycle (they break A3/A1 functioning: a closed directory cycle reads running, JSON text truncated, B-id formats, 0/0 done); F5 covered by FWD-030's round trip — owner of the fix: FWD-027-fix
- 2026-09-29 FWD-027-fix claim runtime/status.py, bin/fde/status.py, tests/test_status.py
- 2026-09-29 FWD-031 claim skills/fde-scrum/**, AGENTS.md ## Scrum mode (+ template), tests/test_scrum.py (handed off by FWD-029)
- 2026-09-29 FWD-032 claim SETUP.md, spec/invariants.toml, templates/findings.template.toml, agents/fde-promotion.md, runtime/guard.py, docs/adr/0017*, README.md, AGENTS.md ## Roles (+ template)
- 2026-09-29 C-5 decided residuals routed: templates/cycle/ install destination → FWD-032; I1-REQS reading R# from plan.md → FWD-032; guard promotions/ + acceptance.md paths → FWD-032
- 2026-09-29 FWD-031 decided merged fc11fd3; ## Scrum mode → ## Backlog; [scrum] survives only as the backlog dated-goal switch; touched tests/test_mirror.py D12 row (unclaimed)
- 2026-09-29 FWD-031 proposes FWD-032: sprint wording left in SETUP.md:132, README.md:301, templates/fde.config.template.toml:74
- 2026-09-29 FWD-027 decided reconcile 5429d1d merged: closed:/abandoned: end a cycle over state:, JSON unclipped with cells, one B-id format with warnings, directory-cycle progress from plan criteria vs promotion.md (`- A1 — <evidence> — met`)
- 2026-09-29 C-5 decided review of 026/028/029/030: 15 findings break A1/A5/A7/A8 and are fixed in-cycle; FWD-029 F4 (I5 read at the cycle's promotion.md ## Signals) → backlog as a declared limit: I5 stays repository-wide (observability.toml)
- 2026-09-29 RECON-TEXT claim AGENTS.md demand loop + ## Cycle (+ template), skills/fde-triage, skills/fde-review, skills/fde-walkthrough, templates/cycle/** — fixes 026 F1–F4, 028 F1/F3/F4
- 2026-09-29 RECON-GATE claim runtime/verify.py, runtime/graph.py, runtime/fde_lib.py, runtime/status.py (+ bin/fde), skills/fde-backlog, tests for them — fixes 029 F1–F3, 030 F1–F4
- 2026-09-29 FWD-032 takes 028 F2 (guard: adversarial and spec write backlog.md, every role writes board.md) — guard.py is in its claim
- 2026-09-29 RECON-TEXT decided merged 08c6a7b: overrun is a board fact, never a re-split at review; rounds XS/S 1, M/L full+delta, demand review 1; plan.md and promotion at every size; state: owners named; walkthrough whenever a front demand exists
- 2026-09-29 RECON-GATE decided merged b327188: any <PREFIX>-<n> demand id; I4 needs a real ISO date and a non-placeholder criterion; tolerant plan table; draft items, → C-n marks, double-grouping warning and next ids in status JSON; headlabs byte-identical
- 2026-09-29 FWD-032 decided merged 940119f (rebased twice; main's ADR-0019 semantics won every conflict); guard SHARED backlog.md + cycles/*/board.md; templates installed to .fde/templates/
- 2026-09-29 FWD-033 claim every instruction text: AGENTS.md (+ template), skills/**, agents/** (+ .claude copies), their pins in tests; includes discovery item 14 (backlog line format AGENTS ## Cycle vs fde-scrum)
