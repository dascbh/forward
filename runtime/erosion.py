#!/usr/bin/env python3
"""
erosion — measure the decay the thesis predicts, instead of assuming it.

Four long-horizon studies (SlopCodeBench arXiv 2603.24755, SWE-EVO,
NL2Repo-Bench, SpecBench) show coding agents degrade MONOTONICALLY:
erosion in 80% of trajectories, verbosity in 89.8%, complexity 10×, agent
code 2.2× more verbose than maintained repos. Their decisive finding is
negative — prompt interventions ("anti-slop") cut initial verbosity but
degradation resumes at the identical rate. So this is not a skill telling
the model to "write clean code" (that demonstrably fails); it is
measurement the gate can consume (ADR-0011).

Stdlib only, language-agnostic subset the papers rely on: the clone ratio
(duplicate-block density), the add/delete ratio (growth by accretion),
dependency count, large-change rate — and, for Python, the paper's
structural erosion (SlopCodeBench v2 §2.3) with the stdlib `ast`. Other
languages report it as not measured; exact cyclomatic complexity beyond
that stays with the client's tools, as I1 delegates the eval framework —
the kernel keeps I6.

Thresholds are project-specific, so they are DECLARED in `[erosion]`
(I4 pattern), never hardcoded: the gate enforces the declared budget and
is silent when undeclared.
"""

from __future__ import annotations

import argparse
import ast
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
from fde_lib import gate_paths, path_matches, project_root  # noqa: E402

DEFAULT_WINDOW = 50
CLONE_K = 6  # line-window size for duplicate-block detection
# Vendor trees are nobody's organic code, in any project — this is the
# only hardcoded exclusion, and it excludes code the project did not
# write. Which of the project's OWN paths are generated copies is
# declared in `[erosion] generated_paths`, never assumed here.
VENDOR_PREFIXES = ("node_modules/", ".venv/", "venv/", "vendor/", "dist/",
                   "build/", ".git/", "__pycache__/")
DUPLICATION_EXCLUDED = VENDOR_PREFIXES
# A project that declares no [gate] roots is measured whole, except the
# cycle records (cycles/C-<n>/ plans, boards, reviews): they only grow,
# and counting them read as accretion in the project's code (B-20).
RECORD_PREFIXES = ("cycles/",)
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
                 ".rb", ".php", ".c", ".h", ".cpp", ".cs", ".kt", ".swift",
                 ".scala", ".sh", ".sql", ".toml", ".md"}
MANIFESTS = {
    "package.json": lambda t: _count_json_deps(t),
    "requirements.txt": lambda t: sum(1 for l in t.splitlines()
                                      if l.strip() and not l.startswith("#")),
    "pyproject.toml": lambda t: _count_pyproject_deps(t),
    "go.mod": lambda t: len(re.findall(r"^\s+[^\s]+\s+v\d", t, re.M)),
    "Cargo.toml": lambda t: _count_cargo_deps(t),
}


# ---------------------------------------------------------------------------
# pure cores — no git, no fs; unit-tested directly
# ---------------------------------------------------------------------------
_ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
            "t": "\t", "v": "\v", '"': '"', "\\": "\\"}


def _unquote(raw: str) -> str:
    """Undo git's C-style path quoting: a path with non-ASCII or special
    bytes arrives as "src/caf\\303\\251.py". Left quoted, it matches no
    declared root and its churn vanishes from the measurement."""
    if len(raw) < 2 or not (raw.startswith('"') and raw.endswith('"')):
        return raw
    body, out, i = raw[1:-1], bytearray(), 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in _ESCAPES:
                out += _ESCAPES[nxt].encode()
                i += 2
                continue
            if nxt.isdigit() and len(body) >= i + 4:
                try:
                    out.append(int(body[i + 1:i + 4], 8))
                    i += 4
                    continue
                except ValueError:
                    pass
        out += c.encode()
        i += 1
    return out.decode("utf-8", "replace")


def numstat_path(raw: str) -> str:
    """The path a numstat row refers to, as it stands after the commit.
    Three forms, two of which a naive `.strip()` gets wrong (FWD-016):

        src/a.py                     plain
        "src/caf\\303\\251.py"          quoted (non-ASCII or special bytes)
        old.py => new.py             rename
        pre/{old => new}/f.py        rename with the common parts factored

    A row left unresolved is a path that matches neither the declared
    scope nor the declared exclusions — it escapes the measurement in
    whichever direction happens to be wrong."""
    p = _unquote(raw.strip())
    m = re.search(r"\{(.*?) => (.*?)\}", p)
    if m:
        return re.sub(r"/{2,}", "/", p[:m.start()] + m.group(2) + p[m.end():])
    if " => " in p:
        return p.split(" => ", 1)[1].strip()
    return p


def parse_numstat(text: str, scope: tuple | None = None,
                  generated: tuple = ()) -> tuple[int, int, int]:
    """Sum (added, deleted, rows_counted) from `git log --numstat`. Binary
    files show '-' and are skipped. Paths outside the declared churn
    population are not counted (FWD-016); rows_counted is how many rows
    were, so a caller can tell "zero churn" from "nothing measured"."""
    added = deleted = rows = 0
    for line in text.splitlines():
        m = re.match(r"^(\d+)\t(\d+)\t(.+)$", line)
        if m and in_churn_scope(numstat_path(m.group(3)), scope, generated):
            added += int(m.group(1))
            deleted += int(m.group(2))
            rows += 1
    return added, deleted, rows


def add_delete_ratio(added: int, deleted: int) -> float:
    """Growth by accretion: how many lines added per line removed. High =
    the codebase grows without consolidating (the papers' reuse inversion)."""
    return round(added / deleted, 2) if deleted else float(added)


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def dedupe_copies(contents: dict) -> tuple[dict, int]:
    """Byte-identical files kept in several places (a shared module copied
    into each deploy package) count once: they are one piece of code, and
    counting every copy read as 50% duplication in a real client. Returns
    (contents with one file per identical group, number of groups with
    more than one file)."""
    groups: dict = {}
    for name in sorted(contents):
        h = hashlib.blake2b(contents[name].encode(), digest_size=16).hexdigest()
        groups.setdefault(h, []).append(name)
    kept = {names[0]: contents[names[0]] for names in groups.values()}
    return kept, sum(1 for names in groups.values() if len(names) > 1)


HIGH_CC = 10   # the paper's cutoff, after Radon
# Radon's counting: each if/elif, loop, except, with, assert, ternary,
# comprehension `for` and its `if`s, match case, and each extra boolean
# operand adds one.
_BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
             ast.With, ast.AsyncWith, ast.IfExp, ast.Assert) + (
    (ast.match_case,) if hasattr(ast, "match_case") else ())
_OWN_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _is_test_path(name: str) -> bool:
    """Python's conventions and the front's: `x.test.ts`, `x.spec.tsx`,
    `__tests__/`."""
    base = name.rsplit("/", 1)[-1]
    return ("/tests/" in f"/{name}" or "/test/" in f"/{name}" or "/__tests__/" in f"/{name}"
            or base.startswith("test_") or base.endswith("_test.py")
            or ".test." in base or ".spec." in base)


def cyclomatic(fn) -> int:
    """1 + decision points of one function, nested functions excluded (they
    are callables of their own)."""
    n, todo = 1, list(ast.iter_child_nodes(fn))
    while todo:
        node = todo.pop()
        if isinstance(node, _OWN_SCOPE):
            continue
        if isinstance(node, _BRANCHES):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            n += 1 + len(node.ifs)
        todo.extend(ast.iter_child_nodes(node))
    return n


def _sloc(fn, lines: list) -> int:
    """Source lines of a function without blanks, comments and its
    docstring: documentation is not erosion."""
    body = lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)]
    doc = set()
    first = fn.body[0] if fn.body else None
    if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)):
        doc = set(range(first.lineno - fn.lineno,
                        (first.end_lineno or first.lineno) - fn.lineno + 1))
    return sum(1 for i, l in enumerate(body)
               if i not in doc and l.strip() and not l.strip().startswith("#"))


def structural_erosion(contents: dict) -> dict:
    """SlopCodeBench v2 §2.3 over production Python, TypeScript and
    JavaScript (jscc.py, calibrated on ESLint's complexity): each function's mass
    is CC × √SLOC; erosion is the share of the total mass held by
    functions with CC > 10 — complexity concentrated in functions already
    complex. Test files are left out; identical function bodies count
    once. Returns {"erosion": share rounded to 3 places or None,
    "functions": distinct functions measured, "complex": those with
    CC > 10, "unparsed": Python files that did not parse}."""
    seen, total, high, complex_, unparsed = set(), 0.0, 0.0, 0, 0
    import jscc
    for name, text in contents.items():
        if _is_test_path(name) or name.endswith(".d.ts"):
            continue
        if name.endswith(jscc.SUFFIXES):  # TypeScript and JavaScript, by tokens
            for f in jscc.functions(text):
                if f["key"] in seen:
                    continue
                seen.add(f["key"])
                mass = f["cc"] * math.sqrt(max(f["sloc"], 1))
                total += mass
                if f["cc"] > HIGH_CC:
                    high += mass
                    complex_ += 1
            continue
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            unparsed += 1
            continue
        lines = text.splitlines()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = "\n".join(lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)])
            key = hashlib.blake2b(body.strip().encode(), digest_size=16).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            cc = cyclomatic(fn)
            mass = cc * math.sqrt(max(_sloc(fn, lines), 1))
            total += mass
            if cc > HIGH_CC:
                high += mass
                complex_ += 1
    return {"erosion": round(high / total, 3) if seen and total else None,
            "functions": len(seen), "complex": complex_, "unparsed": unparsed}


def duplicate_block_pct(contents: dict, k: int = CLONE_K) -> float:
    """Clone ratio: fraction of k-line windows (whitespace-normalized, over
    all given files) that recur. The stdlib form of the duplication the
    papers measure. contents: {name: text}."""
    seen: dict = {}
    windows = []
    for text in contents.values():
        lines = [_normalize(l) for l in text.splitlines() if _normalize(l)]
        for i in range(len(lines) - k + 1):
            h = hashlib.blake2b("\n".join(lines[i:i + k]).encode(),
                                digest_size=8).hexdigest()
            windows.append(h)
            seen[h] = seen.get(h, 0) + 1
    if not windows:
        return 0.0
    duplicated = sum(1 for h in windows if seen[h] > 1)
    return round(100.0 * duplicated / len(windows), 1)


def check_budget(metrics: dict, budget: dict) -> tuple[list, list]:
    """Compare measured metrics against DECLARED thresholds only. Returns
    (breaches, unmeasured). An undeclared key is not checked — silence,
    never a false wall. A key declared but NOT measurable is reported as
    unmeasured, never counted as a pass: a threshold that measured
    nothing has not been met, it has been skipped."""
    out, unmeasured = [], []
    checks = [
        ("max_add_delete_ratio", "add_delete_ratio", "add/delete ratio"),
        ("max_duplication_pct", "duplication_pct", "duplicate-block %"),
        ("max_dependencies", "dependencies", "dependency count"),
        ("max_change_lines", "largest_change", "largest change (lines)"),
        ("max_structural_erosion", "structural_erosion", "structural erosion"),
    ]
    for bkey, mkey, label in checks:
        if bkey not in budget:
            continue
        if metrics.get(mkey) is None:
            unmeasured.append(label)
            continue
        # a non-numeric budget is a config error (caught by the config
        # gate); here it must never crash --report — skip it
        try:
            if float(metrics[mkey]) > float(budget[bkey]):
                out.append(f"{label} {metrics[mkey]} > budget {budget[bkey]}")
        except (TypeError, ValueError):
            continue
    return out, unmeasured


# ---------------------------------------------------------------------------
# git / fs wrappers
# ---------------------------------------------------------------------------
def _git(project: Path, *args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=project, capture_output=True,
                           text=True, check=False)
        return r.stdout
    except FileNotFoundError:
        return ""


def _tracked(project: Path) -> list:
    """Tracked paths, never quoted. `git ls-files` C-quotes any path with
    non-ASCII or special bytes, exactly as numstat does; a quoted name
    matches no declared root, so the file vanishes from the duplication
    scan and its own root reads as stale. -z is NUL-separated and quotes
    nothing."""
    return [n for n in _git(project, "ls-files", "-z").split("\0") if n]


def _tracked_code(project: Path, scope: tuple | None = None,
                  generated: tuple = ()) -> tuple[dict, int]:
    """The files the duplication scan reads, over the SAME population
    churn uses — the acceptance criterion's "one definition of the
    codebase". Returns (contents, excluded_count) so the report can state
    how many tracked files were left out (R3)."""
    out, excluded = {}, 0
    for name in _tracked(project):
        p = project / name
        if p.suffix.lower() not in CODE_SUFFIXES or not p.is_file():
            continue
        if not in_churn_scope(name, scope, generated):
            excluded += 1
            continue
        try:
            out[name] = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return out, excluded


def _count_json_deps(text: str) -> int:
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return 0
    return len(d.get("dependencies", {})) + len(d.get("devDependencies", {}))


def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~;\[\s]", spec.strip(), maxsplit=1)[0].lower()


def _count_pyproject_deps(text: str) -> int:
    try:
        d = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return 0
    proj = d.get("project", {})
    # distinct package names — a package in two optional groups is one
    # dependency, not two (review finding, FWD-009)
    names = {_dep_name(s) for s in proj.get("dependencies", [])}
    for group in (proj.get("optional-dependencies", {}) or {}).values():
        names |= {_dep_name(s) for s in group}
    names.discard("")
    return len(names)


def _count_cargo_deps(text: str) -> int:
    try:
        d = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return 0
    return len(d.get("dependencies", {})) + len(d.get("dev-dependencies", {}))


def dependency_count(project: Path) -> int | None:
    total, seen = 0, False
    for name, fn in MANIFESTS.items():
        p = project / name
        if p.is_file():
            seen = True
            total += fn(p.read_text(encoding="utf-8", errors="ignore"))
    return total if seen else None


def _config(project: Path) -> dict:
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return {}
    try:
        return tomllib.loads(cfg.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return {}


def churn_scope(project: Path) -> tuple | None:
    """The paths churn is measured over: the roots the project DECLARED
    in `[gate]` for I1. None when `[gate]` declares none — a project that
    declared nothing is measured whole, never silently narrowed to
    defaults that may not exist in it (R2)."""
    gate = _config(project).get("gate") or {}
    declared = _as_paths(gate.get("behavior_paths")) + _as_paths(gate.get("eval_paths"))
    return declared or None


def _as_paths(value) -> tuple:
    """A path list, or nothing. A bare string is NOT a list of paths:
    tuple("src/") is ('s','r','c','/'), a scope that matches nothing and
    disarms the gate in silence (review finding, FWD-016)."""
    if not isinstance(value, list):
        return ()
    return tuple(x for x in value if isinstance(x, str) and x.strip())


def generated_paths(project: Path) -> tuple:
    """Paths the project DECLARES as generated copies, in
    `[erosion] generated_paths`. Excluded from churn because a mirror is
    the same change counted twice, not organic growth — but the project
    says which paths those are. The kernel does not un-declare, from a
    hardcoded list, roots the config declares as behavior (review
    finding, FWD-016)."""
    return _as_paths((_config(project).get("erosion") or {}).get("generated_paths"))


def in_churn_scope(path: str, scope: tuple | None,
                   generated: tuple = ()) -> bool:
    if generated and path_matches(path, generated):
        return False
    if path.startswith(VENDOR_PREFIXES):
        return False
    if scope is None:
        # measured whole, but the cycle records are the kernel's own
        # append-only trail, not the project's code (B-20)
        return not path.startswith(RECORD_PREFIXES)
    return path_matches(path, scope)


def stale_roots(project: Path, scope: tuple | None) -> list:
    """Declared roots that match no tracked file — a stale or misspelled
    root, or one declared at install time before the code exists.

    It is NAMED, not walled. From outside, a typo and a greenfield root
    are the same observation, and `[gate]` is written by `fde-init`
    before any code exists while `[erosion]` is opt-in: failing on the
    first because of the second couples two different lifecycles. So the
    gate exits 0 and says, in the same line as the metric it could not
    measure, which declaration produced the silence (review finding,
    FWD-016). A repo with nothing tracked is exempt entirely."""
    if not scope:
        return []
    tracked = _tracked(project)
    if not tracked:
        return []
    return [r for r in scope if not any(path_matches(f, (r,)) for f in tracked)]


def measure(project: Path, window: int = DEFAULT_WINDOW) -> dict:
    """All stdlib signals over ONE population, stated in the output: the
    roots the project declared in `[gate]`, minus the copies it declared
    in `[erosion] generated_paths`, minus vendor trees. Duplication and
    churn agree about what "the codebase" is. Every metric degrades to
    None when unavailable — no git history, no manifests, empty tree —
    instead of crashing.
    """
    m: dict = {"window": window}

    scope = churn_scope(project)
    gen = generated_paths(project)
    m["scope"] = list(scope) if scope else []
    m["generated"] = list(gen)
    m["churn_scope"] = ", ".join(scope) if scope else "everything tracked except cycles/"

    contents, excluded = _tracked_code(project, scope, gen)
    contents, m["copy_groups"] = dedupe_copies(contents)
    m["duplication_pct"] = duplicate_block_pct(contents) if contents else None
    se = structural_erosion(contents)
    m["structural_erosion"] = se["erosion"]
    m["python_functions"], m["complex_functions"] = se["functions"], se["complex"]
    m["unparsed_python"] = se["unparsed"]
    m["files_scanned"] = len(contents)
    m["files_excluded"] = excluded

    log = _git(project, "log", f"-{window}", "--numstat", "--format=")
    added, deleted, rows = parse_numstat(log, scope, gen) if log.strip() else (0, 0, 0)
    m["added"], m["deleted"], m["churn_rows"] = added, deleted, rows
    # rows==0 is NOT zero churn: it is churn never measured (the window
    # touched nothing inside the population, or the declared roots do not
    # exist here). Reporting it as a pass would be a silent green.
    m["add_delete_ratio"] = add_delete_ratio(added, deleted) if rows else None
    m["largest_change"] = (_largest_change(project, window, scope, gen)
                           if rows else None)

    m["stale_roots"] = stale_roots(project, scope)
    m["dependencies"] = dependency_count(project)
    # over every commit in the window, not the population above: it
    # measures the history's process overhead, a report line, never gated
    m["process_only_ratio"] = process_only_ratio(_commit_paths(project, window))
    return m


def _largest_change(project: Path, window: int, scope: tuple | None = None,
                    generated: tuple = ()) -> int | None:
    # batch size = the largest NON-ROOT commit. A root/scaffold commit
    # (--min-parents=1 excludes 0-parent commits) is a bulk import, not a
    # batch — counting it makes max_change_lines a false wall on any repo
    # younger than the window (review finding, FWD-009).
    out = _git(project, "log", f"-{window}", "--min-parents=1",
               "--numstat", "--format=%H")
    if not out.strip():
        return None
    biggest, cur = 0, 0
    for line in out.splitlines():
        if re.fullmatch(r"[0-9a-f]{7,40}", line.strip()):
            biggest = max(biggest, cur)
            cur = 0
            continue
        mt = re.match(r"^(\d+)\t(\d+)\t(.+)$", line)
        if mt and in_churn_scope(numstat_path(mt.group(3)), scope, generated):
            cur += int(mt.group(1)) + int(mt.group(2))
    return max(biggest, cur)


# Process records: the paths a commit touches when it records the work
# rather than doing it. A high share of process-only commits is overhead
# the history carries; the merge rule (fde-review) squashes them at merge.
# The list is the merge rule's, nothing wider: a demand's spec is part of
# its change, so specs/ is not a process record here.
PROCESS_PATHS = ("reviews/", "cycles/", "promotions/", "backlog.md")


def is_process_path(path: str) -> bool:
    return any(path == p or (p.endswith("/") and path.startswith(p))
               for p in PROCESS_PATHS)


def process_only_ratio(commits: list) -> float | None:
    """Share of commits (each a list of the paths it touched) that touch
    only process paths. Commits touching no file do not count; no commit
    left is None — not measured, never 0."""
    touched = [c for c in commits if c]
    if not touched:
        return None
    only = sum(1 for c in touched if all(is_process_path(p) for p in c))
    return round(only / len(touched), 2)


def _commit_paths(project: Path, window: int) -> list:
    out = _git(project, "-c", "core.quotepath=off", "log", f"-{window}",
               "--name-only", "--format=%x01%H")
    commits: list = []
    for line in out.splitlines():
        if line.startswith("\x01"):
            commits.append([])
        elif line.strip() and commits:
            commits[-1].append(line.strip())
    return commits


def load_budget(project: Path) -> dict:
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return {}
    try:
        return tomllib.loads(cfg.read_text(encoding="utf-8")).get("erosion", {}) or {}
    except tomllib.TOMLDecodeError:
        return {}


def gate(project: Path) -> tuple[bool, list, list]:
    """Return (declared, breaches, unmeasured). declared=False means
    [erosion] is absent — the gate stays silent (never a false wall).
    declared=True with two empty lists means measured and within budget.
    unmeasured is what the budget declared and the window could not
    measure — it passes, but it never passes silently."""
    declared = load_budget(project)
    if not declared:
        return False, [], []
    budget = effective_budget(declared)
    window = int(budget.get("window", DEFAULT_WINDOW))
    m = measure(project, window)
    open_debt = covered(declared)
    breaches, unmeasured = check_budget(m, {k: v for k, v in budget.items()
                                            if METRIC_OF.get(k) not in open_debt})
    if "max_quarantined" in declared and quarantine_count(project) > int(declared["max_quarantined"]):
        breaches.append(f"quarantined tests {quarantine_count(project)} > "
                        f"{declared['max_quarantined']} at the last close — fix a red, never park it")
    if declared.get("debt_overdue"):
        breaches.insert(0, f"erosion debt of {declared.get('debt_cycle')} "
                        f"({declared.get('debt_item')}) unpaid after {DEBT_DUE_CLOSES} "
                        "cycle closes — a replan for the owner")
    if unmeasured and m["stale_roots"]:
        unmeasured = [u + f" (declared root(s) {', '.join(m['stale_roots'])} "
                      f"match no tracked file)" for u in unmeasured]
    return True, breaches, unmeasured


def population_lines(m: dict) -> list:
    """R3: state the population that was measured, so a reader sees what
    was left out instead of trusting the number. The churn population is
    the declared roots MINUS the declared generated copies — both halves
    named, because the second half is what moves the ratio most."""
    roots = ", ".join(m["scope"]) if m["scope"] else "everything tracked"
    out = [f"measured over: {roots}",
           f"  ({m['files_scanned']} code files scanned for duplication, "
           f"{m['files_excluded']} tracked code files excluded; "
           f"{m['churn_rows']} changed files counted for churn)"]
    if m["generated"]:
        out.append("excluded as generated copies (declared in [erosion] "
                   "generated_paths):")
        out.append("  " + ", ".join(m["generated"]))
    if m.get("copy_groups"):
        out.append(f"{m['copy_groups']} group(s) of byte-identical files counted "
                   "once — if they are generated copies, declare them in "
                   "[erosion] generated_paths")
    if m["stale_roots"]:
        out.append("declared but matching no tracked file (stale or "
                   "misspelled): " + ", ".join(m["stale_roots"]))
    if not m["churn_rows"]:
        out.append("no churn inside this population in the window — the "
                   "churn metrics below are NOT measured")
    return out


def verdict(breaches: list, unmeasured: list) -> str:
    if breaches:
        return "; ".join(breaches)
    if unmeasured:
        return ("within budget, but not measured: " + ", ".join(unmeasured) +
                " — the declared threshold had nothing to check")
    return "within the declared erosion budget"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# the ratchet, the bounded loop and the one debt (owner, 2026-10-01): the
# budget identifies and blocks a deviation, the agent corrects it, and
# nothing loops — at most two consolidation attempts, then one debt that
# must be paid within two cycle closes, else a replan for the owner.
# ---------------------------------------------------------------------------
TARGETS = {"max_duplication_pct": 3.0, "max_structural_erosion": 0.5}  # absolute direction
GLIDE = 0.10      # each close moves a budget this share of the way to its target
MARGIN = 0.05     # a ratcheted budget sits this far above the measured value
SMALL_COMMIT = 10  # added + deleted lines a commit may always carry
METRIC_OF = {"max_add_delete_ratio": "add_delete_ratio",
             "max_duplication_pct": "duplication_pct",
             "max_structural_erosion": "structural_erosion"}
DEBT_DUE_CLOSES = 2


def effective_budget(budget: dict) -> dict:
    """The declared budget, each metric under an open debt raised to the
    debt's value — the room the debt bought, until it is paid."""
    out = dict(budget)
    if budget.get("debt_overdue"):
        return out  # a debt past due buys no room
    for bkey, mkey in METRIC_OF.items():
        debt = budget.get(f"debt_{mkey}")
        if isinstance(debt, (int, float)) and bkey in out:
            out[bkey] = max(float(out[bkey]), float(debt))
    return out


def has_debt(budget: dict) -> bool:
    return any(k.startswith("debt_") for k in budget)


def covered(budget: dict) -> set:
    """Metrics an open debt covers until it falls due: their breach blocks
    neither a commit nor a merge. Coverage is by the debt's existence,
    not its value — a count window drifts as old commits leave it, and a
    value would turn into a moving target (a client's debt was "adjusted"
    13.31 → 18.24 with no new code)."""
    if budget.get("debt_overdue"):
        return set()
    return {mkey for mkey in METRIC_OF.values() if f"debt_{mkey}" in budget}


def set_erosion_keys(project: Path, updates: dict, remove: tuple = ()) -> None:
    """Rewrite keys of the `[erosion]` table in fde.config.toml in place,
    other lines untouched; a missing key is appended to the table."""
    cfg = project / "fde.config.toml"
    lines = cfg.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "[erosion]"), None)
    if start is None:
        lines += ["", "[erosion]"]
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")),
               len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    todo = dict(updates)
    kept = []
    for l in lines[start + 1:end]:
        key = l.split("=", 1)[0].strip() if "=" in l and not l.lstrip().startswith("#") else None
        if key in remove:
            continue
        if key in todo:
            kept.append(f"{key} = {_toml(todo.pop(key))}")
        else:
            kept.append(l)
    kept += [f"{k} = {_toml(v)}" for k, v in todo.items()]
    cfg.write_text("\n".join(lines[:start + 1] + kept + lines[end:]) + "\n", encoding="utf-8")


def _toml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace('"', "'") + '"'


QUARANTINE = re.compile(r"quarantine[d]?\W{1,3}B-\d+", re.I)


def quarantine_count(project: Path) -> int:
    """Tests skipped as `quarantine B-<n>` across the tracked test files."""
    n = 0
    for name in _tracked(project):
        if _is_test_path(name) and Path(name).suffix.lower() in CODE_SUFFIXES:
            try:
                n += len(QUARANTINE.findall((project / name).read_text(encoding="utf-8",
                                                                          errors="replace")))
            except OSError:
                pass
    return n


def close_cycle(project: Path, cycle: str) -> dict:
    """At a cycle's close: each declared budget drops to the measured value
    (plus a margin) when it improved, duplication and structural erosion
    also glide toward their absolute targets, nothing ever rises; an open
    debt is settled when paid and falls due at its second close."""
    budget = load_budget(project)
    if not budget:
        return {"declared": False}
    m = measure(project, int(budget.get("window", DEFAULT_WINDOW)))
    updates, changes = {}, []
    for bkey, mkey in METRIC_OF.items():
        if bkey not in budget or m.get(mkey) is None:
            continue
        old, now = float(budget[bkey]), float(m[mkey])
        digits = 3 if bkey == "max_structural_erosion" else (1 if bkey == "max_duplication_pct" else 2)
        new = min(old, round(now * (1 + MARGIN), digits)) if now < old else old
        target = TARGETS.get(bkey)
        if target is not None and old > target:
            new = min(new, round(old - GLIDE * (old - target), digits))
        new = max(new, target or 0.0) if target is not None and old >= target else new
        if new < old:
            updates[bkey] = new
            changes.append(f"{bkey} {old} → {new} (measured {now})")
    q = quarantine_count(project)
    old_q = budget.get("max_quarantined")
    if old_q is None or q < int(old_q):
        updates["max_quarantined"] = q  # recorded at the first close, then only down
        if old_q is not None:
            changes.append(f"max_quarantined {old_q} → {q}")
    remove: tuple = ()
    debt = None
    if has_debt(budget):
        unpaid = [mkey for bkey, mkey in METRIC_OF.items()
                  if f"debt_{mkey}" in budget and m.get(mkey) is not None
                  and float(m[mkey]) > float(updates.get(bkey, budget.get(bkey, 0)))]
        if not unpaid:
            remove = tuple(k for k in budget if k.startswith("debt_"))
            debt = "paid"
        else:
            closes = int(budget.get("debt_closes", 0)) + 1
            updates["debt_closes"] = closes
            debt = "overdue" if closes >= DEBT_DUE_CLOSES else f"open ({closes}/{DEBT_DUE_CLOSES} closes)"
            if closes >= DEBT_DUE_CLOSES:
                updates["debt_overdue"] = True
    if updates or remove:
        set_erosion_keys(project, updates, remove)
    return {"declared": True, "cycle": cycle, "changes": changes, "debt": debt}


def register_debt(project: Path, cycle: str, item: str) -> tuple[bool, str]:
    """After two consolidation attempts left a budget breached: one debt,
    worth the breach measured now, tied to the backlog item that pays it.
    A second debt is refused — the loop has one way out, not a wall of
    them."""
    budget = load_budget(project)
    if has_debt(budget):
        return False, ("an erosion debt is already open "
                       f"({budget.get('debt_cycle')}, {budget.get('debt_item')}): pay it — "
                       "a second one is refused")
    m = measure(project, int(budget.get("window", DEFAULT_WINDOW)))
    updates = {}
    for bkey, mkey in METRIC_OF.items():
        if bkey in budget and m.get(mkey) is not None and float(m[mkey]) > float(budget[bkey]):
            updates[f"debt_{mkey}"] = m[mkey]
    # the breach the pre-commit refused counts: the debt exists to let that
    # commit through (a client's --debt answered "nothing to owe" while its
    # commit stood blocked, and the agent went to the owner)
    ok, msg = staged_check(project)
    if not ok and "debt_add_delete_ratio" not in updates:
        after = re.search(r"→ ([\d.]+)", msg)
        updates["debt_add_delete_ratio"] = float(after.group(1)) if after else budget.get(
            "max_add_delete_ratio")
    if not updates:
        return False, "no budget is breached, now or by the staged change: nothing to owe"
    updates.update({"debt_cycle": cycle, "debt_item": item, "debt_closes": 0})
    set_erosion_keys(project, updates)
    return True, "debt registered: " + ", ".join(f"{k[5:]} {v}" for k, v in updates.items()
                                                  if k.startswith("debt_") and k[5:] in METRIC_OF.values())


def staged_check(project: Path) -> tuple[bool, str]:
    """Pre-commit, under a second: with the add/delete ratio over its
    (effective) budget, a commit passes only when it does not make the
    ratio worse, or when it is small. A consolidation always passes."""
    declared = load_budget(project)
    budget = effective_budget(declared)
    if "max_add_delete_ratio" not in budget:
        return True, "no add/delete budget declared"
    if "add_delete_ratio" in covered(declared):
        return True, (f"add/delete covered by the open erosion debt "
                      f"({declared.get('debt_item')}) until it falls due")
    window = int(budget.get("window", DEFAULT_WINDOW))
    scope, gen = churn_scope(project), generated_paths(project)
    a0, d0, rows0 = parse_numstat(_git(project, "log", f"-{window}", "--numstat", "--format="),
                                  scope, gen)
    a1, d1, _ = parse_numstat(_git(project, "log", f"-{max(window - 1, 1)}", "--numstat",
                                   "--format="), scope, gen)
    sa, sd, _ = parse_numstat(_git(project, "diff", "--cached", "--numstat"), scope, gen)
    limit = float(budget["max_add_delete_ratio"])
    before = add_delete_ratio(a0, d0) if rows0 else 0.0
    after = add_delete_ratio(a1 + sa, d1 + sd)
    if after <= limit or sa + sd <= SMALL_COMMIT or after <= before:
        return True, f"add/delete {after} (budget {limit})"
    return False, (f"add/delete ratio would go {before} → {after}, over its budget {limit}: "
                   "consolidate (fde-erosion — at most two attempts, then one debt), "
                   "never raise the budget")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--window", type=int, default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--ratchet", action="store_true",
                    help="print an [erosion] budget at today's measured values "
                         "(install and sync write it when none is declared)")
    ap.add_argument("--close", metavar="C-N",
                    help="at a cycle's close: ratchet the budgets, glide to the targets, settle the debt")
    ap.add_argument("--debt", nargs=2, metavar=("C-N", "B-N"),
                    help="after two consolidation attempts: register the one debt")
    ap.add_argument("--staged", action="store_true", help="pre-commit add/delete check")
    args = ap.parse_args()

    project = project_root()
    if args.close:
        r = close_cycle(project, args.close)
        if not r["declared"]:
            print("no [erosion] budget declared — nothing to ratchet")
            return 0
        print(f"erosion at {args.close} close: " + ("; ".join(r["changes"]) or "budgets unchanged")
              + (f"; debt {r['debt']}" if r["debt"] else ""))
        return 0
    if args.debt:
        ok, msg = register_debt(project, *args.debt)
        print(msg)
        return 0 if ok else 1
    if args.staged:
        ok, msg = staged_check(project)
        print(msg)
        return 0 if ok else 1
    budget = load_budget(project)
    window = args.window or int(budget.get("window", DEFAULT_WINDOW))

    if args.gate:
        declared, breaches, unmeasured = gate(project)
        if not declared:
            print("no [erosion] budget declared — trend measured, not gated")
            return 0
        print(verdict(breaches, unmeasured))
        return 1 if breaches else 0

    m = measure(project, window)
    if args.ratchet:
        import fde_lib
        print(fde_lib.erosion_ratchet_toml(m), end="")
        return 0
    if args.format == "json":
        print(json.dumps(m, indent=2))
        return 0

    def fmt(v):
        return "n/a" if v is None else v
    print(f"\nerosion signals (last {window} commits)")
    for line in population_lines(m):
        print(f"  {line}")
    print()
    print(f"  add/delete ratio      {fmt(m['add_delete_ratio'])}   "
          f"(growth by accretion; lower is healthier)")
    print(f"  duplicate-block %     {fmt(m['duplication_pct'])}   "
          f"(the clone ratio the papers measure)")
    print(f"  structural erosion    {fmt(m['structural_erosion'])}   "
          f"(Python: share of complexity mass in the {m['complex_functions']} "
          f"functions with CC > {HIGH_CC}, of {m['python_functions']} distinct; "
          f"human repositories ≈ 0.34)")
    if m.get("unparsed_python"):
        print(f"  ({m['unparsed_python']} Python file(s) did not parse and are "
              "not in the structural measure)")
    print(f"  dependency count      {fmt(m['dependencies'])}")
    print(f"  largest change (lines){fmt(m['largest_change'])}   "
          f"(batch size; large batches carry DORA's instability)")
    print(f"  process-only commits  {fmt(m['process_only_ratio'])}   "
          f"(last {m['window']} commits on HEAD; share touching only "
          f"reviews/, cycles/, promotions/, backlog.md — reported, not gated)")
    if budget:
        breaches, unmeasured = check_budget(m, budget)
        mark = "✗ " if breaches else ("! " if unmeasured else "✓ ")
        print("\n  " + mark + verdict(breaches, unmeasured))
    else:
        print("\n  no [erosion] budget declared — measured, not gated")
    print("\n  deeper signals (other languages' complexity, exact tool metrics)")
    print("  are delegated to your own tools, wired into the eval suite (I1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
