"""FM-1/R1/R2: the gate as subprocess, on fixture projects."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
