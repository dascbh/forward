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
import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

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
        self.assertIn("✓ done   ▸ now   · to come", out)
        self.assertIn("cycle: plan ✓ → sign-off ✓ → BUILD ▸ → cycle review → deploy", out)
        self.assertIn("1 of 4 merged", out)
        self.assertIn("merged", self.line(out, "DEM-1"))
        self.assertIn(" a ", self.line(out, "DEM-1"), "the demand's name from the plan")
        self.assertIn("▸ DEM-2", out)
        self.assertIn("building for", self.line(out, "DEM-2"))
        self.assertIn("BUILD ▸ → suite → review → merge", out)
        self.assertIn("waits for DEM-2", self.line(out, "DEM-3"))
        self.assertIn("not started", self.line(out, "DEM-4"))
        self.assertIn("next: DEM-2 merges → DEM-4 starts → DEM-3 starts → cycle review → deploy",
                      out)

    def test_a_demand_building_in_its_own_worktree_shows_before_it_merges(self):
        wt = Path(self.tmp.name) / "wt"
        git(self.root, "worktree", "add", "-q", "-b", "dem4", str(wt))
        with open(wt / "cycles" / "C-1" / "board.md", "a") as f:
            f.write("- 2026-10-01 DEM-4 claim src/d.py\n"
                    "- 2026-10-01 DEM-4 done 999 — --record-suite: suite exit 0\n")
        git(wt, "commit", "-qam", "dem-4 work")
        self.assertIn("in review for", self.line(self.progress(), "DEM-4"))

    def test_a_worktree_with_no_new_board_line_is_not_blamed(self):
        import status
        for i in range(3):
            git(self.root, "worktree", "add", "-q", "-b", f"idle{i}",
                str(Path(self.tmp.name) / f"idle{i}"))
        calls = []
        real = status._blame_times
        status._blame_times = lambda wt, rel: calls.append(wt) or real(wt, rel)
        try:
            cycle = [c for c in status.load_cycles(self.root, []) if c.id == "C-1"][0]
            events = status.board_events(self.root, cycle)
        finally:
            status._blame_times = real
        self.assertEqual(len(calls), 1, "only the board with lines not seen yet is blamed")
        self.assertTrue(any(e["who"] == "DEM-2" for e in events))

    def test_the_panel_carries_the_tree_under_the_running_cycle(self):
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "status.py"),
                              "--root", str(self.root), "--panel"],
                             capture_output=True, text=True).stdout
        head = out.split("## Backlog")[0]
        self.assertIn("- running: C-1", head)
        self.assertIn("cycle: plan ✓ → sign-off ✓ → BUILD ▸", head)
        self.assertIn("DEM-2", head)


class TestMergeFromGit(unittest.TestCase):
    """Whether a demand is on main is read from git, not from the board's
    wording; a board line by another author never marks it merged."""

    setUp = TestProgress.setUp
    progress = TestProgress.progress
    line = TestProgress.line

    def commit(self, rel, msg, merge_of=None):
        f = self.root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(msg + "\n")
        if merge_of:
            git(self.root, "checkout", "-q", "-b", merge_of)
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "-m", f"{merge_of}: work")
            git(self.root, "checkout", "-q", "main")
            git(self.root, "merge", "-q", "--no-ff", merge_of, "-m", msg)
        else:
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "-m", msg)

    def test_a_merge_commit_that_names_the_demand_marks_it(self):
        self.commit("src/b.py", "Merge DEM-2 (b, reviewed)", merge_of="dem-2")
        self.assertIn("merged", self.line(self.progress(), "DEM-2"))

    def test_its_own_commit_on_main_marks_it_a_board_commit_does_not(self):
        self.commit("cycles/C-1/notes.md", "DEM-4: board note")
        self.assertNotIn("merged", self.line(self.progress(), "DEM-4"))
        self.commit("src/d.py", "DEM-4: the change, rebased onto main")
        self.assertIn("merged", self.line(self.progress(), "DEM-4"))

    def test_another_authors_board_line_naming_it_never_marks_it(self):
        with open(self.root / "cycles" / "C-1" / "board.md", "a") as f:
            f.write("- 2026-10-01 C-1 decided merges of DEM-1; DEM-4 starts next\n")
        git(self.root, "commit", "-qam", "board")
        self.assertNotIn("merged", self.line(self.progress(), "DEM-4"))

    def test_a_cycle_waits_until_the_one_it_depends_on_has_merged(self):
        d = self.root / "cycles" / "C-2"
        d.mkdir()
        (d / "plan.md").write_text(PLAN.replace("cycle: C-1", "cycle: C-2").replace(
            "signed-off:", "depends: C-1\nsigned-off:").replace("DEM-", "NEW-"))
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "c-2")
        out = self.progress()
        self.assertIn("waits for C-1", out)
        self.assertIn("next: C-1 merges", out)
        for i in (2, 3, 4):
            self.commit(f"src/x{i}.py", f"DEM-{i}: done on main")
        self.assertNotIn("waits for C-1", self.progress())


class TestProgressTab(unittest.TestCase):
    """The panel's progress tab: fold, unfold, open a demand, quit."""

    setUp = TestProgress.setUp

    def tab(self):
        import backlog
        return backlog.Progress(self.root)

    def test_the_first_cycle_opens_and_the_keys_navigate(self):
        p = self.tab()
        texts = [r.text for r in p.rows()]
        self.assertTrue(texts[0].startswith("▼ C-1"))
        self.assertTrue(any("DEM-2" in t for t in texts))
        p.handle("h")
        self.assertTrue(p.rows()[0].text.startswith("▶ C-1"))
        self.assertIn("1 of 4 merged", p.rows()[0].text, "a folded cycle shows its summary")
        p.handle("\n")
        self.assertTrue(p.rows()[0].text.startswith("▼ C-1"))

    def test_a_demand_opens_its_board_timeline(self):
        p = self.tab()
        rows = p.rows()
        p.cur = next(i for i, r in enumerate(rows) if r.kind == "demand" and r.key == "DEM-1")
        p.handle("d")
        self.assertIsNotNone(p.view)
        joined = "\n".join(p.view)
        self.assertIn("DEM-1 · a", joined)
        self.assertIn("claim src/a.py", joined)
        self.assertIn("decided merged def456", joined)
        p.handle("q")
        self.assertIsNone(p.view, "q closes the detail first")
        self.assertFalse(p.handle("q"), "then q quits")

    def test_it_reloads_on_its_own(self):
        import backlog
        clock = [1000.0]
        p = backlog.Progress(self.root, clock=lambda: clock[0])
        self.assertFalse(p.maybe_refresh())
        clock[0] += backlog.Progress.REFRESH
        self.assertTrue(p.maybe_refresh())


class TestNaming(ProseTestCase):
    def test_agents_are_named_by_cycle_demand_and_phase(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("agent names: `C-<n> › <id> › <phase>`",
                          (ROOT / rel).read_text(encoding="utf-8"), rel)
        self.assertIn("## Progress — what each agent is doing, and for how long",
                      (ROOT / "skills" / "fde-status" / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
