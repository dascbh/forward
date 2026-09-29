"""FWD-002 R1, FWD-029, FWD-039: the backlog's dated goal — checked only when
[backlog] (old name [scrum], still read) is enabled. The sprint gates
(SCRUM-GOAL, SCRUM-RETRO) are retired (ADR-0019)."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from support import make_project, verify

from prose import ProseTestCase  # noqa: E402

DATED_GOAL = "---\ngoal: something worth building\ndate: 2026-08-09\n---\n"


class TestScrumOff(ProseTestCase):
    def test_mode_off_reports_off_and_never_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)  # no [backlog]
            r = verify(p, "--gate", "backlog")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("off", r.stdout)

    def test_mode_off_is_silent_in_a_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            r = verify(p)
            self.assertNotIn("SCRUM", r.stdout)
            self.assertNotIn("BACKLOG", r.stdout)


class TestScrumOn(ProseTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, backlog=True)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "backlog")

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


class TestScrumConfigShape(ProseTestCase):
    def test_enabled_as_string_is_a_config_violation_and_stays_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            with open(Path(p) / "fde.config.toml", "a") as fh:
                fh.write('\n[scrum]\nenabled = "false"\n')
            r = verify(p, "--gate", "config")
            self.assertEqual(r.returncode, 1)
            self.assertIn("BACKLOG-ENABLED", r.stdout)
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


class TestBacklogInstructions(ProseTestCase):
    """FWD-031, ADR-0019 rule 13: fde-scrum shrinks to the backlog format and
    AGENTS.md's Scrum section becomes ## Backlog. That the section cannot
    drift between template and repo is the agents-md pair in
    tests/mirror.toml (FWD-020)."""

    ROOT = Path(__file__).resolve().parent.parent
    SKILLS = ("skills/fde-backlog-format/SKILL.md", ".claude/skills/fde-backlog-format/SKILL.md")
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
                            "at most", "Sprints are retired",
                            "`goal: not set`", "`--gate backlog` requires both"):
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
            # FWD-037: the header rule and "Sprints are retired" were
            # duplicates of fde-scrum's (cycles/C-14/inventory.md #68,
            # #71); the skill keeps them, AGENTS.md points to it
            for needle in ("becomes a backlog item, not a demand",
                           "`fde-backlog-format` skill"):
                self.assertIn(needle, section, f"{rel}: {needle}")
            for gone in self.SPRINT_CEREMONY + ("retro", "sprint;"):
                self.assertNotIn(gone, section, f"{rel}: {gone}")



class TestScrumIsAnAlias(ProseTestCase):
    """FWD-039 FM2 (B-37): an old client with `[scrum] enabled = true` and
    `--gate scrum` in its scripts keeps its meaning and stays green."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, scrum=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_old_client_is_armed_and_green_under_both_names(self):
        for gate in ("scrum", "backlog"):
            r = verify(self.p, "--gate", gate)
            self.assertEqual(r.returncode, 1, f"{gate}: {r.stdout}")
            self.assertIn("BACKLOG", r.stdout)
        (self.p / "backlog.md").write_text(DATED_GOAL + "# Backlog\n")
        for args in (("--gate", "scrum"), ("--gate", "backlog"),
                     ("--gate", "config")):
            r = verify(self.p, *args)
            self.assertEqual(r.returncode, 0, f"{args}: {r.stdout}{r.stderr}")
            self.assertNotIn("Traceback", r.stderr)
        # the full run arms it too (the bare fixture fails other gates)
        self.assertIn("backlog carries a dated product goal",
                      verify(self.p).stdout)

    def test_backlog_wins_and_both_is_named(self):
        with open(self.p / "fde.config.toml", "a") as fh:
            fh.write("\n[backlog]\nenabled = false\n")
        r = verify(self.p, "--gate", "backlog")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("off", r.stdout)
        r = verify(self.p, "--gate", "config")
        self.assertEqual(r.returncode, 1)
        self.assertIn("BACKLOG-ALIAS", r.stdout)

    def test_scrum_under_staged_still_names_the_conflict(self):
        r = verify(self.p, "--gate", "scrum", "--staged")
        self.assertEqual(r.returncode, 2)
        self.assertIn("drop --staged", r.stderr)

    def test_this_repository_declares_the_new_name(self):
        text = (TestBacklogInstructions.ROOT / "fde.config.toml").read_text()
        self.assertIn("\n[backlog]\nenabled = true\n", text)
        self.assertNotIn("[scrum]", text)
        tmpl = (TestBacklogInstructions.ROOT / "templates"
                / "fde.config.template.toml").read_text()
        self.assertIn("# [backlog]\n", tmpl)
        self.assertNotIn("[scrum]", tmpl)


class TestGoalIsHeaderOnlyAndStrict(ProseTestCase):
    """FWD-039 B-34: the goal is read from the header (the lines before the
    first `## `, as fde_lib.header_lines reads it); with the switch on,
    `goal: not set` is not a goal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name, backlog=True)

    def tearDown(self):
        self._tmp.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "backlog")

    def test_goal_below_the_first_section_does_not_count(self):
        (self.p / "backlog.md").write_text(
            "# Backlog\n\n## Items\n\ngoal: ship it\ndate: 2026-08-09\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_goal_not_set_is_rejected_when_on(self):
        (self.p / "backlog.md").write_text(
            "goal: not set\ndate: 2026-08-09\n\n# Backlog\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("goal: not set", r.stdout)
        (self.p / "backlog.md").write_text(
            "goal: Not Set\ndate: 2026-08-09\n")
        self.assertEqual(self.gate().returncode, 1)

    def test_goal_not_set_is_fine_when_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            (Path(p) / "backlog.md").write_text("goal: not set\ndate: 2026-08-09\n")
            r = verify(p, "--gate", "backlog")
            self.assertEqual(r.returncode, 0, r.stdout)


class TestSwitchNotATable(ProseTestCase):
    """FWD-039 B-13: `scrum = true` or `backlog = "on"` is a CFG violation,
    never a traceback."""

    CASES = ('scrum = true', 'backlog = "on"', 'scrum = [1, 2]',
             'backlog = 3')

    def test_non_table_is_a_named_violation_not_a_crash(self):
        for case in self.CASES:
            with tempfile.TemporaryDirectory() as tmp:
                p = make_project(tmp)
                cfg = Path(p) / "fde.config.toml"
                # a top-level key must precede every table
                cfg.write_text(case + "\n" + cfg.read_text())
                for args in (("--gate", "config"), ("--gate", "backlog"),
                             ("--gate", "scrum"), ()):
                    r = verify(p, *args)
                    self.assertNotIn("Traceback", r.stderr, f"{case} {args}")
                r = verify(p, "--gate", "config")
                self.assertEqual(r.returncode, 1, case)
                self.assertIn("BACKLOG-TABLE", r.stdout, case)
                r = verify(p, "--gate", "backlog")
                self.assertEqual(r.returncode, 0, case)
                self.assertIn("off", r.stdout, case)


class TestNoSprintWording(ProseTestCase):
    """FWD-039 B-36: sprints are retired (kernel ADR-0019 rule 13). No
    instruction file speaks of them, except a retirement note carrying an
    allowlisted phrase."""

    ROOT = Path(__file__).resolve().parent.parent
    WORDING = re.compile(r"sprint goal|\bretros?\b|retrospective|"
                         r"sprint review|planning sitting", re.IGNORECASE)
    # a line carrying one of these is a retirement note, not an instruction
    ALLOW = ("Sprints are retired",)

    def instruction_files(self):
        root = self.ROOT
        files = [root / "AGENTS.md", root / "templates" / "AGENTS.md.template",
                 root / "SETUP.md", root / "README.md"]
        for d in ("skills", "agents", ".claude/skills", ".claude/agents"):
            files += sorted(p for p in (root / d).rglob("*")
                            if p.is_file() and p.suffix in (".md", ".toml"))
        return files

    def hits(self, text):
        return [line for line in text.splitlines()
                if self.WORDING.search(line)
                and not any(a in line for a in self.ALLOW)]

    def test_no_instruction_file_speaks_of_sprints(self):
        files = self.instruction_files()
        self.assertGreater(len(files), 20)
        for f in files:
            found = self.hits(f.read_text(encoding="utf-8"))
            self.assertEqual(found, [], str(f.relative_to(self.ROOT)))

    def test_the_check_catches_what_it_guards(self):
        for bad in ("Set the sprint goal first.", "At the retro, reorder.",
                    "Hold a Sprint Review.", "The planning sitting decides.",
                    "Run a retrospective."):
            self.assertTrue(self.hits(bad), bad)
        self.assertEqual(self.hits("retroactive ADR"), [])
        self.assertEqual(self.hits("Sprints are retired; no sprint goal."), [])


if __name__ == "__main__":
    unittest.main()
