"""FWD-032 (C-5 A8): the discovery's inconsistencies stay resolved
(discovery/sharpen-2026-09-29.md). Each class names the item it pins."""
from __future__ import annotations

import importlib.util
import re
import tomllib
import unittest
from pathlib import Path

from support import guard, make_project

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def flat(rel: str) -> str:
    return " ".join(read(rel).split())


def section(text: str, heading: str) -> str:
    parts = text.split(f"\n## {heading}", 1)
    assert len(parts) == 2, f"section '{heading}' missing"
    return parts[1].split("\n## ", 1)[0]


ROLES = tomllib.loads(read("spec/roles.toml"))["role"]
AGENTS_SURFACES = ("AGENTS.md", "templates/AGENTS.md.template")


class TestWeightNeverBlocks(unittest.TestCase):
    """#4: weight orders the attack and sizes the suite (ADR-0018)."""

    def test_no_surface_says_weight_decides_blocking_or_rounds(self):
        for rel in ("SETUP.md", "README.md",
                    "spec/dimensions/quality-attributes.toml",
                    ".fde/spec/dimensions/quality-attributes.toml"):
            text = flat(rel)
            for gone in ("blocks merge", "rounds per dimension",
                         "rounds spent per dimension"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")


class TestInvariantCommandsExist(unittest.TestCase):
    """#12: every verifiable_by is a real command naming a real gate."""

    def test_verifiable_by_names_a_known_gate(self):
        spec = importlib.util.spec_from_file_location(
            "verify_mod", ROOT / "runtime" / "verify.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for rel in ("spec/invariants.toml", ".fde/spec/invariants.toml"):
            for inv in tomllib.loads(read(rel))["invariant"]:
                cmd = inv["verifiable_by"]
                m = re.fullmatch(r"python3 bin/fde/verify\.py --gate (\S+)", cmd)
                self.assertIsNotNone(m, f"{rel} {inv['id']}: {cmd}")
                self.assertIn(m.group(1), mod.KNOWN_GATES, f"{rel} {inv['id']}")


class TestFindingsTemplateReachesClients(unittest.TestCase):
    """#9: the template carries `backlog` and is installed under .fde/."""

    def test_template_declares_the_backlog_key(self):
        text = read("templates/findings.template.toml")
        self.assertRegex(text, r"(?m)^# backlog\s+= ")

    def test_setup_installs_it_and_review_points_there(self):
        sec6 = section(read("SETUP.md"), "6.")
        self.assertIn("`templates/findings.template.toml` → "
                      "`.fde/templates/findings.template.toml`", sec6)
        for rel in ("skills/fde-review/SKILL.md", ".claude/skills/fde-review/SKILL.md"):
            self.assertIn("`.fde/templates/findings.template.toml`", read(rel), rel)
            self.assertNotIn("kernel's `templates/findings", read(rel), rel)

    def test_cycle_template_is_installed_and_named_there(self):
        sec6 = section(read("SETUP.md"), "6.")
        self.assertIn("`templates/cycle/` → `.fde/templates/cycle/`", sec6)
        # FWD-037: the cycle layout moved, verbatim, to fde-spec
        # (cycles/C-14/inventory.md #47)
        for rel in AGENTS_SURFACES + ("agents/fde-spec.md",
                                      ".claude/agents/fde-spec.md"):
            self.assertNotIn("kernel's `templates/cycle/`", flat(rel), rel)
        for rel in ("agents/fde-spec.md", ".claude/agents/fde-spec.md"):
            self.assertIn("`.fde/templates/cycle/`", read(rel), rel)


class TestPromotionReadsWhatExists(unittest.TestCase):
    """#8: nothing produces artifacts/gate-report.json; promotion runs the gate."""

    def test_no_role_input_is_the_phantom_report(self):
        for r in ROLES:
            for i in r["inputs"]:
                self.assertNotIn("gate-report.json", i, r["id"])
        for rel in ("agents/fde-promotion.md", ".claude/agents/fde-promotion.md"):
            text = read(rel)
            self.assertNotIn("gate-report.json", text, rel)
            self.assertIn("python3 bin/fde/verify.py --all", text, rel)


class TestOneDiffCeiling(unittest.TestCase):
    """#11: one ceiling, ~300 production lines per demand (ADR-0019 rule 3)."""

    SURFACES = AGENTS_SURFACES + ("skills/fde-triage/SKILL.md",
                                  "skills/fde-review/SKILL.md",
                                  "agents/fde-spec.md")

    def test_one_ceiling_everywhere(self):
        for rel in self.SURFACES:
            text = flat(rel)
            self.assertIn("300 production lines", text, rel)
            for gone in ("~800 changed", "~800 lines", "above ~800",
                         "twice the estimate"):
                self.assertNotIn(gone, text, f"{rel}: {gone}")


class TestSizesAgree(unittest.TestCase):
    """#3, #5: the role that writes ADRs is active wherever an ADR is due,
    and L names the same role count everywhere."""

    def test_triage_and_agents_agree(self):
        rule = ("M adds architecture: `fde-architecture` writes the ADRs, so "
                "M and L run all five roles.")
        # FWD-037: AGENTS.md's copy was a duplicate of fde-triage's
        # (cycles/C-14/inventory.md #12); the skill keeps the rule
        for rel in ("skills/fde-triage/SKILL.md",
                    ".claude/skills/fde-triage/SKILL.md"):
            self.assertIn(rule, flat(rel), rel)
        for rel in AGENTS_SURFACES + ("skills/fde-triage/SKILL.md",):
            self.assertNotIn("all six roles", flat(rel), rel)


class TestRolesMatchTheSpec(unittest.TestCase):
    """#7: AGENTS.md ## Roles and agents/*.md say what spec/roles.toml says."""

    def test_agents_md_roles_section_lists_each_write_scope(self):
        for rel in AGENTS_SURFACES:
            roles = section(read(rel), "Roles")
            for r in ROLES:
                if r["write_scope"]:
                    line = (f"**{r['label']}** (`fde-{r['id']}`) — writes to "
                            f"`{', '.join(r['write_scope'])}`")
                else:
                    line = f"**{r['label']}** (`fde-{r['id']}`) — writes nothing"
                self.assertIn(line, roles, f"{rel}: {r['id']}")

    def test_every_writing_role_may_write_backlog_and_board(self):
        # reviews/FWD-028 F2, ADR-0019 rules 1 and 11
        for r in ROLES:
            if not r["write_scope"]:
                continue  # walkthrough-evaluator writes nothing
            scope = r["write_scope"]
            self.assertIn("backlog.md", scope, r["id"])
            self.assertTrue("cycles/**" in scope or "cycles/*/board.md" in scope,
                            r["id"])

    def test_role_files_list_the_spec_sections(self):
        # reviews/FWD-032 F1: "Outputs (write only here)" is the role's
        # whole write_scope (board and backlog included); what the role
        # produces is listed apart, under "Produces"
        def bullets(text, heading):
            m = re.search(r"\n## " + re.escape(heading) + r"\n(.*?)(?=\n\n|\n## |\Z)",
                          text, re.S)
            return None if m is None else re.findall(r"^- `([^`]*)`", m.group(1), re.M)
        for r in ROLES:
            if r["write_scope"]:
                sections = (("Inputs", "inputs"),
                            ("Outputs (write only here)", "write_scope"),
                            ("Produces", "outputs"),
                            ("Denied paths", "denied_paths"))
            else:
                sections = (("Inputs", "inputs"), ("Outputs", "outputs"),
                            ("Denied paths", "denied_paths"))
            for base in ("agents", ".claude/agents"):
                text = read(f"{base}/fde-{r['id']}.md")
                for heading, key in sections:
                    want = [v.split(" (")[0] for v in r[key]]
                    self.assertEqual(bullets(text, heading), want,
                                     f"{base}/fde-{r['id']}.md {heading}")


class TestReviewBudgetIsAReplan(unittest.TestCase):
    """#6: budget spent with a blocker open is a replan, the owner's call,
    recorded in promotion.md; plan.md stays frozen."""

    def test_budget_routes_to_the_owner(self):
        # reviews/FWD-032 F4: not a replan (plan.md stays frozen); the
        # owner's choice goes on the board, and promotion marks it at close
        budget = " ".join(section(read("skills/fde-review/SKILL.md"), "Budget").split())
        self.assertIn("the owner picks one (AGENTS.md `## Cycle`)", budget)
        self.assertIn("recorded on the cycle's `board.md`", budget)
        self.assertIn("`plan.md` stays frozen", budget)
        for gone in ("nothing is declined without the user",
                     "records it in the promotion or the closing commit",
                     "the replan records it in `plan.md`",
                     "the cycle replans and the owner picks one"):
            self.assertNotIn(gone, budget, gone)
        for rel in AGENTS_SURFACES:
            cycle = " ".join(section(read(rel), "Cycle").split())
            for needle in ("narrow, declare the limit, or pause",
                           "recorded on `board.md`",
                           "marked in `promotion.md` at close"):
                self.assertIn(needle, cycle, f"{rel}: {needle}")
        # reviews/C-5 F1: the frozen plan is stated once, at sign-off;
        # FWD-037 moved it with the state writers to fde-backlog
        for rel in ("skills/fde-backlog/SKILL.md",
                    ".claude/skills/fde-backlog/SKILL.md"):
            self.assertIn("The plan is frozen at sign-off", flat(rel), rel)
        for rel in ("agents/fde-promotion.md", ".claude/agents/fde-promotion.md"):
            self.assertIn("recorded on `board.md`) is marked here",
                          flat(rel), rel)


class TestRoleCountIsOneSentence(unittest.TestCase):
    """reviews/FWD-032 F2: "all five" is the five working roles; the
    example beside the size table names architecture at M and the two
    review kinds with their real budgets."""

    FIVE = ("\"All five roles\" means the five working roles; the "
            "walkthrough evaluator is a sixth role that writes nothing.")

    def test_same_sentence_in_each_place(self):
        for rel in AGENTS_SURFACES + ("README.md", "skills/fde-triage/SKILL.md",
                                      ".claude/skills/fde-triage/SKILL.md"):
            self.assertIn(self.FIVE, flat(rel), rel)
        for rel in AGENTS_SURFACES:
            self.assertIn(self.FIVE, " ".join(section(read(rel), "Roles").split()), rel)

    def test_example_matches_the_table(self):
        # C-13 cycle F1: the M example also names the plan review
        example = ("`FORWARD: M — spec + plan review + architecture + impl + "
                   "demand review(1r) + cycle review(full+delta) + promotion`")
        for rel in ("skills/fde-triage/SKILL.md", ".claude/skills/fde-triage/SKILL.md"):
            self.assertIn(example, flat(rel), rel)
        for rel in AGENTS_SURFACES + ("skills/fde-triage/SKILL.md", "README.md"):
            self.assertNotIn("spec + impl + adversarial(2r)", flat(rel), rel)


class TestFindingsTemplateRounds(unittest.TestCase):
    """reviews/FWD-032 F3: the installed template states ADR-0019's rounds."""

    def test_rounds_comment(self):
        for rel in ("templates/findings.template.toml",
                    ".fde/templates/findings.template.toml"):
            line = next(l for l in read(rel).splitlines()
                        if l.startswith("rounds_planned"))
            self.assertIn("demand review 1; cycle review XS/S 1, M/L 2", line, rel)
            self.assertNotIn("L 3", line, rel)


class TestNoFdeCli(unittest.TestCase):
    """reviews/FWD-032 F5: there is no `fde` executable; regeneration is
    the fde-sync skill."""

    def test_marker_names_the_skill(self):
        marker = section(read("SETUP.md"), "6.")
        self.assertIn("Regenerate with the fde-sync skill.", marker)
        for rel in ("SETUP.md", "AGENTS.md", "templates/AGENTS.md.template",
                    "templates/fde-gate.yml", ".github/workflows/fde-gate.yml",
                    "templates/fde.config.template.toml", "fde.config.toml",
                    "agents/fde-adversarial.md", ".claude/agents/fde-adversarial.md",
                    "tests/mirror.toml", "runtime/verify.py"):
            text = read(rel)
            self.assertNotIn("`fde sync`", text, rel)
            self.assertNotIn("re-run fde sync", text, rel)

    def test_runtime_names_no_fde_cli(self):
        # reviews/FWD-033 F5: the missing-config error names the skill
        import re
        files = sorted(ROOT.glob("runtime/*.py")) + sorted(ROOT.glob("bin/fde/*.py"))
        self.assertGreater(len(files), 5)   # not vacuous
        for p in files:
            text = p.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"`fde (init|sync|verify|status)`", text), p.name)
        for rel in ("runtime/fde_lib.py", "bin/fde/fde_lib.py"):
            self.assertIn("run the fde-init skill first", read(rel), rel)


class TestWalkthroughSizeIsOneRule(unittest.TestCase):
    """#13: one rule — whenever the cycle has a `front` demand, any size
    (ADR-0019 rule 5)."""

    def test_runs_with_a_front_demand_at_every_size(self):
        text = flat("skills/fde-walkthrough/SKILL.md")
        self.assertIn("whenever the cycle has a `front` demand, at every size", text)
        for gone in ("Opt-in at every size", "Opt-in at M and L", "| XS / S | never |"):
            self.assertNotIn(gone, text, gone)


class TestAdr0017StatusIsCurrent(unittest.TestCase):
    """#10: ADR-0017's status names what now holds its ground."""

    def test_status_points_at_adr_0019(self):
        text = read("docs/adr/0017-a-cycle-is-declared-in-git-before-it-runs.md")
        status = re.search(r"(?m)^status: (.*)$", text).group(1)
        self.assertIn("ADR-0019", status)
        head = text.split("### Earlier status", 1)[0]
        self.assertIn("backlog.md", head)


class TestSetupInstallsTheCycleLayout(unittest.TestCase):
    """Guard residual, SETUP side: an install creates the ADR-0019 layout."""

    def test_setup_creates_cycles_and_points_criteria_there(self):
        text = flat("SETUP.md")
        self.assertIn("`reviews/`, `cycles/`", text)
        self.assertNotIn("`reviews/`, `promotions/`", text)
        self.assertNotIn("criteria live in `specs/<demand-id>/acceptance.md`", text)


class TestScrumIsTheBacklogGoalSwitch(unittest.TestCase):
    """FWD-031 board note: sprints are retired (ADR-0019); `[scrum]` only
    arms the backlog's dated goal."""

    def test_no_install_surface_sells_sprints(self):
        for rel in ("SETUP.md", "README.md", "templates/fde.config.template.toml"):
            text = flat(rel)
            self.assertNotIn("sprints", text.lower(), rel)
            self.assertIn("dated goal", text, rel)


class TestGuardNamesTheCycleLayoutFirst(unittest.TestCase):
    """Board residual: cycles/ is the primary layout; promotions/ and
    specs/**/acceptance.md are kept for cycles opened before ADR-0019."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.p = make_project(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_guard(self, rel, agent):
        return guard(self.p, {"tool_input": {"file_path": str(self.p / rel)},
                              "agent_name": agent})

    def test_promotion_block_names_the_legacy_path_as_legacy(self):
        r = self.run_guard("reviews/D-1/findings.toml", "fde-promotion")
        self.assertEqual(r.returncode, 2)
        self.assertIn("writes only in cycles/, backlog.md", r.stderr)
        self.assertIn("promotions/ only for a cycle opened before kernel ADR-0019", r.stderr)

    def test_implementation_block_names_the_cycle_files(self):
        r = self.run_guard("cycles/C-1/plan.md", "fde-implementation")
        self.assertEqual(r.returncode, 2)
        self.assertIn("plan.md, deploy.md, review.md, promotion.md", r.stderr)


if __name__ == "__main__":
    unittest.main()
