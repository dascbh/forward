@AGENTS.md

## Claude Code-specific layer

This project's roles live in `.claude/agents/`. Each one has a write
scope restricted by design — if a role cannot edit a path, that is
intentional, not an impediment to work around.

This repository is FORWARD installed on itself (ADR-0007): `runtime/`,
`spec/`, `skills/`, `agents/`, `templates/`, and `SETUP.md` are behavior;
their measure lives in `tests/`. Role scopes map onto this repo as
follows (finding F10): what `src/**` means in a client is `runtime/` +
`spec/` + `skills/` + `agents/` + `templates/` here — the implementation
role owns those plus `tests/`; the judging roles keep their generic
scopes (`specs/`, `docs/adr/`, `reviews/`, `promotions/`). Before any
commit: `python3 bin/fde/verify.py`.
