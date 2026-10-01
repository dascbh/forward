"""The ratchet and the bounded loop (owner, 2026-10-01): the budget
identifies and blocks a deviation, the agent corrects it, and nothing
loops — two attempts, then one debt due within two cycle closes, then a
replan for the owner."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

import erosion  # noqa: E402

CONFIG = """[gate]
behavior_paths = ["src/"]
eval_paths = ["tests/"]

[erosion]
window = 50
max_add_delete_ratio = {ratio}
{extra}
[other]
keep = "me"
"""


def git(p, *a):
    return subprocess.run(["git", *a], cwd=p, check=True, capture_output=True, text=True).stdout


class Ratchet(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = p = Path(self.tmp.name)
        for a in (["init", "-q"], ["config", "user.email", "f@t"], ["config", "user.name", "f"]):
            git(p, *a)
        (p / "src").mkdir()
        # history: 40 added, 10 deleted → ratio 4.0
        (p / "src" / "a.py").write_text("".join(f"x{i} = {i}\n" for i in range(20)))
        git(p, "add", "-A"); git(p, "commit", "-qm", "one")
        (p / "src" / "a.py").write_text("".join(f"x{i} = {i}\n" for i in range(10, 40)))
        git(p, "add", "-A"); git(p, "commit", "-qm", "two")

    def config(self, ratio, extra=""):
        (self.p / "fde.config.toml").write_text(CONFIG.format(ratio=ratio, extra=extra))

    def budget(self):
        return tomllib.loads((self.p / "fde.config.toml").read_text())["erosion"]

    def stage(self, text):
        (self.p / "src" / "b.py").write_text(text)
        git(self.p, "add", "src/b.py")

    def test_over_budget_a_commit_that_worsens_is_blocked(self):
        self.config(2.0)
        self.stage("".join(f"y{i} = {i}\n" for i in range(60)))
        ok, msg = erosion.staged_check(self.p)
        self.assertFalse(ok)
        self.assertIn("at most two attempts, then one debt", msg)

    def test_a_consolidation_and_a_small_commit_pass(self):
        self.config(2.0)
        (self.p / "src" / "a.py").write_text("x = 1\n")
        git(self.p, "add", "-A")
        self.assertTrue(erosion.staged_check(self.p)[0])          # deletes: improves
        git(self.p, "reset", "-q"); git(self.p, "checkout", "-q", "--", ".")
        self.stage("z = 1\nw = 2\n")
        self.assertTrue(erosion.staged_check(self.p)[0])          # 2 lines: small

    def test_under_budget_anything_passes(self):
        self.config(50.0)
        self.stage("".join(f"y{i} = {i}\n" for i in range(60)))
        self.assertTrue(erosion.staged_check(self.p)[0])

    def test_close_ratchets_down_and_never_up(self):
        self.config(9.0)
        r = erosion.close_cycle(self.p, "C-1")
        self.assertEqual(self.budget()["max_add_delete_ratio"], 4.2)  # 4.0 + 5%
        self.assertTrue(r["changes"])
        self.config(3.0)                                              # measured 4.0 > 3.0
        erosion.close_cycle(self.p, "C-2")
        self.assertEqual(self.budget()["max_add_delete_ratio"], 3.0)  # never rises
        self.assertEqual(tomllib.loads((self.p / "fde.config.toml").read_text())["other"],
                         {"keep": "me"})

    def test_duplication_and_structure_glide_to_their_targets(self):
        (self.p / "src" / "f.py").write_text("def f(a):\n    return a\n")  # something to measure
        git(self.p, "add", "-A"); git(self.p, "commit", "-qm", "f")
        self.config(9.0, "max_duplication_pct = 13.0\nmax_structural_erosion = 0.9\n")
        erosion.close_cycle(self.p, "C-1")
        b = self.budget()
        self.assertLessEqual(b["max_duplication_pct"], 12.0)        # 10% of the gap to 3.0
        self.assertLessEqual(b["max_structural_erosion"], 0.86)     # 10% of the gap to 0.5
        self.assertGreaterEqual(b["max_structural_erosion"], 0.5)

    def test_one_debt_then_due_then_a_replan(self):
        self.config(2.0)
        self.assertFalse(erosion.gate(self.p)[1] == [])               # breached: 4.0 > 2.0
        ok, _ = erosion.register_debt(self.p, "C-1", "B-9")
        self.assertTrue(ok)
        self.assertEqual(erosion.gate(self.p)[1], [])                 # the debt's room
        ok, msg = erosion.register_debt(self.p, "C-1", "B-10")
        self.assertFalse(ok)
        self.assertIn("second one is refused", msg)
        erosion.close_cycle(self.p, "C-1")
        self.assertEqual(erosion.gate(self.p)[1], [])                 # 1 of 2 closes
        erosion.close_cycle(self.p, "C-2")
        breaches = erosion.gate(self.p)[1]
        self.assertIn("replan for the owner", breaches[0])

    def test_a_paid_debt_is_cleared(self):
        self.config(2.0)
        erosion.register_debt(self.p, "C-1", "B-9")
        (self.p / "src" / "a.py").write_text("x = 1\n")               # consolidate
        git(self.p, "add", "-A"); git(self.p, "commit", "-qm", "consolidate")
        r = erosion.close_cycle(self.p, "C-1")
        self.assertEqual(r["debt"], "paid")
        self.assertFalse(any(k.startswith("debt_") for k in self.budget()))

    def test_no_breach_no_debt(self):
        self.config(50.0)
        ok, msg = erosion.register_debt(self.p, "C-1", "B-9")
        self.assertFalse(ok)
        self.assertIn("nothing to owe", msg)


if __name__ == "__main__":
    unittest.main()
