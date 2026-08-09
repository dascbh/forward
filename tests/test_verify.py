"""FM-1/R1/R2: the gate as subprocess, on fixture projects."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_project, run_git, verify


class TestI1EvalCoverage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, behavior='["backend/app/", "src/"]')

    def tearDown(self):
        self._tmp.cleanup()

    def test_staged_behavior_without_eval_fails(self):
        (self.p / "backend" / "app").mkdir(parents=True)
        (self.p / "backend" / "app" / "svc.py").write_text("x = 1\n")
        run_git(self.p, "add", "backend/app/svc.py")
        r = verify(self.p, "--staged")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no corresponding entry", r.stdout)

    def test_gitkeep_does_not_count_as_eval_entry(self):
        (self.p / "backend" / "app").mkdir(parents=True)
        (self.p / "backend" / "app" / "svc.py").write_text("x = 1\n")
        (self.p / "evals").mkdir()
        (self.p / "evals" / ".gitkeep").touch()
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--staged")
        self.assertEqual(r.returncode, 1)

    def test_staged_behavior_with_eval_passes(self):
        (self.p / "backend" / "app").mkdir(parents=True)
        (self.p / "backend" / "app" / "svc.py").write_text("x = 1\n")
        (self.p / "tests").mkdir()
        (self.p / "tests" / "test_svc.py").write_text("assert True\n")
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--staged")
        self.assertEqual(r.returncode, 0, r.stdout)


class TestI8FindingDiscipline(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        self.f = self.p / "reviews" / "D-1" / "findings.toml"
        self.f.parent.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_probe_and_principle_citations_pass(self):
        self.f.write_text(
            '[meta]\ncontext_policy = "artifact_only"\n\n'
            '[[finding]]\nattribute = "functional_correctness"\n'
            'severity = "high"\nprobe = "boundary input"\nevidence = "x"\n\n'
            '[[finding]]\nattribute = "usability_accessibility"\n'
            'severity = "medium"\nprinciple = "USE-3"\nevidence = "y"\n')
        r = verify(self.p, "--gate", "finding-discipline")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_naked_opinion_fails(self):
        self.f.write_text(
            '[meta]\ncontext_policy = "artifact_only"\n\n'
            '[[finding]]\nattribute = "maintainability"\n'
            'severity = "low"\nevidence = "feels off"\n')
        r = verify(self.p, "--gate", "finding-discipline")
        self.assertEqual(r.returncode, 1)
        self.assertIn("without probe or principle", r.stdout)


class TestI4PromotionCriteria(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_and_undated_acceptance_fail_dated_passes(self):
        r = verify(self.p, "--gate", "promotion-criteria")
        self.assertEqual(r.returncode, 1)

        acc = self.p / "specs" / "D-1" / "acceptance.md"
        acc.parent.mkdir(parents=True)
        acc.write_text("# Acceptance\nno stamp here\n")
        r = verify(self.p, "--gate", "promotion-criteria")
        self.assertEqual(r.returncode, 1)
        self.assertIn("without a date", r.stdout)

        acc.write_text("---\ndate: 2026-08-09\n---\n# Acceptance\n")
        r = verify(self.p, "--gate", "promotion-criteria")
        self.assertEqual(r.returncode, 0, r.stdout)


class TestI5Observability(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_vendored_telemetry_is_not_a_signal(self):
        (self.p / ".gitignore").write_text("node_modules/\n")
        vend = self.p / "node_modules" / "sdk"
        vend.mkdir(parents=True)
        (vend / "telemetry.js").write_text("stub\n")
        r = verify(self.p, "--gate", "observability")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_project_owned_tracing_file_is_a_signal(self):
        (self.p / "src").mkdir()
        (self.p / "src" / "tracing.py").write_text("spans\n")
        run_git(self.p, "add", "src/tracing.py")
        r = verify(self.p, "--gate", "observability")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_observability_toml_is_a_signal(self):
        (self.p / "observability.toml").write_text("[signals]\nci = 'gate'\n")
        r = verify(self.p, "--gate", "observability")
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
