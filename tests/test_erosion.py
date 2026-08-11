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
from support import commit_all, make_project, run_git, verify  # noqa: E402


class TestPureCores(unittest.TestCase):
    def test_numstat_sums_and_skips_binary(self):
        text = "12\t3\tsrc/a.py\n-\t-\tlogo.png\n5\t0\tsrc/b.py\n"
        self.assertEqual(erosion.parse_numstat(text), (17, 3, 2))

    def test_quoted_paths_are_not_silently_dropped(self):
        # git quotes a path with non-ASCII bytes; left quoted it matches
        # no declared root and its churn disappears (FWD-016 F3)
        self.assertEqual(erosion.numstat_path(r'"src/caf\303\251.py"'),
                         "src/café.py")
        text = "10\t0\t" + r'"src/caf\303\251.py"' + "\n"
        self.assertEqual(erosion.parse_numstat(text, ("src/",)), (10, 0, 1))

    def test_renamed_paths_resolve_to_where_the_file_now_is(self):
        # both rename spellings; unresolved, they escape scope AND
        # exclusions (FWD-016 F4)
        self.assertEqual(erosion.numstat_path("runtime/{old => new}/f.py"),
                         "runtime/new/f.py")
        self.assertEqual(erosion.numstat_path("old.py => src/new.py"),
                         "src/new.py")
        self.assertEqual(erosion.numstat_path("src/{a => }/f.py"), "src/f.py")
        # a rename INTO an excluded copy is excluded on its new path
        self.assertFalse(erosion.in_churn_scope(
            erosion.numstat_path("runtime/{x => y}/f.py"), ("runtime/",),
            ("runtime/y/",)))

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
        breaches, _ = erosion.check_budget(metrics, {"max_add_delete_ratio": 6.0})
        self.assertEqual(len(breaches), 1)
        # duplication under budget → no flag; deps not declared → not checked
        self.assertEqual(erosion.check_budget(
            metrics, {"max_duplication_pct": 5.0}), ([], []))

    def test_a_threshold_that_measured_nothing_is_not_a_pass(self):
        # FWD-016 F10: None used to be skipped and the gate printed
        # "within budget" — a green over an empty measurement
        breaches, unmeasured = erosion.check_budget(
            {"add_delete_ratio": None}, {"max_add_delete_ratio": 1.0})
        self.assertEqual(breaches, [])
        self.assertEqual(unmeasured, ["add/delete ratio"])
        self.assertIn("not measured", erosion.verdict(breaches, unmeasured))
        self.assertNotIn("within the declared", erosion.verdict(breaches, unmeasured))


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
                                     {"max_add_delete_ratio": "lots"}), ([], []))


class TestChurnScope(unittest.TestCase):
    """FWD-016: churn is measured over the roots the project DECLARED —
    not over everything, not over a scope invented for this metric, and
    not over defaults the project never asked for.

    The fixture deliberately declares roots that are NOT in
    DEFAULT_BEHAVIOR_PATHS. An implementation that ignored the config and
    fell back to the defaults would pass a fixture built on `src/`; it
    cannot pass this one.
    """

    ROOT_A, ROOT_B = "kernel/", "checks/"   # neither is a kernel default

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name, behavior=f'["{self.ROOT_A}"]',
                              evals=f'["{self.ROOT_B}"]')
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def commit(self, rel, lines):
        f = Path(self.p) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("\n".join(f"line {i}" for i in range(lines)) + "\n")
        commit_all(self.p, f"add {rel}")

    def test_scope_is_the_declaration_not_the_defaults(self):
        scope = erosion.churn_scope(Path(self.p))
        self.assertEqual(set(scope), {self.ROOT_A, self.ROOT_B})
        for default in ("src/", "lib/", "app/"):
            self.assertNotIn(default, scope)
        # and it is honored, not merely returned
        self.commit("src/a.py", 300)          # a default root, undeclared here
        self.assertIsNone(erosion.measure(Path(self.p))["add_delete_ratio"])
        self.commit(self.ROOT_A + "a.py", 300)
        self.assertIsNotNone(erosion.measure(Path(self.p))["add_delete_ratio"])

    def test_the_audit_trail_does_not_read_as_accretion(self):
        # 500 lines of findings and specs, never deleted, must not move
        # the ratio — an append-only record is not decay
        self.commit("reviews/D-1/findings.toml", 250)
        self.commit("specs/D-1/spec.md", 250)
        m = erosion.measure(Path(self.p))
        self.assertIsNone(m["add_delete_ratio"])   # nothing in scope changed
        self.assertEqual(m["churn_rows"], 0)

    def test_code_growth_does_move_the_ratio(self):
        self.commit(self.ROOT_A + "a.py", 300)
        m = erosion.measure(Path(self.p))
        self.assertIsNotNone(m["add_delete_ratio"])
        self.assertGreater(m["added"], 200)

    def test_only_paths_the_project_declared_generated_are_excluded(self):
        # the kernel does not carry a hardcoded list that un-declares
        # roots the config declares as behavior (FWD-016 F5/F7)
        self.assertTrue(erosion.in_churn_scope("bin/fde/verify.py", ("bin/",)))
        self.assertFalse(erosion.in_churn_scope("bin/fde/verify.py", ("bin/",),
                                                ("bin/fde/",)))
        # …and the declaration is read from the config, not assumed
        self.assertEqual(erosion.generated_paths(Path(self.p)), ())
        cfg = Path(self.p) / "fde.config.toml"
        cfg.write_text(cfg.read_text() +
                       '\n[erosion]\ngenerated_paths = ["mirror/"]\n')
        self.assertEqual(erosion.generated_paths(Path(self.p)), ("mirror/",))

    def test_vendor_trees_are_nobody_s_code_in_any_project(self):
        # the only hardcoded exclusion, and it excludes code the project
        # did not write
        self.assertFalse(erosion.in_churn_scope("node_modules/x/i.js", None))
        self.assertTrue(erosion.in_churn_scope("anything/x.py", None))

    def test_no_gate_section_means_measure_everything(self):
        # R2: a project that declared nothing is measured whole, never
        # narrowed to defaults it never asked for (FWD-016 F1)
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(erosion.churn_scope(Path(t)))         # no config
            cfg = Path(t) / "fde.config.toml"
            cfg.write_text('[project]\nname = "x"\n')             # no [gate]
            self.assertIsNone(erosion.churn_scope(Path(t)))
            self.assertTrue(erosion.in_churn_scope("whatever/x.py", None))
            cfg.write_text('[project]\nname = "x"\n[gate]\n')    # empty [gate]
            self.assertIsNone(erosion.churn_scope(Path(t)))

    def test_one_population_for_both_metrics(self):
        # acceptance.md's "one definition of the codebase, used by every
        # metric": the duplication scan reads the churn population, and
        # says how many tracked code files it left out
        self.commit("reviews/D-1/findings.toml", 40)
        self.commit(self.ROOT_A + "a.py", 40)
        m = erosion.measure(Path(self.p))
        self.assertEqual(m["files_scanned"], 1)      # only kernel/a.py
        self.assertGreaterEqual(m["files_excluded"], 1)   # the findings file

    def test_a_root_that_matches_no_tracked_file_is_named_not_silent(self):
        # FWD-016 F1/F10: a stale or misspelled root measures nothing and
        # used to report "within the declared erosion budget". It is not
        # walled (a greenfield root looks identical from outside) but the
        # gate must never claim a green it did not measure, and must name
        # the declaration that produced the silence.
        cfg = Path(self.p) / "fde.config.toml"
        cfg.write_text(cfg.read_text().replace(
            f'["{self.ROOT_A}"]', '["kernle/"]')        # typo, on purpose
            + "\n[erosion]\nmax_add_delete_ratio = 12.0\n")
        self.commit(self.ROOT_A + "a.py", 300)
        self.assertIn("kernle/", erosion.measure(Path(self.p))["stale_roots"])
        r = verify(self.p, "--gate", "erosion")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("kernle/", r.stdout)
        self.assertIn("not measured", r.stdout)
        self.assertNotIn("within the declared erosion budget", r.stdout)

    def test_a_quoted_filename_is_measured_and_does_not_fake_a_stale_root(self):
        # against what git actually emits, not a synthetic string: both
        # `ls-files` and `--numstat` C-quote a non-ASCII path. Quoted, the
        # file vanishes from the duplication scan and its own declared
        # root reads as matching nothing (FWD-016 F3)
        self.commit(self.ROOT_A + "avaliação.py", 100)
        m = erosion.measure(Path(self.p))
        self.assertNotIn(self.ROOT_A, m["stale_roots"])   # kernel/ is not stale
        self.assertGreaterEqual(m["files_scanned"], 1)
        self.assertGreaterEqual(m["added"], 100)     # its churn is counted

    def test_a_rename_is_attributed_to_where_the_file_landed(self):
        # `git mv` into an undeclared root: real git output, real scope
        self.commit(self.ROOT_A + "old.py", 60)
        run_git(self.p, "mv", self.ROOT_A + "old.py", "attic_old.py")
        commit_all(self.p, "move out of the declared root")
        rows = erosion._git(Path(self.p), "log", "-1", "--numstat", "--format=")
        self.assertIn(" => ", rows)                  # git really emits this
        self.assertEqual(erosion.parse_numstat(rows, (self.ROOT_A,))[2], 0)

    def test_a_root_declared_as_a_string_is_not_a_scope_of_characters(self):
        # tuple("src/") == ('s','r','c','/') — a scope matching nothing
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "fde.config.toml").write_text(
                '[project]\nname = "x"\n[gate]\nbehavior_paths = "src/"\n')
            self.assertIsNone(erosion.churn_scope(Path(t)))
            self.assertTrue(erosion.in_churn_scope("src/a.py", None))

    def test_the_report_states_the_population_it_measured(self):
        # R3: both halves — the roots included AND the copies excluded
        cfg = Path(self.p) / "fde.config.toml"
        cfg.write_text(cfg.read_text() +
                       '\n[erosion]\ngenerated_paths = ["mirror/"]\n')
        commit_all(self.p, "declare the mirror")
        lines = "\n".join(erosion.population_lines(erosion.measure(Path(self.p))))
        self.assertIn(self.ROOT_A, lines)
        self.assertIn("mirror/", lines)
        self.assertIn("generated_paths", lines)

    def test_an_unmeasured_population_says_so(self):
        # F10: nothing in scope changed — the report must not read as a
        # measured zero
        self.commit("docs/readme.md", 20)
        lines = "\n".join(erosion.population_lines(erosion.measure(Path(self.p))))
        self.assertIn("NOT measured", lines)


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
        # churn must be IN the declared roots to count (FWD-016): the
        # seed commit is config and mirrors, so add code first
        src = Path(self.p) / "src"
        src.mkdir(exist_ok=True)
        (src / "a.py").write_text("x = 1\n" * 40)
        commit_all(self.p, "code growth")
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

    def test_generated_paths_is_a_list_of_paths_not_a_number(self):
        # the one non-numeric key: a typo'd exclusion must not pass as a
        # threshold, and a threshold must not pass as an exclusion
        self._add_erosion('generated_paths = "bin/fde/"\n')
        r = verify(self.p, "--gate", "config")
        self.assertEqual(r.returncode, 1)
        self.assertIn("generated_paths", r.stdout)

    def test_a_declared_list_of_generated_paths_is_accepted(self):
        self._add_erosion('generated_paths = ["bin/fde/", ".fde/"]\n')
        r = verify(self.p, "--gate", "config")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_budget_over_a_population_it_never_measured_says_so(self):
        # FWD-016 F10: the fixture's declared root is untouched by the
        # window, so the threshold has nothing to check — it passes, but
        # it must not print "within the declared erosion budget"
        self._add_erosion("max_add_delete_ratio = 1.0\n")
        commit_all(self.p, "config only")
        r = verify(self.p, "--gate", "erosion")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("not measured", r.stdout)


if __name__ == "__main__":
    unittest.main()
