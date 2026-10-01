#!/usr/bin/env python3
"""
mutation — how much of the test suite catches a bug, sampled (owner
request, 2026-09-30). Time says what a suite costs, coverage says what
ran; a mutation score says what the tests would catch: plant one small
defect, run the module's own tests, count the defects they kill.

Measured on the kernel itself before it shipped: 105 sampled mutants
over seven modules, 64% killed, from 2/15 to 15/15 by module — the size
of a suite does not say where it protects.

Nothing to choose by hand — the agent runs it at cycle close (fde-review):
- modules: the project's own Python modules with tests — the test files
  named after the module (`test_<stem>.py`, `<stem>_test.py`) and those
  that import it; `--changed-since <ref>` keeps the modules changed since;
- runner: `[codebench] test_file_command` ('{test}' is the file list)
  when declared; pytest when `[stack] test_command` names it or the
  project has a conftest.py; unittest when it names unittest or nothing;
- size: N mutants per module, or a time budget (`--minutes`, default 10)
  shared across modules from each module's baseline seconds;
- place: always a temporary worktree at HEAD, never the working copy —
  other sessions may be committing there. What the tests need and git
  does not hold (ignored build output, bundles, node_modules, a venv) is
  linked into it from the working copy, read as it is.

Per module: the tests run unchanged (the baseline and its seconds; a
failing baseline is skipped, never scored), then the mutants — a
comparison flipped, `and` ↔ `or`, an `if` negated, an integer + 1, a
returned boolean inverted, drawn with a fixed seed. A failure or a
timeout kills a mutant; a pass is a survivor, reported with its line. A
byte-identical copy (a mirror) is mutated with its source. It reports;
it never gates. stdlib only (I6).
"""
from __future__ import annotations

import ast
import json
import os
import random
import re
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


GENERIC_STEMS = {"__init__", "main", "app", "handler", "utils", "util",
                 "models", "views", "config", "settings", "conftest"}


def _imports(text: str, dotted: str) -> bool:
    parent, _, leaf = dotted.rpartition(".")
    pats = [rf"^\s*(?:from|import)\s+(?:[\w.]+\.)?{re.escape(dotted)}\b"]
    if parent:
        pats.append(rf"^\s*from\s+(?:[\w.]+\.)?{re.escape(parent)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b")
    return any(re.search(p, text, re.M) for p in pats)


def tests_for(module: str, test_texts: dict[str, str], limit: int = 3) -> list[str]:
    """The test files of a module: named after it, then those importing it."""
    p = Path(module)
    stem = p.stem
    named = [t for t in test_texts
             if Path(t).stem in (f"test_{stem}", f"{stem}_test")]
    parts = list(p.with_suffix("").parts)
    dotted = [".".join(parts[i:]) for i in range(len(parts))]
    if stem in GENERIC_STEMS:  # `handler` alone names every lambda
        dotted = [d for d in dotted if "." in d]
    importing = [t for t, text in sorted(test_texts.items())
                 if t not in named and any(_imports(text, d) for d in dotted)]
    return (named + importing)[:limit]


def candidates(root: Path, only: list[str], since: str | None = None) -> list[tuple[str, list[str]]]:
    """(module, its test files), largest logic first, mirrors once."""
    test_texts = {}
    for n in tracked(root):
        if n.endswith(".py") and erosion._is_test_path(n) and Path(n).name != "conftest.py":
            try:
                test_texts[n] = (root / n).read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    changed = None
    if since:
        changed = set((fde_lib._git(root, "diff", "--name-only", f"{since}..HEAD") or "").splitlines())
    src = codebench.snapshot_files(root, "HEAD")
    out = []
    for name, text in src.items():
        if not name.endswith(".py") or (only and name not in only):
            continue
        if changed is not None and name not in changed:
            continue
        tests = tests_for(name, test_texts)
        if not tests:
            continue
        try:
            weight = len(points(ast.parse(text)))
        except SyntaxError:
            continue
        out.append((weight, name, tests))
    out.sort(key=lambda t: (-t[0], t[1]))
    seen, uniq = set(), []
    for _, name, tests in out:  # a mirror is mutated with its source, not again
        if src[name] not in seen:
            seen.add(src[name])
            uniq.append((name, tests))
    return uniq


def runner(root: Path, tests: list[str], template: str | None) -> list[str] | str | None:
    """The command that runs these test files, or None when it cannot be told."""
    raw = fde_lib.load_toml(root / "fde.config.toml") if (root / "fde.config.toml").exists() else {}
    template = template or str((raw.get("codebench") or {}).get("test_file_command") or "")
    files = " ".join(shlex.quote(t) for t in tests)
    if template:
        return template.replace("{test}", files)
    cmd = str((raw.get("stack") or {}).get("test_command") or "")
    conftest = any(Path(n).name == "conftest.py" for n in tracked(root))
    if "pytest" in cmd:
        return f"{cmd} -x {files}"
    if not conftest and ("unittest" in cmd or not cmd):
        py = shlex.quote(sys.executable)
        return " && ".join(f"{py} -m unittest discover -s {shlex.quote(str(Path(t).parent))} "
                           f"-p {shlex.quote(Path(t).name)}" for t in tests)
    if conftest:
        if _has_pytest():
            return f"{shlex.quote(sys.executable)} -m pytest -q -x -p no:cacheprovider {files}"
        if shutil.which("pytest"):
            return f"pytest -q -x -p no:cacheprovider {files}"
    return None


def _has_pytest() -> bool:
    return subprocess.run([sys.executable, "-c", "import pytest"],
                          capture_output=True).returncode == 0


def run(cmd, cwd: Path, timeout: float) -> tuple[bool, float]:
    """(passed, seconds); a timeout is a failure — a mutant that hangs is caught."""
    t0 = time.monotonic()
    try:
        # no bytecode: two same-size mutants written in one second would
        # otherwise share a stale .pyc — and the working copy stays clean
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                           capture_output=True, timeout=timeout, env=env)
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    return ok, time.monotonic() - t0


def link_ignored(root: Path, wt: Path) -> list[str]:
    """Link into the worktree what the working copy holds and git ignores."""
    out = fde_lib._git(root, "ls-files", "--others", "--ignored", "--exclude-standard",
                       "--directory") or ""
    linked = []
    for rel in out.splitlines():
        rel = rel.rstrip("/")
        if not rel or rel.startswith(".fde/runs") or (wt / rel).exists() or (wt / rel).is_symlink():
            continue
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).symlink_to(root / rel)
        linked.append(rel)
    return linked


def _mutate_module(wt: Path, name: str, copies: list[str], cmd, secs: float,
                   n: int, seed: int, row: dict) -> None:
    src = (wt / name).read_text(encoding="utf-8")
    k = len(points(ast.parse(src)))
    rng = random.Random(f"{seed}:{name}")
    files = (name, *copies)
    for i in rng.sample(range(k), min(n, k)):
        m = mutant(src, i)
        if m is None:
            continue
        kind, text, line = m
        try:
            for c in files:
                (wt / c).write_text(text, encoding="utf-8")
            passed, _ = run(cmd, wt, secs * 3 + 10)
        finally:
            for c in files:
                (wt / c).write_text(src, encoding="utf-8")
        row["mutants"] += 1
        if passed:
            code = src.splitlines()[line - 1].strip()
            row["survivors"].append({"line": line, "kind": kind, "code": code[:100]})
        else:
            row["killed"] += 1


def sample(root: Path, n: int | None = None, modules: int = 8, only: list[str] | None = None,
           template: str | None = None, seed: int = 0, minutes: float = 10,
           since: str | None = None) -> dict:
    picked = candidates(root, only or [], since)
    if not only:
        picked = picked[:modules]
    tmp = Path(tempfile.mkdtemp(prefix="fde-mutation-"))
    wt = tmp / "wt"
    if fde_lib._git(root, "worktree", "add", "--detach", "-q", str(wt), "HEAD") is None:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"error": "git worktree add failed", "modules": []}
    rows, deadline = [], time.monotonic() + minutes * 60
    try:
        link_ignored(root, wt)
        names = tracked(wt)
        plan = []
        for name, tests in picked:
            row = {"module": name, "tests": tests, "killed": 0, "mutants": 0,
                   "survivors": [], "baseline_seconds": None, "skipped": None}
            rows.append(row)
            cmd = runner(wt, tests, template)
            if cmd is None:
                row["skipped"] = ("no runner found: declare [codebench] test_file_command "
                                  "= '<cmd> {test}'")
                continue
            ok, secs = run(cmd, wt, 600)
            if not ok:
                row["skipped"] = "its tests fail unchanged"
                continue
            src = (wt / name).read_text(encoding="utf-8")
            copies = [c for c in names if c != name and c.endswith(".py") and (wt / c).is_file()
                      and not (wt / c).is_symlink()
                      and (wt / c).read_text(encoding="utf-8", errors="replace") == src]
            row["baseline_seconds"] = round(secs, 1)
            plan.append((row, name, copies, secs, cmd))
        for idx, (row, name, copies, secs, cmd) in enumerate(plan):
            left = deadline - time.monotonic()
            if n is None and left <= 0:
                row["skipped"] = "time budget spent"
                continue
            share = left / (len(plan) - idx)
            count = n if n is not None else max(3, min(25, int(share / (secs * 1.2 + 0.5))))
            _mutate_module(wt, name, copies, cmd, secs, count, seed, row)
    finally:
        fde_lib._git(root, "worktree", "remove", "--force", str(wt))
        shutil.rmtree(tmp, ignore_errors=True)
    total = sum(r["mutants"] for r in rows)
    killed = sum(r["killed"] for r in rows)
    return {"seed": seed, "per_module": n, "minutes": minutes, "since": since,
            "modules": rows,
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
