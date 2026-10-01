"""What the kernel prescribes never asks the owner to leave auto mode
(owner, 2026-10-01): the settings merge and the worktree cleanup run as
fixed kernel scripts, never as an agent's own edit of its permissions or
an `rm -rf`, which auto mode blocks."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import quietgit  # noqa: E402,F401
import settings_merge  # noqa: E402
import worktrees  # noqa: E402


def git(p, *a):
    return subprocess.run(["git", *a], cwd=p, check=True, capture_output=True, text=True).stdout


class SettingsMerge(unittest.TestCase):
    def test_adds_the_kernel_part_keeps_the_users_and_is_idempotent(self):
        before = {"permissions": {"allow": ["Bash(ls)"], "ask": ["Bash(rm *)"]}, "x": 1}
        new, added = settings_merge.merged(before, True)
        self.assertIn("Bash(ls)", new["permissions"]["allow"])
        self.assertEqual(new["permissions"]["ask"], ["Bash(rm *)"])
        self.assertEqual(new["x"], 1)
        self.assertEqual(new["worktree"]["baseRef"], "head")
        self.assertIn("mcp__claude-in-chrome", new["permissions"]["allow"])
        self.assertTrue(added)
        self.assertEqual(settings_merge.merged(new, True)[1], [])  # nothing to write again

    def test_closed_permissions_add_no_tool(self):
        new, added = settings_merge.merged({}, False)
        self.assertNotIn("permissions", new)
        self.assertNotIn("allow Bash", added)

    def test_writes_nothing_when_already_there(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            git(p, "init", "-q")
            (p / ".claude").mkdir()
            full, _ = settings_merge.merged({}, True)
            (p / ".claude" / "settings.json").write_text(json.dumps(full))
            before = (p / ".claude" / "settings.json").stat().st_mtime_ns
            self.assertEqual(settings_merge.main(["--root", str(p)]), 0)
            self.assertEqual((p / ".claude" / "settings.json").stat().st_mtime_ns, before)


class Worktrees(unittest.TestCase):
    def test_only_merged_and_clean_worktrees_go(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "repo"
            p.mkdir()
            for a in (["init", "-q", "-b", "main"], ["config", "user.email", "f@t"], ["config", "user.name", "f"]):
                git(p, *a)
            (p / "a.txt").write_text("a\n")
            git(p, "add", "-A"); git(p, "commit", "-qm", "a")
            merged, dirty, ahead = (Path(d) / n for n in ("merged", "dirty", "ahead"))
            git(p, "worktree", "add", "-q", "-b", "w1", str(merged))
            git(p, "worktree", "add", "-q", "-b", "w2", str(dirty))
            (dirty / "wip.txt").write_text("work\n")
            git(p, "worktree", "add", "-q", "-b", "w3", str(ahead))
            (ahead / "b.txt").write_text("b\n")
            git(ahead, "add", "-A"); git(ahead, "commit", "-qm", "b")
            worktrees.main(["--root", str(p), "--prune-merged"])
            self.assertFalse(merged.exists())
            self.assertTrue(dirty.exists())
            self.assertTrue(ahead.exists())
            self.assertNotIn("w1", git(p, "branch"))

    def test_the_skills_never_prescribe_rm_rf_or_a_settings_edit(self):
        sync = " ".join((ROOT / "skills/fde-sync/SKILL.md").read_text().split())
        self.assertIn("python3 bin/fde/settings_merge.py", sync)
        self.assertIn("python3 bin/fde/worktrees.py --prune-merged", sync)
        self.assertIn("Never ask the owner to leave auto mode for a step this skill prescribes", sync)
        self.assertNotIn("they should leave auto mode and re-run fde-sync", sync)
        self.assertIn("worktrees.py --prune-merged", (ROOT / "skills/fde-review/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
