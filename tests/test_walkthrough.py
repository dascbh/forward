"""ADR-0014/FWD-018: the stdlib divergence metric and its opt-in gate.

Every case here builds a fixture on disk and asserts what the parser, the
formula, or the GATE does — never a grep for a word (the exact tautology
FWD-010's own review killed, test_divergence.py's docstring records it).
"""
from __future__ import annotations

import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import walkthrough  # noqa: E402
from support import make_project, run_git, verify  # noqa: E402

# The exact worked "partial overlap" example ADR-0014 section 4 and
# skills/fde-walkthrough/SKILL.md publish: primary_actions overlap 1/3
# (distance 0.667), the other two slots identical (distance 0.0), mean
# score 0.222. Reused here so this suite is checked against the same
# numbers the design record already committed to, not a fresh guess.
MODEL_A = """\
## What this is
A storefront for buying a single digital product.

## Perceived primary actions
- buy product
- view cart

## Perceived action -> consequence
- buy product -> completes the purchase
- view cart -> shows items added

## Unclear points
- unclear if tax is included
- unclear how to remove an item
"""

MODEL_B = """\
## What this is
A checkout flow for a single product purchase.

## Perceived primary actions
- buy product
- checkout now

## Perceived action -> consequence
- buy product -> completes the purchase
- view cart -> shows items added

## Unclear points
- unclear if tax is included
- unclear how to remove an item
"""

DISJOINT_A = """\
## Perceived primary actions
- alpha action

## Perceived action -> consequence
- alpha action -> alpha consequence

## Unclear points
- alpha unclear
"""

DISJOINT_B = """\
## Perceived primary actions
- beta action

## Perceived action -> consequence
- beta action -> beta consequence

## Unclear points
- beta unclear
"""


class TestNormalization(unittest.TestCase):
    def test_normalize_phrase_strips_lowers_and_collapses_whitespace(self):
        self.assertEqual(walkthrough.normalize_phrase("  Buy   Product  "),
                         "buy product")
        self.assertEqual(walkthrough.normalize_phrase("Buy\tProduct\n"),
                         "buy product")

    def test_canonicalize_pair_normalizes_both_sides_of_the_arrow(self):
        a = walkthrough.canonicalize_pair("Buy Product -> Ships Free")
        b = walkthrough.canonicalize_pair("buy   product->ships   free")
        self.assertEqual(a, b)
        self.assertEqual(a, "buy product -> ships free")

    def test_canonicalize_pair_without_an_arrow_falls_back_to_whole_phrase(self):
        self.assertEqual(walkthrough.canonicalize_pair("no arrow here"),
                         walkthrough.normalize_phrase("no arrow here"))

    def test_agreeing_on_action_but_not_consequence_is_still_divergence(self):
        # ADR-0014 section 4's own requirement: the pair is the unit, not
        # the action alone
        a = walkthrough.canonicalize_pair("buy product -> ships free")
        b = walkthrough.canonicalize_pair("buy product -> charges immediately")
        self.assertNotEqual(a, b)


class TestSlotDistance(unittest.TestCase):
    def test_both_empty_is_zero_not_incomparable(self):
        self.assertEqual(walkthrough.slot_distance(set(), set()), 0.0)

    def test_identical_sets_is_zero(self):
        s = {"a", "b"}
        self.assertEqual(walkthrough.slot_distance(s, set(s)), 0.0)

    def test_fully_disjoint_nonempty_is_one(self):
        self.assertEqual(walkthrough.slot_distance({"a"}, {"b"}), 1.0)

    def test_partial_overlap_matches_the_published_worked_example(self):
        a = {"buy product", "view cart"}
        b = {"buy product", "checkout now"}
        self.assertEqual(walkthrough.slot_distance(a, b), 0.667)

    def test_symmetric(self):
        a, b = {"x", "y"}, {"y", "z"}
        self.assertEqual(walkthrough.slot_distance(a, b),
                         walkthrough.slot_distance(b, a))


class TestParsePerceivedModel(unittest.TestCase):
    def test_atx_headings_parse_all_four_sections(self):
        m = walkthrough.parse_perceived_model(MODEL_A)
        self.assertEqual(m["what_this_is"],
                         "A storefront for buying a single digital product.")
        self.assertEqual(m["primary_actions"], {"buy product", "view cart"})
        self.assertEqual(m["action_consequences"],
                         {"buy product -> completes the purchase",
                          "view cart -> shows items added"})
        self.assertEqual(m["unclear_points"],
                         {"unclear if tax is included",
                          "unclear how to remove an item"})

    def test_bold_headings_parse_identically_to_atx(self):
        bold = """\
**What this is**
A storefront for buying a single digital product.

**Perceived primary actions**
- buy product
- view cart

**Perceived action -> consequence**
- buy product -> completes the purchase
- view cart -> shows items added

**Unclear points**
- unclear if tax is included
- unclear how to remove an item
"""
        self.assertEqual(walkthrough.parse_perceived_model(bold),
                         walkthrough.parse_perceived_model(MODEL_A))

    def test_non_bullet_prose_inside_a_scored_section_is_never_scored(self):
        text = """\
## Perceived primary actions
I spent a few minutes looking around before deciding.
- buy product
"""
        m = walkthrough.parse_perceived_model(text)
        self.assertEqual(m["primary_actions"], {"buy product"})

    def test_what_this_is_is_captured_but_excluded_from_scored_slots(self):
        m = walkthrough.parse_perceived_model(MODEL_A)
        self.assertTrue(m["what_this_is"])
        # compute_divergence must never see it — proven in TestComputeDivergence


class TestComputeDivergence(unittest.TestCase):
    def test_identical_models_score_zero(self):
        m = walkthrough.parse_perceived_model(MODEL_A)
        result = walkthrough.compute_divergence(m, dict(m))
        self.assertEqual(result["score"], 0.0)
        for slot in walkthrough.SLOTS:
            self.assertEqual(result["per_slot"][slot]["distance"], 0.0)

    def test_fully_disjoint_models_score_one(self):
        a = walkthrough.parse_perceived_model(DISJOINT_A)
        b = walkthrough.parse_perceived_model(DISJOINT_B)
        result = walkthrough.compute_divergence(a, b)
        self.assertEqual(result["score"], 1.0)

    def test_partial_overlap_matches_the_published_worked_example(self):
        a = walkthrough.parse_perceived_model(MODEL_A)
        b = walkthrough.parse_perceived_model(MODEL_B)
        result = walkthrough.compute_divergence(a, b)
        self.assertEqual(result["score"], 0.222)
        pa = result["per_slot"]["primary_actions"]
        self.assertEqual((pa["intersection"], pa["union"], pa["distance"]), (1, 3, 0.667))
        ac = result["per_slot"]["action_consequences"]
        self.assertEqual((ac["intersection"], ac["union"], ac["distance"]), (2, 2, 0.0))
        up = result["per_slot"]["unclear_points"]
        self.assertEqual((up["intersection"], up["union"], up["distance"]), (2, 2, 0.0))

    def test_symmetric_regardless_of_run_order(self):
        a = walkthrough.parse_perceived_model(MODEL_A)
        b = walkthrough.parse_perceived_model(MODEL_B)
        self.assertEqual(walkthrough.compute_divergence(a, b)["score"],
                         walkthrough.compute_divergence(b, a)["score"])

    def test_a_change_to_what_this_is_alone_never_moves_the_score(self):
        a = walkthrough.parse_perceived_model(MODEL_A)
        b = dict(a)
        b["what_this_is"] = "a completely different one-line description"
        self.assertEqual(walkthrough.compute_divergence(a, a)["score"],
                         walkthrough.compute_divergence(a, b)["score"])


class TestRenderDivergenceToml(unittest.TestCase):
    def test_round_trips_through_tomllib(self):
        a = walkthrough.parse_perceived_model(MODEL_A)
        b = walkthrough.parse_perceived_model(MODEL_B)
        result = walkthrough.compute_divergence(a, b)
        text = walkthrough.render_divergence_toml(
            demand="FWD-018", score=result["score"], per_slot=result["per_slot"],
            intended_model="specs/FWD-018-x/design/intended-model.md",
            perceived_model_a="walkthroughs/FWD-018-x/perceived-model-a.md",
            perceived_model_b="walkthroughs/FWD-018-x/perceived-model-b.md",
            threshold=0.30)
        data = tomllib.loads(text)
        self.assertEqual(data["demand"], "FWD-018")
        self.assertEqual(data["score"], 0.222)
        self.assertEqual(data["threshold"], 0.30)
        self.assertEqual(data["per_slot"]["primary_actions"]["distance"], 0.667)

    def test_no_threshold_omits_the_key_entirely(self):
        text = walkthrough.render_divergence_toml(
            demand="FWD-018", score=0.0,
            per_slot={s: {"intersection": 0, "union": 0, "distance": 0.0}
                     for s in walkthrough.SLOTS},
            intended_model="x", perceived_model_a="a", perceived_model_b="b")
        data = tomllib.loads(text)
        self.assertNotIn("threshold", data)


class TestGate(unittest.TestCase):
    """[erosion]'s exact silence discipline, restated for [walkthrough]."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)
        run_git(self.p, "add", "-A")
        run_git(self.p, "commit", "-q", "-m", "seed")

    def tearDown(self):
        self._t.cleanup()

    def _add_walkthrough(self, block: str):
        with open(Path(self.p) / "fde.config.toml", "a") as fh:
            fh.write("\n[walkthrough]\n" + block)

    def _write_divergence(self, did: str, score: float):
        d = Path(self.p) / "walkthroughs" / did
        d.mkdir(parents=True, exist_ok=True)
        (d / "divergence.toml").write_text(
            f'demand = "{did}"\nscore = {score}\n'
            f'intended_model = "specs/{did}/design/intended-model.md"\n'
            f'perceived_model_a = "walkthroughs/{did}/perceived-model-a.md"\n'
            f'perceived_model_b = "walkthroughs/{did}/perceived-model-b.md"\n')

    def gate(self):
        return verify(self.p, "--gate", "walkthrough")

    def test_absent_section_reports_mode_off_when_invoked_explicitly(self):
        r = self.gate()
        self.assertEqual(r.returncode, 0)
        self.assertIn("walkthrough mode off", r.stdout)

    def test_enabled_without_a_threshold_is_not_measured_not_a_pass(self):
        self._add_walkthrough("enabled = true\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0)
        self.assertIn("not measured", r.stdout)
        self.assertNotIn("within the declared", r.stdout)

    def test_enabled_with_threshold_but_no_divergence_file_is_not_measured(self):
        self._add_walkthrough("enabled = true\ndivergence_threshold = 0.30\n")
        r = self.gate()
        self.assertEqual(r.returncode, 0)
        self.assertIn("not measured", r.stdout)

    def test_score_under_threshold_passes(self):
        self._add_walkthrough("enabled = true\ndivergence_threshold = 0.30\n")
        self._write_divergence("FWD-500", 0.222)
        r = self.gate()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("within the declared divergence budget", r.stdout)

    def test_score_over_threshold_fails(self):
        self._add_walkthrough("enabled = true\ndivergence_threshold = 0.10\n")
        self._write_divergence("FWD-501", 0.222)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("score 0.222", r.stdout)
        self.assertIn("threshold 0.1", r.stdout)

    def test_absent_budget_stays_silent_under_the_full_gate(self):
        # --all must not surface WALKTHROUGH at all when [walkthrough] is
        # undeclared — silence is the point, not merely a passing row
        r = verify(self.p, "--all")
        self.assertNotIn("WALKTHROUGH", r.stdout)


class TestPureCoreCLIWiring(unittest.TestCase):
    def test_walkthrough_is_a_known_gate(self):
        with tempfile.TemporaryDirectory() as t:
            p = make_project(t)
            run_git(p, "add", "-A")
            run_git(p, "commit", "-q", "-m", "seed")
            r = verify(p, "--gate", "bogus-gate-name")
            self.assertEqual(r.returncode, 2)
            self.assertIn("walkthrough", r.stderr)


if __name__ == "__main__":
    unittest.main()
