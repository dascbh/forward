"""The lean-process rules (owner direction, 2026-09-29): a direct lane
with no cycle, tests run once per SHA, a delta round only for a blocker,
backlog ids assigned on main, and no kernel sync under a running cycle.

Each rule is pinned where an agent reads it; the copies are held equal to
their sources by tests/test_mirror.py.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split())


class TestDirectLane(unittest.TestCase):
    def test_agents_md_names_the_direct_lane(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            self.assertIn("or in the direct lane (`fde-triage`).", text, rel)

    def test_triage_states_every_condition_and_the_exit(self):
        text = read("skills/fde-triage/SKILL.md")
        self.assertIn("## Direct lane — no cycle", text)
        for cond in ("exactly one layer", "about 300 production lines at "
                     "most", "not `sensitive`", "not `irreversible`",
                     "needs no ADR", "Unsure on any → a cycle."):
            self.assertIn(cond, text)
        self.assertIn("One isolated code review (I2, I3)", text)
        self.assertIn("The test comes first and is the declared criterion "
                      "(I1, I4).", text)
        self.assertIn("stops and becomes a cycle.", text)

    def test_fix_it_now_takes_the_direct_lane(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("the direct lane when it fits, else the next "
                          "cycle's first demand.", read(rel), rel)


class TestTestsRunOncePerSha(unittest.TestCase):
    def test_review_skill_names_each_role(self):
        text = read("skills/fde-review/SKILL.md")
        self.assertIn("## Test runs — once per SHA", text)
        self.assertIn("no role runs it again at that SHA.", text)
        self.assertIn("never reruns the suite.", text)
        self.assertIn("never a full-suite rerun.", text)
        self.assertIn("not a red→green reproduction per criterion.", text)
        self.assertIn("**Mutation testing** runs only where `plan.md` "
                      "declares it", text)

    def test_roles_carry_it(self):
        self.assertIn("never rerun the suite", read("agents/fde-adversarial.md"))
        self.assertIn("Nobody reruns it at that SHA.",
                      read("agents/fde-implementation.md"))
        self.assertIn("no red→green reproduction per criterion, no mutation "
                      "testing unless `plan.md` declares it.",
                      read("agents/fde-promotion.md"))
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Tests run once per SHA", read(rel), rel)


class TestDeltaOnlyForABlocker(unittest.TestCase):
    def test_a_clean_full_round_ends_the_review(self):
        self.assertIn("A full round with no blocking finding ends the "
                      "review: the delta round runs only to check a "
                      "blocker's fix.", read("skills/fde-review/SKILL.md"))
        self.assertIn("No blocking finding ends the review; a delta runs "
                      "only to check a blocker's fix.",
                      read("agents/fde-adversarial.md"))


class TestBacklogIdsOnMain(unittest.TestCase):
    def test_worktree_lines_carry_no_id(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Only main assigns backlog ids.", read(rel), rel)
        self.assertIn("with no id (ids are assigned on main after the "
                      "merge)", read("agents/fde-implementation.md"))
        self.assertIn("Ids are assigned on main only.",
                      read("skills/fde-backlog-format/SKILL.md"))

    def test_appends_merge_as_a_union(self):
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("backlog.md merge=union", attrs)
        self.assertIn("cycles/*/board.md merge=union", attrs)
        setup = read("SETUP.md")
        self.assertIn("`backlog.md merge=union`", setup)
        self.assertIn("`cycles/*/board.md merge=union`", setup)


class TestNoSyncUnderARunningCycle(unittest.TestCase):
    def test_sync_waits_for_the_cycle_to_end(self):
        text = read("skills/fde-sync/SKILL.md")
        self.assertIn("## 0. When — between cycles", text)
        self.assertIn("a cycle is `running`", text)
        self.assertIn("never changes the rules under a running cycle", text)


if __name__ == "__main__":
    unittest.main()


class TestWavesFromThePlan(unittest.TestCase):
    def test_the_plan_declares_files_and_the_runtime_computes_waves(self):
        self.assertIn("| id | layer | depends on | files | what | meets | "
                      "follows |", read("templates/cycle/plan.md"))
        self.assertIn("`status.py --waves C-<n>` computes from them which "
                      "demands run in parallel.", read("agents/fde-spec.md"))
        self.assertIn("A demand that needs a file outside its row posts "
                      "`claim widened`", read("templates/cycle/board.md"))
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Parallel demands come from the plan's `files` "
                          "(`status.py --waves`).", read(rel), rel)
