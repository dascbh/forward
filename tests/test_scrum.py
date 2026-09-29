"""FWD-002 R1, FWD-029: the backlog's dated goal — checked only when [scrum] is
enabled. The sprint gates (SCRUM-GOAL, SCRUM-RETRO) are retired (ADR-0019)."""
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

    def test_incidental_substrings_are_not_commitments(self):
        # 'created date:' and 'sprint goal:' lines must not satisfy the gate
        (self.p / "backlog.md").write_text(
            "# Backlog\ncreated date: 2026-08-09\nsprint goal: decide later\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_sprints_are_history_never_a_gate(self):
        # ADR-0019 rule 13: sprints are retired. A sprint with no goal,
        # an undated goal, a missing retro and a stray directory all pass;
        # SCRUM-GOAL and SCRUM-RETRO are gone.
        (self.p / "backlog.md").write_text(DATED_GOAL)
        for name in ("S-1", "S-2", "S-3", "S-archive"):
            (self.p / "sprints" / name).mkdir(parents=True)
        (self.p / "sprints" / "S-2" / "goal.md").write_text("goal without a stamp\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("SCRUM-GOAL", r.stdout)
        self.assertNotIn("SCRUM-RETRO", r.stdout)

    def test_header_window_is_lines_not_characters(self):
        long_first_line = "# " + ("context " * 80)  # ~640 chars, one line
        (self.p / "backlog.md").write_text(
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


class TestBacklogInstructions(unittest.TestCase):
    """FWD-031, ADR-0019 rule 13: fde-scrum shrinks to the backlog format and
    AGENTS.md's Scrum section becomes ## Backlog. That the section cannot
    drift between template and repo is the agents-md pair in
    tests/mirror.toml (FWD-020)."""

    ROOT = Path(__file__).resolve().parent.parent
    SKILLS = ("skills/fde-scrum/SKILL.md", ".claude/skills/fde-scrum/SKILL.md")
    AGENTS = ("templates/AGENTS.md.template", "AGENTS.md")
    SPRINT_CEREMONY = ("sprints/S-N", "sprint goal", "Plan — the user",
                       "## Retro", "## Review", "retro.md", "review.md",
                       "## Unplanned", "mid-sprint", "two sittings")

    def flat(self, rel):
        return " ".join((self.ROOT / rel).read_text(encoding="utf-8").split())

    def section(self, rel):
        text = (self.ROOT / rel).read_text(encoding="utf-8")
        start = text.index("\n## Backlog\n")
        return " ".join(text[start:text.index("\n## ", start + 1)].split())

    def test_skill_is_the_backlog_format(self):
        for rel in self.SKILLS:
            flat = self.flat(rel)
            for element in ("`B-<n>`", "`opinion < usage-data < user-test "
                            "< production`", "`(C-<n>)`", "## Capture",
                            "becomes a backlog item, not a demand",
                            "`promotion.md` `## What changes`: three lines "
                            "at most", "Sprints are retired"):
                self.assertIn(element, flat, f"{rel}: {element}")

    def test_skill_carries_no_sprint_ceremony(self):
        for rel in self.SKILLS:
            flat = self.flat(rel)
            for gone in self.SPRINT_CEREMONY:
                self.assertNotIn(gone, flat, f"{rel}: {gone}")

    def test_skill_description_is_terse_and_sprint_free(self):
        for rel in self.SKILLS:
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            desc = next(l for l in text.splitlines()
                        if l.startswith("description:"))
            self.assertLessEqual(len(desc.split()) - 1, 40, rel)
            self.assertNotIn("sprint", desc.lower(), rel)
            self.assertNotIn("retro", desc.lower(), rel)

    def test_both_agents_surfaces_carry_a_backlog_section(self):
        for rel in self.AGENTS:
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("\n## Backlog\n", text, rel)
            self.assertNotIn("## Scrum mode", text, rel)
            section = self.section(rel)
            for needle in ("becomes a backlog item, not a demand",
                           "Sprints are retired; `sprints/` is history.", "`backlog.md` starts with `goal:` (or "
                           "`goal: not set`) and `date:`; with `[scrum] "
                           "enabled = true`, `--gate scrum` requires them.",
                           "`fde-scrum` skill"):
                self.assertIn(needle, section, f"{rel}: {needle}")
            for gone in self.SPRINT_CEREMONY + ("retro", "sprint;"):
                self.assertNotIn(gone, section, f"{rel}: {gone}")


if __name__ == "__main__":
    unittest.main()
