"""FM-1/R1/R2: the gate as subprocess, on fixture projects."""
from __future__ import annotations

import inspect
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import commit_all, git_out, make_project, run_git, verify

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
import verify as verify_mod  # noqa: E402 — the module, distinct from support.verify above


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

    # -- F10: `script` must resolve inside the demand's own
    # evals/journeys/<demand-id>/ tree — a bare .is_file() on the
    # manifest-relative join let it trace to a file the demand never
    # authored
    def test_script_escaping_via_parent_traversal_does_not_satisfy(self):
        """A manifest's script pointing outside the demand's own
        evals/journeys/<demand-id>/ tree — even to another real,
        legitimate demand's own script — must not satisfy this demand's
        own obligation."""
        self._demand("FWD-400", "R1: WHEN...\n")
        # FWD-999's own real, legitimate journey
        self._journeys("FWD-999", ["R1"], script_name="real.spec.ts")
        jdir = self.p / "evals" / "journeys" / "FWD-400"
        jdir.mkdir(parents=True)
        (jdir / "main.journey.toml").write_text(
            '[meta]\nid = "main"\ndemand_id = "FWD-400"\n'
            'requirements = ["R1"]\nscript = "../FWD-999/real.spec.ts"\n'
            'authored_with = "claude-code"\n')
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-400", r.stdout)
        self.assertIn("R1", r.stdout)

    def test_script_as_absolute_path_does_not_satisfy(self):
        """An absolute script path (e.g. a binary that merely happens to
        exist on the host) replaces the manifest-relative join entirely
        under Path.__truediv__ and must not satisfy the check."""
        self._demand("FWD-401", "R1: WHEN...\n")
        jdir = self.p / "evals" / "journeys" / "FWD-401"
        jdir.mkdir(parents=True)
        (jdir / "main.journey.toml").write_text(
            '[meta]\nid = "main"\ndemand_id = "FWD-401"\n'
            'requirements = ["R1"]\nscript = "/bin/sh"\n'
            'authored_with = "claude-code"\n')
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-401", r.stdout)
        self.assertIn("R1", r.stdout)

    def test_script_via_symlink_pointing_outside_does_not_satisfy(self):
        """A script file that is itself a symlink resolving outside the
        demand's own evals/journeys/<demand-id>/ tree must not satisfy
        the check either — containment follows real paths, not just the
        manifest-declared relative name."""
        self._demand("FWD-402", "R1: WHEN...\n")
        self._journeys("FWD-999", ["R1"], script_name="real.spec.ts")
        jdir = self.p / "evals" / "journeys" / "FWD-402"
        jdir.mkdir(parents=True)
        link = jdir / "escape.spec.ts"
        link.symlink_to(self.p / "evals" / "journeys" / "FWD-999" / "real.spec.ts")
        (jdir / "main.journey.toml").write_text(
            '[meta]\nid = "main"\ndemand_id = "FWD-402"\n'
            'requirements = ["R1"]\nscript = "escape.spec.ts"\n'
            'authored_with = "claude-code"\n')
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-402", r.stdout)

    # -- F13: F10's fix hardened `script` but not the containment ROOT
    # itself — evals/journeys/<demand-id> can be a directory-level symlink
    # pointing at a different demand's real tree, so every manifest and
    # script found under it trivially "contains" against the SYMLINK'S OWN
    # resolved target. Fixed with a categorical, per-component symlink
    # walk (Gate._no_symlink_descendant) instead of a fourth resolve()-
    # and-compare patch on top of F10's.
    def test_demand_id_directory_symlinked_to_another_demands_tree_does_not_satisfy(self):
        """FWD-500 authors NO manifest and NO script of its own — instead
        its whole evals/journeys/FWD-500 directory is a symlink pointing
        at FWD-999's real, legitimate journeys tree. A demand must not be
        able to borrow another demand's entire authored work through a
        directory-level pointer one layer above where F10's fix checks."""
        self._demand("FWD-999", "R1: WHEN...\n")
        self._journeys("FWD-999", ["R1"], script_name="real.spec.ts")
        self._demand("FWD-500", "R1: WHEN...\n")
        link = self.p / "evals" / "journeys" / "FWD-500"
        link.symlink_to(self.p / "evals" / "journeys" / "FWD-999",
                        target_is_directory=True)
        commit_all(self.p, "FWD-500 points its journeys dir at FWD-999's")
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-500", r.stdout)
        self.assertIn("R1", r.stdout)

    def test_symlinked_intermediate_directory_in_scripts_own_path_does_not_satisfy(self):
        """A symlink strictly BETWEEN the manifest and the script leaf —
        neither the demand-id root (F13) nor the script file itself (F10)
        — must also make the journey uncounted. This one even resolves to
        a location genuinely inside the demand's own tree, so a
        resolve()-and-compare containment check would have let it pass;
        the categorical rule rejects it purely on the symlink's presence,
        confirming the walk checks every component, not just the two
        levels the earlier two findings already reported."""
        self._demand("FWD-600", "R1: WHEN...\n")
        jdir = self.p / "evals" / "journeys" / "FWD-600"
        jdir.mkdir(parents=True)
        real_target = jdir / "real_target"
        real_target.mkdir()
        (real_target / "real.spec.ts").write_text(
            "// real, inside FWD-600's own tree\n")
        (jdir / "linked").symlink_to(real_target, target_is_directory=True)
        (jdir / "main.journey.toml").write_text(
            '[meta]\nid = "main"\ndemand_id = "FWD-600"\n'
            'requirements = ["R1"]\nscript = "linked/real.spec.ts"\n'
            'authored_with = "claude-code"\n')
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-600", r.stdout)
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

    # -- F11: --staged is the only tier that scopes down to touched
    # demands; --since alone (CI's diff-range flag) no longer does, and an
    # explicit --all always forces the unscoped audit even when --since is
    # also passed (this is CI's real, exact invocation)
    def test_all_with_since_still_catches_an_old_unrelated_demands_gap(self):
        self._demand("FWD-070", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-070", ["R1"])  # R2 has always been missing
        old_sha = commit_all(self.p, "FWD-070 shipped, R2 gap and all")
        (self.p / "README.md").write_text("later, unrelated PR\n")
        commit_all(self.p, "unrelated readme fix")
        r = verify(self.p, "--all", "--since", old_sha,
                   "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-070", r.stdout)
        self.assertIn("R2", r.stdout)

    def test_bare_since_without_staged_or_all_also_catches_the_gap(self):
        """FWD-017 F11 design decision: `--since` alone no longer scopes
        the R#-completeness check down — only `--staged` (the pre-commit,
        don't-block-unrelated-work tier) does. An old, untouched demand's
        real gap must still surface through the plain `--since` path,
        since that is what CI's audit tier ultimately relies on."""
        self._demand("FWD-071", "R1: WHEN...\nR2: WHEN...\n")
        self._journeys("FWD-071", ["R1"])
        old_sha = commit_all(self.p, "FWD-071 shipped, R2 gap and all")
        (self.p / "README.md").write_text("later, unrelated commit\n")
        commit_all(self.p, "unrelated readme fix")
        r = verify(self.p, "--since", old_sha, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-071", r.stdout)
        self.assertIn("R2", r.stdout)


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


class TestSharedRangeResolution(unittest.TestCase):
    """reviews/FWD-019 round 1, F3: `changed()` and `_commits_in_range()`
    used to be two independently-maintained copies of the same three-tier
    --since -> HEAD~1..HEAD -> "everything in HEAD" fallback chain
    (MNT-1/MNT-8). Both now delegate to one shared `_resolve_range`. This
    is verified as a PROPERTY — the two methods agree on which commits/
    files are in scope, across all three tiers — not merely "both still
    pass their own pre-existing tests", which would not have caught the
    two copies drifting apart."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def _files_touched_by(self, shas) -> set[str]:
        """The independently-derived ground truth: every file touched by
        the given commits, computed one commit at a time via a fresh git
        call — never routed through changed() or _commits_in_range()
        itself, so this is a real cross-check, not a tautology."""
        files: set[str] = set()
        for sha in shas:
            out = subprocess.run(
                ["git", "diff-tree", "--root", "--no-commit-id", "-r",
                 "--name-only", sha],
                cwd=self.p, capture_output=True, text=True, check=True)
            files.update(l for l in out.stdout.splitlines() if l.strip())
        return files

    def test_valid_since_range_agrees_between_changed_and_commits_in_range(self):
        base = git_out(self.p, "rev-parse", "HEAD")
        (self.p / "a.py").write_text("x = 1\n")
        commit_all(self.p, "one")
        (self.p / "b.py").write_text("y = 1\n")
        commit_all(self.p, "two")

        g = verify_mod.Gate(self.p)
        files = set(g.changed(staged=False, since=base))
        shas = [sha for sha, _ in g._commits_in_range(base)]

        self.assertEqual(len(shas), 2)
        self.assertEqual(files, self._files_touched_by(shas))

    def test_invalid_since_falls_back_to_head_minus_one_for_both(self):
        (self.p / "a.py").write_text("x = 1\n")
        commit_all(self.p, "one")
        (self.p / "b.py").write_text("y = 1\n")
        commit_all(self.p, "two")

        g = verify_mod.Gate(self.p)
        files = set(g.changed(staged=False, since="not-a-real-rev"))
        shas = [sha for sha, _ in g._commits_in_range("not-a-real-rev")]

        self.assertEqual(len(shas), 1)   # HEAD~1..HEAD == just "two"
        self.assertEqual(files, self._files_touched_by(shas))

    def test_no_history_beyond_root_falls_back_to_everything_in_head_for_both(self):
        # setUp already made exactly one commit ("seed") with nothing
        # before it — HEAD~1 does not resolve, so tier 3 applies to both.
        g = verify_mod.Gate(self.p)
        files = set(g.changed(staged=False, since=None))
        shas = [sha for sha, _ in g._commits_in_range(None)]

        self.assertEqual(len(shas), 1)
        self.assertEqual(files, self._files_touched_by(shas))

    def test_commits_in_range_carries_the_real_subject_alongside_each_sha(self):
        # F5's combined call must not lose or misalign the subject
        base = git_out(self.p, "rev-parse", "HEAD")
        (self.p / "a.py").write_text("x = 1\n")
        commit_all(self.p, "FORWARD: RULE — first")
        (self.p / "b.py").write_text("y = 1\n")
        commit_all(self.p, "an unrelated second commit")

        g = verify_mod.Gate(self.p)
        pairs = g._commits_in_range(base)
        subjects = {subj for _, subj in pairs}
        self.assertEqual(subjects,
                         {"FORWARD: RULE — first", "an unrelated second commit"})


def _fake_git_that_fails_diff_tree(bindir: Path) -> Path:
    """A `git` shim that fails only on a `diff-tree` invocation (the
    exact call `triage._commit_numstat_text`/`commit_files` makes) and
    delegates everything else — `log`, `rev-list`, `rev-parse` — to the
    real git. Reproduces a genuine, non-mocked git subprocess failure
    (F4) isolated to the ONE call the finding is about, without needing
    to corrupt repository objects (unreliable: git tolerated a corrupted
    or missing loose object in manual testing, likely reading through a
    pack or delta base — not a dependable repro)."""
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH to build the fake-git shim"
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' diff-tree '*)\n"
        "    echo 'fake git: simulated diff-tree failure (F4 repro)' >&2\n"
        "    exit 128\n"
        "    ;;\n"
        "esac\n"
        f"exec \"{real_git}\" \"$@\"\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


class TestRuleLaneGateMergeAndGitFailure(unittest.TestCase):
    """reviews/FWD-019 round 1, F2/F4, at the GATE level (not just the
    triage.py wrapper level covered in test_triage.py): the live,
    blocking `rule-lane` gate — the mechanism ADR-0015's whole safety
    argument rests on — must not silently pass a merge commit or a
    commit whose diff git failed to read."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def test_gate_blocks_a_merge_commit_declaring_rule(self):
        base = git_out(self.p, "rev-parse", "HEAD")
        orig_branch = git_out(self.p, "symbolic-ref", "--short", "HEAD")
        run_git(self.p, "checkout", "-q", "-b", "feature")
        big = self.p / "src" / "big.py"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text("\n".join(f"x{i} = 1" for i in range(500)) + "\n")
        commit_all(self.p, "big feature work")
        run_git(self.p, "checkout", "-q", orig_branch)
        run_git(self.p, "merge", "--no-ff", "-q", "feature",
               "-m", "FORWARD: RULE — trivial merge")

        r = verify(self.p, "--gate", "rule-lane", "--since", base)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("merge", r.stdout)

    def test_gate_blocks_when_git_fails_reading_a_commits_diff(self):
        src = self.p / "src" / "a.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("x = 1\ny = 2\n")
        commit_all(self.p, "FORWARD: RULE — tiny add")

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_diff_tree(bindir)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "rule-lane", env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("git_failure", r.stdout)


def _fake_git_that_fails_log(bindir: Path) -> Path:
    """A `git` shim that fails only on `git log` invocations — the exact
    call `Gate._commits_in_range` makes to discover WHICH commits are
    even in range for `gate_rule_lane` to examine (reviews/FWD-019 round
    2, F6) — and delegates everything else (`rev-parse`, `diff-tree`,
    `diff`) to the real git. Same fake-git-shim technique
    `_fake_git_that_fails_diff_tree` above already uses for F4's sibling
    repro, rather than corrupting `.git/objects` directly (the review's
    own `chmod 000` repro; noted there as environment-fragile — some git
    builds/platforms tolerate a corrupted or unreadable object by reading
    through a pack or delta base, so a shim on the exact subcommand is
    the more reliable mechanism for a test suite)."""
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH to build the fake-git shim"
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' log '*)\n"
        "    echo 'fake git: simulated log failure (F6 repro)' >&2\n"
        "    exit 128\n"
        "    ;;\n"
        "esac\n"
        f"exec \"{real_git}\" \"$@\"\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


class TestRuleLaneGateGitFailureDuringRangeDiscovery(unittest.TestCase):
    """reviews/FWD-019 round 2, F6: a git failure one level up from where
    F4 already fixed it — not while reading ONE commit's own diff (F4;
    `triage._git` -> `GitFailure`, caught in `eligibility_for_commit`),
    but while `Gate._commits_in_range` discovers WHICH commits are even
    in the range `gate_rule_lane` is about to examine. Before this fix,
    `Gate._git` swallowed any non-FileNotFoundError git failure (a
    permission error, a lock, a corrupted object, a disk I/O problem)
    into the same `[]` a genuinely empty range produces, so
    `gate_rule_lane` read a real git failure as "no commit in range
    claims RULE" and silently passed — even for a commit that in fact
    declares RULE and exceeds the loc threshold. The exact scenario the
    review reproduced end-to-end with `chmod 000` on `.git/objects`;
    reproduced here with the shim above for reliability across
    environments/CI."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def _commit_an_over_threshold_rule_claim(self) -> str:
        base = git_out(self.p, "rev-parse", "HEAD")
        big = self.p / "src" / "big.py"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text("\n".join(f"x{i} = 1" for i in range(40)) + "\n")
        commit_all(self.p, "FORWARD: RULE — actually not small")
        return base

    def test_healthy_git_blocks_the_over_threshold_claim(self):
        # control: the same commit, healthy git — establishes this is a
        # real positive before trusting the git-failure variant below
        base = self._commit_an_over_threshold_rule_claim()
        r = verify(self.p, "--gate", "rule-lane", "--since", base)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("'loc'", r.stdout)

    def test_gate_blocks_rather_than_silently_passes_when_git_fails_listing_the_range(self):
        base = self._commit_an_over_threshold_rule_claim()

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_log(bindir)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "rule-lane", "--since", base, env=env)

        # the exact failure mode this finding names: never "no commit in
        # range claims RULE", never a clean pass — a blocking, clearly
        # named git failure instead
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RULE-LANE", r.stdout)
        self.assertIn("could not determine which commits are in", r.stdout)
        self.assertIn("mechanical certainty is unavailable", r.stdout)
        self.assertNotIn("nothing to re-verify", r.stdout)

    def test_default_full_run_still_reports_and_blocks_on_the_same_git_failure(self):
        # the CI shape: no --gate, no --since — the RULE-LANE row must
        # not go missing from the report entirely (the review's step 4)
        self._commit_an_over_threshold_rule_claim()

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_log(bindir)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RULE-LANE", r.stdout)
        self.assertIn("could not determine which commits are in", r.stdout)
        self.assertNotIn("nothing to re-verify", r.stdout)


def _fake_git_that_fails_rev_parse_for(bindir: Path, rev: str) -> Path:
    """A `git` shim that fails only the ONE `rev-parse --verify --quiet
    <rev>^{commit}` invocation for the given `rev` — the exact call
    `Gate._rev_ok` makes for THIS `since` value (reviews/FWD-019 round 3,
    F9) — and delegates every OTHER invocation (rev-parse for any other
    revision, e.g. `HEAD~1` or `HEAD`; `git log`; `git diff`) to the real
    git. Exit 128 with a stderr message simulates a genuine operational
    failure (permission, lock, corrupted object, disk I/O) — the
    categorically different shape from the exit-1/empty-stderr a
    legitimately-absent revision produces (see `Gate._rev_ok`'s own
    docstring), so this reproduces F9 without also tripping the
    legitimate fresh-repo/shallow-clone fallback that must keep working."""
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH to build the fake-git shim"
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        f"  *' rev-parse --verify --quiet {rev}^{{commit}} '*)\n"
        "    echo 'fake git: simulated rev-parse failure (F9 repro)' >&2\n"
        "    exit 128\n"
        "    ;;\n"
        "esac\n"
        f"exec \"{real_git}\" \"$@\"\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


class TestRuleLaneGateGitFailureDuringRevResolution(unittest.TestCase):
    """reviews/FWD-019 round 3, F9: one call further upstream than F6
    (round 2) fixed. `_commits_in_range` calls `_resolve_range` FIRST to
    pick the revspec, and `_resolve_range` depends on `_rev_ok` — before
    this fix, `_rev_ok` only caught `FileNotFoundError`; any OTHER git
    failure resolving `since` (a permission error, a lock, a corrupted
    object, a disk I/O problem) read exactly the same as "this revision
    does not exist" and silently fell through to a narrower tier
    (`HEAD~1..HEAD`, or "everything in HEAD"). A real, ineligible
    RULE-tagged commit outside that wrongly-narrowed range was never
    examined at all — not mis-scored, simply never asked about."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def _commit_an_over_threshold_rule_claim_then_a_trailing_commit(self) -> str:
        base = git_out(self.p, "rev-parse", "HEAD")
        big = self.p / "src" / "big.py"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text("\n".join(f"x{i} = 1" for i in range(40)) + "\n")
        commit_all(self.p, "FORWARD: RULE — actually not small")
        # a later, untagged commit — under the fault, this is the ONLY
        # commit that survives the wrongly-narrowed HEAD~1..HEAD range,
        # exactly F9's own end-to-end reproduction
        (self.p / "trivial.txt").write_text("x\n")
        commit_all(self.p, "an unrelated trailing commit")
        return base

    def test_healthy_git_blocks_the_over_threshold_claim(self):
        # control: the same commits, healthy git — establishes this is a
        # real positive before trusting the git-failure variant below
        base = self._commit_an_over_threshold_rule_claim_then_a_trailing_commit()
        r = verify(self.p, "--gate", "rule-lane", "--since", base)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("'loc'", r.stdout)

    def test_gate_blocks_rather_than_silently_narrows_when_rev_parse_fails_for_since(self):
        base = self._commit_an_over_threshold_rule_claim_then_a_trailing_commit()

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_rev_parse_for(bindir, base)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "rule-lane", "--since", base, env=env)

        # F9's exact failure mode: never a silent narrowing to
        # HEAD~1..HEAD (which would only see the trailing, untagged
        # commit and miss the RULE-claiming one entirely) — a blocking,
        # clearly named git failure instead, same posture as F6
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RULE-LANE", r.stdout)
        self.assertIn("could not determine which commits are in", r.stdout)
        self.assertIn("mechanical certainty is unavailable", r.stdout)
        self.assertNotIn("nothing to re-verify", r.stdout)
        # never quietly examines only the trailing commit as if the range
        # had narrowed on purpose
        self.assertNotIn("'loc'", r.stdout)

    def test_default_full_run_still_reports_and_blocks_and_i1_is_not_narrowed_either(self):
        # the true CI shape per .github/workflows/fde-gate.yml: no
        # --gate, --since <base> only. F9's own repro also showed I1's
        # file list (changed() -> the SAME _resolve_range) silently
        # narrowing under this fault — confirm it now blocks too, not
        # just rule-lane.
        base = self._commit_an_over_threshold_rule_claim_then_a_trailing_commit()

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_rev_parse_for(bindir, base)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--since", base, env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("RULE-LANE", r.stdout)
        self.assertIn("could not determine which commits are in", r.stdout)
        self.assertNotIn("nothing to re-verify", r.stdout)
        self.assertIn("I1", r.stdout)
        self.assertIn("could not determine which files changed", r.stdout)


class TestZeroCommitRepoStaysLegitimateNotAFailure(unittest.TestCase):
    """Discovered auditing `_git`'s new strict default (reviews/FWD-019
    round 3, F9): a brand-new repository with zero commits (an unborn
    HEAD) makes `git diff EMPTY_TREE HEAD` and `git log HEAD` themselves
    fail (exit 128, "fatal: ambiguous argument 'HEAD'") purely because
    HEAD does not resolve yet — a different fact from a genuine git
    operational failure (permission, lock, corruption). This is NOT one
    of the review's own findings; it is the tier-3 sibling of the same
    legitimate-fallback distinction `_rev_ok`/`_resolve_range` already
    protect for tiers 1-2, caught here so `_git`'s inverted default would
    not turn an ordinary "nothing has ever been committed yet" project
    state into a raised GitOpFailure. `changed()` and `_commits_in_range()`
    both check `_rev_ok("HEAD")` before their tier-3 git call and read a
    zero-commit repo exactly as before: empty, not a failure."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)  # git init, zero commits

    def tearDown(self):
        self._tmp.cleanup()

    def test_changed_returns_empty_not_raise_on_zero_commit_repo(self):
        g = verify_mod.Gate(self.p)
        self.assertEqual(g.changed(staged=False, since=None), [])

    def test_commits_in_range_returns_empty_not_raise_on_zero_commit_repo(self):
        g = verify_mod.Gate(self.p)
        self.assertEqual(g._commits_in_range(None), [])

    def test_gate_eval_coverage_does_not_crash_on_zero_commit_repo(self):
        r = verify(self.p, "--gate", "eval-coverage")
        # no behavior files exist yet either way; the point is this must
        # not raise/crash on the unborn-HEAD git failure — a clean pass
        self.assertEqual(r.returncode, 0, r.stdout)


def _fake_git_that_fails_log_dash20(bindir: Path) -> Path:
    """A `git` shim that fails only `git log -20 --format=%H` — the exact
    call `gate_adversarial`'s I3 review/behavior-separation scan makes —
    delegating everything else to the real git. Distinct shim from
    `_fake_git_that_fails_log` above (which matches ANY ` log ` call,
    including `_commits_in_range`'s) so this test cannot be confused with
    exercising rule-lane's own, already-covered path."""
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH to build the fake-git shim"
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' log -20 --format=%H '*)\n"
        "    echo 'fake git: simulated I3 history-scan failure (F9 audit repro)' >&2\n"
        "    exit 128\n"
        "    ;;\n"
        "esac\n"
        f"exec \"{real_git}\" \"$@\"\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


class TestI3GitFailureDuringHistoryScanBlocks(unittest.TestCase):
    """reviews/FWD-019 round 3, F9 audit (task step 3): every
    pre-existing `Gate._git` caller was individually re-examined once
    `_git` itself became strict, not blanket-wrapped to keep compiling.
    `gate_adversarial`'s I3 review/behavior-separation scan is one of the
    two (with `changed()`/I1) found to need the strict default: an
    unsignaled git failure enumerating recent history would have read as
    "no commit mixes review findings with behavior" — a false PASS on I3,
    the same shape of bug as F4/F6/F9 — so this call site keeps the
    strict default rather than becoming a `_git_lenient` opt-out."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        f = self.p / "reviews" / "D-1" / "findings.toml"
        f.parent.mkdir(parents=True)
        f.write_text('[meta]\ncontext_policy = "artifact_only"\n')
        commit_all(self.p, "review only")

    def tearDown(self):
        self._tmp.cleanup()

    def test_i3_blocks_rather_than_silently_passes_when_git_log_fails(self):
        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_log_dash20(bindir)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "adversarial-isolation", env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("I3", r.stdout)
        self.assertIn("could not scan recent history", r.stdout)
        # the actual PASS message ("...clean") must not appear — the
        # blocking message above deliberately echoes a similar phrase
        # ("no commit mixes findings with behavior") as part of its OWN
        # explanation, so this checks the full, exact pass sentence, not
        # a fragment shared with that explanation
        self.assertNotIn("no commit mixes review findings with behavior changes", r.stdout)


def _fake_git_that_fails_ls_files(bindir: Path) -> Path:
    """A `git` shim that fails only `ls-files` invocations — the exact
    call `gate_observability`'s legacy telemetry/tracing file-listing
    fallback makes — delegating everything else to the real git."""
    real_git = shutil.which("git")
    assert real_git, "git must be on PATH to build the fake-git shim"
    shim = bindir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        "  *' ls-files '*)\n"
        "    echo 'fake git: simulated ls-files failure (F9 audit repro)' >&2\n"
        "    exit 128\n"
        "    ;;\n"
        "esac\n"
        f"exec \"{real_git}\" \"$@\"\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


class TestObservabilityGitFailureIsDeliberatelyLenient(unittest.TestCase):
    """reviews/FWD-019 round 3, F9 audit (task step 3): unlike I1's
    `changed()` and I3's history scan, `gate_observability`'s legacy
    telemetry/tracing file-listing fallback deliberately opts into
    `_git_lenient` — a git failure here and a query that legitimately
    finds nothing already produce the IDENTICAL, safe I5 verdict (I5 only
    ever passes off `hits` being non-empty, never off the mere absence of
    a failure), so there is no false-PASS path for a swallowed failure to
    hide behind, unlike F4/F6/F9's own bug class. This confirms the
    chosen behavior end to end: a git failure degrades to the same
    "no corresponding signal" message a real absence produces — not a
    crash, and not a false pass."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_git_failure_listing_files_still_fails_i5_cleanly_not_a_crash_or_pass(self):
        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_ls_files(bindir)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "observability", env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no corresponding signal", r.stdout)


class TestGateEvalCoverageBodyUnmodifiedR6(unittest.TestCase):
    """reviews/FWD-019 round 4, F10: round 3's own fix for F9 (a
    try/except GitOpFailure wrapping `self.changed(staged, since)`)
    landed INSIDE `gate_eval_coverage`'s body — a regression against R6
    (spec.md, non-negotiable): "zero lines added, removed, or reordered
    inside its body, verifiable by direct inspection." The safety
    property F9 needed is real and stays; it now lives at the ONE
    dispatch call site in `main()` that can raise `GitOpFailure` through
    `gate_eval_coverage` (`want("eval-coverage") or want("eval")`),
    never inside the method itself. These tests guard against a fourth
    recurrence of the identical mistake (F4 -> F6 -> F9 -> F10)."""

    def test_body_contains_no_git_op_failure_handling(self):
        # bd4e9ff (R6's own pre-round-3 baseline) never references
        # GitOpFailure inside this function's body at all — the
        # pre-existing `try: import design / import graph` block is
        # unrelated to F9/F10 and stays (it predates FWD-019 entirely);
        # only a GitOpFailure-specific try/except reappearing here means
        # the round-3 fix has regressed back inside the method.
        src = inspect.getsource(verify_mod.Gate.gate_eval_coverage)
        self.assertNotIn("GitOpFailure", src)
        self.assertNotIn("except GitOpFailure", src)

    def test_files_assignment_is_a_plain_unwrapped_statement(self):
        # a second, independent check straight from runtime/verify.py on
        # disk (not the imported module object): "files = self.changed
        # (...)" is exactly the one plain line bd4e9ff's own version
        # used — not the first line of a try block, never wrapped in a
        # try/except of its own.
        text = (ROOT / "runtime" / "verify.py").read_text(encoding="utf-8")
        lines = text.splitlines()
        start = next(i for i, l in enumerate(lines)
                    if l.startswith("    def gate_eval_coverage("))
        end = next(i for i in range(start + 1, len(lines))
                   if lines[i].startswith("    def "))
        body_lines = lines[start:end]
        idx = next(i for i, l in enumerate(body_lines)
                  if "files = self.changed(staged, since)" in l)
        # the line immediately before it is blank or a comment — never
        # "try:" (which would mean this assignment is wrapped again)
        prev = body_lines[idx - 1].strip()
        self.assertNotEqual(prev, "try:")
        self.assertNotIn("except GitOpFailure", "\n".join(body_lines))


class TestGitOpFailureCaughtAtDispatchNotInsideTheGateMethod(unittest.TestCase):
    """The dispatch-level fix (F10), proven end to end: `--gate
    eval-coverage` ALONE — isolated from rule-lane's own, separately-
    handled path — still blocks I1 on a git failure discovering which
    files changed, even though the try/except no longer lives inside
    `gate_eval_coverage` itself (moved to `main()`'s dispatch loop)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def test_eval_coverage_alone_blocks_on_a_git_failure_via_dispatch(self):
        base = git_out(self.p, "rev-parse", "HEAD")
        (self.p / "trivial.txt").write_text("x\n")
        commit_all(self.p, "a trailing commit")

        with tempfile.TemporaryDirectory() as shimdir:
            bindir = Path(shimdir)
            _fake_git_that_fails_rev_parse_for(bindir, base)
            env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
            r = verify(self.p, "--gate", "eval-coverage", "--since", base, env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("I1-REQS", r.stdout)
        self.assertIn("I1", r.stdout)
        self.assertIn("could not determine which files changed", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


class TestRunGitPermissionErrorIsAGitOpFailure(unittest.TestCase):
    """reviews/FWD-019 round 4, F12: `Gate._run_git` used to catch only
    `FileNotFoundError`. A `git` file present on PATH but not executable
    raises `PermissionError` instead (confirmed empirically distinct
    from `FileNotFoundError`) — before this fix that propagated uncaught
    as a raw traceback rather than the clean `GitOpFailure` every other
    git failure mode already produces."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_permission_denied_git_raises_git_op_failure_not_a_crash(self):
        with tempfile.TemporaryDirectory() as bindir:
            broken = Path(bindir) / "git"
            broken.write_text("#!/bin/sh\necho should never run\n")
            broken.chmod(0o644)   # present, NOT executable, and the ONLY
            # git anywhere on this PATH (a working git found elsewhere on
            # PATH lets POSIX's exec search skip right past a broken
            # entry — confirmed empirically, F12's own finding).
            g = verify_mod.Gate(self.p)
            with mock.patch.dict(os.environ, {"PATH": bindir}):
                with self.assertRaises(verify_mod.GitOpFailure) as ctx:
                    g._git("rev-parse", "HEAD")
        self.assertIn("git could not be run", str(ctx.exception))


class TestGitSpawnPermissionErrorEndToEndDoesNotCrashTheWholeRun(unittest.TestCase):
    """The same fault (F12), reproduced through the real
    `bin/fde/verify.py` subprocess end to end, matching this file's
    established never-a-mock reproduction standard: a PermissionError
    spawning `git` must never surface as a bare, unhandled Python
    traceback — which would print nothing at all (not even the report
    header) and discard every gate result that had already run — but
    instead fails the gate cleanly, the same shape every other git
    failure mode in this file already produces."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._tmp.cleanup()

    def test_permission_denied_git_fails_the_gate_cleanly_not_a_crash(self):
        with tempfile.TemporaryDirectory() as root:
            pydir = Path(root) / "py"
            gitdir = Path(root) / "git_broken"
            pydir.mkdir()
            gitdir.mkdir()
            real_python = shutil.which("python3") or shutil.which("python")
            assert real_python, "python3 must be on PATH to build this fixture"
            (pydir / "python3").symlink_to(real_python)
            broken = gitdir / "git"
            broken.write_text("#!/bin/sh\necho should never run\n")
            broken.chmod(0o644)   # present, NOT executable, and the ONLY
            # git anywhere on this constructed PATH — a working git found
            # LATER on PATH lets POSIX's exec search skip right past the
            # broken one (confirmed empirically, F12's own finding), so
            # no other git may be reachable from this PATH at all.
            env = {"PATH": f"{pydir}{os.pathsep}{gitdir}"}
            r = verify(self.p, "--gate", "eval-coverage", env=env)

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("I1", r.stdout)
        self.assertIn("gate(s) failed", r.stdout)


# -- FWD-029 (ADR-0019 rule 14): gates read the level that owns the thing --
CYCLE_PLAN = """\
cycle: C-{n}
objective: something worth shipping
date: 2026-09-29

## Acceptance criteria

- **A1 — works.** It works.

## Demands

| id | layer | depends on | what | meets |
|---|---|---|---|---|
{rows}
"""

FINDINGS = '[meta]\ncontext_policy = "artifact_only"\n'


def cycle_plan(p, n, rows, date=True, criteria=True):
    d = Path(p) / "cycles" / f"C-{n}"
    d.mkdir(parents=True, exist_ok=True)
    text = CYCLE_PLAN.format(n=n, rows="\n".join(rows))
    if not date:
        text = text.replace("date: 2026-09-29\n", "")
    if not criteria:
        text = text.replace(
            "## Acceptance criteria\n\n- **A1 — works.** It works.\n\n", "")
    (d / "plan.md").write_text(text)
    return d


def cycle_spec(p, did, cycle=None):
    d = Path(p) / "specs" / did
    d.mkdir(parents=True, exist_ok=True)
    head = f"cycle: {cycle} · layer: back · meets: A1\n\n" if cycle else ""
    (d / "spec.md").write_text(f"# {did} — a demand\n\n{head}What it does.\n")
    return d


def review_of(p, did):
    r = Path(p) / "reviews" / did
    r.mkdir(parents=True, exist_ok=True)
    (r / "findings.toml").write_text(FINDINGS)


def old_demand(p, did, promoted=True):
    d = Path(p) / "specs" / did
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text(f"# {did}\nTriage: → **M**\n")
    (d / "acceptance.md").write_text("---\ndate: 2026-08-09\n---\n# ok\n")
    review_of(p, did)
    if promoted:
        pr = Path(p) / "promotions" / did
        pr.mkdir(parents=True, exist_ok=True)
        (pr / "decision.md").write_text("promoted\n")


class TestI4CycleCriteria(unittest.TestCase):
    """I4 accepts dated criteria in cycles/C-<n>/plan.md, inherited by the
    cycle's demands; the per-demand acceptance.md still counts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "promotion-criteria")

    def test_spec_cycle_line_inherits_the_plans_dated_criteria(self):
        cycle_plan(self.p, 1, [])
        cycle_spec(self.p, "FWD-101-slug", cycle="C-1")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_plan_demands_table_links_a_spec_without_a_cycle_line(self):
        cycle_plan(self.p, 1, ["| FWD-102 | back | — | x | A1 |"])
        cycle_spec(self.p, "FWD-102-slug")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_depends_on_column_is_not_a_link(self):
        cycle_plan(self.p, 1, ["| FWD-103 | back | FWD-104 | x | A1 |"])
        cycle_spec(self.p, "FWD-103")
        cycle_spec(self.p, "FWD-104")  # only named as a dependency
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-104", r.stdout)
        self.assertNotIn("FWD-103", r.stdout)

    def test_undated_plan_does_not_carry_criteria(self):
        cycle_plan(self.p, 1, [], date=False)
        cycle_spec(self.p, "FWD-105", cycle="C-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("C-1", r.stdout)
        self.assertIn("date", r.stdout)

    def test_plan_without_criteria_does_not_carry_criteria(self):
        cycle_plan(self.p, 1, [], criteria=False)
        cycle_spec(self.p, "FWD-106", cycle="C-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("criteria", r.stdout)

    def test_cycle_named_by_the_spec_must_have_a_plan(self):
        cycle_spec(self.p, "FWD-107", cycle="C-9")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("C-9", r.stdout)

    def test_cycle_line_below_the_header_does_not_link(self):
        cycle_plan(self.p, 1, [])
        d = Path(self.p) / "specs" / "FWD-108"
        d.mkdir(parents=True)
        (d / "spec.md").write_text("# FWD-108\n\n## Notes\ncycle: C-1\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-108", r.stdout)

    def test_dated_plan_alone_declares_criteria_before_any_demand(self):
        cycle_plan(self.p, 1, [])
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_old_single_file_cycles_are_not_plans(self):
        (Path(self.p) / "cycles").mkdir()
        (Path(self.p) / "cycles" / "C-1.md").write_text(
            "objective: x\ndate: 2026-09-01\n## Acceptance criteria\n- a\n")
        cycle_spec(self.p, "FWD-109", cycle="C-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)


class TestCyclePromotionNeedsReviews(unittest.TestCase):
    """Promotion is found per cycle (cycles/C-<n>/promotion.md) or per
    demand (promotions/<id>/decision.md); either way a promoted demand
    without a recorded review is a bypass (I2 and TRACE)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        d = cycle_plan(self.p, 1, ["| FWD-111 | back | — | x | A1 |",
                                   "| FWD-113 | back | — | x | A1 |"])
        (d / "promotion.md").write_text("decision: promote\n")
        cycle_spec(self.p, "FWD-111", cycle="C-1")
        cycle_spec(self.p, "FWD-112", cycle="C-1")
        review_of(self.p, "FWD-111")

    def tearDown(self):
        self._tmp.cleanup()

    def test_promoted_cycle_with_an_unreviewed_demand_fails_i2_and_trace(self):
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("promoted without a recorded review", r.stdout)
        self.assertIn("FWD-112", r.stdout)
        r = verify(self.p, "--gate", "traceability")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FWD-112", r.stdout)

    def test_every_specified_demand_reviewed_passes(self):
        # FWD-113 is planned but never specified: not built, not required
        review_of(self.p, "FWD-112")
        for gate in ("adversarial-isolation", "traceability"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 0, gate + r.stdout)

    def test_unpromoted_cycle_does_not_require_reviews(self):
        (Path(self.p) / "cycles" / "C-1" / "promotion.md").unlink()
        for gate in ("adversarial-isolation", "traceability"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 0, gate + r.stdout)


class TestCodeReviewRecordPassesTheGate(unittest.TestCase):
    """FWD-036 FM2 (kernel ADR-0021): a code review is a review. A promoted
    demand whose findings.toml is the installed template filled in with
    `kind = "code"` passes I2 and TRACE; the gate reads isolation, not
    the review's kind, so a code review without the isolation declaration
    still fails I2."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        d = cycle_plan(self.p, 1, ["| FWD-121 | back | — | x | A1 |"])
        (d / "promotion.md").write_text("decision: promote\n")
        cycle_spec(self.p, "FWD-121", cycle="C-1")
        template = (ROOT / "templates" / "findings.template.toml").read_text(
            encoding="utf-8")
        self.record = (template.replace("{{DEMAND_ID}}", "FWD-121")
                       .replace("{{REVIEW_KIND}}", "code")
                       .replace("{{ROUNDS_PLANNED}}", "1"))
        self.f = Path(self.p) / "reviews" / "FWD-121" / "findings.toml"
        self.f.parent.mkdir(parents=True)
        self.f.write_text(self.record)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_filled_template_is_a_code_review(self):
        import tomllib
        self.assertNotIn("{{", self.record)
        self.assertEqual(tomllib.loads(self.record)["meta"]["kind"], "code")

    def test_code_review_record_passes_i2_trace_and_i8(self):
        for gate in ("adversarial-isolation", "traceability",
                     "finding-discipline"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 0, gate + r.stdout)

    def test_code_review_without_isolation_still_fails_i2(self):
        self.f.write_text(self.record.replace(
            'context_policy = "artifact_only"', ""))
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("without isolation declaration", r.stdout)


class TestBothLayoutsStayGreen(unittest.TestCase):
    """FM1 (C-5): the gate change must not turn an old-layout repository
    red. One fixture per layout, one mixed, and this repository itself."""

    GATES = ("promotion-criteria", "adversarial-isolation", "traceability",
             "finding-discipline", "scrum", "backlog")

    def assert_green(self, p):
        for gate in self.GATES:
            r = verify(p, "--gate", gate)
            self.assertEqual(r.returncode, 0, f"{gate}: {r.stdout}{r.stderr}")
            self.assertNotIn("SCRUM-GOAL", r.stdout)
            self.assertNotIn("SCRUM-RETRO", r.stdout)

    def old_layout(self, p):
        old_demand(p, "DEM-001")
        old_demand(p, "DEM-002", promoted=False)
        # an XS review with no spec and no sprint selecting it
        review_of(p, "DEM-003")
        (Path(p) / "backlog.md").write_text(
            "---\ngoal: a goal\ndate: 2026-08-09\n---\n# Backlog\n")
        # sprints from before ADR-0019 stay as history, never required:
        # an undated goal, a missing retro and a stray directory pass
        for name in ("S-1", "S-2", "S-archive"):
            (Path(p) / "sprints" / name).mkdir(parents=True)
        (Path(p) / "sprints" / "S-1" / "goal.md").write_text("| DEM-001 |\n")

    def new_layout(self, p):
        d = cycle_plan(p, 7, ["| DEM-010 | back | — | x | A1 |",
                              "| DEM-011 | front | DEM-010 | y | A1 |"])
        (d / "promotion.md").write_text("decision: promote\n")
        cycle_spec(p, "DEM-010", cycle="C-7")
        cycle_spec(p, "DEM-011")
        review_of(p, "DEM-010")
        review_of(p, "DEM-011")

    def test_old_per_demand_layout_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp, scrum=True)
            self.old_layout(p)
            self.assert_green(p)

    def test_new_cycle_layout_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp, scrum=True)
            (Path(p) / "backlog.md").write_text(
                "---\ngoal: a goal\ndate: 2026-09-29\n---\n# Backlog\n")
            self.new_layout(p)
            self.assert_green(p)

    def test_both_layouts_in_one_repository_are_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp, scrum=True)
            self.old_layout(p)
            self.new_layout(p)
            self.assert_green(p)

    def test_this_repository_passes_the_cycle_level_gates(self):
        for gate in ("promotion-criteria", "adversarial-isolation",
                     "traceability", "scrum", "backlog"):
            r = subprocess.run(
                [sys.executable, str(ROOT / "bin" / "fde" / "verify.py"),
                 "--gate", gate], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{gate}: {r.stdout}{r.stderr}")


class TestClientDemandPrefix(unittest.TestCase):
    """FWD-029 F1: a demand id is <PREFIX>-<n>, whatever prefix the plan's
    ## Demands first cell and the spec directory declare (ACME-1)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_plan_row_links_a_client_prefixed_slugged_spec(self):
        cycle_plan(self.p, 1, ["| ACME-1 | back | — | x | A1 |"])
        cycle_spec(self.p, "ACME-1-thing")
        r = verify(self.p, "--gate", "promotion-criteria")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_promoted_client_demand_meets_its_bare_review(self):
        d = cycle_plan(self.p, 1, ["| ACME-1 | back | — | x | A1 |"])
        (d / "promotion.md").write_text("decision: promote\n")
        cycle_spec(self.p, "ACME-1-thing", cycle="C-1")
        review_of(self.p, "ACME-1")
        for gate in ("promotion-criteria", "adversarial-isolation",
                     "traceability"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 0, gate + r.stdout)

    def test_unreviewed_promoted_client_demand_still_fails(self):
        d = cycle_plan(self.p, 1, ["| ACME-2 | back | — | x | A1 |"])
        (d / "promotion.md").write_text("decision: promote\n")
        cycle_spec(self.p, "ACME-2-thing", cycle="C-1")
        review_of(self.p, "ACME-3")  # a review exists, not this demand's
        for gate in ("adversarial-isolation", "traceability"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 1, gate + r.stdout)
            self.assertIn("ACME-2", r.stdout)

    def test_kernel_id_families_are_not_demands(self):
        import fde_lib
        for name in ("C-1", "B-4", "S-2", "ADR-0019", "login-2fa", "notes"):
            self.assertIsNone(fde_lib.demand_id(name), name)
        self.assertEqual(fde_lib.demand_id("acme-12-slug"), "ACME-12")


class TestPlanCriteriaAreDeclared(unittest.TestCase):
    """FWD-029 F2/F3: I4 wants a real ISO date and a criterion id that is
    not the template's placeholder; ordinary markdown in the plan is read."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "promotion-criteria")

    def write_plan(self, text):
        d = Path(self.p) / "cycles" / "C-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.md").write_text(text)

    def test_unedited_template_does_not_declare_criteria(self):
        tpl = (ROOT / "templates" / "cycle" / "plan.md").read_text()
        self.write_plan(tpl.replace("DEM-<n>", "DEM-1"))
        cycle_spec(self.p, "DEM-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("YYYY-MM-DD", r.stdout)

    def test_template_placeholder_criterion_does_not_count(self):
        tpl = (ROOT / "templates" / "cycle" / "plan.md").read_text()
        self.write_plan(tpl.replace("DEM-<n>", "DEM-1")
                        .replace("date: YYYY-MM-DD", "date: 2026-09-29"))
        cycle_spec(self.p, "DEM-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("placeholder", r.stdout)

    def test_impossible_date_is_not_a_date(self):
        self.write_plan(CYCLE_PLAN.format(n=1, rows="| DEM-1 | back | — | x | A1 |")
                        .replace("2026-09-29", "2026-13-45"))
        cycle_spec(self.p, "DEM-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("not a date", r.stdout)

    def test_criteria_section_without_an_id_does_not_count(self):
        self.write_plan(CYCLE_PLAN.format(n=1, rows="| DEM-1 | back | — | x | A1 |")
                        .replace("- **A1 — works.** It works.", "- it works"))
        cycle_spec(self.p, "DEM-1")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_bold_link_and_lowercase_first_cells_link(self):
        cycle_plan(self.p, 1, ["| **FWD-1** | back | — | x | A1 |",
                               "| [FWD-2](specs/FWD-2) | back | — | x | A1 |",
                               "| fwd-3 | back | — | x | A1 |"])
        for did in ("FWD-1", "FWD-2", "FWD-3"):
            cycle_spec(self.p, did)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_verify_skill_declares_the_ordering_limit(self):
        for rel in ("skills/fde-verify/SKILL.md",
                    ".claude/skills/fde-verify/SKILL.md"):
            text = (ROOT / rel).read_text()
            self.assertIn("`date: YYYY-MM-DD`", text, rel)
            self.assertIn("Declared limit: the gate does not check that the "
                          "date precedes the first demand commit", text, rel)

    def test_acceptance_heading_without_the_word_criteria(self):
        self.write_plan(CYCLE_PLAN.format(n=1, rows="| DEM-1 | back | — | x | A1 |")
                        .replace("## Acceptance criteria", "## Acceptance"))
        cycle_spec(self.p, "DEM-1")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)


class TestClosedCycleNeedsPromotionGate(unittest.TestCase):
    """C-5 F5: a closed directory cycle with no promotion.md skipped the
    only cycle-level check that its demands were reviewed. I4 is red."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        self.d = cycle_plan(self.p, 6, ["| FWD-040 | back | — | x | A1 |"])
        cycle_spec(self.p, "FWD-040", cycle="C-6")

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "promotion-criteria")

    def close(self, line):
        plan = self.d / "plan.md"
        plan.write_text(plan.read_text().replace(
            "date: 2026-09-29\n", f"date: 2026-09-29\n{line}\n"))

    def test_running_cycle_without_promotion_passes(self):
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_closed_state_without_promotion_fails(self):
        self.close("state: closed")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("C-6 is closed without promotion.md", r.stdout)

    def test_closed_line_without_promotion_fails(self):
        self.close("closed: 2026-10-02")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("C-6 is closed without promotion.md", r.stdout)

    def test_closed_line_below_the_header_does_not_close(self):
        plan = self.d / "plan.md"
        plan.write_text(plan.read_text() + "\nclosed: 2026-10-02\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_closed_with_promotion_passes(self):
        self.close("closed: 2026-10-02")
        (self.d / "promotion.md").write_text("decision: promote\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_closed_cycle_before_any_demand_still_needs_promotion(self):
        shutil.rmtree(Path(self.p) / "specs" / "FWD-040")
        self.close("state: closed")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("C-6 is closed without promotion.md", r.stdout)

    def test_abandoned_cycle_without_promotion_passes(self):
        self.close("abandoned: 2026-10-02")
        self.assertEqual(self.gate().returncode, 0)

    def test_old_single_file_closed_cycle_is_never_affected(self):
        (Path(self.p) / "cycles" / "C-1.md").write_text(
            "objective: old\nclosed: 2026-09-01\n\n## Done when\n- [x] a\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)


class TestFileListsAreNulSeparated(unittest.TestCase):
    """B-12 (FWD-041): without -z git C-quotes a path with non-ASCII bytes
    or a tab ("src/a\\303\\247.py"); the quoted name matched no declared
    root and I1 read a behavior change as none."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def behavior_file(self, name):
        (self.p / "src").mkdir(exist_ok=True)
        (self.p / "src" / name).write_text("x = 1\n")

    def test_staged_non_ascii_behavior_path_is_seen(self):
        self.behavior_file("ação.py")
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--staged", "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("src/ação.py", r.stdout)

    def test_committed_tab_behavior_path_is_seen(self):
        (self.p / "tests").mkdir()
        (self.p / "tests" / "seed.py").write_text("assert True\n")
        commit_all(self.p, "eval seed")
        self.behavior_file("a\tb.py")
        commit_all(self.p, "behavior, no eval")
        r = verify(self.p, "--gate", "eval-coverage")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_i3_sees_a_non_ascii_behavior_path_beside_a_finding(self):
        self.behavior_file("ação.py")
        (self.p / "reviews" / "D-1").mkdir(parents=True)
        (self.p / "reviews" / "D-1" / "findings.toml").write_text(FINDINGS)
        commit_all(self.p, "finding and behavior together")
        r = verify(self.p, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("same commit", r.stdout)


class TestI1ReqsFrontDemandInTheCycleLayout(unittest.TestCase):
    """B-27 (FWD-041): a `front` demand of the cycle layout traces the
    plan criteria it meets (the ## Demands row's `meets`, or the spec's
    `meets:`) to evals/journeys/<id>/, as an old-layout design surface
    traces the R# of its acceptance.md."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def demand(self, layer="front", meets="A1, A2", spec_head=None, n=3):
        cycle_plan(self.p, n, [f"| DEM-9 | {layer} | — | x | {meets} |"])
        d = Path(self.p) / "specs" / "DEM-9-panel"
        d.mkdir(parents=True, exist_ok=True)
        head = spec_head if spec_head is not None \
            else f"cycle: C-{n} · layer: {layer} · meets: {meets}"
        (d / "spec.md").write_text(f"# DEM-9 — a panel\n\n{head}\n\nWhat.\n")
        return d

    def journey(self, reqs):
        TestI1RequirementCoverage._journeys(self, "DEM-9", reqs)

    def reqs_row(self):
        r = verify(self.p, "--gate", "eval-coverage", "--format", "json")
        rows = [g for g in json.loads(r.stdout)["gates"] if g["id"] == "I1-REQS"]
        return r, (rows[0] if rows else None)

    def test_red_when_a_met_criterion_has_no_journey(self):
        self.demand()
        self.journey(["A1"])
        r, row = self.reqs_row()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertFalse(row["passed"], row)
        self.assertIn("A2", row["detail"])

    def test_green_when_every_met_criterion_has_a_journey(self):
        self.demand()
        self.journey(["A1", "A2"])
        r, row = self.reqs_row()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(row["passed"], row)

    def test_plan_row_alone_links_a_spec_without_header_fields(self):
        self.demand(spec_head="")
        r, row = self.reqs_row()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("A1", str(row))

    def test_spec_meets_alone_counts(self):
        self.demand(meets="—", spec_head="cycle: C-3 · layer: front · meets: A4")
        r, row = self.reqs_row()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("A4", str(row))

    def test_back_demand_is_silent(self):
        self.demand(layer="back")
        _, row = self.reqs_row()
        self.assertIsNone(row)

    def test_ended_cycle_is_not_read(self):
        self.demand()
        plan = Path(self.p) / "cycles" / "C-3" / "plan.md"
        plan.write_text(plan.read_text().replace(
            "date: 2026-09-29", "date: 2026-09-29\nclosed: 2026-10-02"))
        _, row = self.reqs_row()
        self.assertIsNone(row)

    def test_old_layout_design_surface_is_unchanged(self):
        d = Path(self.p) / "specs" / "DEM-8"
        (d / "design").mkdir(parents=True)
        (d / "design" / "flow.md").write_text("# flow\n")
        (d / "acceptance.md").write_text("---\ndate: 2026-08-09\n---\nR1: x\n")
        r, row = self.reqs_row()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("R1", str(row))


class TestRunRecordPerTree(unittest.TestCase):
    """`--all` records its outcome in .fde/runs/<tree>.json; `--status`
    reads it back; recording never changes a gate result."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        commit_all(self.p, "init")

    def tearDown(self):
        self._tmp.cleanup()

    def tree(self) -> str:
        return git_out(self.p, "write-tree")

    def record(self) -> dict:
        path = self.p / ".fde" / "runs" / f"{self.tree()}.json"
        self.assertTrue(path.is_file(), path)
        return json.loads(path.read_text(encoding="utf-8"))

    def test_all_records_gates_timestamp_and_command(self):
        self.assertFalse((self.p / ".fde" / "runs").exists())
        r = verify(self.p, "--all", "--format", "json")
        rec = self.record()
        self.assertEqual(rec["tree"], self.tree())
        gate = rec["gate"]
        self.assertEqual(gate["passed"], r.returncode == 0)
        self.assertEqual(gate["gates"], json.loads(r.stdout)["gates"])
        self.assertIn("--all", gate["command"])
        self.assertRegex(gate["recorded_at"], r"^\d{4}-\d\d-\d\dT")

    def test_a_single_gate_run_records_nothing(self):
        verify(self.p, "--gate", "config")
        self.assertFalse((self.p / ".fde" / "runs").exists())

    def test_status_on_the_recorded_tree(self):
        verify(self.p, "--all")
        r = verify(self.p, "--status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(self.tree(), r.stdout)
        self.assertIn("gate:", r.stdout)
        self.assertNotIn("no record for this tree", r.stdout)

    def test_status_on_another_tree(self):
        verify(self.p, "--all")
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no record for this tree", r.stdout)
        j = verify(self.p, "--status", "--format", "json")
        self.assertEqual(j.returncode, 0)
        self.assertEqual(json.loads(j.stdout),
                         {"tree": self.tree(), "record": None})

    def test_status_json_is_the_record(self):
        verify(self.p, "--all")
        r = verify(self.p, "--status", "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["tree"], self.tree())
        self.assertEqual(out["record"], self.record())

    def test_record_suite_stores_exit_code_and_summary(self):
        # the fixture's configured test_command is `true`
        verify(self.p, "--all", "--record-suite")
        suite = self.record()["suite"]
        self.assertEqual(suite["exit_code"], 0)
        self.assertEqual(suite["command"], "true")
        verify(self.p, "--all", "--record-suite",
               "echo Ran 3 tests; echo 'FAILED (failures=1)'; exit 3")
        suite = self.record()["suite"]
        self.assertEqual(suite["exit_code"], 3)
        self.assertIn("FAILED (failures=1)", suite["summary"])
        self.assertIn("exit 3", verify(self.p, "--status").stdout)

    def test_a_gate_only_rerun_drops_the_earlier_suite_block(self):
        # F3 (DIRECT-2026-09-29-B): a record is one run, never two mixed
        verify(self.p, "--all", "--record-suite")
        self.assertIn("suite", self.record())
        verify(self.p, "--all")
        self.assertNotIn("suite", self.record())
        self.assertIn("suite: not recorded", verify(self.p, "--status").stdout)

    def test_gate_and_suite_of_one_invocation_share_a_run_id(self):
        verify(self.p, "--all", "--record-suite")
        rec = self.record()
        self.assertTrue(rec["gate"]["run_id"])
        self.assertEqual(rec["suite"]["run_id"], rec["gate"]["run_id"])

    def test_status_never_shows_a_suite_block_of_another_run(self):
        verify(self.p, "--all", "--record-suite", "echo MARK-OTHER-RUN")
        path = self.p / ".fde" / "runs" / f"{self.tree()}.json"
        rec = json.loads(path.read_text())
        rec["suite"]["run_id"] = "another-run"
        path.write_text(json.dumps(rec))
        out = verify(self.p, "--status").stdout
        self.assertNotIn("suite: exit", out)
        self.assertIn("suite: not recorded", out)

    def test_a_dirty_tree_is_recorded_as_dirty(self):
        # F2: untracked or unstaged files under the gate's paths
        verify(self.p, "--all")
        self.assertIs(self.record()["dirty"], False)
        self.assertNotIn("dirty tree", verify(self.p, "--status").stdout)
        (self.p / "src").mkdir()
        (self.p / "src" / "new.py").write_text("x = 1\n")        # untracked
        (self.p / "notes.txt").write_text("outside the gate's paths\n")
        verify(self.p, "--all")
        rec = self.record()
        self.assertIs(rec["dirty"], True)
        self.assertEqual(rec["dirty_paths"], ["src/new.py"])
        self.assertIn("dirty tree — rerun before relying on it",
                      verify(self.p, "--status").stdout)

    def test_an_unstaged_change_is_dirty(self):
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        commit_all(self.p, "src")
        (self.p / "src" / "a.py").write_text("x = 2\n")        # unstaged
        verify(self.p, "--all")
        self.assertEqual(self.record()["dirty_paths"], ["src/a.py"])

    def test_record_suite_without_all_is_refused(self):
        r = verify(self.p, "--record-suite")
        self.assertEqual(r.returncode, 2)

    def test_recording_never_changes_the_gate_result(self):
        base = verify(self.p, "--all", "--format", "json")
        again = verify(self.p, "--all", "--format", "json")
        suite_red = verify(self.p, "--all", "--format", "json",
                           "--record-suite", "exit 1")
        shutil.rmtree(self.p / ".fde" / "runs")
        (self.p / ".fde" / "runs").write_text("not a directory\n")
        blocked = verify(self.p, "--all", "--format", "json")
        for other in (again, suite_red, blocked):
            self.assertEqual(other.returncode, base.returncode)
            self.assertEqual(json.loads(other.stdout), json.loads(base.stdout))
        self.assertIn("not recorded", blocked.stderr)

    def test_status_reads_a_record_from_another_worktree(self):
        verify(self.p, "--all")
        wt = Path(self._tmp.name).parent / (Path(self._tmp.name).name + "-wt")
        run_git(self.p, "worktree", "add", "-q", "--detach", str(wt))
        self.addCleanup(shutil.rmtree, wt, ignore_errors=True)
        r = verify(wt, "--status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("recorded in", r.stdout)
        self.assertIn("gate:", r.stdout)

    def test_kernel_and_clients_gitignore_the_runs(self):
        self.assertIn(".fde/runs/", (ROOT / ".gitignore").read_text().splitlines())
        self.assertIn("`.fde/runs/`", (ROOT / "SETUP.md").read_text())

    def test_roles_read_the_record_instead_of_rerunning(self):
        def read(rel):
            return " ".join((ROOT / rel).read_text(encoding="utf-8").split())
        self.assertIn("`python3 bin/fde/verify.py --all --record-suite`",
                      read("agents/fde-implementation.md"))
        for rel in ("agents/fde-adversarial.md", "agents/fde-promotion.md"):
            self.assertIn("`python3 bin/fde/verify.py --status`", read(rel), rel)
        self.assertIn("`verify.py --status` prints the record for the current "
                      "tree", read("skills/fde-review/SKILL.md"))

    def test_a_missing_fde_directory_is_created(self):
        shutil.rmtree(self.p / ".fde")
        path = verify_mod.record_run(self.p, "0" * 40, gate={"passed": True})
        self.assertTrue(path.is_file())
        self.assertEqual(json.loads(path.read_text())["gate"], {"passed": True})


class TestDuplicateBacklogIds(unittest.TestCase):
    """A true duplicate is one `B-<n>` opening two item lines with different
    texts — in this tree's backlog.md, or between it and another worktree's
    or main's. An id merely seen in several places passes."""

    HEAD = "---\ngoal: g\ndate: 2026-09-29\n---\n# Backlog\n\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def backlog(self, root, *lines):
        (Path(root) / "backlog.md").write_text(self.HEAD + "\n".join(lines) + "\n")

    def gate(self, root=None):
        r = verify(root or self.p, "--gate", "backlog")
        rows = [l for l in r.stdout.splitlines() if "BL-IDS" in l]
        return r, "\n".join(rows)

    def test_a_duplicate_within_one_file_is_red(self):
        self.backlog(self.p, "- B-3 (C-1) opinion — the first thing",
                     "- B-3 (C-2) opinion — something else")
        r, row = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("B-3", row)
        self.assertIn("the first thing", row)
        self.assertIn("something else", row)

    def test_a_duplicate_across_two_worktrees_is_red(self):
        self.backlog(self.p, "- B-4 opinion — shared item")
        commit_all(self.p, "init")
        wt = Path(self._tmp.name).parent / (Path(self._tmp.name).name + "-wt")
        run_git(self.p, "worktree", "add", "-q", "--detach", str(wt))
        self.addCleanup(shutil.rmtree, wt, ignore_errors=True)
        self.backlog(wt, "- B-4 opinion — shared item",
                     "- B-5 opinion — assigned in the worktree")
        self.backlog(self.p, "- B-4 opinion — shared item",
                     "- B-5 opinion — assigned here too, differently")
        r, row = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("B-5", row)
        self.assertIn(f"worktree:{wt.resolve()}", row)
        self.assertIn("backlog.md", row)
        self.assertNotIn("B-4", row)

    def test_the_same_text_in_several_places_passes(self):
        self.backlog(self.p, "- B-6 (C-1) opinion — one item")
        commit_all(self.p, "init")
        wt = Path(self._tmp.name).parent / (Path(self._tmp.name).name + "-wt")
        run_git(self.p, "worktree", "add", "-q", "--detach", str(wt))
        self.addCleanup(shutil.rmtree, wt, ignore_errors=True)
        # grouped here, discarded there: the mark and the suffix are not text
        self.backlog(self.p, "- B-6 (C-1) opinion — one item → C-2")
        self.backlog(wt, "- B-6 (C-1) opinion — one item — discarded: done")
        r, row = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("✓", row)

    def test_a_condensed_title_is_the_same_item(self):
        # an item moved to a closing list keeps its opening words
        self.backlog(self.p, "- B-7 (C-1) opinion — split the parser so the "
                             "gate reads one file (…",
                     "- B-007 (C-1) opinion — split the parser so the gate "
                     "reads one file (non-ASCII paths) and reports it")
        r, row = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_prefix_inside_a_word_is_a_duplicate(self):
        # F1 (DIRECT-2026-09-29-B): `Fix` is not the opening of `Fixture…`
        self.backlog(self.p, "- B-12 Fix", "- B-12 Fixture cleanup")
        r, row = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("B-12", row)

    def test_a_short_prefix_is_a_duplicate(self):
        # two words are too few to call one title the other's shortening
        self.backlog(self.p, "- B-13 Add tests", "- B-13 Add tests for erosion")
        r, row = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("B-13", row)

    def test_same_item_rule(self):
        same = verify_mod.same_item
        self.assertTrue(same("Add tests now", "Add tests now for erosion"))
        self.assertTrue(same("Add tests now …", "Add tests now, for erosion"))
        self.assertTrue(same("one", "One."))
        self.assertFalse(same("Add tests now", "Add tests nowhere else"))
        self.assertFalse(same("Add tests", "Add tests for erosion"))
        self.assertFalse(same("Fix", "Fixture cleanup"))
        self.assertFalse(same("", "anything"))
        # a `…` cut mid-word: the whole words before it are the evidence
        self.assertTrue(same("so one red commit does not ke…",
                             "so one red commit does not keep runs red"))
        self.assertFalse(same("Fix…", "Fixture cleanup"))
        self.assertFalse(same("Add tests fo…", "Add tests for erosion"))

    def test_this_repository_stays_green(self):
        r = verify(ROOT, "--gate", "backlog")
        rows = [l for l in r.stdout.splitlines() if "BL-IDS" in l]
        self.assertFalse(any("✗" in l for l in rows), rows)

    def test_a_plan_items_mention_passes(self):
        self.backlog(self.p, "- B-8 (C-1) opinion — the item")
        d = Path(self.p) / "cycles" / "C-2"
        d.mkdir(parents=True)
        (d / "plan.md").write_text("state: draft\n\n## Items\n\n"
                                   "- B-8 the item, as the plan names it\n")
        r, row = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("✗", row)

    def test_a_table_row_is_an_item_line(self):
        self.backlog(self.p, "| B-9 | first | h | opinion | S |",
                     "| B-9 | second | h | opinion | S |")
        r, row = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("B-9", row)

    def test_a_table_rows_title_cell_is_its_item(self):
        # a short title closed as a list line is the same item as the table
        # row it came from: the row's other cells are not its title
        self.backlog(self.p, "| B-10 | Verification discipline → C-10 | five "
                             "factual errors | usage-data (S-005) | M |",
                     "- B-10 Verification discipline — discarded: no recurrence")
        r, row = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(verify_mod.backlog_items(
            "| B-10 | Verification discipline → C-10 | five | opinion | M |"),
            [("B-10", "Verification discipline")])


if __name__ == "__main__":
    unittest.main()


class TestRunRecordCarriesItsInstructions(unittest.TestCase):
    """A run is judged under the instructions it ran with: the record keeps
    the kernel version and one hash over the instruction files in reach,
    plugin included; --status says when they changed since."""

    setUp = TestRunRecordPerTree.setUp
    tearDown = TestRunRecordPerTree.tearDown
    tree = TestRunRecordPerTree.tree
    record = TestRunRecordPerTree.record

    def _fp(self, env=None):
        import importlib
        import os
        sys.path.insert(0, str(ROOT / "runtime"))
        import verify as v
        importlib.reload(v)
        old = os.environ.get("CLAUDE_PLUGIN_ROOT")
        try:
            if env is None:
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            else:
                os.environ["CLAUDE_PLUGIN_ROOT"] = env
            return v.instructions_fingerprint(self.p)
        finally:
            if old is None:
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
            else:
                os.environ["CLAUDE_PLUGIN_ROOT"] = old

    def test_the_record_names_kernel_version_and_hash(self):
        verify(self.p, "--all")
        ins = self.record()["instructions"]
        self.assertEqual(ins["kernel_version"], self._fp()["kernel_version"])
        self.assertRegex(ins["sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(ins["files"], 0)

    def test_an_edited_instruction_changes_the_hash_and_status_says_so(self):
        verify(self.p, "--all")
        before = self._fp()["sha256"]
        skill = self.p / ".claude" / "skills" / "fde-x" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("One more rule.\n")
        self.assertNotEqual(self._fp()["sha256"], before)
        r = verify(self.p, "--status")
        self.assertIn("instructions: kernel", r.stdout)
        self.assertIn("CHANGED since this run", r.stdout)

    def test_a_plugin_root_is_part_of_the_hash(self):
        with tempfile.TemporaryDirectory() as plugin:
            (Path(plugin) / "skills" / "fde-x").mkdir(parents=True)
            (Path(plugin) / "skills" / "fde-x" / "SKILL.md").write_text("a\n")
            with_plugin = self._fp(plugin)
            self.assertEqual(with_plugin["plugin_root"], plugin)
            self.assertNotEqual(with_plugin["sha256"], self._fp()["sha256"])
            (Path(plugin) / "skills" / "fde-x" / "SKILL.md").write_text("b\n")
            self.assertNotEqual(self._fp(plugin)["sha256"], with_plugin["sha256"])


class TestC4Gates(unittest.TestCase):
    """0.29 gates from the auris C-4 exercise (owner direction 2026-09-30),
    each calibrated on auris, headlabs-platform and the forward before it
    was armed: records outside git, long backlog lines, stale doc paths,
    the close's docs line, and running cycles on the same files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)
        commit_all(self.p, "init")

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self, name, *extra):
        r = verify(self.p, "--gate", name, "--format", "json", *extra)
        return r.returncode, json.loads(r.stdout)["gates"]

    def test_an_untracked_review_fails_and_an_untracked_spec_warns(self):
        (self.p / "reviews" / "D-1").mkdir(parents=True)
        (self.p / "reviews" / "D-1" / "findings.toml").write_text("x = 1\n")
        (self.p / "specs" / "D-2").mkdir(parents=True)
        (self.p / "specs" / "D-2" / "spec.md").write_text("draft\n")
        code, gates = self.gate("untracked")
        self.assertEqual(code, 1)
        fail = [g for g in gates if not g["passed"]]
        warn = [g for g in gates if g.get("warning")]
        self.assertIn("reviews/D-1/findings.toml", fail[0]["detail"])
        self.assertIn("specs/D-2/spec.md", warn[0]["detail"])
        run_git(self.p, "add", "-A")
        commit_all(self.p, "records")
        self.assertEqual(self.gate("untracked")[0], 0)

    def _backlog(self, *items):
        (self.p / "backlog.md").write_text(
            "goal: x\ndate: 2026-09-30\n\n## Backlog\n\n" + "".join(f"{i}\n" for i in items))

    def test_a_new_long_backlog_line_fails_an_old_one_does_not(self):
        long = "- B-9 " + " ".join(["word"] * 70)
        self._backlog(long)
        commit_all(self.p, "old long line")
        self._backlog(long, "- B-10 a short line with a pointer to docs/vision.md")
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--staged")
        self.assertNotIn("BL-LEN", [l for l in r.stdout.splitlines() if "✗" in l][0:1] or [""])
        self._backlog(long, "- B-11 " + " ".join(["detail"] * 61))
        run_git(self.p, "add", "-A")
        r = verify(self.p, "--staged")
        self.assertIn("B-11", r.stdout)
        self.assertNotEqual(r.returncode, 0)
        code, gates = self.gate("backlog-length")
        self.assertEqual(code, 1)
        self.assertIn("B-9", gates[0]["detail"])

    def test_the_word_ceiling_is_configurable(self):
        cfg = self.p / "fde.config.toml"
        cfg.write_text(cfg.read_text() + "\n[backlog]\nmax_item_words = 100\n")
        self._backlog("- B-11 " + " ".join(["detail"] * 80))
        run_git(self.p, "add", "-A")
        self.assertEqual(self.gate("backlog-length")[0], 0)

    def test_a_stale_doc_path_warns_and_concepts_and_routes_do_not(self):
        (self.p / "src").mkdir(exist_ok=True)
        (self.p / "src" / "a.py").write_text("x = 1\n")
        (self.p / "CLAUDE.md").write_text(
            "See `src/a.py`, `src/gone.py`, `plan.md`, `owner/repo`, the `/login` route.\n")
        code, gates = self.gate("doc-refs")
        self.assertEqual(code, 0)
        self.assertTrue(gates[0].get("warning"))
        self.assertIn("src/gone.py", gates[0]["detail"])
        for fp in ("src/a.py", "plan.md", "owner/repo", "/login"):
            self.assertNotIn(fp + ",", gates[0]["detail"] + ",".replace(fp, ""))

    def _closed_cycle(self, date, docs):
        d = self.p / "cycles" / "C-1"
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.md").write_text("cycle: C-1\nstate: closed\ndate: 2026-09-20\n")
        (d / "promotion.md").write_text(
            f"cycle: C-1\ndate: {date}\ndecision: promote\n" + (f"docs: {docs}\n" if docs else ""))

    def test_a_close_from_the_rule_date_needs_its_docs_line(self):
        self._closed_cycle("2026-10-02", None)
        self.assertEqual(self.gate("docs")[0], 1)
        self._closed_cycle("2026-10-02", "none")
        self.assertEqual(self.gate("docs")[0], 0)
        self._closed_cycle("2026-09-30", None)
        self.assertEqual(self.gate("docs")[0], 0)

    def _running(self, cid, files, depends=""):
        d = self.p / "cycles" / cid
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.md").write_text(
            f"cycle: {cid}\nstate: running\ndate: 2026-09-30\n{depends}"
            "signed-off: 2026-09-30\n\n## Demands\n\n"
            "| id | layer | depends on | files | what | meets | follows |\n"
            "|---|---|---|---|---|---|---|\n"
            f"| {cid.replace('C-', 'D-')}01 | back | — | {files} | x | A1 | — |\n")

    def test_running_cycles_on_the_same_files_fail_unless_one_depends(self):
        self._running("C-1", "src/a.py")
        self._running("C-2", "src/a.py")
        code, gates = self.gate("cycles")
        self.assertEqual(code, 1)
        self.assertIn("src/a.py", gates[0]["detail"])
        self._running("C-2", "src/a.py", depends="depends: C-1\n")
        self.assertEqual(self.gate("cycles")[0], 0)
        self._running("C-2", "src/b.py")
        self.assertEqual(self.gate("cycles")[0], 0)

    def test_the_new_gates_are_known_names(self):
        for name in ("untracked", "backlog-length", "process-dup", "doc-refs",
                     "docs", "cycles"):
            r = verify(self.p, "--gate", name)
            self.assertNotIn("unknown gate", r.stdout + r.stderr, name)
