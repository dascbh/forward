"""The product map in graph formats (runtime/mapexport.py, owner request
2026-09-30), over the same synthetic project as tests/test_productmap.py —
no client code in the kernel."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import mapexport  # noqa: E402
import productmap  # noqa: E402
from test_productmap import CONVENTIONS, FILES  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for rel, text in FILES.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(text))
        (self.root / "docs" / "map").mkdir(parents=True)
        (self.root / "docs" / "map" / "conventions.toml").write_text(CONVENTIONS)
        conv = productmap.load_conventions(self.root)
        g, _ = productmap.generate(self.root, conv, conv["feature"][0])
        self.graph = {"feature": conv["feature"][0], "nodes": g.nodes,
                      "edges": [dict(zip(("source", "relation", "target", "provenance"), e))
                                for e in g.edges]}
        self.screens = sorted(n for n, v in self.graph["nodes"].items()
                              if v["kind"] == "screen")

    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(ROOT / "runtime" / "mapexport.py"), *args],
                              cwd=self.root, input=stdin, capture_output=True, text=True)


class TestMermaid(Fixture):
    def test_one_flowchart_per_screen(self):
        md = mapexport.to_mermaid(self.graph)
        self.assertEqual(md.count("```mermaid\nflowchart LR"), len(self.screens)
                         + ("## not reached from a screen" in md))
        for sid in self.screens:
            self.assertIn(f"## {sid[len('screen:'):]}\n", md)

    def test_a_screen_chart_holds_what_it_reaches_and_nothing_else(self):
        sid = self.screens[0]
        nodes, edges = mapexport.reach(self.graph, sid)
        chart = mapexport.to_mermaid(self.graph, sid[len("screen:"):])
        self.assertEqual(chart.count(" -->|"), len(edges))
        for other in self.screens[1:]:
            self.assertNotIn(f'"{other[len("screen:"):]}"', chart)
        self.assertTrue(all(e[0] in nodes and e[2] in nodes for e in edges))

    def test_a_trigger_upstream_of_a_reached_table_is_shown(self):
        triggers = [a for a, rel, b, _ in mapexport._edges(self.graph) if rel == "fires_into"]
        self.assertTrue(triggers)
        shown = set().union(*(set(mapexport.reach(self.graph, s)[0]) for s in self.screens))
        self.assertTrue(set(triggers) <= shown | {
            a for a, rel, b, _ in mapexport._edges(self.graph)
            if rel == "fires_into" and b not in shown})

    def test_quotes_in_labels_do_not_break_the_chart(self):
        g = {"feature": {"slug": "x"}, "nodes": {
            "screen:/a": {"kind": "screen"}, 'rule:SAY_"HI"': {"kind": "rule"}},
             "edges": [{"source": "screen:/a", "relation": "applies",
                        "target": 'rule:SAY_"HI"', "provenance": ""}]}
        chart = mapexport.to_mermaid(g, "/a")
        self.assertIn("SAY_#quot;HI#quot;", chart)
        self.assertNotIn('SAY_"HI"', chart)

    def test_an_unknown_screen_names_the_real_ones(self):
        r = self.cli("--export", "mermaid", "--screen", "/nowhere")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(self.screens[0][len("screen:"):], r.stderr)


class TestGraphFormats(Fixture):
    def test_jgf_keeps_every_node_edge_and_provenance(self):
        doc = json.loads(mapexport.to_jgf(self.graph))["graph"]
        self.assertTrue(doc["directed"])
        self.assertEqual(set(doc["nodes"]), set(self.graph["nodes"]))
        self.assertEqual(len(doc["edges"]), len(self.graph["edges"]))
        e = doc["edges"][0]
        self.assertEqual({"source", "target", "relation", "directed", "metadata"}, set(e))
        self.assertIn("provenance", e["metadata"])

    def test_graphml_parses_with_one_element_per_node_and_edge(self):
        dom = xml.dom.minidom.parseString(mapexport.to_graphml(self.graph))
        self.assertEqual(len(dom.getElementsByTagName("node")), len(self.graph["nodes"]))
        self.assertEqual(len(dom.getElementsByTagName("edge")), len(self.graph["edges"]))

    def test_dot_is_one_digraph_with_every_edge(self):
        dot = mapexport.to_dot(self.graph)
        self.assertTrue(dot.startswith('digraph "billing" {'))
        self.assertEqual(dot.count(" -> "), len(self.graph["edges"]))
        self.assertTrue(dot.rstrip().endswith("}"))


class TestCli(Fixture):
    def test_input_from_stdin_and_built_from_the_code_agree(self):
        built = self.cli("--export", "jgf")
        self.assertEqual(built.returncode, 0, built.stderr)
        piped = self.cli("--export", "jgf", "--input", "-", stdin=json.dumps(self.graph))
        self.assertEqual(json.loads(built.stdout), json.loads(piped.stdout))

    def test_screen_goes_only_with_mermaid(self):
        r = self.cli("--export", "dot", "--screen", "/billing")
        self.assertNotEqual(r.returncode, 0)


class TestMapGate(unittest.TestCase):
    """The MAP gate warns on a stale map and never fails (first version)."""

    def setUp(self):
        from support import make_project
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = make_project(self.tmp.name)
        for rel, text in FILES.items():
            f = self.p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(textwrap.dedent(text))
        (self.p / "docs" / "map").mkdir(parents=True, exist_ok=True)
        (self.p / "docs" / "map" / "conventions.toml").write_text(CONVENTIONS)

    def gate(self):
        r = subprocess.run([sys.executable, "bin/fde/verify.py", "--gate", "map",
                            "--format", "json"], cwd=self.p, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)["gates"]

    def test_a_stale_map_warns_and_never_fails(self):
        code, gates = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(gates[0].get("warning"), gates)
        self.assertIn("docs/map/billing.md", gates[0]["detail"])
        subprocess.run([sys.executable, "bin/fde/productmap.py", "--write"],
                       cwd=self.p, capture_output=True)
        code, gates = self.gate()
        self.assertEqual(code, 0)
        self.assertFalse(gates[0].get("warning"), gates)

    def test_no_conventions_no_map_gate(self):
        (self.p / "docs" / "map" / "conventions.toml").unlink()
        code, gates = self.gate()
        self.assertEqual(code, 0)
        self.assertIn("no docs/map/conventions.toml", gates[0]["detail"])


if __name__ == "__main__":
    unittest.main()
