# FWD-035 — terminal panel

cycle: C-12 · layer: front · meets: A1, A2, A3, A5, A6 · follows: ADR-0020

`status.py --panel` prints markdown in five sections — Overview, Backlog, Cycles, Demands, Discarded — from the same data as `--format json`. Overview: running cycle or none with criteria progress, planned and draft cycles, warnings, next ids, counts. Cycles: running and planned in full (criteria progress, items, demands with layer, review and promotion status, artifacts); drafts with their items; closed cycles one line each. Demands: loose demands one line each. Discarded: id, text, reason. One line per item, clipped; table pipes and headings in file text escaped so the layout holds. fde-backlog: run `--panel`, show the output as it is, list the actions in plain text (no question box), answer "abre C-n" / "mostra <id>" with `--cycle` / `--demand`, read any artifact on request.
