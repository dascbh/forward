"""FM-1/R1: the PreToolUse guard — role scopes, gate paths, absolute paths."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import guard, make_project


class TestGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, behavior='["backend/app/", "src/"]')

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, rel, agent=""):
        return {"tool_input": {"file_path": str(Path(self.p) / rel)},
                "agent_name": agent}

    def test_adversarial_cannot_write_code_default_paths(self):
        r = guard(self.p, self.payload("src/x.py", "fde-adversarial"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not write", r.stderr)

    def test_code_denied_roles_blocked_on_configured_behavior_roots(self):
        r = guard(self.p, self.payload("backend/app/x.py", "fde-adversarial"))
        self.assertEqual(r.returncode, 2)

    def test_behavior_write_blocked_while_no_suite_exists(self):
        (self.p / "evals").mkdir()
        (self.p / "evals" / ".gitkeep").touch()  # structure, not a suite
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("I1", r.stderr)

    def test_behavior_write_allowed_once_suite_exists(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "test_x.py").write_text("assert True\n")
        r = guard(self.p, self.payload("backend/app/x.py", "fde-implementation"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_paths_outside_the_project_are_not_its_jurisdiction(self):
        r = guard(self.p, {"tool_input": {"file_path": "/etc/hosts"},
                           "agent_name": "fde-adversarial"})
        self.assertEqual(r.returncode, 0)

    def test_unreadable_payload_never_blocks_by_accident(self):
        r = guard(self.p, {})
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
