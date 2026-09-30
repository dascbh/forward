#!/usr/bin/env python3
"""
mapexport — the product map (productmap.py) in the formats graph tools read.

    python3 bin/fde/mapexport.py --export mermaid [--feature <slug>]
    python3 bin/fde/mapexport.py --export jgf|graphml|dot --input map.json

- mermaid: one flowchart per screen — the whole graph in one chart is
  unreadable — as Markdown sections with ```mermaid blocks, plus one block
  for what no screen reaches. `--screen <path>` prints that one chart.
- jgf: JSON Graph Format v2 (jsongraphformat.info).
- graphml: GraphML, opened by Gephi, yEd and Cytoscape.
- dot: Graphviz.

The graph comes from `--input` (a `productmap.py --format json` file, or
`-` for stdin) or, without it, from productmap itself over `--root`.
Stdlib only (I6); nothing here knows a project.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent))

FORMATS = ("mermaid", "jgf", "graphml", "dot")

# kind → (mermaid open, close), graphviz shape
SHAPES = {
    "screen": (("[[", "]]"), "tab"),
    "component": (("(", ")"), "box"),
    "api": (("[/", "/]"), "parallelogram"),
    "handler": (("[", "]"), "box"),
    "guard": (("{{", "}}"), "hexagon"),
    "rule": (("{", "}"), "diamond"),
    "event": ((">", "]"), "cds"),
    "table": (("[(", ")]"), "cylinder"),
    "column": ((("([", "])")), "ellipse"),
    "trigger": ((("((", "))")), "doublecircle"),
    "unresolved": (("[", "]"), "note"),
}


def load(args) -> list[dict]:
    """Graphs as {"feature", "nodes", "edges"}: one per feature."""
    if args.input:
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        return [json.loads(text)]
    import productmap
    root = Path(args.root).resolve()
    conv = productmap.load_conventions(root, args.conventions)
    out = []
    for feature in conv.get("feature", []):
        if args.feature and feature.get("slug") != args.feature:
            continue
        g, _ = productmap.generate(root, conv, feature)
        out.append({"feature": feature, "nodes": g.nodes,
                    "edges": [dict(zip(("source", "relation", "target", "provenance"), e))
                              for e in g.edges]})
    return out


def label(nid: str, node: dict) -> str:
    """The id without its `kind:` prefix — the kind is the shape."""
    kind = node.get("kind", "")
    return nid[len(kind) + 1:] if nid.startswith(kind + ":") else nid


def _edges(graph: dict) -> list[tuple[str, str, str, str]]:
    return [(e["source"], e["relation"], e["target"], e.get("provenance", ""))
            for e in graph.get("edges", [])]


# -- mermaid ------------------------------------------------------------------

def _mermaid_text(s: str) -> str:
    return s.replace('"', "#quot;")


def reach(graph: dict, start: str) -> tuple[list[str], list[tuple]]:
    """What a screen reaches following edges forward, plus the triggers
    that fire into a table it reaches (they sit upstream of it)."""
    edges = _edges(graph)
    seen, todo = [start], [start]
    while todo:
        cur = todo.pop(0)
        for a, _, b, _ in edges:
            if a == cur and b not in seen:
                seen.append(b)
                todo.append(b)
    for a, rel, b, _ in edges:
        if rel == "fires_into" and b in seen and a not in seen:
            seen.append(a)
    keep = set(seen)
    return seen, [e for e in edges if e[0] in keep and e[2] in keep]


def mermaid_chart(graph: dict, nodes: list[str], edges: list[tuple]) -> str:
    ids = {nid: f"n{i}" for i, nid in enumerate(nodes)}
    lines = ["flowchart LR"]
    for nid in nodes:
        node = graph["nodes"].get(nid, {"kind": "unresolved"})
        (o, c), _ = SHAPES.get(node.get("kind"), SHAPES["unresolved"])
        lines.append(f'  {ids[nid]}{o}"{_mermaid_text(label(nid, node))}"{c}')
    for a, rel, b, _ in edges:
        lines.append(f"  {ids[a]} -->|{rel}| {ids[b]}")
    return "\n".join(lines) + "\n"


def to_mermaid(graph: dict, screen: str | None = None) -> str:
    screens = sorted(n for n, v in graph["nodes"].items() if v.get("kind") == "screen")
    if screen is not None:
        sid = screen if screen.startswith("screen:") else f"screen:{screen}"
        if sid not in graph["nodes"]:
            raise SystemExit(f"mapexport: no screen {screen!r}; screens: "
                             + ", ".join(label(s, {"kind": "screen"}) for s in screens))
        return mermaid_chart(graph, *reach(graph, sid))
    title = graph.get("feature", {}).get("name") or graph.get("feature", {}).get("slug", "map")
    out, reached = [f"# {title} — one flowchart per screen\n"], set()
    for sid in screens:
        nodes, edges = reach(graph, sid)
        reached.update(nodes)
        out.append(f"## {label(sid, {'kind': 'screen'})}\n\n```mermaid\n"
                   f"{mermaid_chart(graph, nodes, edges)}```\n")
    rest = [n for n in graph["nodes"] if n not in reached]
    if rest:
        keep = set(rest)
        edges = [e for e in _edges(graph) if e[0] in keep and e[2] in keep]
        out.append(f"## not reached from a screen\n\n```mermaid\n"
                   f"{mermaid_chart(graph, rest, edges)}```\n")
    return "\n".join(out)


# -- JSON Graph Format --------------------------------------------------------

def to_jgf(graph: dict) -> str:
    feature = graph.get("feature", {})
    doc = {"graph": {
        "id": feature.get("slug", "map"),
        "label": feature.get("name", feature.get("slug", "map")),
        "directed": True,
        "type": "fde-map",
        "metadata": feature,
        "nodes": {nid: {"label": label(nid, n), "metadata": n}
                  for nid, n in graph["nodes"].items()},
        "edges": [{"source": a, "target": b, "relation": rel, "directed": True,
                   "metadata": {"provenance": prov}}
                  for a, rel, b, prov in _edges(graph)],
    }}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# -- GraphML ------------------------------------------------------------------

def to_graphml(graph: dict) -> str:
    keys = [("label", "node"), ("kind", "node"), ("file", "node"),
            ("relation", "edge"), ("provenance", "edge")]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">']
    for name, scope in keys:
        out.append(f'  <key id="{name}" for="{scope}" attr.name="{name}" attr.type="string"/>')
    gid = graph.get("feature", {}).get("slug", "map")
    out.append(f'  <graph id={quoteattr(gid)} edgedefault="directed">')
    for nid, n in graph["nodes"].items():
        out.append(f"    <node id={quoteattr(nid)}>")
        out.append(f'      <data key="label">{escape(label(nid, n))}</data>')
        out.append(f'      <data key="kind">{escape(str(n.get("kind", "")))}</data>')
        if n.get("file"):
            out.append(f'      <data key="file">{escape(str(n["file"]))}</data>')
        out.append("    </node>")
    for i, (a, rel, b, prov) in enumerate(_edges(graph)):
        out.append(f"    <edge id=\"e{i}\" source={quoteattr(a)} target={quoteattr(b)}>")
        out.append(f'      <data key="relation">{escape(rel)}</data>')
        if prov:
            out.append(f'      <data key="provenance">{escape(prov)}</data>')
        out.append("    </edge>")
    out += ["  </graph>", "</graphml>"]
    return "\n".join(out) + "\n"


# -- Graphviz -----------------------------------------------------------------

def _dot(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_dot(graph: dict) -> str:
    gid = graph.get("feature", {}).get("slug", "map")
    out = [f"digraph {_dot(gid)} {{", "  rankdir=LR;", "  node [fontsize=10];"]
    for nid, n in graph["nodes"].items():
        _, shape = SHAPES.get(n.get("kind"), SHAPES["unresolved"])
        out.append(f"  {_dot(nid)} [label={_dot(label(nid, n))}, shape={shape}];")
    for a, rel, b, _ in _edges(graph):
        out.append(f"  {_dot(a)} -> {_dot(b)} [label={_dot(rel)}];")
    out.append("}")
    return "\n".join(out) + "\n"


def export(graph: dict, fmt: str, screen: str | None = None) -> str:
    if fmt == "mermaid":
        return to_mermaid(graph, screen)
    return {"jgf": to_jgf, "graphml": to_graphml, "dot": to_dot}[fmt](graph)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="export the product map to graph formats")
    ap.add_argument("--export", required=True, choices=FORMATS)
    ap.add_argument("--input", help="a `productmap.py --format json` file, or - for stdin")
    ap.add_argument("--root", default=".", help="project root when --input is absent")
    ap.add_argument("--feature", help="one feature slug (default: all)")
    ap.add_argument("--conventions", help="conventions file (default: docs/map/conventions.toml)")
    ap.add_argument("--screen", help="mermaid only: the one screen to chart")
    args = ap.parse_args(argv)
    if args.screen and args.export != "mermaid":
        ap.error("--screen goes with --export mermaid")
    graphs = load(args)
    if not graphs:
        print("mapexport: no [[feature]] matches", file=sys.stderr)
        return 2
    sys.stdout.write("\n".join(export(g, args.export, args.screen) for g in graphs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
