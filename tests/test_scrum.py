"""FWD-002 R1: the cadence gates — active only when [scrum] is enabled."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import make_project, verify

DATED_GOAL = "---\ngoal: something worth building\ndate: 2026-08-09\n---\n"


class TestScrumOff(unittest.TestCase):
    def test_mode_off_reports_off_and_never_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)  # no [scrum]
            r = verify(p, "--gate", "scrum")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("off", r.stdout)

    def test_mode_off_is_silent_in_a_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p)
            self.assertNotIn("SCRUM", r.stdout)


class TestScrumOn(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, scrum=True)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "scrum")

    def test_backlog_with_dated_product_goal_is_required(self):
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("header lines", r.stdout)

        (self.p / "backlog.md").write_text("# Backlog\ngoal: x\n(no date)\n")
        # goal present in head but no date: still red
        r = self.gate()
        self.assertEqual(r.returncode, 1)

        (self.p / "backlog.md").write_text(DATED_GOAL + "# Backlog\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sprint_needs_a_dated_goal(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        s1 = self.p / "sprints" / "S-001"
        s1.mkdir(parents=True)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("S-001", r.stdout)

        (s1 / "goal.md").write_text("goal without a stamp\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1)

        (s1 / "goal.md").write_text(DATED_GOAL)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_no_retro_no_next_sprint(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        for name in ("S-001", "S-002"):
            d = self.p / "sprints" / name
            d.mkdir(parents=True)
            (d / "goal.md").write_text(DATED_GOAL)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no retro, no next sprint", r.stdout)

        (self.p / "sprints" / "S-001" / "retro.md").write_text("")  # empty
        r = self.gate()
        self.assertEqual(r.returncode, 1)  # an empty retro is not a retro

        (self.p / "sprints" / "S-001" / "retro.md").write_text("# Retro\nfindings\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)  # latest may stay open

    def test_sprint_ordering_is_numeric_not_lexicographic(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        for n in range(1, 11):  # S-1..S-10, unpadded
            d = self.p / "sprints" / f"S-{n}"
            d.mkdir(parents=True)
            (d / "goal.md").write_text(DATED_GOAL)
            if n < 10:
                (d / "retro.md").write_text("# Retro\nok\n")
        r = self.gate()  # S-10 is latest and open — must be exempt
        self.assertEqual(r.returncode, 0, r.stdout)

        (self.p / "sprints" / "S-9" / "retro.md").unlink()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("S-9", r.stdout)

    def test_stray_directories_under_sprints_are_rejected(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        d = self.p / "sprints" / "S-001"
        d.mkdir(parents=True)
        (d / "goal.md").write_text(DATED_GOAL)
        (self.p / "sprints" / "S-archive").mkdir()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unrecognized", r.stdout)

    def test_incidental_substrings_are_not_commitments(self):
        # 'created date:' and 'sprint goal:' lines must not satisfy the gate
        (self.p / "backlog.md").write_text(
            "# Backlog\ncreated date: 2026-08-09\nsprint goal: decide later\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_sprint_goal_needs_goal_line_not_only_date(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        d = self.p / "sprints" / "S-001"
        d.mkdir(parents=True)
        (d / "goal.md").write_text("date: 2026-08-09\n")  # no goal
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("'goal:'", r.stdout)

    def test_header_window_is_lines_not_characters(self):
        (self.p / "backlog.md").write_text(DATED_GOAL)
        d = self.p / "sprints" / "S-001"
        d.mkdir(parents=True)
        long_first_line = "# " + ("context " * 80)  # ~640 chars, one line
        (d / "goal.md").write_text(
            long_first_line + "\ngoal: ship it\ndate: 2026-08-09\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_backlog_as_directory_is_a_red_not_a_crash(self):
        (self.p / "backlog.md").mkdir()
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)


class TestScrumConfigShape(unittest.TestCase):
    def test_enabled_as_string_is_a_config_violation_and_stays_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            with open(Path(p) / "fde.config.toml", "a") as fh:
                fh.write('\n[scrum]\nenabled = "false"\n')
            r = verify(p, "--gate", "config")
            self.assertEqual(r.returncode, 1)
            self.assertIn("SCRUM-ENABLED", r.stdout)
            r = verify(p, "--gate", "scrum")  # non-boolean never arms the gates
            self.assertEqual(r.returncode, 0)
            self.assertIn("off", r.stdout)

    def test_broken_config_toml_is_a_named_error_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            (Path(p) / "fde.config.toml").write_text("[scrum\nbroken = \n")
            r = verify(p, "--gate", "scrum")
            self.assertEqual(r.returncode, 1)
            self.assertIn("not valid TOML", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_ci_tier_gate_under_staged_names_the_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp, scrum=True)
            r = verify(p, "--gate", "scrum", "--staged")
            self.assertEqual(r.returncode, 2)
            self.assertIn("drop --staged", r.stderr)


class TestScrumR2R3Artifacts(unittest.TestCase):
    """R2/R3 (finding DOM-5): the skill and the AGENTS surfaces are verified,
    and the duplicated scrum section cannot drift between template and repo."""

    ROOT = Path(__file__).resolve().parent.parent

    @staticmethod
    def section(text: str) -> str:
        m = text.split("\n## Scrum mode", 1)
        assert len(m) == 2, "scrum-mode section missing"
        return m[1].split("\n## ", 1)[0]

    def test_skill_defines_the_eight_elements_r2_names(self):
        skill = (self.ROOT / "skills" / "fde-scrum" / "SKILL.md").read_text()
        for element in ("Capture", "Discover", "Plan", "Execute", "Close",
                        "Review", "Retro", "Unplanned"):
            self.assertIn(element, skill, element)

    def test_template_and_repo_carry_the_same_scrum_section(self):
        template = (self.ROOT / "templates" / "AGENTS.md.template").read_text()
        agents = (self.ROOT / "AGENTS.md").read_text()
        self.assertEqual(self.section(template), self.section(agents))


if __name__ == "__main__":
    unittest.main()
