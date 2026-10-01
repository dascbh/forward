"""Promotion decides; it does not hand the owner conditions (owner,
2026-10-01). A running cycle's decision other than promote,
promote-with-limits or hold warns and never fails."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from support import commit_all, make_project  # noqa: E402

PLAN = "cycle: C-1\nstate: {state}\ndate: 2026-10-01\nsigned-off: 2026-10-01\n"
PROMO = "cycle: C-1\ndate: 2026-10-01\ndecision: {decision}\ndocs: none\n\n## Evidence\n"


class TestPromotionGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = make_project(self.tmp.name)
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        commit_all(self.p, "init")

    def gate(self, state, decision):
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN.format(state=state))
        (self.p / "cycles" / "C-1" / "promotion.md").write_text(PROMO.format(decision=decision))
        r = subprocess.run([sys.executable, "bin/fde/verify.py", "--gate", "promotion",
                            "--format", "json"], cwd=self.p, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)["gates"][0]

    def test_conditions_for_the_owner_warn_and_never_fail(self):
        code, g = self.gate("running", "promote_with_conditions")
        self.assertEqual(code, 0)
        self.assertTrue(g.get("warning"))
        self.assertIn("C-1 (promote_with_conditions)", g["detail"])
        self.assertIn("backlog", g["detail"])

    def test_the_three_decisions_pass_with_or_without_a_tail(self):
        for decision in ("promote", "hold", "promote-with-limits — L1 alarm checked",
                         "**promote**", "Promote (all met)"):
            code, g = self.gate("running", decision)
            self.assertEqual(code, 0)
            self.assertFalse(g.get("warning"), (decision, g))

    def test_ended_cycles_are_history(self):
        code, g = self.gate("closed", "promote_with_conditions")
        self.assertFalse(g.get("warning"), g)

    def test_the_promotion_role_says_no_conditions(self):
        text = (ROOT / "agents" / "fde-promotion.md").read_text()
        self.assertIn("never a\n  promotion with conditions for the owner", text)
        self.assertIn("promote | promote-with-limits | hold",
                      (ROOT / "templates" / "cycle" / "promotion.md").read_text())


if __name__ == "__main__":
    unittest.main()
