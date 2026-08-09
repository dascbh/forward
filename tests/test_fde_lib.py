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
                         (DEFAULT_BEHAVIOR_PATHS, DEFAULT_EVAL_PATHS))
        self.assertEqual(gate_paths({"gate": {"behavior_paths": []}})[0],
                         DEFAULT_BEHAVIOR_PATHS)

    def test_prefixes_are_normalized_with_trailing_slash(self):
        bp, ep = gate_paths({"gate": {"behavior_paths": ["backend/app"],
                                      "eval_paths": ["backend/tests/"]}})
        self.assertEqual(bp, ("backend/app/",))
        self.assertEqual(ep, ("backend/tests/",))


class TestProbePlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def test_plan_is_weight_descending_with_round_and_blocking_rules(self):
        plan = probe_plan(cfg(), self.spec)
        weights = [s["weight"] for s in plan]
        self.assertEqual(weights, sorted(weights, reverse=True))
        by_id = {s["attribute"]: s for s in plan}
        self.assertEqual(by_id["functional_correctness"]["rounds"], 3)   # 26/10
        self.assertEqual(by_id["operational_cost"]["rounds"], 1)         # floor 1
        self.assertTrue(by_id["functional_correctness"]["blocking"])     # >= 15
        self.assertFalse(by_id["usability_accessibility"]["blocking"])   # 8 < 15


if __name__ == "__main__":
    unittest.main()
