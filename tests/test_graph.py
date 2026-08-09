"""FWD-008: the artifact graph — builder, weights, analysis, and the gate.
Fixtures build a small artifact tree; assertions pin the derivation."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import graph  # noqa: E402
from support import make_project, verify  # noqa: E402


def demand(p, did, size="S", spec=True, acceptance=True):
    d = Path(p) / "specs" / did
    d.mkdir(parents=True, exist_ok=True)
    if spec:
        (d / "spec.md").write_text(f"# {did}\nTriage: → **{size}**\n")
    if acceptance:
        (d / "acceptance.md").write_text("---\ndate: 2026-08-09\n---\n# ok\n")


def review(p, did, findings, transcript="agent-abc"):
    d = Path(p) / "reviews" / did
    d.mkdir(parents=True, exist_ok=True)
    body = [f'[meta]\ncontext_policy = "artifact_only"\nagent_transcript = "{transcript}"\n']
    for attr, sev, cite in findings:
        key = "principle" if cite[0].isupper() and "-" in cite else "probe"
        body.append(f'\n[[finding]]\nattribute = "{attr}"\nseverity = "{sev}"\n'
                    f'{key} = "{cite}"\nevidence = "x"\n')
    (d / "findings.toml").write_text("".join(body))


class TestBuilder(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_demand_id_canonicalizes_across_slugged_dirs(self):
        # spec dir slugged, review dir bare — must join to one demand
        demand(self.p, "FWD-010-some-slug")
        review(self.p, "FWD-010", [("maintainability", "low", "MNT-1")])
        g = graph.build_graph(Path(self.p))
        demands = [n["id"] for n in g.nodes.values() if n["kind"] == "demand"]
        self.assertEqual(demands.count("FWD-010"), 1)
        self.assertNotIn("FWD-010-some-slug", demands)

    def test_weights_from_size_severity_and_config(self):
        demand(self.p, "FWD-011", size="L")
        review(self.p, "FWD-011", [("functional_correctness", "critical", "boundary probe")])
        g = graph.build_graph(Path(self.p))
        self.assertEqual(g.nodes[graph._node("demand", "FWD-011")]["weight"], 4.0)  # L
        crit = [w for _s, e, _d, w in g.edges if e == "contains"]
        self.assertIn(4.0, crit)  # critical severity
        self.assertEqual(g.nodes[graph._node("attribute", "functional_correctness")]["weight"], 26.0)

    def test_principle_aggregates_by_catalog_id(self):
        demand(self.p, "FWD-012")
        review(self.p, "FWD-012", [("maintainability", "high",
                                    "MNT-1 single source of truth: long text here")])
        g = graph.build_graph(Path(self.p))
        self.assertIn(graph._node("principle", "MNT-1"), g.nodes)

    def test_malformed_findings_degrade_not_crash(self):
        d = Path(self.p) / "reviews" / "FWD-013"
        d.mkdir(parents=True)
        (d / "findings.toml").write_text("[[finding]\nbroken ===\n")
        g = graph.build_graph(Path(self.p))  # must not raise
        self.assertTrue(g.nodes[graph._node("review", "FWD-013")]["malformed"])


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)
        demand(self.p, "FWD-020")
        review(self.p, "FWD-020", [
            ("maintainability", "high", "MNT-1"),
            ("maintainability", "low", "MNT-1"),
            ("observability", "critical", "OBS-1"),
        ])
        self.g = graph.build_graph(Path(self.p))

    def tearDown(self):
        self._t.cleanup()

    def test_recurring_ranks_by_severity_weight(self):
        r = dict((self.g.nodes[n]["id"], w)
                 for n, w in self.g.recurring_principles())
        self.assertEqual(r["OBS-1"], 4.0)     # one critical
        self.assertEqual(r["MNT-1"], 4.0)     # high(3) + low(1), aggregated

    def test_central_surfaces_the_hit_attribute(self):
        top = self.g.weighted_in_degree()[0][0]
        self.assertEqual(self.g.nodes[top]["kind"], "attribute")

    def test_ego_of_a_demand_excludes_siblings(self):
        demand(self.p, "FWD-021")
        review(self.p, "FWD-021", [("maintainability", "low", "MNT-1")])
        g = graph.build_graph(Path(self.p))
        ego = g.ego(graph._node("demand", "FWD-020"))
        ids = {n["id"] for n in ego.nodes.values() if n["kind"] == "demand"}
        self.assertEqual(ids, {"FWD-020"})  # shared MNT-1 does not bridge

    def test_path_follows_directed_edges(self):
        p = self.g.path(graph._node("demand", "FWD-020"),
                        graph._node("attribute", "observability"))
        self.assertIsNotNone(p)
        self.assertEqual(p[0], graph._node("demand", "FWD-020"))


class TestForbiddenOrphans(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "traceability")

    def test_clean_tree_has_no_orphans(self):
        demand(self.p, "FWD-030")
        self.assertEqual(graph.forbidden_orphans(Path(self.p)), [])
        self.assertEqual(self.gate().returncode, 0)

    def test_acceptance_without_spec_is_forbidden(self):
        demand(self.p, "FWD-031", spec=False)  # acceptance only
        self.assertEqual(self.gate().returncode, 1)
        self.assertIn("acceptance.md without spec.md", self.gate().stdout)

    def test_promotion_without_review_is_forbidden(self):
        demand(self.p, "FWD-032")
        d = Path(self.p) / "promotions" / "FWD-032"
        d.mkdir(parents=True)
        (d / "decision.md").write_text("promoted\n")
        self.assertEqual(self.gate().returncode, 1)
        self.assertIn("promoted without a review", self.gate().stdout)

    def test_incomplete_demand_midloop_is_not_an_orphan(self):
        # spec but no review yet — normal, must stay green
        demand(self.p, "FWD-033")
        self.assertEqual(self.gate().returncode, 0)

    def test_dangling_supersedes_is_forbidden(self):
        adr = Path(self.p) / "docs" / "adr"
        adr.mkdir(parents=True)
        (adr / "0001-x.md").write_text("---\nsupersedes: 0099\n---\n# x\n")
        self.assertEqual(self.gate().returncode, 1)
        self.assertIn("missing ADR", self.gate().stdout)

    def test_supersedes_parses_from_title_first_adrs(self):
        # the repo's ACTUAL convention: title first, plain header lines,
        # no --- fence. The fenced-only test above missed this (the
        # blocking FWD-008 review finding). A body 'date:'/'supersedes:'
        # below the first ## section must NOT be read.
        adr = Path(self.p) / "docs" / "adr"
        adr.mkdir(parents=True)
        (adr / "0001-a.md").write_text(
            "# ADR-0001 — Title\n\ndate: 2026-08-09\nstatus: accepted\n"
            "supersedes: 0099\n\n## Context\nsupersedes: 0002 in prose\n")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("0099", r.stdout)      # header supersedes parsed
        self.assertNotIn("0002", r.stdout)   # prose below ## ignored

    def test_size_comes_from_the_triage_line_not_stray_bold(self):
        d = Path(self.p) / "specs" / "FWD-040"
        d.mkdir(parents=True)
        (d / "spec.md").write_text(
            "# FWD-040\nSome prose with **L** bolded early.\n"
            "Triage: → **S**\n")
        g = graph.build_graph(Path(self.p))
        self.assertEqual(g.nodes[graph._node("demand", "FWD-040")]["weight"], 2.0)

    def test_distinct_probes_do_not_merge_on_truncation(self):
        pre = "regression in previously accepted behavior across the system X "
        demand(self.p, "FWD-041")
        review(self.p, "FWD-041", [
            ("functional_correctness", "high", pre + "alpha differs"),
            ("functional_correctness", "high", pre + "beta differs"),
        ])
        g = graph.build_graph(Path(self.p))
        probes = [n for n in g.nodes.values() if n["kind"] == "probe"]
        self.assertEqual(len(probes), 2)  # not merged by a 48-char prefix

    def test_supersedes_cycle_is_forbidden(self):
        adr = Path(self.p) / "docs" / "adr"
        adr.mkdir(parents=True)
        (adr / "0001-a.md").write_text("---\nsupersedes: 0002\n---\n# a\n")
        (adr / "0002-b.md").write_text("---\nsupersedes: 0001\n---\n# b\n")
        self.assertEqual(self.gate().returncode, 1)
        self.assertIn("cycle", self.gate().stdout)

    def test_scrum_off_does_not_flag_unplanned_reviews(self):
        # XS review with no spec dir and no sprint — anchorless, but
        # scrum is off in this fixture, so it must not be flagged
        review(self.p, "FWD-034", [("maintainability", "low", "MNT-1")])
        self.assertEqual(self.gate().returncode, 0)


if __name__ == "__main__":
    unittest.main()
