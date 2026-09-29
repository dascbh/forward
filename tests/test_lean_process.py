"""The lean-process rules (owner direction, 2026-09-29): a direct lane
with no cycle, tests run once per SHA, a delta round only for a blocker,
backlog ids assigned on main, and no kernel sync under a running cycle.

Each rule is pinned where an agent reads it; the copies are held equal to
their sources by tests/test_mirror.py.
"""
import unittest
from pathlib import Path

from prose import ProseTestCase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split())


class TestDirectLane(ProseTestCase):
    def test_agents_md_names_the_direct_lane(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            self.assertIn("or in the direct lane (`fde-triage`).", text, rel)

    def test_triage_states_every_condition_and_the_exit(self):
        text = read("skills/fde-triage/SKILL.md")
        self.assertIn("## Direct lane — no cycle", text)
        for cond in ("exactly one goal", "about 300 production lines at "
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


class TestTestsRunOncePerSha(ProseTestCase):
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


class TestDeltaOnlyForABlocker(ProseTestCase):
    def test_a_clean_full_round_ends_the_review(self):
        self.assertIn("A full round with no blocking finding ends the "
                      "review: the delta round runs only to check a "
                      "blocker's fix.", read("skills/fde-review/SKILL.md"))
        self.assertIn("No blocking finding ends the review; a delta runs "
                      "only to check a blocker's fix.",
                      read("agents/fde-adversarial.md"))


class TestBacklogIdsOnMain(ProseTestCase):
    def test_worktree_lines_carry_no_id(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Only main assigns backlog ids.", read(rel), rel)
        self.assertIn("with no id (ids are assigned on main after the "
                      "merge)", read("agents/fde-implementation.md"))
        self.assertIn("Ids are assigned on main only.",
                      read("skills/fde-backlog-format/SKILL.md"))
        self.assertIn("The `BL-IDS` gate fails when one `B-<n>` opens two "
                      "different items", read("skills/fde-backlog-format/SKILL.md"))

    def test_appends_merge_as_a_union(self):
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("backlog.md merge=union", attrs)
        self.assertIn("cycles/*/board.md merge=union", attrs)
        setup = read("SETUP.md")
        self.assertIn("`backlog.md merge=union`", setup)
        self.assertIn("`cycles/*/board.md merge=union`", setup)


class TestNoSyncUnderARunningCycle(ProseTestCase):
    def test_sync_waits_for_the_cycle_to_end(self):
        text = read("skills/fde-sync/SKILL.md")
        self.assertIn("## 0. When — between cycles", text)
        self.assertIn("a cycle is `running`", text)
        self.assertIn("never changes the rules under a running cycle", text)


if __name__ == "__main__":
    unittest.main()


class TestWavesFromThePlan(ProseTestCase):
    def test_the_plan_declares_files_and_the_runtime_computes_waves(self):
        self.assertIn("| id | layer | depends on | files | what | meets | "
                      "follows |", read("templates/cycle/plan.md"))
        self.assertIn("`status.py --waves C-<n>` computes from them which "
                      "demands run in parallel.", read("agents/fde-spec.md"))
        self.assertIn("A demand that needs a file outside its row posts "
                      "`claim widened`", read("templates/cycle/board.md"))
        self.assertIn("Your files are your plan row's `files` cell; post "
                      "`claim widened` on `cycles/C-<n>/board.md` only for a "
                      "file outside it;", read("agents/fde-implementation.md"))
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("Parallel demands come from the plan's `files` "
                          "(`status.py --waves`).", read(rel), rel)


class TestTriageAndVerificationGap(unittest.TestCase):
    """BMAD-method learnings (owner, 2026-09-29): reviewers find, the
    builder triages; the code review asks the verification-gap question;
    the planner investigates before asking."""

    def test_triage_verifies_then_routes_by_where_the_defect_lives(self):
        text = read("skills/fde-review/SKILL.md")
        self.assertIn("## Triage — reviewer output is data, not a verdict", text)
        self.assertIn("Recall belongs to the reviewer, precision to the triage.", text)
        for route in ("`intent`", "`plan`", "`patch`", "`defer`"):
            self.assertIn(route, text)
        self.assertIn("`real` (the reviewer's severity stands), `false` (write "
                      "what disproves this claim", text)
        self.assertIn("The reviewer's file is never edited (I3).", text)
        self.assertIn("A blocking finding is never triaged away", text)
        self.assertIn("The cycle review audits every `false`.", text)
        self.assertNotIn("## Reconciliation", text)

    def test_a_patch_is_the_second_in_band_exception(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertIn("except a blocker or a triaged `patch` "
                          "(`fde-review`).", read(rel), rel)
        self.assertIn("This is the one in-band fix MNT-9 allows besides a "
                      "blocker.", read("skills/fde-review/SKILL.md"))

    def test_roles_know_who_triages(self):
        self.assertIn("you record it, you never route it.",
                      read("agents/fde-adversarial.md"))
        self.assertIn("You never edit the reviewer's file.",
                      read("agents/fde-implementation.md"))
        self.assertIn("patch, defer or drop",
                      read("templates/findings.template.toml"))

    def test_code_review_asks_the_verification_gap_question(self):
        self.assertIn("if it broke where it is used, would a test fail?",
                      read("skills/fde-review/SKILL.md"))
        self.assertIn("search the repository by the symbol before claiming "
                      "no test exists", read("skills/fde-review/SKILL.md"))
        self.assertIn("if a changed behavior broke where it is used, would a "
                      "test fail?", read("agents/fde-adversarial.md"))

    def test_the_planner_investigates_before_asking(self):
        text = read("agents/fde-spec.md")
        self.assertIn("Investigate before asking", text)
        self.assertIn("at most three questions, all at once, each with its "
                      "options and a recommended answer", text)


class TestOneGoalPerDemand(unittest.TestCase):
    """kernel ADR-0022 (owner, 2026-09-29): a demand is one goal; the
    layer marks files, not demands."""

    def test_the_adr_supersedes_the_split_clause(self):
        adr = read("docs/adr/0022-a-demand-is-one-goal.md")
        self.assertIn("amends: ADR-0019 rule 5, its split clause", adr)
        self.assertIn("superseded in part: rule 5's split clause, by ADR-0022",
                      read("docs/adr/0019-backlog-cycle-demand.md"))

    def test_planner_and_template_split_by_goal_not_layer(self):
        text = read("agents/fde-spec.md")
        self.assertIn("A demand is one goal (kernel ADR-0022)", text)
        self.assertIn("splits here into smaller goals, never into layers", text)
        self.assertNotIn("A change that spans layers is split.", text)
        self.assertIn("| DEM-<n> | back, front |", read("templates/cycle/plan.md"))
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            self.assertNotIn("exactly one layer", read(rel), rel)

    def test_review_limits_cite_their_config_keys(self):
        text = read("skills/fde-review/SKILL.md")
        self.assertIn("`[review] cycle_rounds_small` (default 1)", text)
        self.assertIn("`[review] max_findings` (default 5)", text)
        self.assertIn("`[review] max_findings` (default 5)",
                      read("agents/fde-adversarial.md"))
