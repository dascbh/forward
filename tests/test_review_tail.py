"""The review tail (owner request 2026-10-01): one round per demand, only
blocker/high fixed in the demand, attack ordered by the plan's risks, and
an owner question that pauses only its demand. REVIEW-ROUNDS warns."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import quietgit  # noqa: E402,F401
from prose import ProseTestCase  # noqa: E402
from support import commit_all, make_project  # noqa: E402

PLAN = """cycle: C-1
state: {state}
date: 2026-10-01
signed-off: 2026-10-01

## Demands

| id | layer | depends on | files | what | meets | follows |
|---|---|---|---|---|---|---|
| DEM-1 | back | — | src/a.py | a | A1 | — |
"""


class TestReviewRounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = make_project(self.tmp.name)
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        (self.p / "reviews" / "DEM-1").mkdir(parents=True)
        commit_all(self.p, "init")

    def write(self, state, ids):
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN.format(state=state))
        (self.p / "reviews" / "DEM-1" / "findings.toml").write_text(
            "".join(f'[[findings]]\nid = "{i}"\nseverity = "low"\n\n' for i in ids))

    def gate(self):
        r = subprocess.run([sys.executable, "bin/fde/verify.py", "--gate", "review-rounds",
                            "--format", "json"], cwd=self.p, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)["gates"][0]

    def test_a_second_round_on_a_running_demand_warns_and_never_fails(self):
        self.write("running", ["R1-01", "R2-01", "R3-01"])
        code, g = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(g.get("warning"))
        self.assertIn("DEM-1 (3 rounds)", g["detail"])

    def test_one_round_and_history_are_quiet(self):
        self.write("running", ["R1-01", "R1-02"])
        self.assertFalse(self.gate()[1].get("warning"))
        self.write("closed", ["R1-01", "R2-01"])
        self.assertFalse(self.gate()[1].get("warning"), "an ended cycle is history")


class TestRules(ProseTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_the_rules_are_stated(self):
        review = self.read("skills/fde-review/SKILL.md")
        self.assertIn("no second or third round is ever\nlaunched on a demand", review)
        self.assertIn("A medium or low finding is never\n     patched in the demand", review)
        self.assertIn("attacks first what the plan already names as risk", review)
        self.assertIn("never\n   by a demand review", review)
        self.assertIn("never a\n     blocking question box while other agents run", review)
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Owner questions pause one demand, never the session.", self.read(rel))


if __name__ == "__main__":
    unittest.main()
