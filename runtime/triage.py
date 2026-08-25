#!/usr/bin/env python3
"""
triage — RULE, a lane categorically distinct from XS/S/M/L (ADR-0015).

Kahneman, Sibony & Sunstein's *Noise* (2021): a high-volume, low-stakes
decision should become a RULE — a deterministic checker decides, no
judgment applied at all — while deliberate, multi-perspective judgment
stays reserved for what is genuinely risky or novel. `fde-triage`'s
XS/S/M/L table is entirely the judgment kind, at every size, including
its floor (XS still spends a full isolated adversarial round). RULE is
the missing rule-shaped tier beneath it, not a smaller XS: it consumes
none of the score formula's four estimated inputs, and it is computed —
never estimated — after the fact, against one commit's own actual diff.

Eligibility (R1) is FOUR mechanical criteria, all checkable without
judgment:
  (a) [triage].data_class is exactly "public" or "internal" — the two
      values where FWD-003's own ceiling already makes "sensitive"
      unconditionally false project-wide.
  (b) [triage].reversibility is exactly "reversible".
  (c) the commit's own added+deleted is strictly under the declared
      [triage].rule_lane_max_loc (default 10).
  (d) no file matching [gate].eval_paths was deleted or shrunk (deleted
      > added for that file alone) in the commit.
(a) and (b) are resolved ONCE, at the project level — never per file —
because no per-file sensitivity signal exists anywhere in this kernel
(only these two project-level config values); any other declared value
on either axis makes RULE unavailable for every commit in the project,
not just commits that touch risky-looking files.

A commit self-declares RULE by convention (first message line matching
`FORWARD: RULE`); `verify.py`'s `gate_rule_lane` re-verifies every such
claim against what was ACTUALLY committed — the live "surprise/conflict"
monitor *Noise* asks a rule-governed system to keep, made deterministic
and always-on. I1 (`gate_eval_coverage`) is completely unmodified: RULE
recognizes when empirical verification already covers everything there
is to verify, it does not exempt anything from it.

Split mirrors erosion.py: a pure core (no git, no fs — unit-tested
directly) plus git-aware wrappers. Path resolution (quoting, renames)
reuses erosion.numstat_path — MNT-11: one definition, not a second.
Stdlib only (I6).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import Config, gate_paths, path_matches, project_root  # noqa: E402
import erosion  # noqa: E402 — numstat_path reused, MNT-11

DEFAULT_RULE_LANE_MAX_LOC = 10
DEFAULT_WINDOW = 50   # --report's default commit window (implementation's
                      # call, same as erosion.py's own DEFAULT_WINDOW)

# The self-declaration convention (ADR-0015): the commit's first message
# line, and only the first line — a mention deeper in the body does not
# count, matching how `FORWARD: M — ...` is announced once, up top.
RULE_DECLARATION_RE = re.compile(r"^FORWARD:\s*RULE\b")


# ---------------------------------------------------------------------------
# pure core — no git, no fs; unit-tested directly
# ---------------------------------------------------------------------------
@dataclass
class Eligibility:
    eligible: bool
    criterion: str | None   # "data_class" | "reversibility" | "loc" | "eval_paths" | None
    detail: str
    size: int               # added + deleted, always computed, for --report


def check_eligibility(data_class: str, reversibility: str,
                      files: list[tuple[str, int, int]],
                      eval_paths: tuple[str, ...],
                      rule_lane_max_loc: int = DEFAULT_RULE_LANE_MAX_LOC
                      ) -> Eligibility:
    """R1: the pure eligibility core. Inputs are exactly the two already-
    declared project-level config values, one commit's own per-file
    (path, added, deleted) numstat, and the project's declared
    eval_paths — never git, never the filesystem, never the score
    formula's surfaces/loc/sensitive/irreversible estimate.

    Checked in the ADR's own order: the two project-level axes first,
    because a project that never clears them gets no RULE lane at all,
    regardless of any individual commit's size — the same "unsure ->
    true" tiebreak ADR-0009 established at the demand level, applied
    here, once, at the project level.
    """
    dc = str(data_class).strip().lower()
    if dc not in ("public", "internal"):
        return Eligibility(
            False, "data_class",
            f"[triage].data_class = '{data_class}' — RULE requires exactly "
            f"'public' or 'internal' (FWD-003's own ceiling); any other "
            f"value makes RULE unavailable for every commit in this "
            f"project, not only this one", 0)

    rv = str(reversibility).strip().lower()
    if rv != "reversible":
        return Eligibility(
            False, "reversibility",
            f"[triage].reversibility = '{reversibility}' — RULE requires "
            f"exactly 'reversible'; any other value makes RULE unavailable "
            f"for every commit in this project", 0)

    size = sum(a + d for _, a, d in files)
    if size >= rule_lane_max_loc:
        return Eligibility(
            False, "loc",
            f"commit size {size} line(s) (added+deleted) >= the declared "
            f"rule_lane_max_loc {rule_lane_max_loc}", size)

    # (d): a file matching eval_paths whose deletions outstrip its
    # additions — a true deletion (added=0, deleted=N>0) is the N==added
    # special case of this same inequality, so one check covers both
    # halves of R1(d) without a second branch.
    shrunk = sorted({p for p, a, d in files
                     if path_matches(p, eval_paths) and d > a})
    if shrunk:
        return Eligibility(
            False, "eval_paths",
            f"eval_paths file(s) deleted or shrunk (deleted > added): "
            f"{', '.join(shrunk)}", size)

    return Eligibility(
        True, None,
        f"eligible — {size} line(s), data_class/reversibility clear the "
        f"project-level ceiling, eval_paths intact", size)


# ---------------------------------------------------------------------------
# git wrappers
# ---------------------------------------------------------------------------
def _git(project: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=project, capture_output=True,
                           text=True, check=False)
        return r.stdout
    except FileNotFoundError:
        return ""


def _rows(text: str) -> list[tuple[str, int, int]]:
    """Per-file (path, added, deleted) from one numstat text — binary
    rows ('-', '-') skipped, exactly as erosion.parse_numstat skips them.
    Path resolution (quoting, renames) is erosion.numstat_path, reused
    rather than re-implemented (MNT-11)."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", line)
        if not m or m.group(1) == "-" or m.group(2) == "-":
            continue
        out.append((erosion.numstat_path(m.group(3)),
                    int(m.group(1)), int(m.group(2))))
    return out


def commit_files(project: Path, sha: str) -> list[tuple[str, int, int]]:
    """One commit's OWN numstat, never a range's aggregate (FM-8). --root
    diffs a root commit against the empty tree instead of being skipped."""
    return _rows(_git(project, "diff-tree", "--root", "--no-commit-id",
                      "-r", "--numstat", sha))


def staged_files(project: Path) -> list[tuple[str, int, int]]:
    """The currently staged diff — for --check's preview only (R2);
    never used by the gate, which always re-verifies a real commit."""
    return _rows(_git(project, "diff", "--cached", "--numstat"))


def commit_subject(project: Path, sha: str) -> str:
    return _git(project, "log", "-1", "--format=%s", sha).strip()


def declares_rule(subject: str) -> bool:
    return bool(RULE_DECLARATION_RE.match(subject.strip()))


def _max_loc(cfg: Config) -> int:
    raw = cfg.raw.get("triage", {}).get("rule_lane_max_loc",
                                        DEFAULT_RULE_LANE_MAX_LOC)
    try:
        return int(raw)
    except (TypeError, ValueError):
        # a malformed value must not crash the checker — fall back to the
        # documented default rather than disable RULE entirely (Boundaries)
        return DEFAULT_RULE_LANE_MAX_LOC


def eligibility_for_commit(project: Path, sha: str,
                          cfg: Config | None = None) -> Eligibility:
    """The git-aware wrapper R2 asks for: resolves one commit's numstat
    and the project's declared config, then calls the pure core."""
    cfg = cfg or Config.load(project)
    triage_cfg = cfg.raw.get("triage", {}) or {}
    data_class = triage_cfg.get("data_class", "internal")
    reversibility = triage_cfg.get("reversibility", "reversible")
    _, eval_paths = gate_paths(cfg.raw)
    files = commit_files(project, sha)
    return check_eligibility(data_class, reversibility, files, eval_paths,
                             rule_lane_max_loc=_max_loc(cfg))


# ---------------------------------------------------------------------------
# --report: RULE-lane usage over a commit window, never silent (R2)
# ---------------------------------------------------------------------------
def report(project: Path, window: int) -> dict:
    shas = [s for s in _git(project, "log", f"-{window}", "--format=%H")
            .splitlines() if s]
    try:
        cfg = Config.load(project)
    except FileNotFoundError:
        cfg = None

    declared_n = passed = blocked = 0
    sizes: list[int] = []
    blocked_detail: list[dict] = []
    for sha in shas:
        subject = commit_subject(project, sha)
        if not declares_rule(subject):
            continue
        declared_n += 1
        if cfg is None:
            continue
        elig = eligibility_for_commit(project, sha, cfg=cfg)
        sizes.append(elig.size)
        if elig.eligible:
            passed += 1
        else:
            blocked += 1
            blocked_detail.append({"sha": sha[:7], "subject": subject,
                                   "criterion": elig.criterion,
                                   "detail": elig.detail})

    return {
        "window": window,
        "commits_examined": len(shas),
        "declared_rule": declared_n,
        "passed": passed,
        "would_have_blocked": blocked,
        "avg_loc": round(sum(sizes) / len(sizes), 1) if sizes else None,
        "blocked": blocked_detail,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _run_check(project: Path) -> int:
    """--check (R2): a preview against the currently STAGED diff, mirroring
    design.py's own --check shape. Advisory only — nothing consumes this
    exit code automatically; an agent runs it before deciding whether to
    self-declare RULE in the commit message. A wrong guess here costs
    nothing but redoing the demand through the normal table: the actual
    gate (`verify.py --gate rule-lane`) re-verifies the real commit
    regardless of what this said."""
    try:
        cfg = Config.load(project)
    except FileNotFoundError as e:
        print(f"\033[31m✗\033[0m {e}", file=sys.stderr)
        return 1
    triage_cfg = cfg.raw.get("triage", {}) or {}
    data_class = triage_cfg.get("data_class", "internal")
    reversibility = triage_cfg.get("reversibility", "reversible")
    _, eval_paths = gate_paths(cfg.raw)
    files = staged_files(project)
    elig = check_eligibility(data_class, reversibility, files, eval_paths,
                             rule_lane_max_loc=_max_loc(cfg))
    if elig.eligible:
        print(f"\033[32m✓\033[0m RULE-eligible (staged diff): {elig.detail}")
        print("  advisory only: self-declare 'FORWARD: RULE — <one-line "
              "reason>' as the commit's first message line if you proceed. "
              "The rule-lane gate re-verifies against what you actually "
              "commit, not against this preview.")
    else:
        print(f"\033[31m✗\033[0m not RULE-eligible ({elig.criterion}): "
              f"{elig.detail}")
        print("  run this demand through the normal XS/S/M/L table instead.")
    return 0 if elig.eligible else 1


def _run_report(project: Path, window: int, fmt: str) -> int:
    data = report(project, window)
    if fmt == "json":
        print(json.dumps(data, indent=2))
        return 0
    print(f"\nRULE-lane usage (last {data['commits_examined']} commit(s), "
          f"window={window})")
    print(f"  self-declared RULE      {data['declared_rule']}")
    print(f"  passed re-verification  {data['passed']}")
    print(f"  would have been blocked {data['would_have_blocked']}")
    if data["avg_loc"] is not None:
        print(f"  avg size (added+deleted) of declared commits  "
              f"{data['avg_loc']}")
    if data["blocked"]:
        print("\n  near-misses the gate caught:")
        for b in data["blocked"]:
            print(f"    ✗ {b['sha']} {b['subject']!r} — {b['criterion']}: "
                 f"{b['detail']}")
    if not data["declared_rule"]:
        print("  no commit in this window self-declared RULE")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--window", type=int, default=None)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()

    if args.check:
        return _run_check(project)
    if args.report:
        return _run_report(project, args.window or DEFAULT_WINDOW,
                           args.format)

    print("usage: triage.py --check | --report [--window N] [--format json]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
