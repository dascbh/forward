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
dependency count, large-change rate. Deeper metrics (exact cyclomatic
complexity, the structural-erosion measure) are delegated to the client's
tools, as I1 delegates the eval framework — the kernel keeps I6.

Thresholds are project-specific, so they are DECLARED in `[erosion]`
(I4 pattern), never hardcoded: the gate enforces the declared budget and
is silent when undeclared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    return re.split(r"[<>=!~;\[\s]", spec.strip(), 1)[0].lower()


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
        return True
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
    m["churn_scope"] = ", ".join(scope) if scope else "everything tracked"

    contents, excluded = _tracked_code(project, scope, gen)
    m["duplication_pct"] = duplicate_block_pct(contents) if contents else None
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
    budget = load_budget(project)
    if not budget:
        return False, [], []
    window = int(budget.get("window", DEFAULT_WINDOW))
    m = measure(project, window)
    breaches, unmeasured = check_budget(m, budget)
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
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--window", type=int, default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()
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
    print(f"  dependency count      {fmt(m['dependencies'])}")
    print(f"  largest change (lines){fmt(m['largest_change'])}   "
          f"(batch size; large batches carry DORA's instability)")
    if budget:
        breaches, unmeasured = check_budget(m, budget)
        mark = "✗ " if breaches else ("! " if unmeasured else "✓ ")
        print("\n  " + mark + verdict(breaches, unmeasured))
    else:
        print("\n  no [erosion] budget declared — measured, not gated")
    print("\n  deeper signals (exact cyclomatic complexity, structural erosion)")
    print("  are delegated to your own tools, wired into the eval suite (I1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
