"""FM-1/R2: validation, floors, escalation, gate paths, probe plan."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

from fde_lib import (  # noqa: E402
    DEFAULT_BEHAVIOR_PATHS,
    DEFAULT_EVAL_PATHS,
    Config,
    Spec,
    escalated_security_floor,
    gate_paths,
    path_matches,
    probe_plan,
    validate,
)

WEIGHTS = {
    "functional_correctness": 26, "security_privacy": 14,
    "reliability_resilience": 12, "observability": 12, "maintainability": 12,
    "performance_scale": 9, "usability_accessibility": 8, "operational_cost": 7,
}


def cfg(weights=None, depths=None, **raw_extra) -> Config:
    w = dict(WEIGHTS if weights is None else weights)
    d = dict(depths or {})
    raw = {"weights": w, "depths": d, **raw_extra}
    return Config(path=Path("fixture"), raw=raw, weights=w, depths=d)


def codes(violations) -> set:
    return {v.code for v in violations}


class TestValidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def test_valid_config_has_no_violations(self):
        self.assertEqual(validate(cfg(), self.spec), [])

    def test_budget_must_sum_exactly_100(self):
        w = dict(WEIGHTS, security_privacy=13)
        self.assertIn("VEC-A-BUDGET", codes(validate(cfg(w), self.spec)))

    def test_weight_below_floor_is_rejected(self):
        w = dict(WEIGHTS, security_privacy=5, operational_cost=16)  # still 100
        self.assertIn("VEC-A-FLOOR", codes(validate(cfg(w), self.spec)))

    def test_missing_attribute_is_rejected(self):
        w = dict(WEIGHTS)
        del w["operational_cost"]
        self.assertIn("VEC-A-MISSING", codes(validate(cfg(w), self.spec)))

    def test_unknown_attribute_is_rejected(self):
        w = dict(WEIGHTS, nonsense=1)
        self.assertIn("VEC-A-UNKNOWN", codes(validate(cfg(w), self.spec)))

    def test_forbidden_keys_cannot_exist(self):
        v = validate(cfg(gates_disabled=True), self.spec)
        self.assertIn("CFG-FORBIDDEN-KEY", codes(v))

    def test_depth_override_is_upward_only(self):
        c = cfg(depths={"data_modeling": 1}, derived={"depths": {"data_modeling": 2}})
        self.assertIn("VEC-B-DOWNWARD", codes(validate(c, self.spec)))

    def test_qa_depth_zero_contradicts_i1(self):
        c = cfg(depths={"qa_test_strategy": 0})
        self.assertIn("VEC-B-QA-FLOOR", codes(validate(c, self.spec)))

    def test_empty_gate_lists_are_rejected(self):
        c = cfg(gate={"behavior_paths": []})
        self.assertIn("GATE-EMPTY", codes(validate(c, self.spec)))


class TestEscalation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def test_security_floor_escalates_by_data_class_and_never_drops(self):
        for dc, floor in [("public", 8), ("internal", 8), ("personal", 12),
                          ("financial", 16), ("health", 20)]:
            c = cfg(triage={"data_class": dc})
            self.assertEqual(escalated_security_floor(c, self.spec), floor, dc)


class TestGatePaths(unittest.TestCase):
    def test_defaults_when_gate_absent_or_empty(self):
        self.assertEqual(gate_paths({}),
                         (tuple(DEFAULT_BEHAVIOR_PATHS), tuple(DEFAULT_EVAL_PATHS)))
        self.assertEqual(gate_paths({"gate": {"behavior_paths": []}})[0],
                         tuple(DEFAULT_BEHAVIOR_PATHS))

    def test_entries_are_kept_as_declared(self):
        bp, ep = gate_paths({"gate": {"behavior_paths": ["backend/app", "SETUP.md"],
                                      "eval_paths": ["backend/tests/"]}})
        self.assertEqual(bp, ("backend/app", "SETUP.md"))
        self.assertEqual(ep, ("backend/tests/",))


class TestPathMatches(unittest.TestCase):
    def test_directory_entries_match_their_subtree_slash_optional(self):
        self.assertTrue(path_matches("src/a.py", ("src/",)))
        self.assertTrue(path_matches("backend/app/x.py", ("backend/app",)))
        self.assertFalse(path_matches("backend/apple.py", ("backend/app",)))

    def test_file_entries_match_exactly(self):
        self.assertTrue(path_matches("SETUP.md", ("SETUP.md",)))
        self.assertFalse(path_matches("SETUP.md.bak", ("SETUP.md",)))
        self.assertFalse(path_matches("docs/SETUP.md", ("SETUP.md",)))

    def test_no_sibling_prefix_bleed(self):
        self.assertFalse(path_matches("specs/x.md", ("spec",)))
        self.assertTrue(path_matches("spec/x.toml", ("spec",)))


class TestProbePlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def test_plan_is_weight_descending(self):
        plan = probe_plan(cfg(), self.spec)
        weights = [s["weight"] for s in plan]
        self.assertEqual(weights, sorted(weights, reverse=True))
        by_id = {s["attribute"]: s for s in plan}
        self.assertTrue(by_id["functional_correctness"]["probes"])

    def test_weight_orders_only_never_rounds_or_blocking(self):
        # ADR-0018: rounds come from the triage size, blocking from severity
        # inside the spec's threat model — a heavy weight must not turn
        # every edge case into a blocker or add rounds on its own
        for step in probe_plan(cfg(), self.spec):
            self.assertNotIn("rounds", step, step["attribute"])
            self.assertNotIn("blocking", step, step["attribute"])


class TestGatePathsMustBeLists(unittest.TestCase):
    """B-16 (FWD-041): a bare string is not a list of paths — tuple("src/")
    is four one-letter roots that match nothing, and I1 goes quiet."""

    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def test_string_behavior_paths_are_rejected(self):
        c = cfg(gate={"behavior_paths": "src/", "eval_paths": ["tests/"]})
        self.assertIn("GATE-TYPE", codes(validate(c, self.spec)))

    def test_string_eval_paths_are_rejected(self):
        c = cfg(gate={"behavior_paths": ["src/"], "eval_paths": "tests/"})
        self.assertIn("GATE-TYPE", codes(validate(c, self.spec)))

    def test_non_string_entries_are_rejected(self):
        for bad in ([1], ["src/", ""], [["src/"]], {"a": "src/"}):
            c = cfg(gate={"behavior_paths": bad})
            self.assertIn("GATE-TYPE", codes(validate(c, self.spec)), bad)

    def test_a_list_of_paths_passes(self):
        c = cfg(gate={"behavior_paths": ["src/", "SETUP.md"],
                      "eval_paths": ["tests/"]})
        self.assertEqual(validate(c, self.spec), [])


if __name__ == "__main__":
    unittest.main()


class TestUsedBacklogIds(unittest.TestCase):
    """Backlog ids are taken across parallel worktrees and main, not only in
    this checkout — the collision that cost C-14 two renumberings."""

    def setUp(self):
        import subprocess
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()

        def git(*a, cwd=self.repo):
            subprocess.run(["git", "-C", str(cwd), *a], check=True,
                           capture_output=True)
        self.git = git
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        (self.repo / "backlog.md").write_text(
            "goal: x\ndate: 2026-09-29\n\n- B-1 one\n- B-3 three\n")
        git("add", "-A")
        git("commit", "-q", "-m", "init")

    def test_an_uncommitted_line_in_another_worktree_is_taken(self):
        from fde_lib import next_backlog_id, used_backlog_ids
        wt = Path(self.tmp.name) / "wt"
        self.git("worktree", "add", "-q", "-b", "demand", str(wt))
        with open(wt / "backlog.md", "a") as f:
            f.write("- B-7 found by a parallel demand\n")
        used = used_backlog_ids(self.repo)
        self.assertEqual(used["B-7"], [f"worktree:{wt.resolve()}"])
        self.assertIn("ref:main", used["B-3"])
        self.assertEqual(next_backlog_id(self.repo), "B-8")

    def test_a_cycle_file_counts(self):
        from fde_lib import next_backlog_id
        (self.repo / "cycles" / "C-1").mkdir(parents=True)
        (self.repo / "cycles" / "C-1" / "plan.md").write_text("- B-12 item\n")
        self.assertEqual(next_backlog_id(self.repo), "B-13")

    def test_without_git_only_the_tree_is_read(self):
        from fde_lib import used_backlog_ids
        plain = Path(self.tmp.name) / "plain"
        plain.mkdir()
        (plain / "backlog.md").write_text("- B-2 x\n")
        self.assertEqual(used_backlog_ids(plain), {"B-2": ["tree"]})

    def test_status_next_id_sees_the_worktree(self):
        import subprocess
        wt = Path(self.tmp.name) / "wt2"
        self.git("worktree", "add", "-q", "-b", "d2", str(wt))
        with open(wt / "backlog.md", "a") as f:
            f.write("- B-20 parallel\n")
        out = subprocess.run(
            [sys.executable, str(ROOT / "runtime" / "status.py"), "--root",
             str(self.repo), "--format", "json"], capture_output=True, text=True)
        self.assertIn('"backlog_id": "B-21"', out.stdout, out.stderr)


class TestProcessKnobs(unittest.TestCase):
    """[lanes] and [review]: the numbers the skills cite are tuned in
    fde.config.toml, validated, never edited in skill text."""

    def test_defaults_fill_what_the_project_leaves_out(self):
        from fde_lib import process_settings
        s = process_settings({})
        self.assertEqual(s["lanes"], {"demand_max_loc": 300, "direct_max_loc": 300})
        self.assertEqual(s["review"], {"cycle_rounds_small": 1,
                                       "cycle_rounds_large": 2, "max_findings": 5})

    def test_an_unset_direct_lane_follows_a_lowered_demand_ceiling(self):
        from fde_lib import process_settings, process_violations
        raw = {"lanes": {"demand_max_loc": 200}}
        self.assertEqual(process_settings(raw)["lanes"]["direct_max_loc"], 200)
        self.assertEqual(process_violations(raw), [])

    def test_a_misspelled_key_is_a_violation_not_a_default(self):
        from fde_lib import process_violations
        v = process_violations({"review": {"max_finding": 3}})
        self.assertEqual([x.code for x in v], ["CFG-PROCESS"])
        self.assertIn("max_finding is not a known key", v[0].message)

    def test_ranges_and_orderings_hold(self):
        from fde_lib import process_violations
        for raw in ({"lanes": {"demand_max_loc": 10}},
                    {"review": {"max_findings": True}},
                    {"review": {"cycle_rounds_small": "1"}},
                    {"lanes": {"direct_max_loc": 400}},
                    {"review": {"cycle_rounds_small": 2, "cycle_rounds_large": 1}},
                    {"lanes": "300"}):
            self.assertTrue(process_violations(raw), raw)

    def test_validate_reports_it_through_the_config_gate(self):
        c = cfg(lanes={"demand_max_loc": 5})
        self.assertIn("CFG-PROCESS", codes(validate(c, Spec.load())))

    def test_the_template_and_this_repo_carry_valid_tables(self):
        import tomllib
        from fde_lib import process_violations
        raw = tomllib.loads((ROOT / "fde.config.toml").read_text())
        self.assertEqual(process_violations(raw), [])
        tpl = (ROOT / "templates" / "fde.config.template.toml").read_text()
        for line in ("[lanes]", "demand_max_loc = 300", "[review]", "max_findings = 5"):
            self.assertIn(line, tpl)
        self.assertIn("`[lanes] demand_max_loc`", " ".join(
            (ROOT / "skills" / "fde-triage" / "SKILL.md").read_text().split()))


class TestLayerIsAList(unittest.TestCase):
    """kernel ADR-0022: a demand is one goal; its layer cell lists every
    layer it touches, and a `front` in the list makes it a front demand."""

    def test_layer_cells_read_as_lists(self):
        from fde_lib import _layer_list
        self.assertEqual(_layer_list("back, front"), ["back", "front"])
        self.assertEqual(_layer_list("front"), ["front"])
        self.assertEqual(_layer_list("infra / back"), ["infra", "back"])
        self.assertEqual(_layer_list(""), [])

    def test_a_multi_layer_demand_with_front_is_a_front_demand(self):
        import tempfile
        from fde_lib import front_demand_criteria
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cycles" / "C-1").mkdir(parents=True)
            (root / "cycles" / "C-1" / "plan.md").write_text(
                "cycle: C-1\nstate: running\n\n## Demands\n\n"
                "| id | layer | depends on | files | what | meets | follows |\n"
                "|---|---|---|---|---|---|---|\n"
                "| DEM-1 | back, front | — | api/, web/ | x | A1, A2 | — |\n"
                "| DEM-2 | back | — | api/ | y | A3 | — |\n")
            for did in ("DEM-1", "DEM-2"):
                (root / "specs" / did).mkdir(parents=True)
                (root / "specs" / did / "spec.md").write_text(f"cycle: C-1\n")
            self.assertEqual(front_demand_criteria(root, root / "specs" / "DEM-1"),
                             ["A1", "A2"])
            self.assertIsNone(front_demand_criteria(root, root / "specs" / "DEM-2"))


class TestErosionRatchet(unittest.TestCase):
    """A project with no [erosion] budget gets one from its own measurement
    (SlopCodeBench gap: the gate stayed off in every client)."""

    def test_each_ceiling_is_the_next_step_above_the_measurement(self):
        from fde_lib import erosion_ratchet
        b = erosion_ratchet({"window": 50, "duplication_pct": 0.7,
                             "add_delete_ratio": 7.51, "structural_erosion": 0.619})
        self.assertEqual(b, {"window": 50, "max_duplication_pct": 1.0,
                             "max_add_delete_ratio": 8.0,
                             "max_structural_erosion": 0.62})

    def test_a_value_on_a_step_still_gets_headroom(self):
        from fde_lib import erosion_ratchet
        b = erosion_ratchet({"duplication_pct": 2.0, "add_delete_ratio": 3.0,
                             "structural_erosion": 0.4})
        self.assertEqual((b["max_duplication_pct"], b["max_add_delete_ratio"],
                          b["max_structural_erosion"]), (2.5, 3.5, 0.41))

    def test_an_unmeasured_metric_is_left_out_never_guessed(self):
        from fde_lib import erosion_ratchet
        b = erosion_ratchet({"duplication_pct": 50.0, "add_delete_ratio": None,
                             "structural_erosion": None})
        self.assertEqual(b, {"window": 50, "max_duplication_pct": 50.5})

    def test_the_toml_parses_and_passes_validation(self):
        import tomllib
        from fde_lib import erosion_ratchet_toml
        raw = tomllib.loads(erosion_ratchet_toml(
            {"duplication_pct": 12.3, "add_delete_ratio": 4.2,
             "structural_erosion": 0.448}))
        c = cfg(erosion=raw["erosion"])
        self.assertNotIn("EROSION-BUDGET", codes(validate(c, Spec.load())))

    def test_a_declared_budget_is_never_touched(self):
        from fde_lib import erosion_budget_declared
        self.assertTrue(erosion_budget_declared({"erosion": {"max_change_lines": 900}}))
        self.assertFalse(erosion_budget_declared({"erosion": {"generated_paths": ["x/"]}}))
        self.assertFalse(erosion_budget_declared({}))

    def test_structural_erosion_is_a_share(self):
        c = cfg(erosion={"max_structural_erosion": 45})
        self.assertIn("EROSION-BUDGET", codes(validate(c, Spec.load())))


class TestSlugDemandIds(unittest.TestCase):
    """A project may name demands by slug (auris: DEM-dd-card-portal); the
    kernel read them as no id and skipped them silently (2026-09-30)."""

    def test_slug_ids_are_ids_where_an_id_is_expected(self):
        from fde_lib import canon_demand, demand_id
        self.assertEqual(demand_id("DEM-contratos-familia"), "DEM-contratos-familia")
        self.assertEqual(demand_id("DEM-dd-card-portal"), "DEM-dd-card-portal")
        self.assertEqual(demand_id("`DEM-contratos`"), "DEM-contratos")
        self.assertEqual(canon_demand("DEM-dd-checklist"), "DEM-dd-checklist")

    def test_numbered_ids_keep_their_grammar(self):
        from fde_lib import demand_id
        self.assertEqual(demand_id("FWD-042"), "FWD-042")
        self.assertEqual(demand_id("FWD-001-self-install"), "FWD-001")
        self.assertEqual(demand_id("ctr-3"), "CTR-3")

    def test_prose_and_kernel_families_are_not_demands(self):
        from fde_lib import DEMAND_RE, demand_id
        for word in ("Pre-commit", "e-mail", "DEM-Contratos",
                     "C-14", "B-3", "ADR-0019", "S-005"):
            self.assertIsNone(demand_id(word), word)
        # "API-first" reads as a slug id where an id is expected; it joins
        # nothing (no demand has that name), and prose is never scanned for
        # slugs — the assertion below
        self.assertEqual(DEMAND_RE.findall("see API-first and DEM-dd-x"), [])

    def test_a_plan_table_reads_slug_rows_and_waves_schedule_them(self):
        import status
        from fde_lib import plan_demand_rows
        plan = ("## Demands\n\n| id | layer | depends on | files | what |\n"
                "|---|---|---|---|---|\n"
                "| DEM-contratos-familia | back | — | a/ | x |\n"
                "| DEM-contratos-radar | back | DEM-contratos-familia | b/ | y |\n")
        self.assertEqual(list(plan_demand_rows(plan)),
                         ["DEM-contratos-familia", "DEM-contratos-radar"])
        self.assertEqual(status.plan_waves(plan)["waves"],
                         [["DEM-contratos-familia"], ["DEM-contratos-radar"]])
