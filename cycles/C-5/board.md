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
