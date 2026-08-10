"""FWD-009: the erosion signals, the opt-in budget gate, and graceful
degradation. Pure cores are tested without git."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import erosion  # noqa: E402
from support import make_project, run_git, verify  # noqa: E402


class TestPureCores(unittest.TestCase):
    def test_numstat_sums_and_skips_binary(self):
        text = "12\t3\tsrc/a.py\n-\t-\tlogo.png\n5\t0\tsrc/b.py\n"
        self.assertEqual(erosion.parse_numstat(text), (17, 3))

    def test_add_delete_ratio(self):
        self.assertEqual(erosion.add_delete_ratio(30, 10), 3.0)
        self.assertEqual(erosion.add_delete_ratio(5, 0), 5.0)  # no deletes

    def test_duplicate_block_pct_detects_clones(self):
        block = "\n".join(f"line {i}" for i in range(8))
        clean = {"a.py": block, "b.py": "\n".join(f"uniq {i}" for i in range(8))}
        cloned = {"a.py": block, "b.py": block}  # identical files
        self.assertLess(erosion.duplicate_block_pct(clean), 5.0)
        self.assertGreater(erosion.duplicate_block_pct(cloned), 90.0)

    def test_duplicate_block_pct_ignores_whitespace_and_empty(self):
        a = "def f():\n    return 1\n\n\n"
        b = "def f():\n        return 1\n"  # different indent, same tokens
        self.assertGreater(erosion.duplicate_block_pct({"a": a * 2, "b": b}, k=2), 0)

    def test_check_budget_only_flags_declared_and_breached(self):
        metrics = {"add_delete_ratio": 9.0, "duplication_pct": 2.0,
                   "dependencies": 100, "largest_change": 50}
        # only max_add_delete_ratio declared, and breached
        self.assertEqual(len(erosion.check_budget(metrics, {"max_add_delete_ratio": 6.0})), 1)
        # duplication under budget → no flag; deps not declared → not checked
        self.assertEqual(erosion.check_budget(
            metrics, {"max_duplication_pct": 5.0}), [])

    def test_check_budget_skips_none_metrics(self):
        self.assertEqual(erosion.check_budget(
            {"add_delete_ratio": None}, {"max_add_delete_ratio": 1.0}), [])


class TestMeasureDegrades(unittest.TestCase):
    def test_empty_repo_never_crashes(self):
        with tempfile.TemporaryDirectory() as t:
            run_git(t, "init", "-q")
            m = erosion.measure(Path(t))  # no commits, no files
            self.assertIsNone(m["add_delete_ratio"])
            self.assertIsNone(m["duplication_pct"])
            self.assertIsNone(m["dependencies"])

    def test_dependency_count_from_manifests(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "requirements.txt").write_text("flask\nrequests\n# c\n")
            self.assertEqual(erosion.dependency_count(Path(t)), 2)
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "package.json").write_text(
                '{"dependencies":{"a":"1","b":"2"},"devDependencies":{"c":"3"}}')
            self.assertEqual(erosion.dependency_count(Path(t)), 3)

    def test_pyproject_counts_distinct_packages_not_group_repeats(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "pyproject.toml").write_text(
                '[project]\ndependencies = ["flask>=2", "requests"]\n'
                '[project.optional-dependencies]\n'
                'dev = ["requests", "pytest"]\n')  # requests repeats
            self.assertEqual(erosion.dependency_count(Path(t)), 3)  # flask, requests, pytest

    def test_largest_change_excludes_root_commit(self):
        with tempfile.TemporaryDirectory() as t:
            run_git(t, "init", "-q")
            run_git(t, "config", "user.email", "x@y")
            run_git(t, "config", "user.name", "x")
            big = "\n".join(f"line {i}" for i in range(900))
            (Path(t) / "scaffold.py").write_text(big)      # huge root commit
            run_git(t, "add", "-A")
            run_git(t, "commit", "-q", "-m", "root")
            (Path(t) / "small.py").write_text("one\ntwo\n")  # tiny 2nd commit
            run_git(t, "add", "-A")
            run_git(t, "commit", "-q", "-m", "small")
            # largest NON-ROOT change is the 2-line commit, not the 900-line root
            self.assertLessEqual(erosion.measure(Path(t))["largest_change"], 5)

    def test_report_never_crashes_on_non_numeric_budget(self):
        with tempfile.TemporaryDirectory() as t:
            run_git(t, "init", "-q")
            # check_budget must skip a bad value, not raise
            self.assertEqual(
                erosion.check_budget({"add_delete_ratio": 9.0},
                                     {"max_add_delete_ratio": "lots"}), [])


class TestGate(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def _add_erosion(self, block: str):
        with open(Path(self.p) / "fde.config.toml", "a") as fh:
            fh.write("\n[erosion]\n" + block)

    def test_absent_budget_is_silent_green(self):
        r = verify(self.p, "--gate", "erosion")
        self.assertEqual(r.returncode, 0)
        self.assertIn("not gated", r.stdout)

    def test_declared_breach_fails(self):
        # ratio 1.0 is impossibly tight for any real history → breach
        self._add_erosion("max_add_delete_ratio = 0.01\n")
        r = verify(self.p, "--gate", "erosion")
        self.assertEqual(r.returncode, 1)
        self.assertIn("add/delete ratio", r.stdout)

    def test_generous_budget_passes(self):
        self._add_erosion("max_duplication_pct = 99.0\nmax_dependencies = 9999\n")
        r = verify(self.p, "--gate", "erosion")
        self.assertEqual(r.returncode, 0)

    def test_non_numeric_budget_fails_config_gate(self):
        self._add_erosion('max_duplication_pct = "lots"\n')
        r = verify(self.p, "--gate", "config")
        self.assertEqual(r.returncode, 1)
        self.assertIn("EROSION-BUDGET", r.stdout)


if __name__ == "__main__":
    unittest.main()
