"""FWD-024: the cycle and backlog view — a read-only report, never a gate
(ADR-0018). Every case runs the real script as a subprocess against a
temporary tree, the way the owner runs it."""
from __future__ import annotations

import json
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
        self.assertIn("2 cycles open: C-1, C-2", r.stdout)

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
        self.assertIn("(before any section)", out)


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
        self.assertIn("2 cycles open: C-4, C-5", out)

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
        self.assertEqual(set(data), {"warnings", "next", "cycles", "backlog"})
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
        self.assertEqual(set(self.load("--cycles")), {"warnings", "next", "cycles"})
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


if __name__ == "__main__":
    unittest.main()
