"""FWD-010 R1/R2, enforced: the divergence gate.

These replace the tautology tests the review killed — asserting that a
skill file contains the word "subtract" proves nothing about behavior.
Every case here builds a demand on disk and asserts what the GATE does.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import design  # noqa: E402
from support import make_project, verify  # noqa: E402

GOOD = """\
## How might we…
- HMW make waiting unnecessary?
- HMW make the wait productive?

## Alternatives
### A. Background job
Lens: subtract
Hypothesis: removing the wait removes the abandonment it causes.
### B. Stream partial results
Lens: invert
Hypothesis: results-as-they-arrive beat a faster total.
Traded: gives up one stable snapshot to review.

## Convergence
Chose: A — the wait is the problem, not its length.
"""


def demand(project, did, size="M", with_design=True, alternatives=None):
    d = Path(project) / "specs" / did
    (d / "design").mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text(f"# {did}\nTriage: surfaces 1 → **{size}**\n")
    (d / "acceptance.md").write_text("---\ndate: 2026-08-09\n---\n# ok\n")
    if with_design:
        (d / "design" / "flow.md").write_text("# flow\n")
    if alternatives is not None:
        (d / "design" / "alternatives.md").write_text(alternatives)
    return d


class TestGateEnforces(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "divergence")

    def test_m_sized_design_surface_without_alternatives_fails(self):
        """The exact hole the review exploited: a full M-sized UI demand
        with flow, wireframe and dated acceptance but zero divergence."""
        demand(self.p, "FWD-100", size="M")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("converged without diverging", r.stdout)

    def test_complete_divergence_passes(self):
        demand(self.p, "FWD-101", size="M", alternatives=GOOD)
        self.assertEqual(self.gate().returncode, 0)

    def test_alternatives_sharing_a_lens_count_as_one(self):
        same_lens = GOOD.replace("Lens: invert", "Lens: subtract")
        demand(self.p, "FWD-102", size="M", alternatives=same_lens)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("distinct lens", r.stdout)

    def test_l_requires_three_distinct_lenses(self):
        demand(self.p, "FWD-103", size="L", alternatives=GOOD)  # only 2
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("3 required", r.stdout)

    def test_single_framing_fails_the_reframe_rule(self):
        one_hmw = GOOD.replace("- HMW make the wait productive?\n", "")
        demand(self.p, "FWD-104", size="M", alternatives=one_hmw)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("two 'How might we'", r.stdout)

    def test_missing_discard_trade_fails(self):
        no_trade = GOOD.replace("Traded: gives up one stable snapshot to review.\n", "")
        demand(self.p, "FWD-105", size="M", alternatives=no_trade)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Traded", r.stdout)

    def test_missing_convergence_fails(self):
        no_choice = GOOD.replace("Chose: A — the wait is the problem, not its length.\n", "")
        demand(self.p, "FWD-106", size="M", alternatives=no_choice)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("Chose", r.stdout)

    def test_unknown_lens_is_rejected(self):
        bogus = GOOD.replace("Lens: invert", "Lens: vibes")
        demand(self.p, "FWD-107", size="M", alternatives=bogus)
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown lens", r.stdout)

    # -- proportionality: the gate must not become ceremony inflation ----
    def test_xs_and_s_design_surfaces_are_exempt(self):
        demand(self.p, "FWD-108", size="XS")
        demand(self.p, "FWD-109", size="S")
        self.assertEqual(self.gate().returncode, 0)

    def test_demand_without_a_design_surface_is_untouched(self):
        d = Path(self.p) / "specs" / "FWD-110"
        d.mkdir(parents=True)
        (d / "spec.md").write_text("# backend only\nTriage: → **L**\n")
        self.assertEqual(self.gate().returncode, 0)

    def test_size_read_from_the_triage_line_only(self):
        d = demand(self.p, "FWD-111", size="M", alternatives=GOOD)
        # a stray bold **L** in prose must not raise the requirement
        (d / "spec.md").write_text(
            "# FWD-111\nSome prose mentioning **L** early.\n"
            "Triage: surfaces 1 → **M**\n")
        self.assertEqual(self.gate().returncode, 0)


class TestPureCore(unittest.TestCase):
    def test_check_alternatives_is_usable_without_a_repo(self):
        self.assertEqual(design.check_alternatives(GOOD, 2), [])
        self.assertTrue(design.check_alternatives("", 2))

    def test_lens_vocabulary_matches_the_documented_five(self):
        self.assertEqual(set(design.LENSES),
                         {"subtract", "invert", "analogous",
                          "constraint-first", "object-first"})


if __name__ == "__main__":
    unittest.main()
