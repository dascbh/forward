# FWD-034 — status demands inventory

cycle: C-12 · layer: back · meets: A3, A4, A6 · follows: ADR-0020

status.py JSON gains `demands`: every `specs/<id>/` (bare or slugged dir, old and new layout) with its cycle link (plan `## Demands` table or the spec's `cycle:` line; none = loose), review summary from `reviews/<id>/findings.toml` (findings count, by severity, blocking count; absent = none) and promotion (cycle promotion.md or old `promotions/<id>/`). Each cycle gains its artifact paths. `--demand <id>` prints one demand: spec text, findings (id, severity, blocking, title), promotion and the ADRs its spec follows. Read-only, exit 0 on any content; a bad id exits 2.
