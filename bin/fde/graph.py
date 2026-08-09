#!/usr/bin/env python3
"""
graph — FORWARD's artifacts as a directed, weighted graph.

Not a database and not an index: the graph is DERIVED from the files on
demand (no pre-built summaries to rot — LazyGraphRAG's lesson) and joined
by demand-id, the key already present in every path. The only authored
edge is an ADR's `supersedes:` field; everything else is latent in what
the kernel already writes. Weights come from data the kernel already
holds: vector-A attribute weights, finding severity, triage size.

"Graph as evidence, not graph as program" (ADR-0010): the demand loop
stays the loop; this makes its provenance queryable, minable, and — via
the traceability gate that consumes forbidden_orphans() — enforceable.

Pure stdlib. Runs in the client repo at bin/fde/graph.py with no deps.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import project_root  # noqa: E402

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}
SIZE_WEIGHT = {"xs": 1, "s": 2, "m": 3, "l": 4}
DEMAND_RE = re.compile(r"\b((?:FWD|DEM)-\d+)")
CANON_RE = re.compile(r"^((?:FWD|DEM)-\d+)", re.IGNORECASE)
PRINCIPLE_RE = re.compile(r"^([A-Z]{2,}-\d+)")
SIZE_RE = re.compile(r"\*\*(XS|S|M|L)\*\*")


def canon_demand(raw: str) -> str:
    """Join key: the bare FWD-<n>/DEM-<n> prefix, so a slugged directory
    (specs/FWD-001-self-install) and a bare one (reviews/FWD-001) resolve
    to the same demand."""
    m = CANON_RE.match(raw)
    return m.group(1).upper() if m else raw


def canon_principle(raw: str) -> str:
    """A cited principle aggregates by its catalog id (MNT-1), whether the
    reviewer wrote the id alone or id + full text."""
    m = PRINCIPLE_RE.match(raw.strip())
    return m.group(1) if m else raw.strip()[:48]


def _node(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


@dataclass
class Graph:
    # node id -> attrs (always carries "kind"; may carry "weight", "label")
    nodes: dict = field(default_factory=dict)
    # directed edges: (src, etype, dst, weight)
    edges: list = field(default_factory=list)

    def add_node(self, kind: str, ident: str, **attrs) -> str:
        nid = _node(kind, ident)
        n = self.nodes.setdefault(nid, {"kind": kind, "id": ident})
        n.update({k: v for k, v in attrs.items() if v is not None})
        return nid

    def add_edge(self, src: str, etype: str, dst: str, weight: float = 1.0) -> None:
        self.edges.append((src, etype, dst, weight))

    # -- analysis ---------------------------------------------------------
    def neighbors(self, nid: str, out=True, inc=True) -> list:
        r = []
        for s, e, d, w in self.edges:
            if out and s == nid:
                r.append((d, e, w))
            if inc and d == nid:
                r.append((s, e, w))
        return r

    # shared hubs are reachable leaves, not bridges: an ego-graph includes
    # them but does not traverse THROUGH them into sibling demands
    TERMINAL = {"attribute", "principle", "probe", "transcript",
                "product-goal", "sprint"}

    def ego(self, nid: str, hops: int = 4) -> "Graph":
        seen, frontier = {nid}, {nid}
        for _ in range(hops):
            nxt = set()
            for s, e, d, w in self.edges:
                # expand only from non-terminal frontier nodes
                if s in frontier and d not in seen \
                        and self.nodes.get(s, {}).get("kind") not in self.TERMINAL:
                    nxt.add(d)
                if d in frontier and s not in seen \
                        and self.nodes.get(d, {}).get("kind") not in self.TERMINAL:
                    nxt.add(s)
            seen |= nxt
            frontier = nxt
            if not frontier:
                break
        g = Graph()
        g.nodes = {k: v for k, v in self.nodes.items() if k in seen}
        g.edges = [(s, e, d, w) for s, e, d, w in self.edges
                   if s in seen and d in seen]
        return g

    def weighted_in_degree(self) -> list:
        deg = defaultdict(float)
        for _s, _e, d, w in self.edges:
            deg[d] += w
        ranked = sorted(deg.items(), key=lambda kv: -kv[1])
        return [(nid, round(w, 2)) for nid, w in ranked if nid in self.nodes]

    def recurring_principles(self) -> list:
        """Severity-weighted citation count per principle — mines the review
        history for the weaknesses that keep recurring. Probes are per-finding
        free text and do not recur, so only catalog principles are ranked."""
        score = defaultdict(float)
        for _s, e, d, w in self.edges:
            if e == "cites" and self.nodes.get(d, {}).get("kind") == "principle":
                score[d] += w
        return sorted(score.items(), key=lambda kv: -kv[1])

    def path(self, src: str, dst: str) -> list | None:
        adj = defaultdict(list)
        for s, e, d, _w in self.edges:
            adj[s].append((d, e))
        prev, q = {src: None}, [src]
        while q:
            cur = q.pop(0)
            if cur == dst:
                out, node = [], dst
                while node is not None:
                    out.append(node)
                    node = prev[node]
                return list(reversed(out))
            for d, _e in adj[cur]:
                if d not in prev:
                    prev[d] = cur
                    q.append(d)
        return None

    def cycles_in(self, etype: str) -> list:
        adj = defaultdict(list)
        for s, e, d, _w in self.edges:
            if e == etype:
                adj[s].append(d)
        WHITE, GREY, BLACK = 0, 1, 2
        color = defaultdict(int)
        found = []

        def dfs(u, stack):
            color[u] = GREY
            for v in adj[u]:
                if color[v] == GREY:
                    found.append(stack + [u, v])
                elif color[v] == WHITE:
                    dfs(v, stack + [u])
            color[u] = BLACK

        for n in list(adj):
            if color[n] == WHITE:
                dfs(n, [])
        return found

    def to_dict(self) -> dict:
        return {
            "nodes": [{"node": k, **v} for k, v in sorted(self.nodes.items())],
            "edges": [{"src": s, "type": e, "dst": d, "weight": w}
                      for s, e, d, w in self.edges],
        }


# ---------------------------------------------------------------------------
# builder — everything derived from files, joined by demand-id
# ---------------------------------------------------------------------------
def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _header_fields(text: str) -> dict:
    """Header `key: value` lines, from the top of the file down to the
    first `## ` section. Works for BOTH conventions: `---`-fenced
    front-matter (backlog, sprint goal, acceptance) AND title-first ADRs
    (`# ADR-N — …` then plain `date:`/`status:`/`supersedes:` lines).
    Prose below the header never matches — the scan stops at the first
    section heading."""
    fm = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        s = line.strip()
        if s in ("---", "") or s.startswith("# "):
            continue
        m = re.match(r"([A-Za-z_][\w-]*)\s*:\s*(.*)$", s)
        if m:
            fm[m.group(1).lower()] = m.group(2).strip()
    return fm


def _spec_root(project: Path) -> Path:
    ks = project / ".fde" / "spec"
    return ks if (ks / "dimensions").exists() else project / "spec"


def build_graph(project: Path) -> Graph:
    g = Graph()

    # attribute nodes, weighted by the project's vector-A allocation
    weights = {}
    cfg = project / "fde.config.toml"
    if cfg.exists():
        try:
            weights = tomllib.loads(_read(cfg)).get("weights", {}) or {}
        except tomllib.TOMLDecodeError:
            weights = {}
    for attr, w in weights.items():
        g.add_node("attribute", attr, weight=float(w))

    # product goal + sprints
    backlog = project / "backlog.md"
    goal_node = None
    if backlog.exists():
        fm = _header_fields(_read(backlog))
        if fm.get("goal"):
            goal_node = g.add_node("product-goal", "root", label=fm["goal"])
    sprints_dir = project / "sprints"
    if sprints_dir.is_dir():
        for sd in sorted(sprints_dir.iterdir()):
            if not (sd.is_dir() and re.fullmatch(r"S-\d+", sd.name)):
                continue
            gm = sd / "goal.md"
            snode = g.add_node("sprint", sd.name,
                               label=_header_fields(_read(gm)).get("goal"))
            if goal_node:
                g.add_edge(goal_node, "parents", snode)
            # ids come from the demand TABLE rows only (lines starting `|`),
            # not from prose — a demand mentioned in "Closes when…" is not
            # selected, and a negated mention never counts as planned
            for row in (l for l in _read(gm).splitlines() if l.lstrip().startswith("|")):
                for did in dict.fromkeys(DEMAND_RE.findall(row)):
                    g.add_edge(snode, "selects", g.add_node("demand", did))

    # demands: canonical id -> actual directory, per artifact kind (dir
    # names may be slugged: specs/FWD-001-self-install vs reviews/FWD-001)
    def dir_index(sub: str) -> dict:
        d = project / sub
        return {canon_demand(p.name): p for p in d.iterdir() if p.is_dir()} \
            if d.is_dir() else {}

    specs, reviews, proms = dir_index("specs"), dir_index("reviews"), dir_index("promotions")
    demand_ids = set(specs) | set(reviews) | set(proms)
    demand_ids |= {n["id"] for n in g.nodes.values() if n["kind"] == "demand"}

    for did in sorted(demand_ids):
        dnode = g.add_node("demand", did)
        sdir = specs.get(did)
        if sdir and (sdir / "spec.md").exists():
            # size from the Triage line specifically, not the first bold
            # token anywhere in the spec
            for line in _read(sdir / "spec.md").splitlines():
                if "triage" in line.lower():
                    m = SIZE_RE.search(line)
                    if m:
                        g.nodes[dnode]["weight"] = float(SIZE_WEIGHT[m.group(1).lower()])
                    break
            g.add_edge(dnode, "specified_by", g.add_node("spec", did))
        if sdir and (sdir / "acceptance.md").exists():
            g.add_edge(dnode, "accepted_by", g.add_node("acceptance", did))
        if sdir and (sdir / "architecture.md").exists():
            g.add_edge(dnode, "designed_by", g.add_node("architecture", did))
        if did in proms and (proms[did] / "decision.md").exists():
            g.add_edge(dnode, "promoted_by", g.add_node("promotion", did))
        if did in reviews and (reviews[did] / "findings.toml").exists():
            _build_review(g, dnode, did, reviews[did] / "findings.toml")

    # ADRs + supersedes edges (the one authored edge)
    adr_dir = project / "docs" / "adr"
    if adr_dir.is_dir():
        known = {}
        for a in sorted(adr_dir.glob("*.md")):
            m = re.match(r"(\d+)", a.name)
            aid = m.group(1) if m else a.stem
            known[aid] = g.add_node("adr", aid, label=a.stem)
        for a in sorted(adr_dir.glob("*.md")):
            m = re.match(r"(\d+)", a.name)
            aid = m.group(1) if m else a.stem
            sup = _header_fields(_read(a)).get("supersedes", "")
            for tgt in re.findall(r"\d+", sup):
                # dangling target still gets a node so the gate can catch it
                dst = known.get(tgt) or g.add_node("adr", tgt, missing=True)
                g.add_edge(known[aid], "supersedes", dst)
    return g


def _build_review(g: Graph, dnode: str, did: str, findings: Path) -> None:
    try:
        data = tomllib.loads(findings.read_text(encoding="utf-8", errors="ignore"))
    except tomllib.TOMLDecodeError:
        g.add_node("review", did, malformed=True)
        g.add_edge(dnode, "reviewed_by", _node("review", did))
        return
    rnode = g.add_node("review", did)
    g.add_edge(dnode, "reviewed_by", rnode)
    tx = (data.get("meta") or {}).get("agent_transcript")
    if tx:
        g.add_edge(rnode, "links", g.add_node("transcript", str(tx)))
    for i, f in enumerate(data.get("finding", []), 1):
        sev = str(f.get("severity", "")).lower()
        w = float(SEVERITY_WEIGHT.get(sev, 1))
        fnode = g.add_node("finding", f"{did}#{i}", severity=sev)
        g.add_edge(rnode, "contains", fnode, w)
        if f.get("attribute"):
            g.add_edge(fnode, "against", g.add_node("attribute", f["attribute"]), w)
        if f.get("principle"):
            pid = canon_principle(str(f["principle"]))
            g.add_edge(fnode, "cites", g.add_node("principle", pid), w)
        elif f.get("probe"):
            # keyed by full text so distinct probes never merge; truncate
            # only for display (--central)
            full = str(f["probe"])
            g.add_edge(fnode, "cites", g.add_node("probe", full), w)


# ---------------------------------------------------------------------------
# forbidden orphans — the gate consumes this (impossible states only)
# ---------------------------------------------------------------------------
def forbidden_orphans(project: Path, g: Graph | None = None) -> list:
    g = g or build_graph(project)
    out = []
    specs = _dir_index(project, "specs")
    reviews = _dir_index(project, "reviews")
    proms = _dir_index(project, "promotions")

    # 1. acceptance for an unspecified demand (impossible)
    for did, sdir in sorted(specs.items()):
        if (sdir / "acceptance.md").exists() and not (sdir / "spec.md").exists():
            out.append(f"{did}: acceptance.md without spec.md")

    # 2. promotion without a recorded review (the I2 rule, generalized)
    for did, pdir in sorted(proms.items()):
        if (pdir / "decision.md").exists() and did not in reviews:
            out.append(f"{did}: promoted without a review")

    # 3. (scrum on) a review whose demand is neither specced nor planned
    if _scrum_on(project):
        selected = {d for _s, e, d, _w in g.edges if e == "selects"}
        for did in sorted(reviews):
            if did not in specs and _node("demand", did) not in selected:
                out.append(f"{did}: review for a demand no sprint planned")

    # 4. supersedes: dangling target or cycle
    for _nid, n in g.nodes.items():
        if n.get("missing"):
            out.append(f"ADR supersedes points at a missing ADR {n['id']}")
    for cyc in g.cycles_in("supersedes"):
        out.append("supersedes cycle: " + " -> ".join(cyc))
    return out


def _dir_index(project: Path, sub: str) -> dict:
    d = project / sub
    return {canon_demand(p.name): p for p in d.iterdir() if p.is_dir()} \
        if d.is_dir() else {}


def _scrum_on(project: Path) -> bool:
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return False
    try:
        return (tomllib.loads(_read(cfg)).get("scrum") or {}).get("enabled") is True
    except tomllib.TOMLDecodeError:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _render(g: Graph) -> str:
    lines = ["# Artifact graph", ""]
    demands = sorted(n["id"] for n in g.nodes.values() if n["kind"] == "demand")
    lines.append(f"{len(demands)} demand(s), {len(g.edges)} edge(s)\n")
    for did in demands:
        dn = _node("demand", did)
        kinds = sorted({g.nodes[d]["kind"] for d, _e, _w in g.neighbors(dn, inc=False)
                        if d in g.nodes})
        lines.append(f"- {did}: {', '.join(kinds) or '(no artifacts yet)'}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demand", help="ego-graph of a demand id")
    ap.add_argument("--orphans", action="store_true")
    ap.add_argument("--central", action="store_true")
    ap.add_argument("--recurring", action="store_true")
    ap.add_argument("--path", nargs=2, metavar=("SRC", "DST"))
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()
    g = build_graph(project)

    if args.format == "json":
        target = g.ego(_node("demand", args.demand)) if args.demand else g
        print(json.dumps(target.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.demand:
        ego = g.ego(_node("demand", args.demand))
        print(f"\nego-graph of demand {args.demand} "
              f"({len(ego.nodes)} nodes, {len(ego.edges)} edges)\n")
        for s, e, d, w in sorted(ego.edges):
            ws = f"  (w={w})" if w != 1.0 else ""
            print(f"  {s}  --{e}-->  {d}{ws}")
        return 0
    if args.orphans:
        orphans = forbidden_orphans(project, g)
        print("\n".join(f"  ✗ {o}" for o in orphans) if orphans
              else "no forbidden orphans")
        return 1 if orphans else 0
    if args.central:
        print("\nweighted in-degree (most depended-on):\n")
        for nid, w in g.weighted_in_degree()[:15]:
            label = nid if len(nid) <= 60 else nid[:57] + "..."
            print(f"  {w:6.1f}  {label}")
        return 0
    if args.recurring:
        print("\nrecurring citations (severity-weighted):\n")
        for nid, w in g.recurring_principles()[:15]:
            print(f"  {w:6.1f}  {g.nodes[nid]['id']}")
        return 0
    if args.path:
        p = g.path(*args.path)
        print(" -> ".join(p) if p else "no path")
        return 0 if p else 1
    print(_render(g))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
