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
- 2026-09-29 C-5 decided FWD-032 review F1 (blocking) and F2–F5 fixed in FWD-033, which owns every instruction text; claim widened to templates/findings.template.toml (+ .fde copy) and SETUP.md marker lines
- 2026-09-29 FWD-033 decided merged 39fc3e7: AGENTS.md 2,811 → 1,595 words, descriptions 1,169 → 736 (max 40); FWD-032 F1–F5 fixed in the same commit; all eight demands merged — cycle review starts
- 2026-09-29 C-5 decided one reconcile round for reviews/FWD-033 F1–F5 and reviews/C-5 F1–F5 (+ notes: sync bumps kernel_version, README "sizes the demand", plan template ## Items); then a delta cycle review (L: full + delta)
- 2026-09-29 C-5 decided C-5 F1 path: a blocking finding in a demand review is fixed inside that demand and proven by its regression test; the owner is asked only when the fix changes a criterion or an ADR (replan). A non-blocking finding goes to backlog.md unless it shows a plan criterion unmet — then the cycle fixes it
- 2026-09-29 C-5 decided C-5 F2: draft (grouped) → planned (specified, awaiting sign-off; fde-spec writes it) → running (sign-off; the orchestrating agent writes it with `signed-off:`) → closed/abandoned
- 2026-09-29 C-5 decided C-5 F4: the release rollback is `git revert 321e045..<release>` (restores the 0.18.0 tree exactly, probed by the cycle review); recorded in promotion.md
- 2026-09-29 RECON-C5-TEXT claim AGENTS.md (+ template), skills/**, agents/**, templates/cycle/**, docs/adr/0019*, README.md, SETUP.md, runtime/fde_lib.py message (+ bin/fde), tests pinning them
- 2026-09-29 RECON-C5-RUNTIME claim runtime/status.py, runtime/verify.py (+ bin/fde), tests/test_status.py, tests/test_verify.py
- 2026-09-29 RECON-C5-RUNTIME claim widened: skills/fde-status/** (+ .claude copy) for the F5 promotion-mark convention
- 2026-09-29 RECON-C5-TEXT claim widened: templates/*.template.toml (+ .fde copies), spec/roles.toml comments/purpose, tests/test_coherence.py (TestNoFdeCli), tests/test_instructions.py — bare kernel ADR ids and pins
- 2026-09-29 RECON-C5-TEXT decided: AGENTS.md at 1,600 words; demand blocker fixed in-demand everywhere, cycle-review budget alone goes to the owner; states draft/planned/running with writers; kernel ADR ids in client texts; guard.py message left to backlog
- 2026-09-29 C-5 decided delta cycle review done: L budget spent, no blocking finding open; A1–A9 met; delta F1–F3 (medium) and the partial C-5 F3 / FWD-033 F4 go to backlog.md; promotion starts
