"""FM-1/R1: the PreToolUse guard — allowlist role scopes, gate paths,
absolute paths.

Honesty note (finding F3): payloads here fabricate agent_name to exercise
the role branch as a unit. The real hook payload carries a role identity
only where the harness provides one; the always-on protection is the
no-suite I1 branch, and role scopes are charged at commit by I2/I3.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import guard, make_project


class TestGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name,
                              behavior='["backend/app/", "src/", "SETUP.md"]')

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, rel, agent=""):
        return {"tool_input": {"file_path": str(Path(self.p) / rel)},
                "agent_name": agent}

    # -- judging roles are ALLOWLISTED to their write scope ---------------
    def test_adversarial_writes_only_in_reviews(self):
        for target in ("src/x.py", "backend/app/x.py",
                       "promotions/D-1/decision.md", "docs/adr/0001.md",
                       "bin/fde/verify.py", ".fde/spec/invariants.toml"):
            r = guard(self.p, self.payload(target, "fde-adversarial"))
            self.assertEqual(r.returncode, 2, target)
            self.assertIn("writes only in", r.stderr)
        r = guard(self.p, self.payload("reviews/D-1/findings.toml",
                                       "fde-adversarial"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_promotion_writes_only_in_promotions(self):
        r = guard(self.p, self.payload("reviews/D-1/findings.toml",
                                       "fde-promotion"))
        self.assertEqual(r.returncode, 2)
        r = guard(self.p, self.payload("promotions/D-1/decision.md",
                                       "fde-promotion"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_implementation_cannot_rewrite_its_own_judges(self):
        for target in ("specs/D-1/acceptance.md", "reviews/D-1/findings.toml"):
            r = guard(self.p, self.payload(target, "fde-implementation"))
            self.assertEqual(r.returncode, 2, target)

    # -- the always-on branch: no suite, no behavior write ----------------
    def test_behavior_write_blocked_while_no_suite_exists(self):
        (self.p / "evals").mkdir()
        (self.p / "evals" / ".gitkeep").touch()  # structure, not a suite
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("I1", r.stderr)

    def test_file_entry_behavior_paths_are_guarded_too(self):
        r = guard(self.p, self.payload("SETUP.md", "fde-implementation"))
        self.assertEqual(r.returncode, 2)  # no suite yet

    def test_behavior_write_allowed_once_suite_exists(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "test_x.py").write_text("assert True\n")
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 0, r.stderr)

    # -- boundaries -------------------------------------------------------
    def test_paths_outside_the_project_are_not_its_jurisdiction(self):
        r = guard(self.p, {"tool_input": {"file_path": "/etc/hosts"},
                           "agent_name": "fde-adversarial"})
        self.assertEqual(r.returncode, 0)

    def test_unreadable_payload_never_blocks_by_accident(self):
        r = guard(self.p, {})
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
