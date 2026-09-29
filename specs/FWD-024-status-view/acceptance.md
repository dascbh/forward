---
date: 2026-09-29
demand: FWD-024
---

# Acceptance — FWD-024 cycle and backlog view

1. R1–R4 each have a test in tests/test_status.py, red before
   runtime/status.py exists and green after.
2. Run on this repository and on ~/Documents/headlabs-platform, the view
   shows the open cycle with its done progress and the backlog, with no
   traceback.
3. Every content case exits 0; `verify.py` does not import or call it.
4. runtime/status.py and bin/fde/status.py are identical; skills/fde-status
   and .claude/skills/fde-status are identical (mirror suite green).
5. One isolated adversarial round with no blocking finding open.
