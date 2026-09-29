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


class TestCycleLevel(unittest.TestCase):
    """FWD-029 (ADR-0019 rule 14): the cycle links to its demands through
    plan.md's ## Demands table or the spec's `cycle:` line; sprint
    planning is no longer required, and old sprint links stay readable."""

    PLAN = ("cycle: C-{n}\ndate: 2026-09-29\n\n## Acceptance criteria\n\n"
            "- A1\n\n## Demands\n\n| id | layer | depends on | what |\n"
            "|---|---|---|---|\n{rows}\n")

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = Path(make_project(self._t.name))

    def tearDown(self):
        self._t.cleanup()

    def plan(self, n, rows, promoted=False):
        d = self.p / "cycles" / f"C-{n}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.md").write_text(self.PLAN.format(n=n, rows="\n".join(rows)))
        if promoted:
            (d / "promotion.md").write_text("decision: promote\n")

    def spec(self, did, head=""):
        d = self.p / "specs" / did
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.md").write_text(f"# {did}\n\n{head}\nbody\n")

    def edges(self, etype):
        g = graph.build_graph(self.p)
        return {(s, d) for s, e, d, _w in g.edges if e == etype}

    def test_plan_table_links_cycle_to_its_demands_not_dependencies(self):
        self.plan(1, ["| FWD-301 | back | FWD-302 | x |"])
        plans = self.edges("plans")
        self.assertIn((graph._node("cycle", "C-1"),
                       graph._node("demand", "FWD-301")), plans)
        self.assertNotIn((graph._node("cycle", "C-1"),
                          graph._node("demand", "FWD-302")), plans)

    def test_spec_cycle_line_links_cycle_to_demand(self):
        self.plan(2, [])
        self.spec("FWD-303-slug", "cycle: C-2 · layer: back · meets: A1\n")
        self.assertIn((graph._node("cycle", "C-2"),
                       graph._node("demand", "FWD-303")), self.edges("plans"))

    def test_spec_follows_line_links_demand_to_adrs(self):
        adr = self.p / "docs" / "adr"
        adr.mkdir(parents=True)
        (adr / "0019-x.md").write_text("# ADR-0019\n\ndate: 2026-09-29\n")
        self.spec("FWD-304",
                  "cycle: C-2 · layer: back · follows: ADR-0019 rule 14, ADR-18\n")
        follows = self.edges("follows")
        self.assertIn((graph._node("demand", "FWD-304"),
                       graph._node("adr", "0019")), follows)
        self.assertIn((graph._node("demand", "FWD-304"),
                       graph._node("adr", "0018")), follows)

    def test_cycle_plan_and_promotion_are_nodes(self):
        self.plan(3, ["| FWD-305 | back | — | x |"], promoted=True)
        g = graph.build_graph(self.p)
        cnode = graph._node("cycle", "C-3")
        out = {(e, d) for s, e, d, _w in g.edges if s == cnode}
        self.assertIn(("accepted_by", graph._node("plan", "C-3")), out)
        self.assertIn(("promoted_by", graph._node("promotion", "C-3")), out)

    def test_promoted_cycle_with_an_unreviewed_specified_demand_is_forbidden(self):
        self.plan(4, ["| FWD-306 | back | — | x |",
                      "| FWD-307 | back | — | x |"], promoted=True)
        self.spec("FWD-306")  # FWD-307 never specified: not built
        orphans = graph.forbidden_orphans(self.p)
        self.assertEqual(len(orphans), 1, orphans)
        self.assertIn("FWD-306", orphans[0])
        review(self.p, "FWD-306", [("maintainability", "low", "MNT-1")])
        self.assertEqual(graph.forbidden_orphans(self.p), [])

    def test_ego_of_a_demand_does_not_bridge_through_its_cycle(self):
        self.plan(5, ["| FWD-308 | back | — | x |", "| FWD-309 | back | — | x |"])
        g = graph.build_graph(self.p)
        ego = g.ego(graph._node("demand", "FWD-308"))
        ids = {n["id"] for n in ego.nodes.values() if n["kind"] == "demand"}
        self.assertEqual(ids, {"FWD-308"})
        self.assertIn(graph._node("cycle", "C-5"), ego.nodes)

    def test_unplanned_review_with_scrum_on_is_no_longer_forbidden(self):
        p = Path(make_project(tempfile.mkdtemp(dir=self._t.name), scrum=True))
        review(p, "FWD-310", [("maintainability", "low", "MNT-1")])
        self.assertEqual(graph.forbidden_orphans(p), [])
        r = verify(p, "--gate", "traceability")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_old_sprint_links_stay_readable(self):
        s = self.p / "sprints" / "S-1"
        s.mkdir(parents=True)
        (s / "goal.md").write_text("goal: g\ndate: 2026-08-09\n\n| FWD-311 |\n")
        self.assertIn((graph._node("sprint", "S-1"),
                       graph._node("demand", "FWD-311")), self.edges("selects"))


class TestWalkthroughGraph(unittest.TestCase):
    """ADR-0014 section 8 / FWD-018: intended-model, perceived-model, and
    divergence as pure analytics, plus the three impossible states
    forbidden_orphans() must catch."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.p = make_project(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def gate(self):
        return verify(self.p, "--gate", "traceability")

    def _intended(self, did, text="# intended\n"):
        d = Path(self.p) / "specs" / did / "design"
        d.mkdir(parents=True, exist_ok=True)
        (d / "intended-model.md").write_text(text)

    def _perceived(self, did, letter, text="perceived\n"):
        d = Path(self.p) / "walkthroughs" / did
        d.mkdir(parents=True, exist_ok=True)
        (d / f"perceived-model-{letter}.toml").write_text(text)
        return d / f"perceived-model-{letter}.toml"

    def _divergence(self, did, score=0.2, a=None, b=None):
        d = Path(self.p) / "walkthroughs" / did
        d.mkdir(parents=True, exist_ok=True)
        a = a or f"walkthroughs/{did}/perceived-model-a.toml"
        b = b or f"walkthroughs/{did}/perceived-model-b.toml"
        (d / "divergence.toml").write_text(
            f'demand = "{did}"\nscore = {score}\n'
            f'intended_model = "specs/{did}/design/intended-model.md"\n'
            f'perceived_model_a = "{a}"\nperceived_model_b = "{b}"\n')

    def test_complete_chain_has_no_orphans_and_appears_in_the_graph(self):
        demand(self.p, "FWD-200")
        self._intended("FWD-200")
        self._perceived("FWD-200", "a")
        self._perceived("FWD-200", "b")
        self._divergence("FWD-200")
        self.assertEqual(graph.forbidden_orphans(Path(self.p)), [])
        self.assertEqual(self.gate().returncode, 0)

        g = graph.build_graph(Path(self.p))
        self.assertIn(graph._node("intended-model", "FWD-200"), g.nodes)
        self.assertIn(graph._node("perceived-model", "FWD-200#a"), g.nodes)
        self.assertIn(graph._node("perceived-model", "FWD-200#b"), g.nodes)
        self.assertIn(graph._node("divergence", "FWD-200"), g.nodes)
        etypes = {e for _s, e, _d, _w in g.edges}
        self.assertEqual({"modeled_by", "walked_by", "confronted_by"} & etypes,
                         {"modeled_by", "walked_by", "confronted_by"})
        # both runs confront the same divergence node — its in-degree of
        # 2 is the structural signature the ADR names
        dvnode = graph._node("divergence", "FWD-200")
        confronted = [s for s, e, d, _w in g.edges if e == "confronted_by" and d == dvnode]
        self.assertEqual(len(confronted), 2)

    def test_demand_ego_graph_surfaces_the_whole_chain(self):
        demand(self.p, "FWD-205")
        self._intended("FWD-205")
        self._perceived("FWD-205", "a")
        self._perceived("FWD-205", "b")
        self._divergence("FWD-205")
        g = graph.build_graph(Path(self.p))
        ego = g.ego(graph._node("demand", "FWD-205"))
        kinds = {n["kind"] for n in ego.nodes.values()}
        self.assertTrue({"intended-model", "perceived-model", "divergence"} <= kinds)

    def test_perceived_model_without_intended_model_is_forbidden(self):
        # R4's ordering requirement (intended model compiled BEFORE either
        # run) made an observable graph failure, not a documentation promise
        demand(self.p, "FWD-201")
        self._perceived("FWD-201", "a")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no specs/FWD-201/design/intended-model.md counterpart", r.stdout)

    def test_a_demand_untouched_by_walkthrough_stays_green(self):
        # normal mid-loop state: no walkthrough evidence at all
        demand(self.p, "FWD-206")
        self.assertEqual(self.gate().returncode, 0)

    def test_divergence_pointing_at_a_missing_perceived_model_is_forbidden(self):
        demand(self.p, "FWD-202")
        self._intended("FWD-202")
        self._perceived("FWD-202", "a")
        self._perceived("FWD-202", "b")
        self._divergence("FWD-202",
                         b="walkthroughs/FWD-202/perceived-model-MISSING.toml")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("points at a missing file", r.stdout)

    def test_divergence_with_fewer_than_two_runs_on_record_is_forbidden(self):
        # only run "a" is actually on disk; the toml's own pointers both
        # resolve (to the same existing file) so this isolates check #7
        # (confronted_by in-degree) from check #5 (dangling pointer)
        demand(self.p, "FWD-203")
        self._intended("FWD-203")
        self._perceived("FWD-203", "a")
        self._divergence("FWD-203",
                         a="walkthroughs/FWD-203/perceived-model-a.toml",
                         b="walkthroughs/FWD-203/perceived-model-a.toml")
        r = self.gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("only 1 confronted_by edge", r.stdout)

    def test_use15_finding_cites_the_divergence_it_traces_to(self):
        demand(self.p, "FWD-204")
        self._intended("FWD-204")
        self._perceived("FWD-204", "a")
        self._perceived("FWD-204", "b")
        self._divergence("FWD-204")
        review(self.p, "FWD-204",
              [("usability_accessibility", "medium",
                "USE-15 interpretive divergence is evidence about the artifact")])
        g = graph.build_graph(Path(self.p))
        fnode = graph._node("finding", "FWD-204#1")
        dvnode = graph._node("divergence", "FWD-204")
        self.assertIn((fnode, "cites", dvnode),
                      [(s, e, d) for s, e, d, _w in g.edges])

    def test_a_finding_unrelated_to_any_divergence_does_not_cite_one(self):
        demand(self.p, "FWD-207")
        review(self.p, "FWD-207", [("maintainability", "low", "MNT-1")])
        g = graph.build_graph(Path(self.p))
        cites_divergence = [(s, e, d) for s, e, d, _w in g.edges
                            if e == "cites"
                            and g.nodes.get(d, {}).get("kind") == "divergence"]
        self.assertEqual(cites_divergence, [])


if __name__ == "__main__":
    unittest.main()
