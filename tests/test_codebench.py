"""The code-quality view over history (runtime/codebench.py, owner request
2026-09-29): snapshots, complexity, erosion, clones, hotspots."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import codebench  # noqa: E402

SIMPLE = "def ok(x):\n    return x + 1\n"
def handle(n: int) -> str:
    return ("def handle(a, b):\n" + "".join(
        f"    if a == {i} and b:\n        b += {i}\n" for i in range(n))
        + "    return b\n")


GROWN = handle(8)


class TestBench(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        r = self.root = Path(self.tmp.name)

        def git(*a):
            subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)
        self.git = git
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        (r / "app").mkdir()
        (r / "tests").mkdir()
        (r / "fde.config.toml").write_text(
            '[gate]\nbehavior_paths = ["app/"]\neval_paths = ["tests/"]\n')
        (r / "app" / "core.py").write_text(SIMPLE + "\n" + handle(3))
        (r / "tests" / "test_core.py").write_text(GROWN)
        git("add", "-A")
        git("commit", "-q", "-m", "install")
        (r / "app" / "core.py").write_text(SIMPLE + "\n" + GROWN)
        for i in range(3):   # a module copied into three packages
            (r / "app" / f"pkg{i}").mkdir()
            (r / "app" / f"pkg{i}" / "shared.py").write_text(SIMPLE)
        git("add", "-A")
        git("commit", "-q", "-m", "grow")

    def test_snapshots_track_growth_and_copies_once(self):
        data = codebench.bench(self.root, points=2)
        first, head = data["snapshots"][0], data["snapshots"][-1]
        self.assertEqual(first["label"], "FORWARD installed")
        self.assertEqual(head["label"], "HEAD")
        self.assertEqual(first["complex"], 0)
        self.assertEqual(head["complex"], 1)
        self.assertEqual(head["copy_groups"], 1)
        self.assertEqual(head["files"], 2)          # core + one shared copy
        self.assertGreater(head["structural_erosion"], first["structural_erosion"])

    def test_tests_are_out_and_hotspots_show_growth(self):
        data = codebench.bench(self.root, points=2)
        hot = data["hotspots"][0]
        self.assertEqual((hot["path"], hot["function"]), ("app/core.py", "handle"))
        self.assertEqual((hot["cc_then"], hot["cc"]), (7, 17))
        self.assertNotIn("tests/", json.dumps(data["hotspots"]))

    def test_text_and_json_render(self):
        text = "\n".join(codebench.render(codebench.bench(self.root, points=2)))
        self.assertIn("CC>10", text)
        self.assertIn("← FORWARD installed", text)
        self.assertIn("CC 7 → 17", text)
        out = subprocess.run([sys.executable, str(ROOT / "runtime" / "codebench.py"),
                              "--root", str(self.root), "--format", "json"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("snapshots", json.loads(out.stdout))

    def test_skill_and_readme_point_to_it(self):
        skill = (ROOT / "skills/fde-codebench/SKILL.md").read_text()
        self.assertIn("It reports; it never gates.", skill)
        self.assertIn("`fde-codebench`", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
