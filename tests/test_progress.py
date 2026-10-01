"""status.py --progress (owner request 2026-10-01): running cycles as a
tree — cycle phases, each demand's current phase, its elapsed time and
what comes next — read from the board in every worktree."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

from prose import ProseTestCase  # noqa: E402

PLAN = """cycle: C-1
state: running
date: 2026-10-01
objective: the owner sees what each agent is doing
signed-off: 2026-10-01 (owner: "aprovado")

## Demands

| id | layer | depends on | files | what | meets | follows |
|---|---|---|---|---|---|---|
| DEM-1 | back | — | src/a.py | a | A1 | — |
| DEM-2 | back | — | src/b.py | b | A1 | — |
| DEM-3 | back | DEM-2 | src/c.py | c | A1 | — |
| DEM-4 | back | — | src/d.py | d | A1 | — |
"""
BOARD = """cycle: C-1

- 2026-10-01 DEM-1 claim src/a.py
- 2026-10-01 DEM-1 done abc123 — `python3 bin/fde/verify.py --all --record-suite`: suite exit 0
- 2026-10-01 DEM-1 decided triage F1 real/patch
- 2026-10-01 DEM-1 decided merged def456; review `reviews/DEM-1/findings.toml`
- 2026-10-01 DEM-2 claim src/b.py
"""


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


class TestProgress(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        (self.root / "cycles" / "C-1").mkdir(parents=True)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        (self.root / "cycles" / "C-1" / "plan.md").write_text(PLAN)
        (self.root / "cycles" / "C-1" / "board.md").write_text(BOARD)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "c-1")

    def progress(self):
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "status.py"),
                              "--root", str(self.root), "--progress"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def line(self, out, did):
        return next(l for l in out.splitlines() if f" {did} " in l + " ")

    def test_each_demand_shows_its_phase_and_what_comes_next(self):
        out = self.progress()
        self.assertIn("plan ✓  sign-off ✓  build ▸  cycle review ·  deploy ·", out)
        self.assertIn("✓ merged", self.line(out, "DEM-1"))
        dem2 = self.line(out, "DEM-2")
        self.assertIn("▸ building", dem2)
        self.assertIn("(build ▸ · suite · · review · · merge ·)", dem2)
        self.assertIn("· waits DEM-2", self.line(out, "DEM-3"))
        self.assertIn("· not started", self.line(out, "DEM-4"))

    def test_a_demand_building_in_its_own_worktree_shows_before_it_merges(self):
        wt = Path(self.tmp.name) / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "dem4", str(wt))
        with open(wt / "cycles" / "C-1" / "board.md", "a") as f:
            f.write("- 2026-10-01 DEM-4 claim src/d.py\n"
                    "- 2026-10-01 DEM-4 done 999 — --record-suite: suite exit 0\n")
        git(wt, "commit", "-qam", "dem-4 work")
        self.assertIn("▸ in review", self.line(self.progress(), "DEM-4"))

    def test_the_panel_carries_the_tree_under_the_running_cycle(self):
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "status.py"),
                              "--root", str(self.root), "--panel"],
                             capture_output=True, text=True).stdout
        head = out.split("## Backlog")[0]
        self.assertIn("- running: C-1", head)
        self.assertIn("    plan ✓  sign-off ✓  build ▸", head)
        self.assertIn("DEM-2", head)


class TestNaming(ProseTestCase):
    def test_agents_are_named_by_cycle_demand_and_phase(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("agent names: `C-<n> › <id> › <phase>`",
                          (ROOT / rel).read_text(encoding="utf-8"), rel)
        self.assertIn("## Progress — what each agent is doing, and for how long",
                      (ROOT / "skills" / "fde-status" / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
