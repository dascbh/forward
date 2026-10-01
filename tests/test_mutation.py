"""The suite's effectiveness by sampled mutation (runtime/mutation.py,
owner request 2026-09-30): what the tests would catch, not what they cost."""
from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import mutation  # noqa: E402

# `ge` is tested on both sides; `positive` only where `>` and `>=` agree,
# so flipping its comparison survives
CALC = ("def ge(a, b):\n    return a >= b\n\n\n"
        "def positive(x):\n    return x > 0\n")
TESTS = ("import unittest\nfrom calc import ge, positive\n\n\n"
         "class T(unittest.TestCase):\n"
         "    def test_ge(self):\n"
         "        self.assertTrue(ge(2, 2))\n        self.assertFalse(ge(1, 2))\n\n"
         "    def test_positive(self):\n        self.assertTrue(positive(5))\n")


def project(dir, test_command='python3 -m unittest', tests=TESTS) -> Path:
    p = Path(dir)
    (p / "src").mkdir()
    (p / "src" / "calc.py").write_text(CALC)
    (p / "src" / "test_calc.py").write_text(tests)
    (p / "fde.config.toml").write_text(
        f'[gate]\nbehavior_paths = ["src/"]\neval_paths = ["src/test_calc.py"]\n'
        f'[stack]\ntest_command = "{test_command}"\n')
    for args in (["init", "-q"], ["config", "user.email", "f@t"], ["config", "user.name", "f"],
                 ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run(["git", *args], cwd=p, check=True, capture_output=True)
    return p


class Sampling(unittest.TestCase):
    def test_kills_what_the_tests_catch_and_names_the_survivor(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d)
            r = mutation.sample(p, n=50)
            [row] = r["modules"]
            self.assertEqual(row["module"], "src/calc.py")
            self.assertIsNone(row["skipped"])
            self.assertEqual(row["mutants"], len(mutation.points(ast.parse(CALC))))
            self.assertGreater(row["killed"], 0)
            self.assertIn({"line": 6, "kind": "compare", "code": "return x > 0"},
                          row["survivors"])
            self.assertNotIn(2, [s["line"] for s in row["survivors"]])
            self.assertIsNotNone(row["baseline_seconds"])
            self.assertEqual(r["score"], round(100 * row["killed"] / row["mutants"]))

    def test_the_working_copy_and_worktrees_are_left_as_they_were(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d)
            mutation.sample(p, n=50)
            self.assertEqual((p / "src" / "calc.py").read_text(), CALC)
            out = subprocess.run(["git", "worktree", "list"], cwd=p,
                                 capture_output=True, text=True).stdout
            self.assertEqual(len(out.strip().splitlines()), 1)
            status = subprocess.run(["git", "status", "--porcelain"], cwd=p,
                                    capture_output=True, text=True).stdout
            self.assertEqual(status, "")

    def test_a_failing_baseline_is_skipped_never_scored(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d, tests=TESTS.replace("assertTrue(positive(5))",
                                               "assertTrue(positive(-5))"))
            r = mutation.sample(p, n=5)
            self.assertEqual(r["modules"][0]["skipped"], "its tests fail unchanged")
            self.assertEqual(r["modules"][0]["mutants"], 0)
            self.assertIsNone(r["score"])

    def test_an_unknown_runner_asks_for_a_template_and_a_template_runs(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d, test_command="make test")
            r = mutation.sample(p, n=3)
            self.assertIn("--test-cmd", r["modules"][0]["skipped"])
            r = mutation.sample(p, n=3, template=f"cd src && {sys.executable} "
                                "-m unittest test_calc")
            self.assertIsNone(r["modules"][0]["skipped"])
            self.assertEqual(r["modules"][0]["mutants"], 3)

    def test_the_same_seed_draws_the_same_mutants(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d)
            a, b = mutation.sample(p, n=3, seed=4), mutation.sample(p, n=3, seed=4)
            self.assertEqual(a["modules"][0]["survivors"], b["modules"][0]["survivors"])
            self.assertEqual(a["killed"], b["killed"])

    def test_suite_size_counts_tests_against_production(self):
        with tempfile.TemporaryDirectory() as d:
            p = project(d)
            r = mutation.suite_size(p)
            self.assertEqual(r["production_loc"], 4)
            self.assertEqual(r["test_loc"], 8)


class Mutants(unittest.TestCase):
    def test_each_kind_changes_the_program(self):
        src = "def f(a, b):\n    if a < 1 and b:\n        return True\n    return a in b\n"
        kinds = set()
        for i, (kind, _) in enumerate(mutation.points(ast.parse(src))):
            m = mutation.mutant(src, i)
            self.assertIsNotNone(m)
            self.assertNotEqual(ast.dump(ast.parse(m[1])), ast.dump(ast.parse(src)))
            kinds.add(kind)
        self.assertEqual(kinds, {"compare", "and/or", "if", "integer", "return"})


class SuiteDuration(unittest.TestCase):
    def test_the_recorded_suite_carries_its_seconds(self):
        sys.path.insert(0, str(ROOT / "runtime"))
        import verify
        with tempfile.TemporaryDirectory() as d:
            r = verify.run_suite(Path(d), f"{sys.executable} -c pass")
            self.assertEqual(r["exit_code"], 0)
            self.assertIsInstance(r["seconds"], float)


if __name__ == "__main__":
    unittest.main()
