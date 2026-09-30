"""FWD-024: the cycle and backlog view — a read-only report, never a gate
(ADR-0018). Every case runs the real script as a subprocess against a
temporary tree, the way the owner runs it."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "runtime" / "status.py"

OPEN = """cycle: C-2
objective: erase a KB source
opened: 2026-09-28
demands: DEM-035 (M), DEM-036 (M)

## Tasks
- DEM-035 erase
- DEM-036 reindex

## Done when
- [x] DEM-035 — in production
- [ ] DEM-036 — reindex guaranteed
- [-] something not met

closed: this word in the body does not close the cycle
"""

CLOSED = """# C-1 — first round

objective: security debts
closed: 2026-09-28
opened: 2026-09-28

## Done when
- [x] a
- [x] b
"""

BACKLOG = """---
goal: g
date: 2026-08-09
---

# Product backlog

| # | item | hypothesis | evidence | size |
|---|---|---|---|---|
| 1 | Role isolation | shared role crosses tenants | usage-data | M |

## Captured from cycle C-2

- FC-3 listing failure writes existed=False

## Other

- (C-10) unrelated idea from a later cycle
- (C-2) timeout without a total bound
"""


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True)


class StatusCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "cycles").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text, raw=False):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if raw:
            p.write_bytes(text)
        else:
            p.write_text(text)


class TestView(StatusCase):
    """R1: open cycle with progress, its backlog lines, closed cycles one line
    each, the backlog grouped by section."""

    def setUp(self):
        super().setUp()
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)

    def test_open_cycle_with_progress(self):
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OPEN CYCLE C-2", r.stdout)
        self.assertIn("erase a KB source", r.stdout)
        self.assertIn("1/3 met, 1 declined, 1 pending", r.stdout)
        self.assertIn("[ ] DEM-036 — reindex guaranteed", r.stdout)

    def test_body_mention_of_closed_does_not_close(self):
        # FM-1: only header lines decide open/closed
        r = run(self.root)
        self.assertIn("OPEN CYCLE C-2", r.stdout)
        self.assertNotIn("C-2  closed", r.stdout)

    def test_closed_cycle_is_one_line(self):
        r = run(self.root)
        self.assertIn("C-1  closed 2026-09-28  2/2 met  security debts", r.stdout)

    def test_backlog_lines_of_the_open_cycle_by_token_or_section(self):
        # FM-3: C-10 must not be claimed by C-2
        part = run(self.root).stdout.split("BACKLOG")[0]
        self.assertIn("FC-3 listing failure", part)
        self.assertIn("(C-2) timeout", part)
        self.assertNotIn("C-10", part)

    def test_backlog_grouped_by_section(self):
        out = run(self.root).stdout
        backlog = out[out.index("BACKLOG"):]
        self.assertIn("#1 Role isolation", backlog)
        self.assertNotIn("# item", backlog)
        self.assertLess(backlog.index("Captured from cycle C-2"),
                        backlog.index("Other"))


class TestWarnings(StatusCase):
    """R2: warnings first; exit 0 on any content (FM-5)."""

    def test_two_open_cycles_are_reported(self):
        # FM-2
        self.write("cycles/C-1.md", OPEN.replace("C-2", "C-1"))
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)
        r = run(self.root)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("WARNING"), r.stdout)
        # kernel ADR-0024: two running cycles are fine when their files can
        # be checked; these old files declare none, so each is warned
        self.assertIn("C-1 runs beside 1 other cycle(s) but a demand declares "
                      "no `files`", r.stdout)

    def test_missing_objective_and_backlog_warn(self):
        self.write("cycles/C-1.md", "opened: 2026-09-28\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 0)
        self.assertIn("C-1 has no objective", r.stdout)
        self.assertIn("no backlog.md", r.stdout)

    def test_open_cycle_with_every_item_met_is_ready_to_close(self):
        self.write("cycles/C-1.md", "objective: o\n\n## Done when\n- [x] a\n")
        self.assertIn("C-1 has no pending done item but no closed: line",
                      run(self.root).stdout)


class TestSelectors(StatusCase):
    """R3: --cycle, --backlog, --cycles."""

    def setUp(self):
        super().setUp()
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)

    def test_cycle_in_full(self):
        out = run(self.root, "--cycle", "C-1").stdout
        self.assertIn("CYCLE C-1 (closed 2026-09-28)", out)
        self.assertIn("[x] a", out)
        self.assertNotIn("BACKLOG", out)

    def test_unknown_cycle_is_a_bad_argument(self):
        self.assertEqual(run(self.root, "--cycle", "C-9").returncode, 2)

    def test_backlog_only_and_cycles_only(self):
        b = run(self.root, "--backlog").stdout
        self.assertIn("BACKLOG", b)
        self.assertNotIn("OPEN CYCLE", b)
        c = run(self.root, "--cycles").stdout
        self.assertIn("OPEN CYCLE C-2", c)
        self.assertNotIn("#1 Role isolation", c)


class TestTolerance(StatusCase):
    """R4 / FM-4: malformed input never tracebacks."""

    def test_no_cycles_directory(self):
        (self.root / "cycles").rmdir()
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no open cycle", r.stdout)

    def test_empty_non_utf8_and_sectionless_files(self):
        self.write("cycles/C-1.md", "")
        self.write("cycles/C-2.md", b"objective: caf\xe9\n## DONE WHEN\n- [X] ok\n",
                   raw=True)
        self.write("backlog.md", b"\xff\xfe junk\n| broken |\n", raw=True)
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("1/1 met", r.stdout)

    def test_not_called_by_the_gate(self):
        gate = (ROOT / "runtime" / "verify.py").read_text()
        self.assertNotIn("import status", gate)
        self.assertNotIn("status.py", gate)


class TestRoundOneFindings(StatusCase):
    """reviews/FWD-024 round 1: each finding's probe, red before the fix."""

    def test_f1_closed_line_below_the_header_is_named(self):
        self.write("cycles/C-1.md", "objective: o\n\n## Done when\n- [x] a\n\nclosed: 2026-09-28\n")
        out = run(self.root).stdout
        self.assertIn("C-1 has a closed: line below its header", out)
        self.assertNotIn("no pending done item but no closed:", out)

    def test_f2_cycle_named_in_a_later_table_cell(self):
        self.write("cycles/C-3.md", "objective: o\n")
        self.write("backlog.md", "| # | item | evidence |\n|---|---|---|\n"
                   "| 4 | Idea | usage-data (C-3 review) |\n")
        part = run(self.root).stdout.split("BACKLOG")[0]
        self.assertIn("#4 Idea", part)

    def test_f3_numbered_spaced_and_unknown_marks_are_counted(self):
        self.write("cycles/C-1.md", "objective: o\n## Done when\n1. [x] a\n- [ x ] b\n"
                   "- [~] c\n- [] d\n")
        out = run(self.root).stdout
        self.assertIn("2/4 met, 2 pending", out)
        self.assertIn("[~] c", out)
        self.assertNotIn("no pending done item", out)

    def test_f4_narrow_stdout_encoding_never_tracebacks(self):
        self.write("cycles/C-1.md", "objective: seta → e caf\u00e9\n")
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)],
                           capture_output=True, text=True, encoding="ascii",
                           errors="replace", env={"PYTHONIOENCODING": "ascii",
                                                  "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_f5_misnamed_and_duplicate_cycle_files_warn(self):
        self.write("cycles/C-3-status.md", "objective: o\n")
        self.write("cycles/C-01.md", "objective: o\n")
        self.write("cycles/C-1.md", "objective: o\n")
        self.write("cycles/.DS_Store", "x")
        out = run(self.root).stdout
        self.assertIn("cycles/C-3-status.md is not named C-<n>.md", out)
        self.assertIn("2 files in cycles/ read as C-1", out)
        self.assertNotIn(".DS_Store", out)

    def test_notes_bad_root_fences_and_legacy_next_cycle(self):
        self.assertEqual(run(self.root / "nope").returncode, 2)
        self.write("cycles/C-1.md", "objective: o\n## Done when\n- [x] a\n```\n- [ ] fake\n```\n"
                   "## Next cycle\n- old idea\n")
        out = run(self.root).stdout
        self.assertIn("1/1 met", out)
        self.assertIn("C-1 keeps a ## Next cycle list (1 lines)", out)
        self.assertIn("old idea", run(self.root, "--cycle", "C-1").stdout)

    def test_notes_escaped_pipe_empty_closed_and_top_label(self):
        self.write("cycles/C-1.md", "objective: o\nclosed:\n")
        self.write("backlog.md", "- first\n\n| # | item |\n|---|---|\n| 2 | a \\| b |\n")
        out = run(self.root).stdout
        self.assertIn("C-1 has an empty closed: line and still counts as open", out)
        self.assertIn("#2 a | b", out)
        self.assertIn("Unsectioned", out)


PLAN = """cycle: C-5
state: running
objective: backlog > cycle > demand
opened: 2026-09-29

## Acceptance criteria

- **A1 — draft.** the panel groups items
  into a draft
- **A3 — the view.** status shows states

## Demands

| id | layer | depends on | what | meets |
|---|---|---|---|---|
| FWD-027 | back | — | status | A3 |
| FWD-030 | back | FWD-027 | panel | A1 |
| `FWD-032` | front | FWD-026, FWD-028 | coherence | A8 |
"""

PROMOTION = """cycle: C-5
decision: hold

## Evidence

- A1 — tests/test_backlog_panel.py — met
- A3 — status view — not met
"""

DRAFT = """cycle: C-6
state: draft
objective: grouped, not specified
"""


class TestCycleStates(StatusCase):
    """FWD-027 / A3: cycle directories next to the old files, and the states
    draft, planned, running, closed, abandoned (ADR-0019 rules 9, 10)."""

    def test_directory_cycle_with_artifacts_and_demands(self):
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-5/board.md", "# board\n")
        self.write("cycles/C-5/promotion.md", PROMOTION)
        self.write("backlog.md", BACKLOG)
        out = run(self.root).stdout
        self.assertIn("OPEN CYCLE C-5 (running)", out)
        self.assertIn("backlog > cycle > demand", out)
        self.assertIn("artifacts: plan.md, board.md, promotion.md", out)
        self.assertIn("FWD-027  back", out)
        self.assertIn("FWD-030  back  depends on FWD-027", out)
        self.assertIn("FWD-032  front  depends on FWD-026, FWD-028", out)
        self.assertIn("1/2 met, 1 pending", out)
        self.assertNotIn("is not named", out)

    def test_draft_is_not_running_and_drafts_may_be_many(self):
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-6/plan.md", DRAFT)
        self.write("cycles/C-7/plan.md", DRAFT.replace("C-6", "C-7"))
        self.write("cycles/C-8/plan.md", "state: planned\nobjective: signed off, waiting\n")
        self.write("backlog.md", BACKLOG)
        out = run(self.root).stdout
        self.assertNotIn("cycles open", out)
        self.assertNotIn("OPEN CYCLE C-6", out)
        self.assertIn("C-6  draft  grouped, not specified", out)
        self.assertIn("C-7  draft", out)
        self.assertIn("C-8  planned  signed off, waiting", out)

    def test_two_running_is_a_warning_across_layouts(self):
        self.write("cycles/C-4.md", OPEN.replace("C-2", "C-4"))
        self.write("cycles/C-5/plan.md", PLAN)
        out = run(self.root).stdout
        self.assertTrue(out.startswith("WARNING"), out)
        # kernel ADR-0024: two running cycles are allowed when their files
        # can be checked; these declare none, so each is warned
        self.assertIn("C-5 runs beside 1 other cycle(s) but a demand declares "
                      "no `files`", out)

    def test_mixed_layouts_are_all_read(self):
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", CLOSED.replace("C-1", "C-2"))
        self.write("cycles/C-3/plan.md", PLAN.replace("C-5", "C-3"))
        self.write("backlog.md", BACKLOG)
        out = run(self.root).stdout
        self.assertIn("OPEN CYCLE C-3", out)
        self.assertIn("C-1  closed 2026-09-28", out)
        self.assertIn("C-2  closed 2026-09-28", out)
        self.assertNotIn("WARNING", out)

    def test_end_lines_derive_and_explicit_state_decides_the_rest(self):
        self.write("cycles/C-2/plan.md", "objective: p\nabandoned: 2026-09-20\n")
        self.write("cycles/C-3/plan.md", "objective: q\nstate: closed\n")
        out = run(self.root).stdout
        self.assertIn("C-2  abandoned 2026-09-20", out)
        self.assertIn("C-3  closed  ", out)

    def test_unknown_state_and_missing_plan_warn(self):
        self.write("cycles/C-1/plan.md", "objective: o\nstate: paused\nclosed: 2026-09-28\n")
        self.write("cycles/C-2/board.md", "x\n")
        self.write("cycles/notes/x.md", "x\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("C-1 has state: paused", r.stdout)
        self.assertIn("C-1  closed 2026-09-28", r.stdout)
        self.assertIn("cycles/C-2/ has no plan.md", r.stdout)
        self.assertIn("cycles/notes is not named C-<n>", r.stdout)

    def test_file_and_directory_for_one_cycle_warn(self):
        self.write("cycles/C-3.md", CLOSED)
        self.write("cycles/C-3/plan.md", PLAN)
        self.assertIn("2 files in cycles/ read as C-3", run(self.root).stdout)

    def test_cycle_selector_reads_a_directory(self):
        self.write("cycles/C-5/plan.md", PLAN)
        r = run(self.root, "--cycle", "C-5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CYCLE C-5 (running)", r.stdout)
        self.assertIn("FWD-030  back  depends on FWD-027", r.stdout)


BACKLOG_IDS = """# Backlog

| id | item | evidence |
|---|---|---|
| B-1 | Role isolation | usage-data |
| 2 | no id yet | opinion |

## Ideas

- B-3 per-demand triage (C-5)
- B-4: timebox report
- **B-5** resync first
- plain idea
- B-1 duplicated id
"""


class TestBacklogIds(StatusCase):
    """FWD-027 / A3: stable backlog ids B-<n> (ADR-0019 rule 9)."""

    def test_ids_from_table_rows_and_bullets(self):
        self.write("backlog.md", BACKLOG_IDS)
        out = run(self.root, "--backlog").stdout
        self.assertIn("- B-1 Role isolation", out)
        self.assertIn("- #2 no id yet", out)
        self.assertIn("- B-3 per-demand triage (C-5)", out)
        self.assertIn("- B-4 timebox report", out)
        self.assertIn("- B-5 resync first", out)
        self.assertIn("- plain idea", out)

    def test_duplicate_id_warns(self):
        self.write("backlog.md", BACKLOG_IDS)
        self.assertIn("B-1 is used by 2 backlog items", run(self.root).stdout)


class TestJson(StatusCase):
    """FWD-027 / A3: --format json carries the text view's content."""

    def setUp(self):
        super().setUp()
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", CLOSED.replace("C-1", "C-2"))
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-5/board.md", "# board\n")
        self.write("cycles/C-5/promotion.md", PROMOTION)
        self.write("cycles/C-6/plan.md", DRAFT)
        self.write("backlog.md", BACKLOG_IDS)

    def load(self, *args):
        r = run(self.root, "--format", "json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_round_trip(self):
        data = self.load()
        self.assertEqual(set(data), {"warnings", "next", "cycles", "backlog",
                                     "demands"})
        by_id = {c["id"]: c for c in data["cycles"]}
        self.assertEqual([c["id"] for c in data["cycles"]], ["C-1", "C-2", "C-5", "C-6"])
        self.assertEqual(by_id["C-1"]["state"], "closed")
        self.assertEqual(by_id["C-1"]["layout"], "file")
        self.assertEqual(by_id["C-6"]["state"], "draft")
        c5 = by_id["C-5"]
        self.assertEqual(c5["state"], "running")
        self.assertEqual(c5["layout"], "directory")
        self.assertEqual(c5["objective"], "backlog > cycle > demand")
        self.assertEqual(c5["artifacts"], ["plan.md", "board.md", "promotion.md"])
        self.assertEqual(c5["demands"][1],
                         {"id": "FWD-030", "layer": "back", "depends_on": ["FWD-027"]})
        self.assertEqual(c5["demands"][0]["depends_on"], [])
        self.assertEqual(c5["done"]["met"], 1)
        self.assertEqual(c5["done"]["pending"], 1)
        self.assertEqual(c5["done"]["total"], 2)
        self.assertEqual(c5["done"]["items"][0],
                         {"mark": "x", "text": "A1 — draft. the panel groups items into a draft"})
        self.assertEqual(c5["done"]["source"], "criteria")
        self.assertIn("B-3 per-demand triage (C-5)", c5["backlog_lines"])
        items = [i for s in data["backlog"]["sections"] for i in s["items"]]
        self.assertIn({"id": "B-4", "text": "timebox report", "cells": None,
                       "cycle": None}, items)
        self.assertIn({"id": None, "text": "plain idea", "cells": None,
                       "cycle": None}, items)
        self.assertEqual(data["backlog"]["sections"][1]["heading"], "Ideas")

    def test_same_warnings_as_text(self):
        text = run(self.root).stdout
        shown = [l[len("WARNING "):] for l in text.splitlines() if l.startswith("WARNING ")]
        self.assertTrue(shown)
        self.assertEqual(self.load()["warnings"], shown)

    def test_old_file_demands_line_and_no_backlog(self):
        (self.root / "backlog.md").unlink()
        self.write("cycles/C-2.md", OPEN)
        data = self.load()
        self.assertIsNone(data["backlog"])
        c2 = [c for c in data["cycles"] if c["id"] == "C-2"][0]
        self.assertEqual([d["id"] for d in c2["demands"]], ["DEM-035", "DEM-036"])
        self.assertEqual(c2["artifacts"], [])

    def test_selectors_narrow_json(self):
        self.assertEqual(set(self.load("--backlog")), {"warnings", "next", "backlog"})
        self.assertEqual(set(self.load("--cycles")),
                         {"warnings", "next", "cycles", "demands"})
        one = self.load("--cycle", "C-5")
        self.assertEqual([c["id"] for c in one["cycles"]], ["C-5"])

    def test_malformed_input_is_still_valid_json(self):
        self.write("cycles/C-7/plan.md", b"state: \xff\n## Demands\n| broken\n", raw=True)
        self.write("backlog.md", b"\xff\xfe junk\n| broken |\n", raw=True)
        data = self.load()
        self.assertIn("C-7", [c["id"] for c in data["cycles"]])

    def test_bad_format_is_a_bad_argument(self):
        self.assertEqual(run(self.root, "--format", "xml").returncode, 2)


LONG = ("a very long item text that goes well past one hundred and ten characters "
        "so the panel reading json gets a clipped text back ok")


class TestReviewRoundOne(StatusCase):
    """reviews/FWD-027 round 1: each finding's probe, red before the fix."""

    def test_f1_closed_line_ends_a_running_cycle(self):
        self.write("cycles/C-5/plan.md", PLAN.replace("opened:", "closed: 2026-10-02\nopened:"))
        self.write("cycles/C-6/plan.md", PLAN.replace("C-5", "C-6"))
        self.write("cycles/C-7/plan.md", "state: running\nobjective: gave up\n"
                   "abandoned: 2026-10-01\n")
        self.write("backlog.md", BACKLOG)
        out = run(self.root, "--cycles").stdout
        self.assertNotIn("cycles open", out)
        self.assertIn("OPEN CYCLE C-6", out)
        self.assertNotIn("OPEN CYCLE C-5", out)
        self.assertIn("C-5  closed 2026-10-02", out)
        self.assertIn("C-7  abandoned 2026-10-01", out)
        self.assertIn("C-5 has state: running and a closed: line — closed: wins", out)

    def test_f1_state_reads_its_first_word(self):
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-6/plan.md", "state: planned (signed off 2026-09-29)\n"
                   "objective: waiting\n")
        self.write("backlog.md", BACKLOG)
        out = run(self.root).stdout
        self.assertNotIn("cycles open", out)
        self.assertNotIn("C-6 has state:", out)
        self.assertIn("C-6  planned  waiting", out)

    def test_f2_json_carries_full_text_and_cells(self):
        self.write("backlog.md", f"| id | item | evidence |\n|---|---|---|\n"
                   f"| B-1 | {LONG} | usage-data (C-3) |\n| 2 | x | opinion |\n\n"
                   f"## Ideas\n\n- B-4 — {LONG}\n")
        self.assertIn("…", run(self.root, "--backlog").stdout)
        data = json.loads(run(self.root, "--backlog", "--format", "json").stdout)
        [top, ideas] = data["backlog"]["sections"]
        self.assertEqual(top["items"][0], {"id": "B-1", "text": LONG,
                                           "cells": ["B-1", LONG, "usage-data (C-3)"],
                                           "cycle": None})
        self.assertEqual(top["items"][1]["text"], "x")
        self.assertEqual(top["items"][1]["cells"], ["2", "x", "opinion"])
        self.assertEqual(ideas["items"][0], {"id": "B-4", "text": LONG, "cells": None,
                                             "cycle": None})
        self.write("cycles/C-3.md", "objective: o\n")
        data = json.loads(run(self.root, "--format", "json").stdout)
        self.assertEqual(data["cycles"][0]["backlog_lines"], [f"B-1 {LONG}"])

    def test_f3_ids_in_backticks_and_after_a_checkbox(self):
        self.write("backlog.md", "| id | item |\n|---|---|\n| `B-5` | code cell |\n"
                   "| **B-6** | bold cell |\n\n## Ideas\n\n- [ ] B-1 checkbox item\n"
                   "- [x] `B-2` done code id\n- `B-3` code id\n- B-4 mentions B-1 inside\n")
        data = json.loads(run(self.root, "--backlog", "--format", "json").stdout)
        items = [(i["id"], i["text"]) for s in data["backlog"]["sections"] for i in s["items"]]
        self.assertEqual(items, [("B-5", "code cell"), ("B-6", "bold cell"),
                                 ("B-1", "checkbox item"), ("B-2", "done code id"),
                                 ("B-3", "code id"), ("B-4", "mentions B-1 inside")])
        self.assertEqual(data["warnings"], [])
        self.assertIn("- B-1 checkbox item", run(self.root, "--backlog").stdout)

    def test_f3_ids_outside_the_declared_places_warn(self):
        self.write("backlog.md", "## Ideas\n\n### B-7 heading\n\n1. B-8 numbered\n"
                   "- B-9x glued\n| 3 | `B-10` | late cell |\n- plain\n")
        data = json.loads(run(self.root, "--backlog", "--format", "json").stdout)
        ws = "\n".join(data["warnings"])
        for bid in ("B-7", "B-8", "B-9", "B-10"):
            self.assertIn(f"backlog.md: {bid} in", ws)
        self.assertEqual(len(data["warnings"]), 4)
        ids = [i["id"] for s in data["backlog"]["sections"] for i in s["items"]]
        self.assertEqual(ids, [None, None, None])

    def test_f4_directory_progress_from_criteria_and_promotion(self):
        self.write("cycles/C-5/plan.md", PLAN)
        out = run(self.root, "--cycles").stdout
        self.assertIn("criteria:  0/2 met, 2 pending", out)
        self.assertIn("[ ] A3 — the view. status shows states", out)
        self.write("cycles/C-5/promotion.md", PROMOTION)
        out = run(self.root, "--cycles").stdout
        self.assertIn("criteria:  1/2 met, 1 pending", out)
        self.assertNotIn("but no closed: line", out)

    def test_f4_every_criterion_met_is_ready_to_close(self):
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-5/promotion.md", PROMOTION.replace("not met", "met"))
        out = run(self.root, "--cycles").stdout
        self.assertIn("criteria:  2/2 met", out)
        self.assertIn("C-5 has every criterion met in promotion.md but no closed: line", out)
        self.write("cycles/C-5/plan.md", PLAN.replace("opened:", "closed: 2026-10-02\nopened:"))
        out = run(self.root, "--cycles").stdout
        self.assertNotIn("every criterion met", out)
        self.assertIn("C-5  closed 2026-10-02  2/2 met", out)


PANEL_BACKLOG = """# Backlog

| id | item | evidence |
|---|---|---|
| B-1 | one | opinion |
| B-2 | two → C-6 | opinion |

- B-3 three
"""

GROUPED = """# C-{n}

state: draft
objective: {objective}

## Items

{items}
"""


class TestPanelFindings(StatusCase):
    """FWD-030 review F1–F4: what the panel writes is what status reads."""

    def draft(self, n, items, objective="grouped"):
        self.write(f"cycles/C-{n}/plan.md", GROUPED.format(
            n=n, objective=objective, items="\n".join(items)))

    def load(self):
        r = run(self.root, "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_f1_draft_items_in_json_and_text(self):
        self.write("backlog.md", PANEL_BACKLOG)
        self.draft(6, ["- B-2 two"])
        data = self.load()
        [c6] = data["cycles"]
        self.assertEqual(c6["items"], [{"id": "B-2", "text": "two"}])
        out = run(self.root, "--cycles").stdout
        self.assertIn("C-6  draft  grouped", out)
        self.assertIn("    - B-2 two", out)
        out = run(self.root, "--cycle", "C-6").stdout
        self.assertIn("items:     1", out)
        self.assertIn("    - B-2 two", out)

    def test_f2_grouping_mark_is_read(self):
        self.write("backlog.md", PANEL_BACKLOG)
        self.draft(6, ["- B-2 two"])
        data = self.load()
        self.assertEqual(data["warnings"], [])
        items = {i["id"]: i for s in data["backlog"]["sections"] for i in s["items"]}
        self.assertEqual(items["B-2"]["cycle"], "C-6")
        self.assertEqual(items["B-2"]["text"], "two")
        self.assertIsNone(items["B-1"]["cycle"])
        # the grouping mark is not an origin: C-6 produced no backlog line
        self.assertEqual(data["cycles"][0]["backlog_lines"], [])

    def test_f2_one_item_in_two_drafts_warns(self):
        self.write("backlog.md", PANEL_BACKLOG)
        self.draft(6, ["- B-2 two"])
        self.draft(7, ["- B-2 two", "- B-3 three"])
        ws = self.load()["warnings"]
        self.assertTrue(any(w.startswith("B-2 is grouped into C-6, C-7") for w in ws), ws)
        self.assertFalse(any(w.startswith("B-3") for w in ws), ws)

    def test_f2_mark_disagreeing_with_the_draft_warns(self):
        self.write("backlog.md", PANEL_BACKLOG.replace("- B-3 three", "- B-3 three → C-6"))
        self.draft(7, ["- B-3 three"])
        ws = self.load()["warnings"]
        self.assertTrue(any(w.startswith("B-3 is grouped into C-6, C-7") for w in ws), ws)

    def test_f3_next_backlog_id_counts_ids_held_only_by_a_cycle(self):
        self.write("backlog.md", PANEL_BACKLOG)
        self.assertEqual(self.load()["next"]["backlog_id"], "B-4")
        self.draft(6, ["- B-9 taken out of backlog.md"])
        self.assertEqual(self.load()["next"]["backlog_id"], "B-10")
        self.write("cycles/C-2.md", "objective: old\nclosed: 2026-09-01\n\n- B-12 cited\n")
        self.assertEqual(self.load()["next"]["backlog_id"], "B-13")
        self.assertIn("next id B-13", run(self.root, "--backlog").stdout)

    def test_f4_next_cycle_id_counts_files_and_directories(self):
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", CLOSED.replace("C-1", "C-2"))
        self.assertEqual(self.load()["next"]["cycle_id"], "C-3")
        self.draft(3, ["- B-1 one"])
        self.assertEqual(self.load()["next"]["cycle_id"], "C-4")
        self.assertIn("next cycle id: C-4", run(self.root, "--cycles").stdout)

    def test_next_ids_with_nothing_on_disk(self):
        data = self.load()
        self.assertEqual(data["next"], {"backlog_id": "B-1", "cycle_id": "C-1"})


CLOSED_PLAN = PLAN.replace("state: running", "state: closed")


class TestClosedCycleNeedsPromotion(StatusCase):
    """C-5 F5: a closed directory cycle with no promotion.md, or with a
    criterion not settled in it, must not look finished."""

    def test_closed_without_promotion_warns(self):
        self.write("cycles/C-6/plan.md", CLOSED_PLAN.replace("C-5", "C-6"))
        self.write("cycles/C-7/plan.md",
                   PLAN.replace("C-5", "C-7").replace("opened:", "closed: 2026-10-02\nopened:"))
        out = run(self.root).stdout
        self.assertIn("WARNING C-6 is closed without promotion.md", out)
        self.assertIn("WARNING C-7 is closed without promotion.md", out)

    def test_closed_with_an_unmet_criterion_warns(self):
        self.write("cycles/C-6/plan.md", CLOSED_PLAN.replace("C-5", "C-6"))
        self.write("cycles/C-6/promotion.md", PROMOTION)
        out = run(self.root).stdout
        self.assertIn("WARNING C-6 is closed with criteria not met: A3", out)
        self.assertNotIn("without promotion.md", out)

    def test_every_criterion_met_or_declined_is_settled(self):
        self.write("cycles/C-6/plan.md", CLOSED_PLAN.replace("C-5", "C-6"))
        for mark in ("declined", "limit", "**declined**"):
            self.write("cycles/C-6/promotion.md", PROMOTION.replace(
                "status view — not met",
                f"budget spent, user declined 2026-10-01 — {mark}"))
            r = run(self.root)
            self.assertNotIn("WARNING C-6", r.stdout, mark)
            self.assertIn("C-6  closed  1/2 met, 1 declined", r.stdout, mark)

    def test_old_layout_closed_file_is_not_affected(self):
        self.write("cycles/C-1.md", CLOSED)
        out = run(self.root).stdout
        self.assertNotIn("promotion.md", out)
        self.assertNotIn("criteria not met", out)

    def test_running_and_abandoned_cycles_are_not_affected(self):
        self.write("cycles/C-5/plan.md", PLAN)
        self.write("cycles/C-6/plan.md", "objective: gave up\nabandoned: 2026-10-01\n")
        out = run(self.root).stdout
        self.assertNotIn("is closed", out)


# FWD-034: the demands inventory — both layouts, a slugged and a bare spec
# directory, a loose demand, a malformed findings.toml
OLD_FILE_CYCLE = """cycle: C-1
objective: the old layout
closed: 2026-08-09
demands: FWD-001 (S)

## Done when
- [x] FWD-001 done
"""

DEMANDS_PLAN = """cycle: C-3
state: running
objective: the new layout

## Acceptance criteria

- **A1 — one.** first

## Demands

| id | layer | depends on | what | meets | follows |
|---|---|---|---|---|---|
| FWD-030 | back | — | the reader | A1 | ADR-0019 |
| FWD-033 | front | FWD-030 | no spec yet | A1 | — |
"""

OLD_FINDINGS = '''[meta]
demand_id = "FWD-001"

[[finding]]
id = "F1"
severity = "high"
probe = "probe one | with a pipe"
blocking = true

[[finding]]
severity = "low"
evidence = """
first evidence line
second"""
blocking = false
'''

NEW_FINDINGS = """[[finding]]
id = "F1"
title = "the reader drops a row"
severity = "medium"
blocking = false
"""


class DemandsCase(StatusCase):
    def setUp(self):
        super().setUp()
        w = self.write
        w("cycles/C-1.md", OLD_FILE_CYCLE)
        w("cycles/C-3/plan.md", DEMANDS_PLAN)
        w("cycles/C-3/board.md", "# board\n")
        w("cycles/C-3/promotion.md", "cycle: C-3\ndecision: promote\n\n"
          "## Criteria\n\n- A1 — ok — met\n")
        w("reviews/C-3/findings.toml", "")
        # old layout, slugged, linked by the old file's demands: line
        w("specs/FWD-001-self-install/spec.md", "# FWD-001 — self install\n\nold spec body\n")
        w("specs/FWD-001-self-install/acceptance.md", "date: 2026-08-09\n")
        w("reviews/FWD-001/findings.toml", OLD_FINDINGS)
        w("promotions/FWD-001/decision.md", "---\ndemand: FWD-001\n"
          "decision: promote\n---\n")
        # old layout, bare directory, linked by nothing: loose
        w("specs/FWD-002/spec.md", "# FWD-002 — loose\n")
        w("specs/FWD-002/acceptance.md", "date: 2026-08-09\n")
        w("promotions/FWD-002/decision.md", "decision: hold\n")
        # new layout, linked by the plan's table
        w("specs/FWD-030-panel/spec.md", "# FWD-030 — panel\n\ncycle: C-3 · "
          "layer: back · meets: A1 · follows: ADR-0019 rules 9, ADR-0018\n\nbody\n")
        w("reviews/FWD-030/findings.toml", NEW_FINDINGS)
        # new layout, linked only by its own cycle: line
        w("specs/FWD-031-retire/spec.md", "# FWD-031\n\ncycle: C-3 · layer: front\n")
        # a malformed findings.toml
        w("specs/FWD-032-coherence/spec.md", "# FWD-032\n\nfollows: ADR-0099\n")
        w("reviews/FWD-032/findings.toml", "[[finding]\nseverity = \n")
        w("docs/adr/0019-backlog-cycle-demand.md", "# ADR-0019 — Backlog, cycle, demand\n")
        w("docs/adr/0018-status-is-a-report.md", "# ADR-0018 — Status is a report\n")

    def load(self, *args):
        r = run(self.root, "--format", "json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class TestDemands(DemandsCase):
    """FWD-034 / A3, A4, A6: every specs/<id>/ with its cycle link, review
    summary and promotion; per-cycle artifact paths; --demand."""

    def demands(self):
        return {d["id"]: d for d in self.load()["demands"]}

    def test_every_spec_directory_is_a_demand(self):
        self.assertEqual(sorted(self.demands()),
                         ["FWD-001", "FWD-002", "FWD-030", "FWD-031", "FWD-032"])

    def test_cycle_link_from_table_file_line_and_spec_line(self):
        d = self.demands()
        self.assertEqual((d["FWD-030"]["cycle"], d["FWD-030"]["cycle_source"]),
                         ("C-3", "plan"))
        self.assertEqual(d["FWD-030"]["layer"], "back")
        self.assertEqual((d["FWD-001"]["cycle"], d["FWD-001"]["cycle_source"]),
                         ("C-1", "plan"))
        self.assertEqual((d["FWD-031"]["cycle"], d["FWD-031"]["cycle_source"]),
                         ("C-3", "spec"))
        self.assertEqual(d["FWD-031"]["layer"], "front")
        # FM2: a demand no cycle links is listed, and loose
        self.assertIsNone(d["FWD-002"]["cycle"])
        self.assertTrue(d["FWD-002"]["loose"])
        self.assertFalse(d["FWD-030"]["loose"])

    def test_layouts_and_paths(self):
        d = self.demands()
        self.assertEqual(d["FWD-001"]["layout"], "old")
        self.assertEqual(d["FWD-030"]["layout"], "new")
        self.assertEqual(d["FWD-001"]["dir"], "specs/FWD-001-self-install")
        self.assertEqual(d["FWD-001"]["spec"], "specs/FWD-001-self-install/spec.md")
        self.assertEqual(d["FWD-030"]["follows"], ["ADR-0019", "ADR-0018"])

    def test_review_summary(self):
        d = self.demands()
        self.assertEqual(d["FWD-001"]["review"],
                         {"path": "reviews/FWD-001/findings.toml", "findings": 2,
                          "by_severity": {"high": 1, "low": 1}, "blocking": 1,
                          "error": None})
        self.assertEqual(d["FWD-030"]["review"]["by_severity"], {"medium": 1})
        self.assertIsNone(d["FWD-031"]["review"])

    def test_malformed_findings_do_not_traceback(self):
        r = run(self.root, "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        rev = {d["id"]: d for d in json.loads(r.stdout)["demands"]}["FWD-032"]["review"]
        self.assertIsNone(rev["findings"])
        self.assertTrue(rev["error"])
        r = run(self.root, "--demand", "FWD-032")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("not valid TOML", r.stdout)

    def test_malformed_shapes_do_not_traceback(self):
        for body in ('finding = "text"\n', "[[finding]]\nseverity = 3\nblocking = 'yes'\n",
                     "finding = [1, 2]\n", b"\xff\xfe[[finding]]\n"):
            self.write("reviews/FWD-032/findings.toml", body, raw=isinstance(body, bytes))
            for args in (("--format", "json"), ("--demand", "FWD-032")):
                r = run(self.root, *args)
                self.assertEqual(r.returncode, 0, (body, args, r.stderr))
                self.assertNotIn("Traceback", r.stderr)

    def test_promotion_from_cycle_or_old_directory(self):
        d = self.demands()
        self.assertEqual(d["FWD-030"]["promotion"],
                         {"path": "cycles/C-3/promotion.md", "decision": "promote"})
        self.assertEqual(d["FWD-001"]["promotion"],
                         {"path": "promotions/FWD-001/decision.md", "decision": "promote"})
        self.assertEqual(d["FWD-002"]["promotion"]["decision"], "hold")
        self.assertIsNone(d["FWD-032"]["promotion"])

    def test_cycle_artifact_paths(self):
        cycles = {c["id"]: c for c in self.load()["cycles"]}
        self.assertEqual(cycles["C-3"]["artifact_paths"],
                         ["cycles/C-3/plan.md", "cycles/C-3/board.md",
                          "cycles/C-3/promotion.md", "reviews/C-3/findings.toml"])
        self.assertEqual(cycles["C-1"]["artifact_paths"], ["cycles/C-1.md"])

    def test_demand_drill_down(self):
        r = run(self.root, "--demand", "fwd-030")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("DEMAND FWD-030", out)
        self.assertIn("specs/FWD-030-panel/spec.md", out)
        self.assertIn("\nbody\n", out)  # the spec text
        self.assertIn("F1  medium  —  the reader drops a row", out)
        self.assertIn("cycles/C-3/promotion.md — promote", out)
        self.assertIn("ADR-0019  docs/adr/0019-backlog-cycle-demand.md", out)
        self.assertIn("ADR-0018  docs/adr/0018-status-is-a-report.md", out)
        old = run(self.root, "--demand", "FWD-001").stdout
        self.assertIn("F1  high  blocking  probe one | with a pipe", old)
        self.assertIn("#2  low  —  first evidence line", old)
        self.assertIn("promotions/FWD-001/decision.md — promote", old)
        missing = run(self.root, "--demand", "FWD-032").stdout
        self.assertIn("ADR-0099  (no file in docs/adr/)", missing)

    def test_demand_json(self):
        data = self.load("--demand", "FWD-001")
        self.assertEqual(data["demand"]["id"], "FWD-001")
        self.assertEqual([f["id"] for f in data["demand"]["findings"]], ["F1", "#2"])

    def test_bad_demand_id_is_a_bad_argument(self):
        r = run(self.root, "--demand", "FWD-999")
        self.assertEqual(r.returncode, 2)
        self.assertIn("FWD-999", r.stderr)
        # in a plan's table but without a spec directory: not a demand on disk
        self.assertEqual(run(self.root, "--demand", "FWD-033").returncode, 2)

    def test_read_only(self):
        def snapshot():
            return sorted((str(p.relative_to(self.root)), p.stat().st_mtime_ns)
                          for p in self.root.rglob("*"))
        before = snapshot()
        for args in ((), ("--format", "json"), ("--demand", "FWD-001")):
            run(self.root, *args)
        self.assertEqual(before, snapshot())


# FWD-035: the terminal panel
TERMINAL_BACKLOG = """---
goal: g
date: 2026-09-29
---

# Backlog

| id | item | evidence |
|---|---|---|
| B-1 | table item → C-6 | opinion |

## Ideas

- B-2 a bullet idea (C-3)
- B-3 grouped → C-3

## Discarded (2026-09-29)

- B-4 old thing — discarded: done — shipped in FWD-001
- B-5 no reason given
"""

SECTIONS = ["## Overview", "## Backlog", "## Cycles", "## Demands", "## Discarded"]


def panel(root, *args):
    r = run(root, "--panel", *args)
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    return r.stdout


def section(out: str, name: str) -> list[str]:
    lines, keep = [], False
    for line in out.splitlines():
        if line.startswith("## "):
            keep = line.startswith(f"## {name}")
            continue
        if keep:
            lines.append(line)
    return lines


class TestPanel(DemandsCase):
    """FWD-035 / A1, A2, A3, A5: five markdown sections from the JSON."""

    def setUp(self):
        super().setUp()
        self.write("backlog.md", TERMINAL_BACKLOG)
        self.write("cycles/C-6/plan.md", "state: draft\nobjective: later\n\n"
                   "## Items\n\n- B-1 table item\n")
        self.write("cycles/C-7/plan.md", "state: planned\nobjective: next up\n\n"
                   "## Acceptance criteria\n\n- A1 — x\n")

    def test_five_sections_in_order(self):
        out = panel(self.root)
        heads = [line for line in out.splitlines() if line.startswith("## ")]
        self.assertEqual([h.split(" (")[0] for h in heads], SECTIONS)

    def test_overview(self):
        ov = "\n".join(section(panel(self.root), "Overview"))
        self.assertIn("- running: C-3 — the new layout — done 1/1", ov)
        self.assertIn("- planned: C-7", ov)
        self.assertIn("- drafts: C-6", ov)
        self.assertIn("- next ids: B-6 · C-8", ov)
        self.assertIn("- warnings:", ov)
        self.write("cycles/C-3/plan.md", DEMANDS_PLAN.replace("state: running",
                                                              "state: planned"))
        self.assertIn("- running: none", panel(self.root))

    def test_backlog_by_section_with_id_and_cycle_mark(self):
        bl = "\n".join(section(panel(self.root), "Backlog"))
        self.assertIn("- B-1 table item → C-6", bl)
        self.assertIn("### Ideas", bl)
        self.assertIn("- B-3 grouped → C-3", bl)
        self.assertNotIn("B-4", bl)

    def test_running_and_planned_cycles_in_full(self):
        cy = "\n".join(section(panel(self.root), "Cycles"))
        self.assertIn("### C-3 · running · done 1/1", cy)
        self.assertIn("| FWD-030 | back | 1 finding recorded, none blocking | promote |", cy)
        self.assertIn("| FWD-033 | front | no spec | — |", cy)
        self.assertIn("| FWD-031 | front | not reviewed | promote |", cy)
        self.assertIn("- artifacts: cycles/C-3/plan.md, cycles/C-3/board.md, "
                      "cycles/C-3/promotion.md, reviews/C-3/findings.toml", cy)
        self.assertIn("### C-7 · planned", cy)

    def test_drafts_with_items_and_ended_one_line(self):
        cy = section(panel(self.root), "Cycles")
        self.assertIn("- C-6 — later", cy)
        self.assertIn("  - B-1 table item", cy)
        ended = [l for l in cy if l.startswith("- C-1 ")]
        self.assertEqual(ended, ["- C-1 · closed 2026-08-09 · done 1/1 · 1 demand · "
                                 "the old layout"])

    def test_loose_demands_one_line_each(self):
        dm = [l for l in section(panel(self.root), "Demands") if l.startswith("- ")]
        self.assertEqual(dm, ["- FWD-002 · legacy layout (no cycle) · not reviewed · promotion hold",
                              "- FWD-032 · no cycle · findings.toml unreadable · promotion —"])

    def test_discarded_with_reason(self):
        ds = [l for l in section(panel(self.root), "Discarded") if l.startswith("- ")]
        self.assertEqual(ds, ["- B-4 old thing — done — shipped in FWD-001",
                              "- B-5 no reason given — (no reason)"])

    def test_counts_equal_the_json(self):
        # FM4: the panel's numbers are the JSON's
        data = self.load()
        items = [(s["heading"], i) for s in data["backlog"]["sections"] for i in s["items"]]
        disc = [i for h, i in items if h.lower().startswith("discarded")]
        states = [c["state"] for c in data["cycles"]]
        expected = (f"- counts: backlog {len(items) - len(disc)} · discarded {len(disc)} · "
                    f"cycles {len(states)} ({states.count('running')} running, "
                    f"{states.count('planned')} planned, {states.count('draft')} draft, "
                    f"{states.count('closed') + states.count('abandoned')} ended) · "
                    f"demands {len(data['demands'])} "
                    f"({sum(d['loose'] for d in data['demands'])} loose)")
        out = panel(self.root)
        self.assertIn(expected, out)
        self.assertEqual(len([l for l in section(out, "Backlog") if l.startswith("- ")]),
                         len(items) - len(disc))
        self.assertEqual(len([l for l in section(out, "Discarded") if l.startswith("- ")]),
                         len(disc))
        self.assertEqual(len([l for l in section(out, "Demands") if l.startswith("- ")]),
                         sum(d["loose"] for d in data["demands"]))
        self.assertEqual(data["warnings"],
                         [l[4:].replace("\\|", "|") for l in section(out, "Overview")
                          if l.startswith("  - ")])

    def test_panel_json_is_the_full_json(self):
        r = run(self.root, "--panel", "--format", "json")
        self.assertEqual(json.loads(r.stdout), self.load())

    def test_hostile_text_keeps_the_layout(self):
        # FM1: pipes and heading markers from file text are escaped
        self.write("backlog.md", "# b\n\n## # evil | heading\n\n"
                   "- B-1 # looks | like a heading\n- ## two\n- > quote\n- 1. listed\n"
                   "| B-2 | cell with \\| an escaped pipe | x |\n")
        self.write("cycles/C-3/plan.md", DEMANDS_PLAN.replace(
            "objective: the new layout", "objective: | a | b |").replace(
            "| FWD-030 | back |", "| FWD-030 | ba\\|ck |"))
        self.write("specs/FWD-031-retire/spec.md", "# x\n\ncycle: C-3 · layer: # h | x\n")
        out = panel(self.root)
        own = ("## ", "### ")
        for line in out.splitlines():
            if line.startswith("#"):
                self.assertTrue(line.startswith(own), line)
                self.assertFalse(line.split(" ", 1)[1].startswith("#"), line)
            if line.startswith("|"):
                pipes = len(re.findall(r"(?<!\\)\|", line))
                self.assertEqual(pipes, 5, line)
            if line.startswith(("- ", "  - ")):
                body = line.lstrip(" ")[2:]
                self.assertFalse(re.match(r"[#>]|\d+\.", body), line)
        self.assertIn("\\# looks \\| like a heading", out)
        self.assertIn("### \\# evil \\| heading", out)
        self.assertIn("objective: \\| a \\| b \\|", out)


class TestPanelScale(StatusCase):
    """FM3: a large repository stays one line per backlog item, ended cycle
    and loose demand, plus a bounded frame."""

    def test_line_count_is_bounded(self):
        long = "word " * 80
        rows = "\n".join(f"- B-{n} {long}" for n in range(1, 301))
        self.write("backlog.md", f"goal: g\ndate: 2026-09-29\n\n## Ideas\n\n{rows}\n")
        for n in range(1, 41):
            table = "\n".join(f"| X-{n}{k} | back | — |" for k in range(5))
            self.write(f"cycles/C-{n}/plan.md",
                       f"objective: {long}\nclosed: 2026-09-01\n\n## Acceptance criteria\n\n"
                       + "\n".join(f"- A{k} — {long}" for k in range(10))
                       + f"\n\n## Demands\n\n| id | layer | depends on |\n|---|---|---|\n{table}\n")
            self.write(f"cycles/C-{n}/promotion.md", "\n".join(
                f"- A{k} — ok — met" for k in range(10)) + "\n")
            for k in range(5):
                self.write(f"specs/X-{n}{k}-s/spec.md", f"# x\n\n{long}\n")
        for n in range(1, 61):
            self.write(f"specs/L-{n}-loose/spec.md", "# loose\n")
            self.write(f"reviews/L-{n}/findings.toml",
                       "[[finding]]\nseverity = 'low'\nblocking = false\n" * 20)
        out = panel(self.root).splitlines()
        self.assertLessEqual(len(out), 300 + 40 + 60 + 40, len(out))
        self.assertLessEqual(max(len(line) for line in out), 260)
        self.assertNotIn("A3 —", "\n".join(out))  # ended cycles fold



class TestCycleReviewC12(DemandsCase):
    """C-12 cycle review F1, F3, F4, F5; FWD-034 F1; FWD-035 F1."""

    def slugged(self):
        # a loose legacy demand whose review and promotion live in slugged dirs
        self.write("specs/FWD-040-erase/spec.md", "# FWD-040\n")
        self.write("specs/FWD-040-erase/acceptance.md", "date: 2026-08-09\n")
        self.write("reviews/FWD-040-erase-source/findings.toml", OLD_FINDINGS)
        self.write("promotions/FWD-040-erase-source/decision.md", "decision: promote\n")
        # a longer id with the same prefix is not FWD-040's
        self.write("reviews/FWD-0400-other/findings.toml", NEW_FINDINGS)
        # a linked demand reviewed in a slugged dir
        self.write("reviews/FWD-031-retire/findings.toml", NEW_FINDINGS)

    def test_f1_slugged_review_and_promotion_dirs_are_found(self):
        self.slugged()
        d = {x["id"]: x for x in self.load()["demands"]}
        self.assertEqual(d["FWD-040"]["review"]["path"],
                         "reviews/FWD-040-erase-source/findings.toml")
        self.assertEqual(d["FWD-040"]["review"]["blocking"], 1)
        self.assertEqual(d["FWD-040"]["promotion"],
                         {"path": "promotions/FWD-040-erase-source/decision.md",
                          "decision": "promote"})
        self.assertEqual(d["FWD-031"]["review"]["path"],
                         "reviews/FWD-031-retire/findings.toml")
        self.assertEqual(d["FWD-001"]["review"]["path"], "reviews/FWD-001/findings.toml")
        out = run(self.root, "--demand", "FWD-040").stdout
        self.assertIn("review:    reviews/FWD-040-erase-source/findings.toml", out)
        self.assertIn("F1  high  blocking", out)
        self.assertIn("promotion: promotions/FWD-040-erase-source/decision.md — promote",
                      out)
        loose = [l for l in section(panel(self.root), "Demands") if "FWD-040" in l]
        self.assertEqual(loose, ["- FWD-040 · legacy layout (no cycle) · "
                                 "1 blocking finding recorded (2 in all) · promotion promote"])

    def test_f1_bare_directory_is_preferred(self):
        self.write("reviews/FWD-030-panel/findings.toml", OLD_FINDINGS)
        d = {x["id"]: x for x in self.load()["demands"]}
        self.assertEqual(d["FWD-030"]["review"]["path"], "reviews/FWD-030/findings.toml")

    def test_f3_cycle_drill_down_shows_review_and_promotion(self):
        self.slugged()
        out = run(self.root, "--cycle", "C-1").stdout
        self.assertIn("FWD-001  —  1 blocking finding recorded (2 in all) · "
                      "promotion promote", out)
        out = run(self.root, "--cycle", "C-3").stdout
        self.assertIn("FWD-030  back  1 finding recorded, none blocking · promotion promote",
                      out)
        self.assertIn("FWD-031  front  1 finding recorded, none blocking · promotion promote",
                      out)
        self.assertIn("FWD-033  front  depends on FWD-030  no spec · promotion —", out)

    def test_f4_vocabulary(self):
        self.write("backlog.md", "- B-1 top item\n\n## Ideas\n\n- B-2 idea\n")
        long = "cycles with their demands and every loose one " * 4
        self.write("cycles/C-3/plan.md", DEMANDS_PLAN.replace(
            "objective: the new layout", f"objective: {long}"))
        out = panel(self.root)
        self.assertIn("### Unsectioned", out)
        self.assertNotIn("before any section", out)
        self.assertNotIn("criteria 1/1", out)
        self.assertNotIn(" met", "\n".join(section(out, "Cycles")))
        self.assertIn(f"- running: C-3 — {' '.join(long.split())} — done 1/1",
                      out)  # in full, in the Overview
        cy = [l for l in section(out, "Cycles") if l.startswith("- objective:")][0]
        self.assertTrue(cy.endswith("…"), cy)
        self.assertIn(cy[len("- objective: "):-1].split()[-1],
                      long.split())  # cut at a word boundary

    def test_f4_next_action(self):
        def nxt():
            return [l for l in section(panel(self.root), "Overview")
                    if l.startswith("- next:")]
        # running C-3: FWD-031 has a spec and no review
        self.assertEqual(nxt(), ["- next: review FWD-031 (C-3)"])
        self.write("reviews/FWD-031/findings.toml", NEW_FINDINGS)
        self.assertEqual(nxt(), ["- next: run the cycle review of C-3"])
        self.write("cycles/C-3/review.md", "# review\n")
        self.assertEqual(nxt(), ["- next: close C-3 (every criterion met)"])
        self.write("cycles/C-3/promotion.md", "decision: hold\n")
        self.assertEqual(nxt(), ["- next: promote and close C-3 (1 criterion pending)"])
        self.write("cycles/C-3/plan.md", DEMANDS_PLAN.replace("state: running",
                                                              "state: planned"))
        self.assertEqual(nxt(), ["- next: sign off C-3 (planned)"])
        self.write("cycles/C-3/plan.md", DEMANDS_PLAN.replace("state: running",
                                                              "closed: 2026-09-01"))
        self.write("cycles/C-6/plan.md", "state: draft\nobjective: d\n")
        self.write("cycles/C-8/plan.md", "state: draft\nobjective: d\n")
        self.assertEqual(nxt(), ["- next: specify a draft (C-6, C-8)"])

    def test_f5_warnings_fold_after_ten(self):
        for n in range(1, 16):
            self.write(f"cycles/C-{100 + n}/plan.md", "closed: 2026-09-01\nobjective: o\n")
        warns = self.load()["warnings"]
        self.assertGreater(len(warns), 10)
        ov = section(panel(self.root), "Overview")
        shown = [l for l in ov if l.startswith("  - ")]
        self.assertEqual(len(shown), 11)
        self.assertEqual(shown[-1],
                         f"  - … {len(warns) - 10} more (status.py --format json)")
        self.assertIn(f"- warnings: {len(warns)}", ov)

    def test_fwd034_f1_empty_demand_id_is_a_bad_argument(self):
        for bad in ("", "  "):
            r = run(self.root, "--demand", bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertEqual(r.stdout, "")
        self.assertEqual(run(self.root, "--cycle", "").returncode, 2)

    def test_fwd035_f1_dangling_cycle_link_is_loose_and_warns(self):
        self.write("specs/FWD-050-lost/spec.md", "# FWD-050\n\ncycle: C-99 · layer: back\n")
        data = self.load()
        d = {x["id"]: x for x in data["demands"]}["FWD-050"]
        self.assertTrue(d["loose"])
        self.assertIsNone(d["cycle"])
        self.assertEqual(d["dangling_cycle"], "C-99")
        self.assertTrue(any("FWD-050" in w and "C-99" in w for w in data["warnings"]),
                        data["warnings"])
        dm = [l for l in section(panel(self.root), "Demands") if "FWD-050" in l]
        self.assertEqual(dm, ["- FWD-050 · no cycle (C-99 not in cycles/) · "
                              "not reviewed · promotion —"])


class TestPanelPolish(DemandsCase):
    """FWD-042 / A8: one findings parse per --demand (B-45), readable panel
    helpers (B-46), a promotion cell that keeps bold and cuts at a word
    (B-47)."""

    def test_b45_demand_parses_its_findings_once(self):
        import contextlib
        import importlib.util
        import io
        from unittest import mock
        spec = importlib.util.spec_from_file_location("status_fwd042", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        seen: list[str] = []
        real = mod.tomllib.loads

        def counting(text, *a, **k):
            seen.append(text)
            return real(text, *a, **k)
        target = (self.root / "reviews/FWD-030/findings.toml").read_text()
        buf = io.StringIO()
        with mock.patch.object(mod.tomllib, "loads", counting), \
                contextlib.redirect_stdout(buf):
            code = mod.main(["--root", str(self.root), "--demand", "FWD-030"])
        self.assertEqual(code, 0)
        self.assertEqual(seen.count(target), 1, "FWD-030's findings.toml parsed "
                         f"{seen.count(target)} times")
        self.assertIn("review:", buf.getvalue())
        with mock.patch.object(mod.tomllib, "loads", counting), \
                contextlib.redirect_stdout(io.StringIO()) as js:
            mod.main(["--root", str(self.root), "--demand", "FWD-030",
                      "--format", "json"])
        demand = json.loads(js.getvalue())["demand"]
        self.assertEqual([f["id"] for f in demand["findings"]],
                         [f["id"] for f in json.loads(run(
                             self.root, "--demand", "FWD-030", "--format", "json"
                         ).stdout)["demand"]["findings"]])
        self.assertTrue(demand["findings"])
        # the panel JSON keeps its shape: no findings list on each demand
        self.assertNotIn("findings", {x["id"]: x for x in self.load()["demands"]}["FWD-030"])

    def test_b46_no_nested_and_subscript_in_the_helpers(self):
        src = SCRIPT.read_text()
        start = src.index("# --- the panel")
        helpers = src[src.index("def _promotion("):src.index("def load_demands(")] \
            + src[start:]
        bad = [l.strip() for l in helpers.splitlines()
               if re.search(r"\b(\w+) and \(?\1\[", l)]
        self.assertEqual(bad, [])

    def test_b47_bold_decision_is_not_escaped_and_cuts_at_a_word(self):
        self.write("specs/FWD-060/spec.md", "# FWD-060\n")
        self.write("specs/FWD-060/acceptance.md", "date: 2026-08-09\n")
        self.write("promotions/FWD-060/decision.md",
                   "decision: **promovido condicionado** — o endpoint está no ar\n")
        self.write("specs/FWD-061/spec.md", "# FWD-061\n")
        self.write("specs/FWD-061/acceptance.md", "date: 2026-08-09\n")
        self.write("promotions/FWD-061/decision.md", "decision: **em dois estágios, "
                   "decididos separadamente porque carregam risco diferente.**\n")
        self.write("specs/FWD-062-x/spec.md", "# FWD-062\n\ncycle: C-3 · layer: back\n")
        dm = {l.split(" · ")[0]: l for l in section(panel(self.root), "Demands")}
        self.assertTrue(dm["- FWD-060"].endswith("· promotion **promovido condicionado**"),
                        dm["- FWD-060"])
        self.assertTrue(dm["- FWD-061"].endswith(
            "· promotion **em dois estágios, decididos…**"), dm["- FWD-061"])
        self.assertNotIn("\\*", "\n".join(dm.values()))
        # the cycle table keeps bold unescaped too
        self.write("cycles/C-3/promotion.md", "cycle: C-3\ndecision: **promote**\n\n"
                   "## Criteria\n\n- A1 — ok — met\n")
        cy = section(panel(self.root), "Cycles")
        self.assertIn("| FWD-030 | back | 1 finding recorded, none blocking | **promote** |", cy)
        # plain-text drill-down: same cell
        self.assertIn("promotion **promote**", run(self.root, "--cycle", "C-3").stdout)


if __name__ == "__main__":
    unittest.main()


class TestWaves(unittest.TestCase):
    """Parallel demands are computed from the plan's `files` and `depends
    on`, not negotiated with claim lines on the board."""

    PLAN = """cycle: C-9
state: running

## Demands

| id | layer | depends on | files | what | meets | follows |
|---|---|---|---|---|---|---|
| FWD-1 | back | — | `runtime/verify.py`, tests/test_verify.py | a | A1 | — |
| FWD-2 | back | — | runtime/status.py (+ bin/fde) | b | A1 | — |
| FWD-3 | back | FWD-1 | skills/fde-review/SKILL.md | c | A2 | — |
| FWD-4 | back | — | runtime/ | d | A2 | — |
| FWD-5 | back | — | skills/*/SKILL.md | e | A3 | — |
"""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))
        import status
        self.status = status

    def test_disjoint_files_share_a_wave_and_overlaps_wait(self):
        w = self.status.plan_waves(self.PLAN)
        self.assertEqual(w["waves"], [["FWD-1", "FWD-2", "FWD-5"],
                                      ["FWD-3", "FWD-4"]])
        self.assertEqual(w["why"]["FWD-3"], "after FWD-1")
        self.assertIn("shares runtime/", w["why"]["FWD-4"])
        self.assertEqual(w["unscheduled"], [])

    def test_a_glob_overlaps_a_concrete_path(self):
        self.assertEqual(self.status.shared_files(
            ["skills/*/SKILL.md"], ["skills/fde-review/SKILL.md"]),
            ["skills/*/SKILL.md"])
        self.assertEqual(self.status.shared_files(["runtime/a.py"],
                                                  ["runtime/ab.py"]), [])

    def test_notes_and_backticks_are_not_paths(self):
        self.assertEqual(self.status.demand_files(
            "`runtime/status.py` (+ bin/fde), tests/test_status.py"),
            ["runtime/status.py", "tests/test_status.py"])
        self.assertEqual(self.status.demand_files("—"), [])

    def test_undeclared_files_run_alone_and_warn(self):
        plan = self.PLAN.replace("runtime/status.py (+ bin/fde)", "—")
        w = self.status.plan_waves(plan)
        self.assertTrue(all(len(x) == 1 for x in w["waves"]
                            if "FWD-2" in x))
        self.assertIn("FWD-2: no `files` declared — runs alone", w["warnings"])

    def test_a_dependency_cycle_is_reported_not_looped(self):
        plan = self.PLAN.replace("| FWD-1 | back | — |", "| FWD-1 | back | FWD-3 |")
        w = self.status.plan_waves(plan)
        self.assertEqual(sorted(w["unscheduled"]), ["FWD-1", "FWD-3"])

    def test_cli_prints_the_waves(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "cycles" / "C-9"
            d.mkdir(parents=True)
            (d / "plan.md").write_text(self.PLAN)
            out = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parent.parent
                                     / "runtime" / "status.py"),
                 "--root", tmp, "--waves", "C-9"],
                capture_output=True, text=True)
            self.assertIn("wave 1: FWD-1, FWD-2, FWD-5", out.stdout, out.stderr)
            self.assertIn("wave 2: FWD-3, FWD-4", out.stdout)


class TestParallelCycles(unittest.TestCase):
    """kernel ADR-0024: small cycles run at once when their files are
    disjoint or one depends on the other."""

    def plan(self, cid, state, files, depends=""):
        return (f"cycle: {cid}\nstate: {state}\nobjective: slice {cid}\n"
                + (f"depends: {depends}\n" if depends else "")
                + "\n## Demands\n\n| id | layer | depends on | files | what |\n"
                  "|---|---|---|---|---|\n"
                + "".join(f"| DEM-{cid[2:]}{i} | back | — | {f} | x |\n"
                          for i, f in enumerate(files)))

    def cycles(self, plans):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "runtime"))
        import status
        self.status = status
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for cid, text in plans.items():
            (root / "cycles" / cid).mkdir(parents=True)
            (root / "cycles" / cid / "plan.md").write_text(text)
        return status.load_cycles(root, [])

    def test_disjoint_running_cycles_do_not_conflict(self):
        cs = self.cycles({"C-1": self.plan("C-1", "running", ["api/a.py"]),
                          "C-2": self.plan("C-2", "running", ["web/src/b/"])})
        self.assertEqual(self.status.cycle_conflicts(cs), [])

    def test_overlap_without_depends_is_a_conflict_and_depends_clears_it(self):
        cs = self.cycles({"C-1": self.plan("C-1", "running", ["api/shared.py"]),
                          "C-2": self.plan("C-2", "running", ["api/"])})
        [msg] = self.status.cycle_conflicts(cs)
        self.assertIn("C-1 and C-2 run at once and both touch", msg)
        cs = self.cycles({"C-1": self.plan("C-1", "running", ["api/shared.py"]),
                          "C-2": self.plan("C-2", "running", ["api/"], "C-1")})
        self.assertEqual(self.status.cycle_conflicts(cs), [])

    def test_program_waves_put_the_foundation_first(self):
        cs = self.cycles({
            "C-1": self.plan("C-1", "planned", ["db/migrations/", "api/registry.py"]),
            "C-2": self.plan("C-2", "planned", ["api/familia.py"], "C-1"),
            "C-3": self.plan("C-3", "planned", ["web/src/assinatura/"], "C-1"),
            "C-4": self.plan("C-4", "planned", ["web/src/assinatura/x.tsx"], "C-1"),
        })
        w = self.status.program_waves(cs)
        self.assertEqual(w["waves"], [["C-1"], ["C-2", "C-3"], ["C-4"]])
        self.assertEqual(w["why"]["C-4"], "shares files with C-3")

    def test_the_cli_prints_the_program(self):
        cs = self.cycles({"C-1": self.plan("C-1", "running", ["a/"]),
                          "C-2": self.plan("C-2", "planned", ["b/"], "C-1")})
        text = "\n".join(self.status.show_program(cs))
        self.assertIn("wave 1: C-1 (running)", text)
        self.assertIn("wave 2: C-2 (planned)", text)


class TestOneParserPerFormat(unittest.TestCase):
    """B-57: status.py read spec headers, the Demands table and demand ids
    with its own parsers beside fde_lib's; one definition each now."""

    def test_status_uses_the_kernel_parsers(self):
        src = (Path(__file__).resolve().parent.parent / "runtime" / "status.py").read_text()
        for gone in ("def _spec_fields", "def _is_separator", "DEMAND_ID = re.compile",
                     "SPEC_DIR = re.compile"):
            self.assertNotIn(gone, src)
        for used in ("fde_lib.spec_fields(", "fde_lib.plan_demand_rows(", "fde_lib.demand_id("):
            self.assertIn(used, src)
