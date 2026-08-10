#!/usr/bin/env python3
"""
survey — checks the brownfield survey, and how stale it has gone.

`discovery/survey.md` is the map a team writes when it takes over a system
nobody documented. Two failure modes are worth a gate: a survey missing
the sections that make it useful, and claims stated without saying how
they were obtained — a confident wrong map gets acted on (FM-1).

The third, staleness, is opt-in: a survey is a snapshot of one commit, and
how far HEAD may move before it misleads is a project judgment, so it is
declared in `[survey] max_drift_commits` like every other threshold.

Pure stdlib.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import project_root  # noqa: E402

SURVEY_PATH = Path("discovery") / "survey.md"
REQUIRED_SECTIONS = ("how it runs", "shape", "history", "seams",
                     "undocumented decisions", "risk", "unknown")
LABELS = ("[observed]", "[inferred]", "[to confirm]")
COMMIT_RE = re.compile(r"^\s*commit\s*:\s*([0-9a-f]{7,40})", re.I | re.M)
DATE_RE = re.compile(r"^\s*date\s*:\s*(\d{4}-\d{2}-\d{2})", re.I | re.M)


def sections(text: str) -> set:
    """`## ` headings, lowercased — the survey's own table of contents."""
    return {m.group(1).strip().lower()
            for m in re.finditer(r"^##\s+(.+?)\s*$", text, re.M)}


def missing_sections(text: str) -> list:
    have = sections(text)
    return [s for s in REQUIRED_SECTIONS
            if not any(s in h for h in have)]


def unlabeled_claims(text: str) -> list:
    """Claim lines carrying no evidence label. A claim is a bullet inside
    a section — headings, code fences and the header block are not claims."""
    out, in_fence, current = [], False, ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if s.startswith("## "):
            current = s[3:].strip().lower()
            continue
        if not any(current.startswith(r.split()[0]) or r in current
                   for r in REQUIRED_SECTIONS):
            continue
        if not s.startswith(("- ", "* ", "+ ")):
            continue
        if len(s) < 12:                      # a stub, not a claim
            continue
        if not any(lab in s.lower() for lab in LABELS):
            out.append(f"{current}: {s[:70]}")
    return out


def drift(project: Path, commit: str) -> int | None:
    """Commits between the surveyed commit and HEAD. None when git or the
    commit is unavailable — an unresolvable commit is reported separately."""
    try:
        r = subprocess.run(["git", "rev-list", "--count", f"{commit}..HEAD"],
                           cwd=project, capture_output=True, text=True)
        return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    except (FileNotFoundError, ValueError):
        return None


def budget(project: Path) -> dict:
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return {}
    try:
        return tomllib.loads(cfg.read_text(encoding="utf-8")).get("survey", {}) or {}
    except tomllib.TOMLDecodeError:
        return {}


def check(project: Path) -> tuple[bool, list]:
    """(present, breaches). A project with no survey is not in breach —
    the survey is owed by brownfield demands, and that is a loop rule,
    not a gate (a greenfield project owes nothing)."""
    path = project / SURVEY_PATH
    if not path.is_file():
        return False, []
    text = path.read_text(encoding="utf-8", errors="ignore")
    out = []
    miss = missing_sections(text)
    if miss:
        out.append(f"survey missing section(s): {', '.join(miss)}")
    unlabeled = unlabeled_claims(text)
    if unlabeled:
        out.append(f"{len(unlabeled)} claim(s) with no evidence label "
                   f"([observed]/[inferred]/[to confirm]) — e.g. {unlabeled[0]}")
    m = COMMIT_RE.search(text)
    if not m:
        out.append("survey records no `commit:` — a snapshot with no anchor "
                   "cannot be told from a current map")
    if not DATE_RE.search(text):
        out.append("survey records no `date:`")
    if m:
        limit = budget(project).get("max_drift_commits")
        d = drift(project, m.group(1))
        if d is None:
            out.append(f"survey's commit {m.group(1)[:7]} does not resolve in "
                       f"this repository")
        elif limit is not None and d > int(limit):
            out.append(f"survey is {d} commits behind HEAD (budget "
                       f"{limit}) — re-survey rather than patch a stale map")
    return True, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    project = project_root()
    present, breaches = check(project)
    if not present:
        print("no discovery/survey.md — nothing to check")
        return 0
    print("\n".join(f"  ✗ {b}" for b in breaches) if breaches
          else "survey complete, every claim labeled, anchor recorded")
    return 1 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
