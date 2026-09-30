#!/usr/bin/env python3
"""
codebench — the code-quality view of a project over its history (owner
request, 2026-09-29). It reports; it never gates: `fde-erosion` is the
gate, and both read the same measures from erosion.py so they cannot
disagree.

For HEAD and a few earlier commits spread over the history (plus the
commit that installed FORWARD, when there is one), over the project's own
code (the `[gate]` roots minus `[erosion] generated_paths`, tests out):

- size: files and non-blank lines of code;
- Python functions: cyclomatic complexity (mean, p90, max), how many
  exceed CC 10, and structural erosion — the share of complexity mass
  (CC × √SLOC) held by those functions (SlopCodeBench v2 §2.3);
- the clone ratio, byte-identical copies counted once.

Then the hotspots at HEAD: the functions with the most mass, with their
complexity then and now, so growth by patching is visible.

Reference (SlopCodeBench v2, 473 human Python repositories): structural
erosion averages about 0.34. The paper's verbosity adds lint-rule hits to
clones, so the clone ratio here is not directly comparable to its 0.19.

Complexity is measured for Python only; other languages count in size
and clones. stdlib only (I6).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import erosion  # noqa: E402
from fde_lib import project_root  # noqa: E402

SOURCE_SUFFIXES = erosion.CODE_SUFFIXES - {".md", ".toml"}
HUMAN_EROSION = 0.34


def _git(root: Path, *args: str, stdin: str | None = None) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], input=stdin,
                       capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else ""


def snapshot_files(root: Path, sha: str) -> dict[str, str]:
    """{path: text} of the project's own source at a commit, read in one
    `git cat-file --batch` pass."""
    scope = erosion.churn_scope(root)
    gen = erosion.generated_paths(root)
    names = [n for n in _git(root, "ls-tree", "-r", "--name-only", sha).splitlines()
             if Path(n).suffix.lower() in SOURCE_SUFFIXES
             and erosion.in_churn_scope(n, scope, gen)
             and not erosion._is_test_path(n)]
    if not names:
        return {}
    proc = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"],
                          input="".join(f"{sha}:{n}\n" for n in names).encode(),
                          capture_output=True)
    out, data, pos = {}, proc.stdout, 0
    for name in names:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].split()
        pos = nl + 1
        if len(header) < 3 or header[1] != b"blob":
            continue
        size = int(header[2])
        out[name] = data[pos:pos + size].decode("utf-8", "replace")
        pos += size + 1
    return out


def functions(name: str, text: str):
    """(qualified name, line, CC, SLOC) of every Python function."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return
    lines = text.splitlines()

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{prefix}{child.name}"
                yield (q, child.lineno, erosion.cyclomatic(child),
                       erosion._sloc(child, lines), child)
                yield from walk(child, q + ".")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, f"{prefix}{child.name}.")
            else:
                yield from walk(child, prefix)
    for q, line, cc, sloc, node in walk(tree, ""):
        body = "\n".join(lines[node.lineno - 1:(node.end_lineno or node.lineno)])
        yield q, line, cc, sloc, hashlib.blake2b(body.strip().encode(),
                                                 digest_size=16).hexdigest()


def measure_snapshot(files: dict[str, str]) -> dict:
    kept, copy_groups = erosion.dedupe_copies(files)
    loc = sum(1 for t in kept.values() for l in t.splitlines() if l.strip())
    seen, ccs, total, high = set(), [], 0.0, 0.0
    per_fn: dict[str, tuple[int, int, int]] = {}
    for name, text in kept.items():
        if not name.endswith(".py"):
            continue
        for q, line, cc, sloc, key in functions(name, text):
            per_fn[f"{name}::{q}"] = (cc, sloc, line)
            if key in seen:
                continue
            seen.add(key)
            ccs.append(cc)
            mass = cc * math.sqrt(max(sloc, 1))
            total += mass
            if cc > erosion.HIGH_CC:
                high += mass
    ccs.sort()
    return {
        "files": len(kept), "loc": loc, "copy_groups": copy_groups,
        "functions": len(ccs),
        "cc_mean": round(sum(ccs) / len(ccs), 2) if ccs else None,
        "cc_p90": ccs[min(len(ccs) - 1, int(0.9 * len(ccs)))] if ccs else None,
        "cc_max": ccs[-1] if ccs else None,
        "complex": sum(1 for c in ccs if c > erosion.HIGH_CC),
        "structural_erosion": round(high / total, 3) if total else None,
        "clone_pct": erosion.duplicate_block_pct(kept) if kept else None,
        "_per_fn": per_fn,
    }


def pick_points(root: Path, n: int) -> list[tuple[str, str]]:
    """(sha, label): n commits spread over the first-parent history, the
    FORWARD install commit, and HEAD — oldest first."""
    shas = _git(root, "rev-list", "--first-parent", "--reverse", "HEAD").split()
    if not shas:
        return []
    idx = sorted({round(i * (len(shas) - 1) / max(n - 1, 1)) for i in range(n)})
    points = {shas[i]: "" for i in idx}
    points[shas[-1]] = "HEAD"
    added = _git(root, "log", "--diff-filter=A", "--format=%H", "--",
                 "fde.config.toml").split()
    if added and added[-1] in shas:
        points[added[-1]] = "FORWARD installed"
    order = {s: i for i, s in enumerate(shas)}
    return sorted(points.items(), key=lambda kv: order[kv[0]])


def bench(root: Path, points: int = 6, top: int = 10) -> dict:
    rows = []
    for sha, label in pick_points(root, points):
        date = _git(root, "log", "-1", "--format=%ad", "--date=short", sha).strip()
        m = measure_snapshot(snapshot_files(root, sha))
        rows.append({"sha": sha[:8], "date": date, "label": label, **m})
    if not rows:
        return {"snapshots": [], "hotspots": []}
    head = rows[-1]["_per_fn"]
    base_row = next((r for r in rows if r["label"] == "FORWARD installed"), rows[0])
    ranked = sorted(head.items(),
                    key=lambda kv: -kv[1][0] * math.sqrt(max(kv[1][1], 1)))[:top]
    hotspots = []
    for key, (cc, sloc, line) in ranked:
        then = base_row["_per_fn"].get(key)
        path, q = key.split("::", 1)
        hotspots.append({"path": path, "function": q, "line": line, "cc": cc,
                         "sloc": sloc, "cc_then": then[0] if then else None,
                         "since": base_row["date"]})
    for r in rows:
        del r["_per_fn"]
    return {"snapshots": rows, "hotspots": hotspots,
            "reference": {"human_structural_erosion": HUMAN_EROSION}}


def render(data: dict) -> list[str]:
    def f(v, w):
        return ("—" if v is None else str(v)).rjust(w)
    out = ["", "codebench — code quality over the history (report only; the gate is fde-erosion)", ""]
    out.append(f"  {'date':10} {'commit':8} {'files':>6} {'LOC':>7} {'fns':>6} "
               f"{'CC avg':>6} {'p90':>4} {'max':>4} {'CC>10':>6} {'erosion':>8} "
               f"{'clones%':>7}")
    for r in data["snapshots"]:
        out.append(f"  {r['date']:10} {r['sha']:8} {f(r['files'], 6)} {f(r['loc'], 7)} "
                   f"{f(r['functions'], 6)} {f(r['cc_mean'], 6)} {f(r['cc_p90'], 4)} "
                   f"{f(r['cc_max'], 4)} {f(r['complex'], 6)} "
                   f"{f(r['structural_erosion'], 8)} {f(r['clone_pct'], 7)}"
                   + (f"  ← {r['label']}" if r["label"] else ""))
    out.append(f"  {'human ref.':10} {'':8} {'':>6} {'':>7} {'':>6} {'':>6} {'':>4} "
               f"{'':>4} {'':>6} {HUMAN_EROSION:>8} {'':>7}  ← 473 Python repositories")
    if data["hotspots"]:
        since = data["hotspots"][0]["since"]
        out += ["", f"  hotspots at HEAD — most complexity mass (CC then = at {since})", ""]
        for h in data["hotspots"]:
            grew = "" if h["cc_then"] is None else (
                f"   CC {h['cc_then']} → {h['cc']}" if h["cc_then"] != h["cc"]
                else "   unchanged")
            new = "   new" if h["cc_then"] is None else ""
            out.append(f"  CC {h['cc']:>3}  {h['sloc']:>4} lines  "
                       f"{h['path']}:{h['line']} {h['function']}{grew}{new}")
    out += ["", "  erosion = share of complexity mass (CC × √SLOC) in functions with "
            "CC > 10; read it with CC>10 — a share falls when simple code lands.",
            "  Complexity is Python only; other languages count in size and clones. "
            "Byte-identical copies count once."]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="code-quality view over history")
    ap.add_argument("--root", default=None, help="project root (default: this repo)")
    ap.add_argument("--points", type=int, default=6,
                    help="snapshots spread over the history (default 6)")
    ap.add_argument("--top", type=int, default=10, help="hotspots listed (default 10)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else project_root()
    data = bench(root, max(2, args.points), args.top)
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print("\n".join(render(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
