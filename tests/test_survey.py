"""FWD-015: the brownfield survey — completeness, evidence labels, anchor
and staleness. Pure cores tested without a repository."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import survey  # noqa: E402
from support import commit_all, make_project, run_git, verify  # noqa: E402

GOOD = """\
# Survey — fixture

commit: {commit}
date: 2026-08-09

## How it runs
- [observed] `make run` starts it; needs Postgres 15.

## Shape
- [observed] Three modules; api depends on core, core on nothing.

## History
- [inferred] The pace halved after the 2025 rewrite, from the commit dates.

## Seams
- [observed] api and worker share the schema, not a contract.

## Undocumented decisions
- [to confirm] Why the queue is in-process — nobody wrote it down.

## Risk
- [observed] The billing path has no test at all.

## Unknown
- [to confirm] Whether the nightly job is still used by anyone.
"""


class TestPureCores(unittest.TestCase):
    def test_missing_sections_are_named(self):
        thin = "# S\n\n## How it runs\n- [observed] x runs it\n"
        miss = survey.missing_sections(thin)
        self.assertIn("risk", miss)
        self.assertIn("unknown", miss)
        self.assertNotIn("how it runs", miss)

    def test_unlabeled_claims_are_caught(self):
        text = GOOD.format(commit="a" * 40).replace(
            "- [observed] The billing path has no test at all.",
            "- The billing path has no test at all.")
        found = survey.unlabeled_claims(text)
        self.assertEqual(len(found), 1)
        self.assertIn("risk", found[0])

    def test_a_complete_survey_has_no_unlabeled_claims(self):
        self.assertEqual(survey.unlabeled_claims(GOOD.format(commit="a" * 40)), [])

    def test_code_fences_and_headings_are_not_claims(self):
        text = GOOD.format(commit="a" * 40) + (
            "\n## Risk\n```\n- this is a fenced example, not a claim\n```\n")
        self.assertEqual(survey.unlabeled_claims(text), [])

    def test_every_required_section_is_one_the_skill_documents(self):
        skill = (ROOT / "skills" / "fde-survey" / "SKILL.md").read_text()
        for section in survey.REQUIRED_SECTIONS:
            self.assertIn(section, skill.lower(), section)


class TestGate(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)
        (Path(self.p) / "discovery").mkdir()
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")
        self.head = survey.subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.p,
            capture_output=True, text=True).stdout.strip()

    def tearDown(self):
        self._t.cleanup()

    def write(self, text):
        (Path(self.p) / "discovery" / "survey.md").write_text(text)

    def test_absent_survey_is_silent_not_red(self):
        # a greenfield project owes no survey
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 0)
        self.assertIn("owed by brownfield", r.stdout)

    def test_complete_survey_passes(self):
        self.write(GOOD.format(commit=self.head))
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_section_fails(self):
        self.write(GOOD.format(commit=self.head).split("## Risk")[0])
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing section", r.stdout)

    def test_unlabeled_claim_fails(self):
        self.write(GOOD.format(commit=self.head).replace(
            "- [observed] The billing path has no test at all.",
            "- The billing path has no test at all."))
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no evidence label", r.stdout)

    def test_missing_anchor_fails(self):
        self.write(GOOD.format(commit=self.head).replace(
            f"commit: {self.head}\n", ""))
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no `commit:`", r.stdout)

    def test_unresolvable_commit_fails(self):
        self.write(GOOD.format(commit="b" * 40))
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not resolve", r.stdout)

    def test_staleness_is_opt_in_and_enforced_when_declared(self):
        self.write(GOOD.format(commit=self.head))
        for i in range(3):
            (Path(self.p) / f"f{i}.txt").write_text("x")
            commit_all(self.p, f"drift {i}")
        # undeclared: measured, not gated
        self.assertEqual(verify(self.p, "--gate", "survey").returncode, 0)
        with open(Path(self.p) / "fde.config.toml", "a") as fh:
            fh.write("\n[survey]\nmax_drift_commits = 1\n")
        r = verify(self.p, "--gate", "survey")
        self.assertEqual(r.returncode, 1)
        self.assertIn("commits behind HEAD", r.stdout)


class TestKernelDogfood(unittest.TestCase):
    def test_this_repo_surveys_itself_and_passes(self):
        present, breaches = survey.check(ROOT)
        self.assertTrue(present, "the kernel does not survey itself")
        self.assertEqual(breaches, [])

    def test_the_kernel_survey_admits_what_it_does_not_know(self):
        # a survey with no [to confirm] is not thorough, it is dishonest
        text = (ROOT / "discovery" / "survey.md").read_text()
        self.assertGreaterEqual(text.count("[to confirm]"), 3)
        self.assertGreaterEqual(text.count("[inferred]"), 2)


if __name__ == "__main__":
    unittest.main()
