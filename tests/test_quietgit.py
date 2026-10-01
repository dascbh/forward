"""tests/quietgit.py turns git's background maintenance off for the suite's
repositories through GIT_CONFIG_*, keeping any keys already set."""
from __future__ import annotations

import subprocess
import tempfile
import unittest

import quietgit


class TestQuietGit(unittest.TestCase):
    def test_keys_are_appended_once_after_existing_ones(self):
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.name",
               "GIT_CONFIG_VALUE_0": "x"}
        quietgit.apply(env)
        quietgit.apply(env)
        self.assertEqual(env["GIT_CONFIG_COUNT"], "3")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "user.name")
        self.assertEqual({env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_KEY_2"]},
                         {"maintenance.auto", "gc.auto"})

    def test_a_spawned_git_sees_maintenance_off(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "-C", d, "init", "-q"], check=True)
            out = subprocess.run(["git", "-C", d, "config", "maintenance.auto"],
                                 capture_output=True, text=True).stdout.strip()
            self.assertEqual(out, "false")


if __name__ == "__main__":
    unittest.main()
