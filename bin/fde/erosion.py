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
from fde_lib import project_root  # noqa: E402

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
def parse_numstat(text: str) -> tuple[int, int]:
    """Sum (added, deleted) from `git log --numstat` output. Binary files
    show '-' and are skipped."""
    added = deleted = 0
    for line in text.splitlines():
        m = re.match(r"^(\d+)\t(\d+)\t", line)
        if m:
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
            if float(metrics[mkey]) > float(budget[bkey]):
                out.append(f"{label} {metrics[mkey]} > budget {budget[bkey]}")
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


def _count_pyproject_deps(text: str) -> int:
    try:
        d = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return 0
    proj = d.get("project", {})
    n = len(proj.get("dependencies", []))
    for group in (proj.get("optional-dependencies", {}) or {}).values():
        n += len(group)
    return n


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


def measure(project: Path, window: int = DEFAULT_WINDOW) -> dict:
    """All stdlib signals. Every one degrades to None when unavailable —
    a repo with no git history, no manifests, or an empty tree never
    crashes the measurement (FM-4)."""
    m: dict = {"window": window}

    log = _git(project, "log", f"-{window}", "--numstat", "--format=")
    if log.strip():
        added, deleted = parse_numstat(log)
        m["added"], m["deleted"] = added, deleted
        m["add_delete_ratio"] = add_delete_ratio(added, deleted)
        m["largest_change"] = _largest_change(project, window)
    else:
        m["add_delete_ratio"] = None
        m["largest_change"] = None

    contents = _tracked_code(project)
    m["duplication_pct"] = duplicate_block_pct(contents) if contents else None
    m["files_scanned"] = len(contents)
    m["dependencies"] = dependency_count(project)
    return m


def _largest_change(project: Path, window: int) -> int | None:
    # %H marks each commit boundary; numstat lines follow it
    out = _git(project, "log", f"-{window}", "--numstat", "--format=%H")
    if not out.strip():
        return None
    biggest, cur = 0, 0
    for line in out.splitlines():
        if re.fullmatch(r"[0-9a-f]{7,40}", line.strip()):
            biggest = max(biggest, cur)
            cur = 0
            continue
        mt = re.match(r"^(\d+)\t(\d+)\t", line)
        if mt:
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
    print(f"\nerosion signals (last {window} commits, {m['files_scanned']} code files)\n")
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
