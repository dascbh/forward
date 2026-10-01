"""Backlog, suite and gate-reach hygiene (owner, 2026-10-01): a client's
backlog held 79 lines from one cycle, mostly copied review findings; its
main carried chronic reds behind a list of "accepted" ones; and scripts
outside the gate's roots changed behavior that I1 read as none."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "runtime"))

from support import commit_all, make_project  # noqa: E402
import erosion  # noqa: E402

PLAN = "cycle: C-1\nstate: running\ndate: 2026-10-01\nsigned-off: 2026-10-01\n"


class Hygiene(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = make_project(self.tmp.name)
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN)
        commit_all(self.p, "init")

    def gate(self, name):
        r = subprocess.run([sys.executable, "bin/fde/verify.py", "--gate", name, "--format", "json"],
                           cwd=self.p, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)["gates"][0]

    def test_more_than_five_lines_from_one_cycle_warns(self):
        lines = "".join(f"- B-{i} (C-1) finding F{i} of a review. Evidence: usage-data\n" for i in range(1, 7))
        (self.p / "backlog.md").write_text("# Backlog\n\n" + lines + "\n## Discarded\n\n- B-99 (C-1) x\n")
        code, g = self.gate("backlog-cycle")
        self.assertEqual(code, 0)
        self.assertTrue(g.get("warning"))
        self.assertIn("C-1 (6)", g["detail"])
        (self.p / "backlog.md").write_text("# Backlog\n\n" + "".join(lines.splitlines(True)[:5]))
        self.assertFalse(self.gate("backlog-cycle")[1].get("warning"))

    def test_a_failing_recorded_suite_warns(self):
        runs = self.p / ".fde" / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "t.json").write_text(json.dumps({"suite": {"exit_code": 2, "summary": "collection error"}}))
        code, g = self.gate("suite")
        self.assertEqual(code, 0)
        self.assertTrue(g.get("warning"))
        self.assertIn("exits 2", g["detail"])

    def test_a_red_suite_record_names_its_failing_tests(self):
        sys.path.insert(0, str(ROOT / "runtime"))
        import verify
        cmd = (f"{sys.executable} -c \"print('ok a'); print('FAILED tests/test_x.py::test_b - "
               f"AssertionError'); print('1 failed'); raise SystemExit(1)\"")
        r = verify.run_suite(self.p, cmd)
        self.assertEqual(r["exit_code"], 1)
        self.assertIn("FAILED tests/test_x.py::test_b - AssertionError", r["failures"])
        self.assertEqual(verify.run_suite(self.p, f"{sys.executable} -c pass")["failures"], [])

    def test_source_outside_the_roots_warns_vendored_does_not(self):
        (self.p / "scripts").mkdir()
        (self.p / "scripts" / "reconcile.py").write_text("x = 1\n")
        (self.p / "lib" / "layers" / "pkg").mkdir(parents=True)
        (self.p / "lib" / "layers" / "pkg" / "v.py").write_text("y = 1\n")
        commit_all(self.p, "scripts")
        code, g = self.gate("scope")
        self.assertEqual(code, 0)
        self.assertIn("scripts/ (1)", g["detail"])
        self.assertNotIn("lib/", g["detail"])

    def test_quarantine_is_counted_and_ratcheted(self):
        (self.p / "tests").mkdir(exist_ok=True)
        (self.p / "tests" / "test_x.py").write_text(
            "import unittest\n\n@unittest.skip('quarantine B-7: red on main')\n"
            "def test_a():\n    pass\n")
        with open(self.p / "fde.config.toml", "a") as f:
            f.write("\n[erosion]\nwindow = 50\n")
        commit_all(self.p, "q")
        self.assertEqual(erosion.quarantine_count(self.p), 1)
        erosion.close_cycle(self.p, "C-1")
        self.assertIn("max_quarantined = 1", (self.p / "fde.config.toml").read_text())
        (self.p / "tests" / "test_y.py").write_text("# quarantine B-8\n")
        commit_all(self.p, "another parked red")
        self.assertTrue(any("quarantined tests 2 > 1" in b for b in erosion.gate(self.p)[1]))


if __name__ == "__main__":
    unittest.main()
