"""FWD-019 / ADR-0015: RULE, a lane below XS — the pure eligibility core
(no git), the git-aware wrapper, and the live `rule-lane` gate that
re-verifies every self-declared claim against what was ACTUALLY
committed, never against the claim itself (FM-2) and never against a
bundled range's aggregate diff (FM-8). I1's `gate_eval_coverage` is not
touched anywhere in this suite — that is enforced by direct inspection
(R6), not by a test that could itself be gamed.

reviews/FWD-019 round 1 (F1/F2/F4): three cases where a commit's real
diff cannot be MECHANICALLY known — a binary file, a merge commit, a git
subprocess failure — must never read as "0 lines, eligible". Every repro
below runs against the real `triage` module and a real git repository
(never a mock), matching how the review itself reproduced each finding."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import triage  # noqa: E402
from support import commit_all, git_out, make_project, run_git, verify  # noqa: E402
import quietgit  # noqa: E402,F401  (git maintenance off in test repos)

EVAL_PATHS = ("evals/", "tests/")


def _write(project, rel, lines):
    f = Path(project) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(f"line {i}" for i in range(lines)) + "\n")


def _binary_bytes(n: int) -> bytes:
    """`n` bytes GUARANTEED to trip git's binary-file sniffing (a leading
    NUL byte) — plain `os.urandom(n)` is not reliable for small `n`: with
    only ~200 random bytes there is a real chance none of them is a NUL,
    and git then treats the file as text."""
    return b"\x00" + os.urandom(max(n - 1, 0))


class TestPureCore(unittest.TestCase):
    """R1: no git, no filesystem. `check_eligibility` takes only the two
    already-declared project-level values, a commit's own per-file
    (path, added, deleted) numstat, and the project's declared
    eval_paths — never git, never the score formula's estimated inputs."""

    def test_a_genuinely_trivial_diff_is_eligible(self):
        files = [("README.md", 3, 1)]   # a comment/text fix, 4 lines
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertTrue(elig.eligible, elig.detail)
        self.assertIsNone(elig.criterion)
        self.assertEqual(elig.size, 4)

    def test_internal_data_class_also_clears_the_ceiling(self):
        files = [("a.py", 1, 0)]
        elig = triage.check_eligibility("internal", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertTrue(elig.eligible)

    def test_exceeding_the_declared_threshold_is_ineligible(self):
        # (2) ineligible PURELY from the loc threshold — nothing else varies
        files = [("a.py", 6, 5)]   # 11 lines
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "loc")

    def test_a_diff_exactly_at_the_threshold_is_ineligible(self):
        # R1(c): STRICTLY under the threshold — equal does not qualify
        files = [("a.py", 5, 5)]   # exactly 10
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "loc")

    def test_sensitive_data_class_blocks_even_a_one_line_diff(self):
        # (3) the project-level ceiling stops it, not the (tiny) size
        files = [("a.py", 1, 0)]
        elig = triage.check_eligibility("financial", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "data_class")

    def test_irreversible_project_blocks_even_a_one_line_diff(self):
        files = [("a.py", 1, 0)]
        elig = triage.check_eligibility("public", "irreversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "reversibility")

    def test_project_level_ceiling_is_checked_before_loc_size(self):
        # a diff that would ALSO fail on size still reports the
        # project-level criterion — proving the order, not just the verdict
        files = [("a.py", 50, 50)]
        elig = triage.check_eligibility("personal", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertEqual(elig.criterion, "data_class")

    def test_eval_paths_file_deleted_blocks_even_under_the_threshold(self):
        # (4) ineligible from a deleted eval_paths file, size well under 10
        files = [("tests/test_x.py", 0, 5)]
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "eval_paths")

    def test_eval_paths_file_shrunk_blocks_even_under_the_threshold(self):
        files = [("evals/journeys/x.toml", 1, 3)]   # deleted > added
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "eval_paths")

    def test_eval_paths_file_growing_is_not_a_shrink(self):
        files = [("tests/test_x.py", 5, 1)]   # net growth
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertTrue(elig.eligible)

    def test_a_file_outside_eval_paths_shrinking_does_not_trip_the_check(self):
        files = [("src/a.py", 0, 3)]   # not under tests/ or evals/
        elig = triage.check_eligibility("public", "reversible", files,
                                        EVAL_PATHS, rule_lane_max_loc=10)
        self.assertTrue(elig.eligible)

    def test_declares_rule_checks_only_the_first_line_convention(self):
        self.assertTrue(triage.declares_rule("FORWARD: RULE — fix a typo"))
        self.assertFalse(triage.declares_rule("FORWARD: M — spec + impl"))
        self.assertFalse(triage.declares_rule("a commit that just mentions RULE"))

    # -- F1/F2: is_merge/is_binary are mechanical-uncertainty short-      --
    # -- circuits, checked right after the two project-level axes and    --
    # -- before loc/eval_paths (reviews/FWD-019 round 1) -----------------
    def test_merge_flag_is_ineligible_regardless_of_files(self):
        elig = triage.check_eligibility("public", "reversible", [],
                                        EVAL_PATHS, rule_lane_max_loc=10,
                                        is_merge=True)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "merge")

    def test_binary_flag_is_ineligible_regardless_of_a_small_loc_sum(self):
        # loc alone would pass (1 line) — is_binary must still block it
        elig = triage.check_eligibility("public", "reversible",
                                        [("a.py", 1, 0)], EVAL_PATHS,
                                        rule_lane_max_loc=10, is_binary=True)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "binary")

    def test_project_level_ceiling_is_checked_before_merge_and_binary(self):
        # the project-level axes still take precedence, matching the
        # existing data_class-before-loc ordering test above
        elig = triage.check_eligibility("financial", "reversible", [],
                                        EVAL_PATHS, rule_lane_max_loc=10,
                                        is_merge=True)
        self.assertEqual(elig.criterion, "data_class")
        elig = triage.check_eligibility("public", "irreversible", [],
                                        EVAL_PATHS, rule_lane_max_loc=10,
                                        is_binary=True)
        self.assertEqual(elig.criterion, "reversibility")


class TestGitWrapper(unittest.TestCase):
    """The git-aware wrapper (R2): one commit's OWN numstat, resolved via
    erosion.numstat_path (MNT-11), and the declared project config."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def test_commit_files_reflects_the_real_numstat(self):
        _write(self.p, "src/a.py", 4)
        sha = commit_all(self.p, "add a.py")
        self.assertEqual(triage.commit_files(Path(self.p), sha),
                         [("src/a.py", 4, 0)])

    def test_eligibility_for_commit_reads_the_declared_config(self):
        _write(self.p, "src/a.py", 3)
        sha = commit_all(self.p, "FORWARD: RULE — tiny add")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertTrue(elig.eligible, elig.detail)

    def test_eval_paths_shrink_through_a_real_commit(self):
        _write(self.p, "tests/test_x.py", 8)
        commit_all(self.p, "add a test")
        (Path(self.p) / "tests" / "test_x.py").write_text("line 0\n")
        sha = commit_all(self.p, "FORWARD: RULE — trim the test")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "eval_paths")


class TestMechanicalUncertaintyDefaultsToNever(unittest.TestCase):
    """reviews/FWD-019 round 1, F1/F2/F4: a binary file, a merge commit,
    and a git subprocess failure each make a commit's real diff
    mechanically unknowable — none of the three may read as "0 lines,
    eligible". Every repro here runs against a real git repository and
    the real `triage` module, exactly as the review itself reproduced
    each finding (never a mock)."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    # -- F1: binary files must not be silently invisible -----------------
    def test_binary_file_deleted_under_eval_paths_is_not_silently_invisible(self):
        # matches the review's own reproduction: a golden fixture blob
        # committed, then deleted, tagged RULE
        binpath = Path(self.p) / "tests" / "golden_snapshot.bin"
        binpath.parent.mkdir(parents=True, exist_ok=True)
        binpath.write_bytes(_binary_bytes(5000))
        commit_all(self.p, "add golden snapshot")
        binpath.unlink()
        sha = commit_all(self.p, "FORWARD: RULE — drop stale fixture")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertFalse(elig.eligible, elig.detail)
        self.assertEqual(elig.criterion, "binary")

    def test_binary_file_added_outside_eval_paths_also_blocks(self):
        # the chosen fix is categorical (F1): ANY binary row makes the
        # whole commit ineligible, not only rows under eval_paths — a
        # binary file's added/deleted is uncomputable either way, so
        # R1(c)'s loc sum cannot be certified regardless of which path
        # the file lives under
        binpath = Path(self.p) / "src" / "asset.bin"
        binpath.parent.mkdir(parents=True, exist_ok=True)
        binpath.write_bytes(_binary_bytes(200))
        sha = commit_all(self.p, "FORWARD: RULE — add a tiny asset")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertFalse(elig.eligible, elig.detail)
        self.assertEqual(elig.criterion, "binary")

    def test_commit_files_still_reports_binary_rows_as_absent_numerically(self):
        # commit_files()'s own contract is unchanged (numeric rows only)
        # — the presence signal lives in _has_binary_row, checked
        # separately by eligibility_for_commit
        binpath = Path(self.p) / "src" / "asset.bin"
        binpath.parent.mkdir(parents=True, exist_ok=True)
        binpath.write_bytes(_binary_bytes(200))
        sha = commit_all(self.p, "add a binary asset")
        self.assertEqual(triage.commit_files(Path(self.p), sha), [])

    # -- F2: merge commits must not be invisible --------------------------
    def test_merge_commit_is_categorically_ineligible(self):
        # matches the review's own reproduction: a real `git merge --no-ff`
        # bringing in hundreds of lines, tagged RULE
        orig_branch = git_out(self.p, "symbolic-ref", "--short", "HEAD")
        run_git(self.p, "checkout", "-q", "-b", "feature")
        _write(self.p, "src/big.py", 500)
        commit_all(self.p, "big feature work")
        run_git(self.p, "checkout", "-q", orig_branch)
        run_git(self.p, "merge", "--no-ff", "-q", "feature",
               "-m", "FORWARD: RULE — trivial merge")
        merge_sha = git_out(self.p, "rev-parse", "HEAD")
        # commit_files() itself reports nothing for a merge — no -m/-c
        self.assertEqual(triage.commit_files(Path(self.p), merge_sha), [])
        self.assertTrue(triage.is_merge_commit(Path(self.p), merge_sha))
        elig = triage.eligibility_for_commit(Path(self.p), merge_sha)
        self.assertFalse(elig.eligible, elig.detail)
        self.assertEqual(elig.criterion, "merge")

    def test_an_ordinary_single_parent_commit_is_not_flagged_as_a_merge(self):
        _write(self.p, "src/a.py", 3)
        sha = commit_all(self.p, "FORWARD: RULE — ordinary commit")
        self.assertFalse(triage.is_merge_commit(Path(self.p), sha))

    # -- F4: git failures must not read as "genuinely zero" ---------------
    def test_git_helper_raises_a_distinguishable_failure_on_a_bad_sha(self):
        bad_sha = "deadbeef" * 5
        with self.assertRaises(triage.GitFailure):
            triage.commit_files(Path(self.p), bad_sha)
        with self.assertRaises(triage.GitFailure):
            triage.is_merge_commit(Path(self.p), bad_sha)

    def test_eligibility_for_commit_reads_a_git_failure_as_ineligible(self):
        bad_sha = "deadbeef" * 5
        elig = triage.eligibility_for_commit(Path(self.p), bad_sha)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "git_failure")
        self.assertNotIn("eligible — 0 line", elig.detail)


class TestFallbackDefault(unittest.TestCase):
    """(7) the `10`-line fallback applies when [triage].rule_lane_max_loc
    is absent from the config — never a crash, never a silently disabled
    check."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)   # rule_lane_max_loc omitted
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def test_default_ten_applies_when_the_key_is_absent(self):
        _write(self.p, "src/a.py", 9)   # under the undeclared default
        sha = commit_all(self.p, "FORWARD: RULE — small tweak")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertTrue(elig.eligible, elig.detail)

    def test_default_ten_blocks_at_the_boundary_when_the_key_is_absent(self):
        _write(self.p, "src/a.py", 10)   # exactly the undeclared default
        sha = commit_all(self.p, "FORWARD: RULE — not actually small")
        elig = triage.eligibility_for_commit(Path(self.p), sha)
        self.assertFalse(elig.eligible)
        self.assertEqual(elig.criterion, "loc")


class TestReport(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def test_report_is_never_silent_even_with_nothing_declared(self):
        data = triage.report(Path(self.p), window=10)
        self.assertEqual(data["declared_rule"], 0)
        self.assertEqual(data["passed"], 0)
        self.assertEqual(data["would_have_blocked"], 0)
        self.assertIsInstance(data["commits_examined"], int)

    def test_report_counts_declared_passed_and_blocked(self):
        f = Path(self.p) / "src" / "a.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n" * 3)
        commit_all(self.p, "FORWARD: RULE — small add")
        f.write_text(f.read_text() + "\n".join(f"y = {i}" for i in range(30)))
        commit_all(self.p, "FORWARD: RULE — actually big")
        data = triage.report(Path(self.p), window=10)
        self.assertEqual(data["declared_rule"], 2)
        self.assertEqual(data["passed"], 1)
        self.assertEqual(data["would_have_blocked"], 1)
        self.assertEqual(len(data["blocked"]), 1)


class TestGate(unittest.TestCase):
    """The live `rule-lane` gate (R3), run as the real CI/full-gate
    subprocess would run it — `verify.py`, not a call into `Gate`
    directly, so a wiring mistake in `main()`'s dispatch would fail
    these too."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name, rule_lane_max_loc=10)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def test_gate_is_silent_by_default_with_no_rule_commit(self):
        # (6) silent (no report row) under the default unscoped run when
        # nothing in range declares RULE — asserted on the row's absence,
        # not on the whole run's exit code (the bare fixture does not
        # satisfy every OTHER gate's on-disk structure, and this test is
        # only about rule-lane's own silence, matching how every other
        # gate in this suite is exercised via --gate <id>)
        _write(self.p, "src/a.py", 3)
        commit_all(self.p, "ordinary commit, no RULE claim")
        r = verify(self.p)   # default full-gate run: --gate not given
        self.assertNotIn("RULE-LANE", r.stdout)

    def test_gate_reports_an_explicit_pass_when_directly_invoked(self):
        # (6) explicit only under --gate rule-lane directly
        _write(self.p, "src/a.py", 3)
        commit_all(self.p, "ordinary commit, no RULE claim")
        r = verify(self.p, "--gate", "rule-lane")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("no commit in range claims RULE", r.stdout)

    def test_gate_passes_a_genuinely_eligible_declared_commit(self):
        _write(self.p, "src/a.py", 4)
        commit_all(self.p, "FORWARD: RULE — trivial fix")
        r = verify(self.p, "--gate", "rule-lane")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("re-verified", r.stdout)

    def test_gate_blocks_a_falsely_tagged_commit_exceeding_loc(self):
        # (5) the live re-verification: claimed RULE, actual diff too big
        _write(self.p, "src/a.py", 40)
        commit_all(self.p, "FORWARD: RULE — actually not small")
        r = verify(self.p, "--gate", "rule-lane")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loc", r.stdout)

    def test_gate_blocks_a_falsely_tagged_commit_shrinking_eval_paths(self):
        _write(self.p, "tests/test_x.py", 8)
        commit_all(self.p, "seed a test")
        (Path(self.p) / "tests" / "test_x.py").write_text("line 0\n")
        commit_all(self.p, "FORWARD: RULE — trim the test")
        r = verify(self.p, "--gate", "rule-lane", "--since", "HEAD~2")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("eval_paths", r.stdout)

    def test_gate_blocks_when_the_project_level_ceiling_fails(self):
        with tempfile.TemporaryDirectory() as t2:
            p2 = make_project(t2, data_class="financial", security=16,
                              rule_lane_max_loc=10)
            run_git(p2, "add", "-A")
            run_git(p2, "commit", "-q", "-m", "seed")
            _write(p2, "src/a.py", 1)
            commit_all(p2, "FORWARD: RULE — tiny, but a sensitive project")
            r = verify(p2, "--gate", "rule-lane")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("data_class", r.stdout)

    def test_per_commit_isolation_a_small_rule_commit_survives_a_large_sibling(self):
        # (8) FM-8: never the range's AGGREGATE diff. The two commits
        # together are 504 lines (well over budget); the RULE-declared
        # one is 4 on its own and must still pass.
        base = git_out(self.p, "rev-parse", "HEAD")
        _write(self.p, "src/a.py", 4)
        commit_all(self.p, "FORWARD: RULE — small, real change")
        _write(self.p, "src/big.py", 500)   # large, unrelated, no RULE claim
        commit_all(self.p, "unrelated large refactor")
        r = verify(self.p, "--gate", "rule-lane", "--since", base)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 commit(s) claim RULE", r.stdout)

    def test_per_commit_isolation_each_declared_commit_judged_on_its_own_diff(self):
        # the other direction: a large sibling's size must not leak onto
        # (or shield) a DIFFERENT commit that also declares RULE — each is
        # judged strictly on its own diff, so exactly the big one blocks
        base = git_out(self.p, "rev-parse", "HEAD")
        _write(self.p, "src/small.py", 3)
        commit_all(self.p, "FORWARD: RULE — small, real change")
        _write(self.p, "src/big.py", 500)
        commit_all(self.p, "FORWARD: RULE — mislabeled, actually huge")
        r = verify(self.p, "--gate", "rule-lane", "--since", base)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loc", r.stdout)


class TestGitWrapperPermissionErrorIsAGitFailure(unittest.TestCase):
    """reviews/FWD-019 round 4, F12: `triage._git` used to catch only
    `FileNotFoundError`. A `git` file present on PATH but not executable
    raises `PermissionError` instead (confirmed empirically distinct
    from `FileNotFoundError` — this is exactly `Gate._run_git`'s sibling
    gap in verify.py, same fault, same fix, mirrored here) — before this
    fix that propagated uncaught as a raw traceback rather than the same
    clean `GitFailure` every other git failure mode already produces."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def test_permission_denied_git_raises_git_failure_not_a_crash(self):
        with tempfile.TemporaryDirectory() as bindir:
            broken = Path(bindir) / "git"
            broken.write_text("#!/bin/sh\necho should never run\n")
            broken.chmod(0o644)   # present, NOT executable, and the ONLY
            # git anywhere on this PATH (a working git found elsewhere on
            # PATH lets POSIX's exec search skip right past a broken
            # entry — confirmed empirically, F12's own finding — so no
            # other git may be reachable here).
            with mock.patch.dict(os.environ, {"PATH": bindir}):
                with self.assertRaises(triage.GitFailure) as ctx:
                    triage.commit_files(Path(self.p), "HEAD")
        self.assertIn("git could not be run", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
