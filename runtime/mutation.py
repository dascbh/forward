#!/usr/bin/env python3
"""
mutation — how much of the test suite catches a bug, sampled (owner
request, 2026-09-30). Time says what a suite costs, coverage says what
ran; a mutation score says what the tests would catch: plant one small
defect, run the module's own tests, count the defects they kill.

Measured on the kernel itself before it shipped: 105 sampled mutants
over seven modules, 64% killed, from 2/15 to 15/15 by module — the size
of a suite does not say where it protects.

For each Python module of the project's own source that has a test file
named after it (`test_<stem>.py` or `<stem>_test.py`):
1. its tests run unchanged — the baseline, and its duration; a module
   whose baseline fails is skipped with the reason, never scored;
2. N mutation points are drawn with a fixed seed: a comparison flipped
   (`<` ↔ `<=`, `==` ↔ `!=`, `in` ↔ `not in`), `and` ↔ `or`, an `if`
   negated, an integer + 1, a returned boolean inverted;
3. each mutant runs the same tests; a failure or a timeout kills it, a
   pass is a survivor, reported with its line.

Everything runs in a temporary git worktree at HEAD: the working copy is
never touched, and the measure is of what is committed. A byte-identical
copy of the module (a mirror) is mutated with it. It reports; it never
gates. stdlib only (I6).
"""
from __future__ import annotations

import ast
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import codebench  # noqa: E402
import erosion  # noqa: E402
import fde_lib  # noqa: E402

FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
        ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn,
        ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def points(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    """Mutation points in a fixed (walk) order, so a seed picks the same ones."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and type(n.ops[0]) in FLIP:
            out.append(("compare", n))
        elif isinstance(n, ast.BoolOp):
            out.append(("and/or", n))
        elif isinstance(n, ast.If):
            out.append(("if", n))
        elif (isinstance(n, ast.Constant) and type(n.value) is int):
            out.append(("integer", n))
        elif (isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
              and isinstance(n.value.value, bool)):
            out.append(("return", n))
    return out


def mutant(src: str, i: int) -> tuple[str, str, int] | None:
    """(kind, mutated source, line) for point i of src, or None."""
    tree = ast.parse(src)
    kind, n = points(tree)[i]
    if kind == "compare":
        n.ops[0] = FLIP[type(n.ops[0])]()
    elif kind == "and/or":
        n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
    elif kind == "if":
        n.test = ast.UnaryOp(ast.Not(), n.test)
    elif kind == "integer":
        n.value += 1
    else:
        n.value.value = not n.value.value
    try:
        return kind, ast.unparse(ast.fix_missing_locations(tree)), n.lineno
    except (ValueError, RecursionError):
        return None


def tracked(root: Path) -> list[str]:
    return (fde_lib._git(root, "ls-files") or "").splitlines()


def candidates(root: Path, only: list[str]) -> list[tuple[str, str]]:
    """(module, its test file): the project's own Python modules with a
    test named after them, largest logic first."""
    names = tracked(root)
    tests = {}
    for n in names:
        p = Path(n)
        if p.suffix == ".py" and erosion._is_test_path(n):
            stem = p.stem.removeprefix("test_").removesuffix("_test")
            tests.setdefault(stem, n)
    src = codebench.snapshot_files(root, "HEAD")
    out = []
    for name, text in src.items():
        if not name.endswith(".py") or (only and name not in only):
            continue
        test = tests.get(Path(name).stem)
        if test:
            try:
                weight = len(points(ast.parse(text)))
            except SyntaxError:
                continue
            out.append((weight, name, test))
    out.sort(key=lambda t: (-t[0], t[1]))
    seen, uniq = set(), []
    for _, name, test in out:  # a mirror is mutated with its source, not again
        text = src[name]
        if text not in seen:
            seen.add(text)
            uniq.append((name, test))
    return uniq


def runner(root: Path, test: str, template: str | None) -> list[str] | str | None:
    """The command that runs one test file: a `{test}` template, pytest
    when the project's test_command is pytest, else unittest."""
    if template:
        return template.replace("{test}", shlex.quote(test))
    cmd = str(((fde_lib.load_toml(root / "fde.config.toml") if (root / "fde.config.toml").exists()
                else {}).get("stack") or {}).get("test_command") or "")
    if "pytest" in cmd:
        return f"{cmd} {shlex.quote(test)}"
    if cmd and "unittest" not in cmd:
        return None
    p = Path(test)
    return [sys.executable, "-m", "unittest", "discover", "-s", str(p.parent), "-p", p.name]


def run(cmd, cwd: Path, timeout: float) -> tuple[bool, float]:
    """(passed, seconds); a timeout is a failure — a mutant that hangs is caught."""
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                           capture_output=True, timeout=timeout)
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    return ok, time.monotonic() - t0


def sample(root: Path, n: int = 10, modules: int = 8, only: list[str] | None = None,
           template: str | None = None, seed: int = 0) -> dict:
    picked = candidates(root, only or [])[:modules] if not only else candidates(root, only)
    tmp = Path(tempfile.mkdtemp(prefix="fde-mutation-"))
    wt = tmp / "wt"
    if fde_lib._git(root, "worktree", "add", "--detach", "-q", str(wt), "HEAD") is None:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"error": "git worktree add failed", "modules": []}
    rows = []
    try:
        names = tracked(wt)
        for name, test in picked:
            cmd = runner(wt, test, template)
            row = {"module": name, "test": test, "killed": 0, "mutants": 0,
                   "survivors": [], "baseline_seconds": None, "skipped": None}
            rows.append(row)
            if cmd is None:
                row["skipped"] = "no single-file runner: pass --test-cmd '<cmd> {test}'"
                continue
            ok, secs = run(cmd, wt, 600)
            row["baseline_seconds"] = round(secs, 1)
            if not ok:
                row["skipped"] = "its tests fail unchanged"
                continue
            src = (wt / name).read_text(encoding="utf-8")
            copies = [c for c in names if c != name and c.endswith(".py")
                      and (wt / c).is_file() and (wt / c).read_text(encoding="utf-8", errors="replace") == src]
            k = len(points(ast.parse(src)))
            rng = random.Random(f"{seed}:{name}")
            for i in rng.sample(range(k), min(n, k)):
                m = mutant(src, i)
                if m is None:
                    continue
                kind, text, line = m
                for c in (name, *copies):
                    (wt / c).write_text(text, encoding="utf-8")
                passed, _ = run(cmd, wt, secs * 3 + 10)
                for c in (name, *copies):
                    (wt / c).write_text(src, encoding="utf-8")
                row["mutants"] += 1
                if passed:
                    code = src.splitlines()[line - 1].strip()
                    row["survivors"].append({"line": line, "kind": kind, "code": code[:100]})
                else:
                    row["killed"] += 1
    finally:
        fde_lib._git(root, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(tmp, ignore_errors=True)
    total = sum(r["mutants"] for r in rows)
    killed = sum(r["killed"] for r in rows)
    return {"seed": seed, "per_module": n, "modules": rows,
            "score": round(100 * killed / total) if total else None,
            "killed": killed, "mutants": total, **suite_size(root)}


def suite_size(root: Path) -> dict:
    """Non-blank lines of tests against production, at HEAD."""
    prod = sum(sum(1 for l in t.splitlines() if l.strip())
               for t in codebench.snapshot_files(root, "HEAD").values())
    test = 0
    for n in tracked(root):
        if Path(n).suffix.lower() in codebench.SOURCE_SUFFIXES and erosion._is_test_path(n):
            try:
                test += sum(1 for l in (root / n).read_text(encoding="utf-8", errors="replace").splitlines()
                            if l.strip())
            except OSError:
                pass
    return {"production_loc": prod, "test_loc": test,
            "test_per_production": round(test / prod, 2) if prod else None}


def render(d: dict) -> list[str]:
    if d.get("error"):
        return [f"mutation: {d['error']}"]
    out = ["Test suite effectiveness (sampled mutation, HEAD)", "",
           f"  tests / production   {d['test_loc']} / {d['production_loc']} lines"
           f" = {d['test_per_production']}", ""]
    out.append(f"  {'module':44} {'killed':>9} {'tests':>8}")
    for r in d["modules"]:
        t = f"{r['baseline_seconds']}s" if r["baseline_seconds"] is not None else "-"
        k = f"{r['killed']}/{r['mutants']}" if not r["skipped"] else "skipped"
        out.append(f"  {r['module'][:44]:44} {k:>9} {t:>8}"
                   + (f"   {r['skipped']}" if r["skipped"] else ""))
    out.append("")
    out.append(f"  score {d['score']}% ({d['killed']}/{d['mutants']} mutants killed, "
               f"seed {d['seed']})" if d["score"] is not None else "  score: no module scored")
    survivors = [(r["module"], s) for r in d["modules"] for s in r["survivors"]]
    if survivors:
        out += ["", "  survivors — a defect here passes every test of its module:"]
        for mod, s in survivors:
            out.append(f"    {mod}:{s['line']}  {s['kind']:8} {s['code']}")
    return out
