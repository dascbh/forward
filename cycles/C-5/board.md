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
