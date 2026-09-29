"""The interactive backlog panel's writes (runtime/backlog.py, owner
request 2026-09-29). Every action is tested on the Board layer, with no
terminal; the curses loop only calls it."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

from backlog import Board, BoardError, build_rows, detail  # noqa: E402

BACKLOG = """goal: ship it
date: 2026-09-29

# Product backlog

## Now

- B-1 first item (C-1) usage-data
- B-2 second item opinion
  continuation of the second item
- B-3 third item opinion

## Later

- B-7 later item opinion

## Discarded (2026-09-29)

- B-4 old thing — discarded: done
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "backlog.md").write_text(BACKLOG, encoding="utf-8")
        (self.root / "cycles").mkdir()
        self.board = Board(self.root)

    def text(self):
        return (self.root / "backlog.md").read_text(encoding="utf-8")


class TestRead(Fixture):
    def test_items_sections_and_blocks(self):
        b = self.board
        self.assertEqual([it.bid for it in b.items(False)], ["B-1", "B-2", "B-3", "B-7"])
        self.assertEqual([it.bid for it in b.items(True)], ["B-4"])
        two = b.find("B-2")
        self.assertEqual(two.end - two.start, 2)   # continuation line belongs to it
        self.assertFalse(b.table)

    def test_rows_collapse_and_search(self):
        rows = build_rows(self.board, set())
        self.assertEqual([r.key for r in rows if r.kind == "item"],
                         ["B-1", "B-2", "B-3", "B-7"])   # discarded starts closed
        now = next(r for r in rows if r.kind == "section")
        rows = build_rows(self.board, {now.key})
        self.assertNotIn("B-1", [r.key for r in rows])
        rows = build_rows(self.board, set(), "later")
        self.assertEqual([r.key for r in rows if r.kind == "item"], ["B-7"])

    def test_item_detail_shows_the_whole_block(self):
        row = next(r for r in build_rows(self.board, set()) if r.key == "B-2")
        self.assertIn("  continuation of the second item", detail(self.board, row))


class TestGroup(Fixture):
    def test_a_new_draft_cycle_lists_the_items_and_marks_them(self):
        msg = self.board.group(["B-3", "B-1"], "ship the first slice")
        self.assertEqual(msg, "2 item(s) → C-1")
        plan = (self.root / "cycles" / "C-1" / "plan.md").read_text()
        self.assertIn("state: draft\nobjective: ship the first slice", plan)
        self.assertLess(plan.index("- B-1 first item"), plan.index("- B-3 third item"))
        self.assertIn("- B-1 first item (C-1) usage-data → C-1", self.text())
        self.assertEqual(self.board.find("B-1").grouped, "C-1")

    def test_into_an_existing_draft(self):
        self.board.group(["B-1"], "first")
        self.board.group(["B-7"], into="C-1")
        plan = (self.root / "cycles" / "C-1" / "plan.md").read_text()
        self.assertIn("- B-1 first item", plan)
        self.assertIn("- B-7 later item opinion", plan)

    def test_refusals(self):
        with self.assertRaises(BoardError):
            self.board.group([], "x")
        with self.assertRaises(BoardError):
            self.board.group(["B-1"], "")          # a new draft needs an objective
        with self.assertRaises(BoardError):
            self.board.group(["B-4"], "x")         # discarded
        self.board.group(["B-1"], "x")
        with self.assertRaises(BoardError):
            self.board.group(["B-1"], "again")     # already grouped


class TestMerge(Fixture):
    def test_the_first_keeps_its_id_and_the_others_retire(self):
        msg = self.board.merge(["B-3", "B-1"])
        self.assertEqual(msg, "B-3 merged into B-1")
        t = self.text()
        self.assertIn("- B-1 first item (C-1) usage-data [merged B-3: third item opinion]", t)
        self.assertIn("- B-3 third item opinion — discarded: merged into B-1", t)
        self.assertEqual([it.bid for it in self.board.items(True)], ["B-4", "B-3"])

    def test_merging_across_sections_keeps_continuation_lines(self):
        self.board.merge(["B-2", "B-7"])
        t = self.text()
        self.assertIn("B-7 later item opinion — discarded: merged into B-2", t)
        self.assertIn("  continuation of the second item", t)

    def test_needs_two(self):
        with self.assertRaises(BoardError):
            self.board.merge(["B-1"])


class TestDiscardRestoreMoveEdit(Fixture):
    def test_discard_then_restore_round_trips(self):
        self.board.discard("B-2", "not needed")
        self.assertIn("- B-2 second item opinion — discarded: not needed\n"
                      "  continuation of the second item", self.text())
        self.board.restore("B-2")
        self.assertFalse(self.board.find("B-2").discarded)
        self.assertNotIn("discarded: not needed", self.text())

    def test_discard_needs_a_reason_and_creates_the_section(self):
        with self.assertRaises(BoardError):
            self.board.discard("B-1", " ")
        (self.root / "backlog.md").write_text("## Now\n\n- B-1 a\n")
        b = Board(self.root)
        b.discard("B-1", "gone")
        self.assertIn("## Discarded\n\n- B-1 a — discarded: gone", self.text())

    def test_move_swaps_neighbours_in_a_section(self):
        self.board.move("B-3", -1)
        t = self.text()
        self.assertLess(t.index("- B-3"), t.index("- B-2"))
        self.assertLess(t.index("- B-2"), t.index("  continuation"))
        with self.assertRaises(BoardError):
            self.board.move("B-1", -1)

    def test_edit_keeps_id_and_bullet(self):
        self.board.edit("B-3", "third item, clearer usage-data")
        self.assertIn("- B-3 third item, clearer usage-data\n", self.text())

    def test_undo_restores_backlog_and_removes_a_new_plan(self):
        before = self.text()
        self.board.group(["B-1"], "x")
        self.board.undo()
        self.assertEqual(self.text(), before)
        self.assertFalse((self.root / "cycles" / "C-1").exists())
        with self.assertRaises(BoardError):
            self.board.undo()


class TestSafety(Fixture):
    def test_a_table_backlog_is_read_only(self):
        (self.root / "backlog.md").write_text(
            "## Now\n\n| id | item |\n|---|---|\n| B-1 | a |\n")
        b = Board(self.root)
        self.assertTrue(b.table)
        with self.assertRaises(BoardError):
            b.discard("B-1", "x")

    def test_without_a_terminal_it_refuses_and_points_to_status(self):
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "backlog.py"),
                              "--root", str(self.root)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("needs a terminal", out.stderr)

    def test_the_real_backlog_parses_like_status_does(self):
        import status
        b = Board(ROOT)
        ids = [it.bid for it in b.items() if it.bid]
        parsed = [it["id"] for _, items in status.load_backlog(ROOT) or []
                  for it in items if it["id"]]
        self.assertEqual(sorted(ids), sorted(parsed))


if __name__ == "__main__":
    unittest.main()


class TestTerminalSession(Fixture):
    """The curses loop, driven through a pseudo-terminal: select two
    items, group them into a new draft, quit."""

    def test_keys_group_selected_items_into_a_draft(self):
        try:
            import pty
            import select
            import time
            import os
        except ImportError:  # pragma: no cover — no pty on this platform
            self.skipTest("no pty")
        pid, fd = pty.fork()
        if pid == 0:  # pragma: no cover — the child
            os.environ["TERM"] = "xterm-256color"
            os.execvp(sys.executable, [sys.executable,
                                       str(ROOT / "runtime" / "backlog.py"),
                                       "--root", str(self.root)])

        def drain(t):
            end = time.time() + t
            while time.time() < end:
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    try:
                        os.read(fd, 65536)
                    except OSError:
                        return
        drain(1.0)
        # cursor starts on the section; j → B-1; space selects B-1 and moves
        # to B-2; space selects B-2; g + objective + enter; q quits
        for k in ["j", " ", " ", "g", *"from the panel", "\r", "q"]:
            os.write(fd, k.encode())
            drain(0.15)
        drain(0.5)
        _, st = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(st), 0)
        plan = (self.root / "cycles" / "C-1" / "plan.md").read_text()
        self.assertIn("objective: from the panel", plan)
        self.assertIn("- B-1 first item", plan)
        self.assertIn("- B-2 second item", plan)
        self.assertIn("- B-2 second item opinion → C-1", self.text())
