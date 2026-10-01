#!/usr/bin/env python3
"""
codebench — the code-quality view of a project over its history (owner
request, 2026-09-29). It reports; it never gates: `fde-erosion` is the
gate, and both read the same measures from erosion.py so they cannot
disagree.

Population: the project's own source — the `[gate]` roots minus
`[erosion] generated_paths`, tests out, byte-identical copies once.

1. HEAD against published references:
   - size: lines of code per language;
   - Python functions: cyclomatic complexity and its Radon rank (A 1-5,
     B 6-10, C 11-20, D 21-30, E 31-40, F 41+); over CC 10 (McCabe 1976,
     NIST SP 500-235); Pylint's defaults for statements (50), arguments
     (5), nested blocks (5) and branches (12); files over 1000 lines;
   - structural erosion (SlopCodeBench v2 §2.3; 473 human Python
     repositories average about 0.34);
   - clone ratio (SonarQube's default quality gate: 3% on new code);
   - SQL: statements embedded in source, and lines in .sql files;
   - layers: controllers doing the model's work — SQL or direct data
     calls in a controller (MVC; the kernel's MNT-2). Controllers are the
     paths declared in `[codebench] controller_paths`; undeclared, common
     names are detected and the report says so.
2. The trend over snapshots spread over the history, the FORWARD install
   commit and HEAD.
3. The hotspots at HEAD: the functions with the most complexity mass,
   their complexity then and now, and whether their file is a controller
   that touches data.

Complexity is measured for Python only; other languages count in size,
clones, SQL and layers. stdlib only (I6).
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import erosion  # noqa: E402
import fde_lib  # noqa: E402
from fde_lib import project_root  # noqa: E402

SOURCE_SUFFIXES = (erosion.CODE_SUFFIXES - {".md", ".toml"}) | {".sql"}
LANGUAGES = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
             ".js": "JavaScript", ".jsx": "JavaScript", ".sql": "SQL",
             ".sh": "Shell", ".go": "Go", ".rs": "Rust", ".java": "Java",
             ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".kt": "Kotlin",
             ".swift": "Swift", ".scala": "Scala", ".c": "C", ".h": "C",
             ".cpp": "C++"}

# published references (see the module docstring)
HUMAN_EROSION = 0.34
MCCABE = 10
PYLINT = {"statements": 50, "args": 5, "nesting": 5, "branches": 12,
          "module_lines": 1000}
SONAR_DUP = 3.0
RADON = ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E"))

SQL = re.compile(r"\b(?:SELECT\s[^;]{0,400}?\sFROM\s|INSERT\s+INTO\s|UPDATE\s+[\w.\"]+\s+SET\s|"
                 r"DELETE\s+FROM\s|CREATE\s+(?:TABLE|INDEX|VIEW)\s|ALTER\s+TABLE\s)",
                 re.IGNORECASE)
DATA_CALL = re.compile(
    r"\bcursor\s*\(|\.execute\s*\(|\bpsycopg2?\b|\bsqlalchemy\b|"
    r"boto3\.(?:client|resource)\(\s*['\"](?:dynamodb|s3|rds-data)|"
    r"\.(?:put_item|get_item|update_item|delete_item|batch_write_item|"
    r"batch_get_item|query|scan)\s*\(|\bprisma\.\w+\.|\bknex\s*\(")
DETECTED_CONTROLLERS = re.compile(
    r"(^|/)(handler|handlers|views|controller|controllers|routes?|routers?)"
    r"(/|\.[a-z]+$)|(_handler|_controller|_view|_routes?)\.[a-z]+$|"
    r"(^|/)(pages/api|app/api)/")


def controller_rule(root: Path):
    """(matcher, declared?) from `[codebench] controller_paths`; common
    names are detected when the project declared none."""
    try:
        raw = tomllib.loads((root / "fde.config.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        raw = {}
    paths = (raw.get("codebench") or {}).get("controller_paths")
    if isinstance(paths, list) and paths and all(isinstance(p, str) for p in paths):
        return (lambda n: any(n.startswith(p) or fnmatch.fnmatch(n, p)
                              for p in paths)), True
    return (lambda n: bool(DETECTED_CONTROLLERS.search(n))), False


def snapshot_files(root: Path, sha: str) -> dict[str, str]:
    """{path: text} of the project's own source at a commit, read in one
    `git cat-file --batch` pass."""
    scope = erosion.churn_scope(root)
    gen = erosion.generated_paths(root)
    names = [n for n in (fde_lib._git(root, "ls-tree", "-r", "--name-only", sha) or "").splitlines()
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


# -- Python function measures -------------------------------------------------

_BLOCKS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
           ast.AsyncWith) + ((ast.Match,) if hasattr(ast, "Match") else ())
_OWN = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _shape(fn) -> tuple[int, int, int]:
    """(statements, branches, deepest nesting) of one function, nested
    scopes excluded. Branches follow Pylint: each if/elif, loop, except,
    match case, and an if's else."""
    statements = branches = deepest = 0
    todo = [(c, 0) for c in ast.iter_child_nodes(fn)]
    while todo:
        node, depth = todo.pop()
        if isinstance(node, _OWN):
            continue
        if isinstance(node, ast.stmt):
            statements += 1
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            branches += 1
            if isinstance(node, ast.If) and node.orelse and not (
                    len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)):
                branches += 1
        elif isinstance(node, ast.ExceptHandler) or (
                hasattr(ast, "match_case") and isinstance(node, ast.match_case)):
            branches += 1
        inner = depth + 1 if isinstance(node, _BLOCKS) else depth
        deepest = max(deepest, inner)
        todo.extend((c, inner) for c in ast.iter_child_nodes(node))
    return statements, branches, deepest


def _args(fn) -> int:
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    return len([n for n in names if n not in ("self", "cls")]) + \
        (1 if a.vararg else 0) + (1 if a.kwarg else 0)


def functions(name: str, text: str):
    """One dict per Python function: qualified name, line, CC, SLOC,
    statements, branches, nesting, arguments, body hash."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return
    lines = text.splitlines()

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{prefix}{child.name}"
                yield q, child
                yield from walk(child, q + ".")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, f"{prefix}{child.name}.")
            else:
                yield from walk(child, prefix)
    for q, fn in walk(tree, ""):
        body = "\n".join(lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)])
        st, br, nest = _shape(fn)
        yield {"q": q, "line": fn.lineno, "cc": erosion.cyclomatic(fn),
               "sloc": erosion._sloc(fn, lines), "statements": st,
               "branches": br, "nesting": nest, "args": _args(fn),
               "key": hashlib.blake2b(body.strip().encode(),
                                      digest_size=16).hexdigest()}


def radon_rank(cc: int) -> str:
    return next((r for limit, r in RADON if cc <= limit), "F")


# -- one snapshot ---------------------------------------------------------------

def measure_snapshot(files: dict[str, str], is_controller) -> dict:
    kept, copy_groups = erosion.dedupe_copies(files)
    by_lang: dict[str, int] = {}
    long_files, sql_embedded, sql_file_loc = 0, 0, 0
    ctrl = {"files": 0, "loc": 0, "with_sql": 0, "with_data": 0, "names": []}
    loc = 0
    for name, text in kept.items():
        n = sum(1 for l in text.splitlines() if l.strip())
        loc += n
        suffix = Path(name).suffix.lower()
        lang = LANGUAGES.get(suffix, suffix.lstrip(".") or "other")
        by_lang[lang] = by_lang.get(lang, 0) + n
        if len(text.splitlines()) > PYLINT["module_lines"]:
            long_files += 1
        if suffix == ".sql":
            sql_file_loc += n
            continue
        hits = len(SQL.findall(text))
        sql_embedded += hits
        if is_controller(name):
            data = bool(DATA_CALL.search(text))
            ctrl["files"] += 1
            ctrl["loc"] += n
            ctrl["with_sql"] += bool(hits)
            ctrl["with_data"] += bool(hits) or data
            if hits or data:
                ctrl["names"].append(name)

    seen, fns, total, high = set(), [], 0.0, 0.0
    per_fn: dict[str, dict] = {}
    for name, text in kept.items():
        if not name.endswith(".py"):
            continue
        for f in functions(name, text):
            per_fn[f"{name}::{f['q']}"] = f
            if f["key"] in seen:
                continue
            seen.add(f["key"])
            fns.append(f)
            mass = f["cc"] * math.sqrt(max(f["sloc"], 1))
            total += mass
            if f["cc"] > MCCABE:
                high += mass
    ccs = sorted(f["cc"] for f in fns)
    ranks = {r: 0 for r in "ABCDEF"}
    for c in ccs:
        ranks[radon_rank(c)] += 1
    return {
        "files": len(kept), "loc": loc, "copy_groups": copy_groups,
        "loc_by_language": dict(sorted(by_lang.items(), key=lambda kv: -kv[1])),
        "functions": len(ccs),
        "cc_mean": round(sum(ccs) / len(ccs), 2) if ccs else None,
        "cc_p90": ccs[min(len(ccs) - 1, int(0.9 * len(ccs)))] if ccs else None,
        "cc_max": ccs[-1] if ccs else None,
        "complex": sum(1 for c in ccs if c > MCCABE),
        "radon_ranks": ranks,
        "over_statements": sum(1 for f in fns if f["statements"] > PYLINT["statements"]),
        "over_args": sum(1 for f in fns if f["args"] > PYLINT["args"]),
        "over_nesting": sum(1 for f in fns if f["nesting"] > PYLINT["nesting"]),
        "over_branches": sum(1 for f in fns if f["branches"] > PYLINT["branches"]),
        "long_files": long_files,
        "structural_erosion": round(high / total, 3) if total else None,
        "clone_pct": erosion.duplicate_block_pct(kept) if kept else None,
        "sql_embedded": sql_embedded, "sql_file_loc": sql_file_loc,
        "controllers": ctrl,
        "_per_fn": per_fn,
    }


def pick_points(root: Path, n: int) -> list[tuple[str, str]]:
    """(sha, label): n commits spread over the first-parent history, the
    FORWARD install commit, and HEAD — oldest first."""
    shas = (fde_lib._git(root, "rev-list", "--first-parent", "--reverse", "HEAD") or "").split()
    if not shas:
        return []
    idx = sorted({round(i * (len(shas) - 1) / max(n - 1, 1)) for i in range(n)})
    points = {shas[i]: "" for i in idx}
    points[shas[-1]] = "HEAD"
    added = (fde_lib._git(root, "log", "--diff-filter=A", "--format=%H", "--",
                          "fde.config.toml") or "").split()
    if added and added[-1] in shas:
        points[added[-1]] = "FORWARD installed"
    order = {s: i for i, s in enumerate(shas)}
    return sorted(points.items(), key=lambda kv: order[kv[0]])


def bench(root: Path, points: int = 6, top: int = 10) -> dict:
    is_controller, declared = controller_rule(root)
    rows = []
    for sha, label in pick_points(root, points):
        date = (fde_lib._git(root, "log", "-1", "--format=%ad", "--date=short", sha) or "").strip()
        m = measure_snapshot(snapshot_files(root, sha), is_controller)
        rows.append({"sha": sha[:8], "date": date, "label": label, **m})
    if not rows:
        return {"snapshots": [], "hotspots": [], "controllers_declared": declared}
    head_row = rows[-1]
    base_row = next((r for r in rows if r["label"] == "FORWARD installed"), rows[0])
    touching = set(head_row["controllers"]["names"])
    ranked = sorted(head_row["_per_fn"].items(),
                    key=lambda kv: -kv[1]["cc"] * math.sqrt(max(kv[1]["sloc"], 1)))[:top]
    hotspots = []
    for key, f in ranked:
        then = base_row["_per_fn"].get(key)
        path = key.split("::", 1)[0]
        hotspots.append({"path": path, "function": f["q"], "line": f["line"],
                         "cc": f["cc"], "sloc": f["sloc"],
                         "cc_then": then["cc"] if then else None,
                         "since": base_row["date"],
                         "controller_with_data": path in touching})
    for r in rows:
        del r["_per_fn"]
    return {"snapshots": rows, "hotspots": hotspots,
            "controllers_declared": declared,
            "reference": {"human_structural_erosion": HUMAN_EROSION,
                          "mccabe": MCCABE, "pylint": PYLINT,
                          "sonar_duplication_pct": SONAR_DUP}}


# -- text ---------------------------------------------------------------------------

def _f(v, w=0):
    return ("—" if v is None else str(v)).rjust(w)


def render(data: dict) -> list[str]:
    out = ["", "codebench — code quality over the history "
           "(report only; the gate is fde-erosion)"]
    if not data["snapshots"]:
        return out + ["", "  no committed history to measure"]
    h = data["snapshots"][-1]
    c = h["controllers"]
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else "—"  # noqa: E731
    langs = ", ".join(f"{k} {v}" for k, v in list(h["loc_by_language"].items())[:5])
    ranks = " ".join(f"{k}:{v}" for k, v in h["radon_ranks"].items())
    fn = h["functions"] or 0
    rows = [
        ("lines of code", f"{h['loc']} in {h['files']} files", langs),
        ("files over 1000 lines", h["long_files"], "Pylint too-many-lines"),
        ("Python functions", fn, "identical bodies once"),
        ("CC avg / p90 / max", f"{_f(h['cc_mean'])} / {_f(h['cc_p90'])} / {_f(h['cc_max'])}", ""),
        ("Radon ranks", ranks, "A 1-5 · B 6-10 · C 11-20 · D-F above"),
        ("functions over CC 10", f"{h['complex']} ({pct(h['complex'], fn)})",
         "McCabe 1976, NIST SP 500-235: ≤ 10"),
        ("over 50 statements", h["over_statements"], "Pylint too-many-statements"),
        ("over 5 arguments", h["over_args"], "Pylint too-many-arguments"),
        ("over 12 branches", h["over_branches"], "Pylint too-many-branches"),
        ("nesting over 5", h["over_nesting"], "Pylint too-many-nested-blocks"),
        ("structural erosion", _f(h["structural_erosion"]),
         f"SlopCodeBench v2: human repos ≈ {HUMAN_EROSION}"),
        ("clones", f"{_f(h['clone_pct'])}%", f"SonarQube gate: ≤ {SONAR_DUP}% on new code"),
        ("SQL in source", f"{h['sql_embedded']} statements",
         f"plus {h['sql_file_loc']} lines in .sql files"),
        ("controllers", f"{c['files']} files, {c['loc']} lines",
         "declared in [codebench]" if data["controllers_declared"]
         else "detected by name — declare [codebench] controller_paths"),
        ("  with SQL", f"{c['with_sql']} ({pct(c['with_sql'], c['files'])})", "MVC: data access belongs to the model"),
        ("  touching data", f"{c['with_data']} ({pct(c['with_data'], c['files'])})",
         "SQL or direct DB/storage calls (MNT-2)"),
    ]
    out += ["", f"  now — HEAD {h['sha']} ({h['date']})", ""]
    out += [f"  {a:24} {str(b):28} {r}" for a, b, r in rows]

    out += ["", "  trend", "",
            f"  {'date':10} {'commit':8} {'LOC':>7} {'fns':>6} {'CC avg':>6} {'max':>4} "
            f"{'CC>10':>6} {'erosion':>8} {'clones%':>7} {'SQL':>5} {'ctrl+data':>9}"]
    for r in data["snapshots"]:
        cc_ = r["controllers"]
        out.append(f"  {r['date']:10} {r['sha']:8} {_f(r['loc'], 7)} {_f(r['functions'], 6)} "
                   f"{_f(r['cc_mean'], 6)} {_f(r['cc_max'], 4)} {_f(r['complex'], 6)} "
                   f"{_f(r['structural_erosion'], 8)} {_f(r['clone_pct'], 7)} "
                   f"{_f(r['sql_embedded'], 5)} "
                   f"{(str(cc_['with_data']) + '/' + str(cc_['files'])):>9}"
                   + (f"  ← {r['label']}" if r["label"] else ""))

    if data["hotspots"]:
        since = data["hotspots"][0]["since"]
        out += ["", f"  hotspots at HEAD — most complexity mass (CC then = at {since}; "
                "◆ = controller touching data)", ""]
        for x in data["hotspots"]:
            if x["cc_then"] is None:
                grew = "   new"
            elif x["cc_then"] != x["cc"]:
                grew = f"   CC {x['cc_then']} → {x['cc']}"
            else:
                grew = "   unchanged"
            mark = "◆" if x["controller_with_data"] else " "
            out.append(f"  {mark} CC {x['cc']:>3} ({radon_rank(x['cc'])})  {x['sloc']:>4} lines  "
                       f"{x['path']}:{x['line']} {x['function']}{grew}")
    out += ["", "  Complexity and function measures are Python only; other languages count "
            "in size, clones, SQL and layers.",
            "  Tests are out; byte-identical copies count once; erosion falls when simple "
            "code lands — read it with CC>10."]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="code-quality view over history")
    ap.add_argument("--root", default=None, help="project root (default: this repo)")
    ap.add_argument("--points", type=int, default=6,
                    help="snapshots spread over the history (default 6)")
    ap.add_argument("--top", type=int, default=10, help="hotspots listed (default 10)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--mutants", type=int, default=0, metavar="N",
                    help="instead: the suite's effectiveness, N sampled mutants per module")
    ap.add_argument("--modules", type=int, default=8, help="with --mutants: modules sampled (default 8)")
    ap.add_argument("--module", action="append", default=[], help="with --mutants: this module only")
    ap.add_argument("--test-cmd", default=None, help="with --mutants: runs one test file, '{test}' replaced")
    ap.add_argument("--seed", type=int, default=0, help="with --mutants: sampling seed (default 0)")
    ap.add_argument("--tests", action="store_true",
                    help="instead: the suite's effectiveness, sized by --minutes")
    ap.add_argument("--minutes", type=float, default=10, help="with --tests: time budget (default 10)")
    ap.add_argument("--changed-since", default=None, metavar="REF",
                    help="with --tests/--mutants: modules changed since REF only")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else project_root()
    if args.mutants > 0 or args.tests:
        import mutation
        data = mutation.sample(root, args.mutants or None, args.modules, args.module,
                               args.test_cmd, args.seed, args.minutes, args.changed_since)
        print(json.dumps(data, indent=2) if args.format == "json"
              else "\n".join(mutation.render(data)))
        return 0
    data = bench(root, max(2, args.points), args.top)
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print("\n".join(render(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
