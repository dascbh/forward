"""FM-1/R1/R2: the gate as subprocess, on fixture projects."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import commit_all, make_project, run_git, verify


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

    def test_file_entry_behavior_paths_fire(self):
        p2 = make_project(tempfile.mkdtemp(dir=self._tmp.name),
                          behavior='["src/", "SETUP.md"]')
        (Path(p2) / "SETUP.md").write_text("changed installer\n")
        run_git(p2, "add", "SETUP.md")
        r = verify(p2, "--staged")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SETUP.md", r.stdout)


class TestI1CIMode(unittest.TestCase):
    """CI never falls back to ls-files: first commits diff the empty tree,
    pushes diff the given range."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_commit_behavior_without_eval_fails_not_vacuous(self):
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        commit_all(self.p, "behavior only")
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_multi_commit_push_is_covered_by_since_range(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "seed.py").write_text("assert True\n")
        base = commit_all(self.p, "eval seed")
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        commit_all(self.p, "behavior, no eval")
        (self.p / "docs.md").write_text("notes\n")
        last = commit_all(self.p, "docs only")

        # last-commit diff hides the uncovered middle commit...
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 0, r.stdout)
        # ...the pushed range does not
        r = verify(self.p, "--gate", "eval-coverage", "--since", base)
        self.assertEqual(r.returncode, 1, (last, r.stdout))

    def test_garbage_since_degrades_to_last_commit_never_ls_files(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "seed.py").write_text("assert True\n")
        commit_all(self.p, "eval seed")
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        commit_all(self.p, "behavior, no eval")
        r = verify(self.p, "--gate", "eval-coverage",
                   "--since", "0" * 40)
        self.assertEqual(r.returncode, 1, r.stdout)


class TestGateNameValidation(unittest.TestCase):
    def test_unknown_gate_is_an_error_not_a_vacuous_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p, "--gate", "evals")  # plausible typo
            self.assertEqual(r.returncode, 2)
            self.assertIn("unknown gate", r.stderr)


class TestI2I3Adversarial(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        self.f = self.p / "reviews" / "D-1" / "findings.toml"
        self.f.parent.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_report_without_isolation_declaration_fails(self):
        self.f.write_text("[meta]\ndemand_id = 'D-1'\n")
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1)
        self.assertIn("isolation", r.stdout)

    def test_promoted_demand_without_review_fails(self):
        self.f.write_text('[meta]\ncontext_policy = "artifact_only"\n')
        dec = self.p / "promotions" / "D-2" / "decision.md"
        dec.parent.mkdir(parents=True)
        dec.write_text("promoted\n")
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1)
        self.assertIn("promoted without", r.stdout)

    def test_findings_and_behavior_in_one_commit_violate_i3(self):
        self.f.write_text('[meta]\ncontext_policy = "artifact_only"\n')
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        commit_all(self.p, "review and fix together")
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1)
        self.assertIn("same commit", r.stdout)

    def test_clean_separation_passes(self):
        self.f.write_text('[meta]\ncontext_policy = "artifact_only"\n')
        commit_all(self.p, "review only")
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        (self.p / "tests").mkdir()
        (self.p / "tests" / "t.py").write_text("assert True\n")
        commit_all(self.p, "fix with eval")
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 0, r.stdout)


class TestI6I7Structure(unittest.TestCase):
    def test_portability_needs_runtime_and_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p, "--gate", "portability")
            self.assertEqual(r.returncode, 1)  # no .githooks yet
            (Path(p) / ".githooks").mkdir()
            (Path(p) / ".githooks" / "pre-commit").write_text("#!/bin/sh\n")
            r = verify(p, "--gate", "portability")
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_artifact_handoff_needs_the_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p, "--gate", "artifact-handoff")
            self.assertEqual(r.returncode, 1)
            for d in ("specs", "docs/adr", "evals"):
                (Path(p) / d).mkdir(parents=True)
            r = verify(p, "--gate", "artifact-handoff")
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

    def test_unparseable_findings_file_fails(self):
        self.f.write_text("[[finding]\nbroken toml ===\n")
        r = verify(self.p, "--gate", "finding-discipline")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unparseable", r.stdout)


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

    def test_criteria_are_per_demand_not_once_per_repo(self):
        acc = self.p / "specs" / "D-1" / "acceptance.md"
        acc.parent.mkdir(parents=True)
        acc.write_text("---\ndate: 2026-08-09\n---\n# ok\n")
        (self.p / "specs" / "D-2").mkdir()
        (self.p / "specs" / "D-2" / "spec.md").write_text("# second demand\n")
        r = verify(self.p, "--gate", "promotion-criteria")
        self.assertEqual(r.returncode, 1)
        self.assertIn("D-2", r.stdout)


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

    def test_observability_toml_with_signals_is_a_signal(self):
        (self.p / "observability.toml").write_text("[signals]\nci = 'gate'\n")
        r = verify(self.p, "--gate", "observability")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_empty_observability_toml_is_not_a_floor(self):
        (self.p / "observability.toml").write_text("# nothing declared\n")
        r = verify(self.p, "--gate", "observability")
        self.assertEqual(r.returncode, 1)
        self.assertIn("declares no", r.stdout)


if __name__ == "__main__":
    unittest.main()
