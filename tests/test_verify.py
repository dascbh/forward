"""FM-1/R1/R2: the gate as subprocess, on fixture projects."""
from __future__ import annotations

import json
import os
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


class TestI1RequirementCoverage(unittest.TestCase):
    """FWD-017 R6/R7: gate_eval_coverage() sharpened — a design-surface
    demand's declared R# criteria must each show up, as a whole token,
    under that demand's own evals/** tree."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _demand(self, did, acceptance_r="", with_design=True):
        d = self.p / "specs" / did
        d.mkdir(parents=True, exist_ok=True)
        if with_design:
            (d / "design").mkdir(parents=True, exist_ok=True)
            (d / "design" / "flow.md").write_text("# flow\n")
        (d / "acceptance.md").write_text(
            f"---\ndate: 2026-08-09\n---\n# ok\n{acceptance_r}\n")
        return d

    def _journeys(self, did, requirements, script_exists=True,
                  slug="main", script_name="main.spec.ts"):
        """Writes a spec-shaped manifest (skills/fde-design/SKILL.md's
        Design QA section: a [meta] table with id/demand_id/requirements/
        script/authored_with) under evals/journeys/<did>/, and — unless
        told otherwise — the script file it names, so the fixture matches
        what a real journey looks like on disk, not just its requirements
        line in isolation."""
        jdir = self.p / "evals" / "journeys" / did
        jdir.mkdir(parents=True, exist_ok=True)
        reqs = ", ".join(f'"{r}"' for r in requirements)
        (jdir / f"{slug}.journey.toml").write_text(
            f'[meta]\nid = "{slug}"\ndemand_id = "{did}"\n'
            f'requirements = [{reqs}]\nscript = "{script_name}"\n'
            f'authored_with = "claude-code"\n')
        if script_exists:
            (jdir / script_name).write_text("// journey script\n")

    def test_green_when_every_r_token_is_under_the_demands_own_evals(self):
        self._demand("FWD-200", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-200", ["R1", "R2"])
        r = verify(self.p, "--gate", "eval-coverage", "--format", "json")
        self.assertEqual(r.returncode, 0, r.stdout)
        row = next(g for g in json.loads(r.stdout)["gates"] if g["id"] == "I1-REQS")
        self.assertTrue(row["passed"], row)

    def test_red_when_a_declared_r_token_is_missing(self):
        self._demand("FWD-201", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-201", ["R1"])
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R2", r.stdout)

    def test_silent_for_a_demand_without_a_design_surface(self):
        self._demand("FWD-202", "R1: WHEN...\n", with_design=False)
        r = verify(self.p, "--gate", "eval-coverage", "--format", "json")
        gates = json.loads(r.stdout)["gates"]
        self.assertFalse(any(g["id"] == "I1-REQS" for g in gates), gates)

    def test_silent_for_a_design_surface_with_zero_r_tokens(self):
        self._demand("FWD-203", "")
        r = verify(self.p, "--gate", "eval-coverage", "--format", "json")
        gates = json.loads(r.stdout)["gates"]
        self.assertFalse(any(g["id"] == "I1-REQS" for g in gates), gates)

    def test_token_boundary_r1_is_not_satisfied_by_r10(self):
        self._demand("FWD-204", "R1: WHEN...\n")
        self._journeys("FWD-204", ["R10"])
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", r.stdout)

    def test_token_present_only_under_an_unrelated_demands_evals_is_still_red(self):
        self._demand("FWD-205", "R1: WHEN...\n")
        self._journeys("FWD-999", ["R1"])  # wrong demand
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", r.stdout)

    # -- F1: demand-id match is a path-segment boundary, never a substring
    def test_demand_id_prefix_is_not_a_substring_match(self):
        """FWD-1 authors no journey of its own; FWD-17 (an unrelated demand
        whose id has FWD-1 as a string prefix) owns a journey mentioning
        FWD-17's own R1. FWD-1 must stay red — the bare `in` substring
        match this used to run on would have let FWD-17's tree satisfy
        FWD-1's own obligation."""
        self._demand("FWD-1", "R1: WHEN...\n")
        self._journeys("FWD-17", ["R1"])  # FWD-17's own R1, nothing to do with FWD-1
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-1:", r.stdout)
        self.assertIn("R1", r.stdout)

    # -- F2: narration is not execution
    def test_narration_mentioning_the_token_does_not_satisfy(self):
        """A stray text file mentioning the R# token is not a journey — no
        *.journey.toml, no [meta] table, no script, nothing executable."""
        self._demand("FWD-300", "R1: WHEN...\n")
        jdir = self.p / "evals" / "journeys" / "FWD-300"
        jdir.mkdir(parents=True)
        (jdir / "notes.txt").write_text("TODO: still need to write R1 someday\n")
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", r.stdout)

    def test_manifest_whose_script_file_does_not_exist_does_not_satisfy(self):
        """A manifest can declare requirements=["R1"] and still not verify
        anything if the `script` file it names was never committed."""
        self._demand("FWD-301", "R1: WHEN...\n")
        self._journeys("FWD-301", ["R1"], script_exists=False)
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", r.stdout)

    def test_unparseable_manifest_does_not_satisfy(self):
        self._demand("FWD-302", "R1: WHEN...\n")
        jdir = self.p / "evals" / "journeys" / "FWD-302"
        jdir.mkdir(parents=True)
        (jdir / "main.journey.toml").write_text("not = valid = toml = at = all\n")
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", r.stdout)

    # -- F3: staged/since scoping — an old, unrelated demand's real gap
    # must not block a commit that never touches that demand
    def test_staged_unrelated_change_is_not_blocked_by_an_old_demands_gap(self):
        self._demand("FWD-050", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-050", ["R1"])  # R2 has always been missing
        commit_all(self.p, "FWD-050 shipped, R2 gap and all")
        (self.p / "README.md").write_text("fix a typo\n")
        run_git(self.p, "add", "README.md")
        r = verify(self.p, "--staged")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("FWD-050", r.stdout)

    def test_staged_change_touching_the_gappy_demand_still_catches_it(self):
        self._demand("FWD-051", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-051", ["R1"])  # R2 missing
        run_git(self.p, "add", "specs/FWD-051")
        r = verify(self.p, "--gate", "eval-coverage", "--staged")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-051", r.stdout)
        self.assertIn("R2", r.stdout)

    # -- F7: one demand's I/O failure must not mask coverage for the rest
    def test_one_demands_io_error_does_not_mask_another_demands_coverage(self):
        self._demand("FWD-060", "R1: WHEN...\n")
        self._journeys("FWD-060", ["R1"])
        self._demand("FWD-061", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-061", ["R1"])  # FWD-061's own, real gap: R2
        broken = self.p / "evals" / "journeys" / "FWD-060" / "main.journey.toml"
        os.chmod(broken, 0o000)
        try:
            r = verify(self.p, "--gate", "eval-coverage", "--format", "json")
        finally:
            os.chmod(broken, 0o644)
        row = next(g for g in json.loads(r.stdout)["gates"] if g["id"] == "I1-REQS")
        self.assertFalse(row["passed"], row)
        self.assertIn("FWD-060", row["detail"])
        # FWD-061's own, unrelated, genuine gap is still visible — the
        # broken demand did not swallow the whole check
        self.assertIn("FWD-061", row["detail"])
        self.assertIn("R2", row["detail"])


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
