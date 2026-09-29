# C-13 board

- 2026-09-29 C-13 decided signed off by the owner ("aprovado"); FWD-036 starts
- 2026-09-29 FWD-036 claim AGENTS.md (+ template), skills/fde-review, agents/fde-adversarial.md (+ .claude copies), templates/findings.template.toml (+ .fde copy), tests
- 2026-09-29 FWD-036 built: one rule pinned in AGENTS.md step 5 (+ template), fde-review, fde-adversarial (+ copies); findings template carries `kind`; gate unchanged (test proves a `kind = "code"` record passes I2/TRACE/I8); AGENTS.md 1,599 words after trimming pointers and in-file repeats; backlog B-50..B-52
- 2026-09-29 C-13 decided code review FWD-036 (4, none blocking) and cycle review (4, none blocking; F3 stale — the code review was committed after its base). In-cycle fixes: cycle F1 (M/L plan review scheduled at the sign-off step, in fde-triage and fde-spec), code F1 (step 1 "only"), cycle F2 (a sensitive or irreversible demand is adversarial even inside a plan — the risk rule wins), cycle F4 (README). code F2–F4 → backlog
- 2026-09-29 C-13 reconcile claim skills/fde-triage, skills/fde-review, agents/fde-spec.md (+ .claude copies), AGENTS.md (+ template) step 1 "only" removed, README.md, tests/test_instructions.py
- 2026-09-29 C-13 decided released 0.21.0 (5127c29), A6 met; cycle closed
