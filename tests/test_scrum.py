"""FWD-002 R1: the cadence gates — active only when [scrum] is enabled."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_project, verify

DATED_GOAL = "---\ngoal: something worth building\ndate: 2026-08-09\n---\n"


class TestScrumOff(unittest.TestCase):
    def test_mode_off_reports_off_and_never_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)  # no [scrum]
            r = verify(p, "--gate", "scrum")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("off", r.stdout)

    def test_mode_off_is_silent_in_a_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p)
            self.assertNotIn("SCRUM", r.stdout)


class TestScrumOn(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, scrum=True)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "scrum")

    def test_backlog_with_dated_product_goal_is_required(self):
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("dated product goal", r.stdout)

        (self.p / "backlog.md").write_text("# Backlog\ngoal: x\n(no date)\n")
        # goal present in head but no date: still red
        r = self.gate()
        self.assertEqual(r.returncode, 1)

        (self.p / "backlog.md").write_text(DATED_GOAL + "# Backlog\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sprint_needs_a_dated_goal(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        s1 = self.p / "sprints" / "S-001"
        s1.mkdir(parents=True)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("S-001", r.stdout)

        (s1 / "goal.md").write_text("goal without a stamp\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1)

        (s1 / "goal.md").write_text(DATED_GOAL)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_no_retro_no_next_sprint(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        for name in ("S-001", "S-002"):
            d = self.p / "sprints" / name
            d.mkdir(parents=True)
            (d / "goal.md").write_text(DATED_GOAL)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no retro, no next sprint", r.stdout)

        (self.p / "sprints" / "S-001" / "retro.md").write_text("# Retro\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)  # latest may stay open


if __name__ == "__main__":
    unittest.main()
