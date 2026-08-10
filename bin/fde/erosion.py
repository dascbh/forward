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
# generated mirrors (FORWARD's own installed copies) and vendor trees are
# not the project's organic code — a drift-checked mirror is expected
# duplication, not erosion. Excluded from the code scan.
EXCLUDED_PREFIXES = ("bin/fde/", ".fde/", ".claude/", "node_modules/",
                     ".venv/", "venv/", "vendor/", "dist/", "build/",
                     ".git/", "__pycache__/")
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
def parse_numstat(text: str, scope: tuple | None = None) -> tuple[int, int]:
    """Sum (added, deleted) from `git log --numstat`. Binary files show
    '-' and are skipped. `scope` is the declared churn scope; paths
    outside it are not counted (FWD-016)."""
    added = deleted = 0
    for line in text.splitlines():
        m = re.match(r"^(\d+)\t(\d+)\t(.+)$", line)
        if m and in_churn_scope(m.group(3).strip(), scope):
            added += int(m.group(1))
            deleted += int(m.group(2))
    return added, deleted


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


def check_budget(metrics: dict, budget: dict) -> list:
    """Compare measured metrics against DECLARED thresholds only. An
    undeclared key is not checked — silence, never a false wall."""
    out = []
    checks = [
        ("max_add_delete_ratio", "add_delete_ratio", "add/delete ratio"),
        ("max_duplication_pct", "duplication_pct", "duplicate-block %"),
        ("max_dependencies", "dependencies", "dependency count"),
        ("max_change_lines", "largest_change", "largest change (lines)"),
    ]
    for bkey, mkey, label in checks:
        if bkey in budget and metrics.get(mkey) is not None:
            # a non-numeric budget is a config error (caught by the config
            # gate); here it must never crash --report — skip it
            try:
                if float(metrics[mkey]) > float(budget[bkey]):
                    out.append(f"{label} {metrics[mkey]} > budget {budget[bkey]}")
            except (TypeError, ValueError):
                continue
    return out


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


def _tracked_code(project: Path) -> dict:
    out = {}
    for name in _git(project, "ls-files").splitlines():
        if name.startswith(EXCLUDED_PREFIXES):
            continue
        p = project / name
        if p.suffix.lower() in CODE_SUFFIXES and p.is_file():
            try:
                out[name] = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
    return out


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


def churn_scope(project: Path) -> tuple | None:
    """The paths churn is measured over: the roots the project ALREADY
    declared for I1 (`[gate] behavior_paths` + `eval_paths`), minus the
    generated mirrors. Not a scope invented for this metric — decay is
    measured where the project said its behavior lives. Artifacts
    (reviews, specs, sprints, promotions) are outside it by construction:
    an append-only audit trail that never shrinks is the record, not
    accretion. None when no config declares them."""
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return None
    try:
        raw = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    bp, ep = gate_paths(raw)
    return tuple(bp) + tuple(ep)


def in_churn_scope(path: str, scope: tuple | None) -> bool:
    if path.startswith(EXCLUDED_PREFIXES):
        return False           # generated mirrors are not organic growth
    if scope is None:
        return True            # no declaration: measure everything tracked
    return path_matches(path, scope)


def measure(project: Path, window: int = DEFAULT_WINDOW) -> dict:
    """All stdlib signals. Duplication is measured over tracked code
    files; churn (add/delete, largest change) over the declared behavior
    and eval roots. Both exclude the generated mirrors, so the two agree
    about what is organic. Every metric degrades to None when
    unavailable — no git history, no manifests, empty tree — instead of
    crashing.
    """
    m: dict = {"window": window}

    contents = _tracked_code(project)
    m["duplication_pct"] = duplicate_block_pct(contents) if contents else None
    m["files_scanned"] = len(contents)

    scope = churn_scope(project)
    m["churn_scope"] = ", ".join(scope) if scope else "everything tracked"

    log = _git(project, "log", f"-{window}", "--numstat", "--format=")
    if log.strip():
        added, deleted = parse_numstat(log, scope)
        m["added"], m["deleted"] = added, deleted
        m["add_delete_ratio"] = (add_delete_ratio(added, deleted)
                                 if (added or deleted) else None)
        m["largest_change"] = _largest_change(project, window, scope)
    else:
        m["add_delete_ratio"] = None
        m["largest_change"] = None

    m["dependencies"] = dependency_count(project)
    return m


def _largest_change(project: Path, window: int,
                    scope: tuple | None = None) -> int | None:
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
        if mt and in_churn_scope(mt.group(3).strip(), scope):
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


def gate(project: Path) -> tuple[bool, list]:
    """Return (declared, breaches). declared=False means [erosion] is
    absent — the gate stays silent (never a false wall). declared=True
    with an empty list means within budget."""
    budget = load_budget(project)
    if not budget:
        return False, []
    window = int(budget.get("window", DEFAULT_WINDOW))
    return True, check_budget(measure(project, window), budget)


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
        declared, breaches = gate(project)
        if not declared:
            print("no [erosion] budget declared — trend measured, not gated")
            return 0
        print("within the declared erosion budget" if not breaches
              else "; ".join(breaches))
        return 1 if breaches else 0

    m = measure(project, window)
    if args.format == "json":
        print(json.dumps(m, indent=2))
        return 0

    def fmt(v):
        return "n/a" if v is None else v
    print(f"\nerosion signals (last {window} commits)")
    print(f"  duplication over {m['files_scanned']} code files; churn over "
          f"the declared roots: {m['churn_scope']}")
    print(f"  (generated mirrors and the audit trail are outside both)\n")
    print(f"  add/delete ratio      {fmt(m['add_delete_ratio'])}   "
          f"(growth by accretion; lower is healthier)")
    print(f"  duplicate-block %     {fmt(m['duplication_pct'])}   "
          f"(the clone ratio the papers measure)")
    print(f"  dependency count      {fmt(m['dependencies'])}")
    print(f"  largest change (lines){fmt(m['largest_change'])}   "
          f"(batch size; large batches carry DORA's instability)")
    if budget:
        breaches = check_budget(m, budget)
        print("\n  " + ("✓ within the declared [erosion] budget" if not breaches
                        else "✗ " + "; ".join(breaches)))
    else:
        print("\n  no [erosion] budget declared — measured, not gated")
    print("\n  deeper signals (exact cyclomatic complexity, structural erosion)")
    print("  are delegated to your own tools, wired into the eval suite (I1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
