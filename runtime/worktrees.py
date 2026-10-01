#!/usr/bin/env python3
"""
worktrees — remove the worktrees whose work is already on main, by one
fixed command (owner, 2026-10-01).

A worktree left inside the repository is a full copy every tool walking
the root sweeps up (one client's CDK asset copied ~95 of them into an
11 GB cdk.out). Removing them with `rm -rf` or a forced `git worktree
remove`, an agent hit auto mode's "irreversible local destruction" and
asked the owner to leave auto mode. This removes only what cannot lose
work: a worktree whose HEAD is contained in the main branch and that has
no uncommitted or untracked change — `git worktree remove` without
`--force` (git itself refuses a dirty one), then its branch with `-d`
(git refuses an unmerged one), then `git worktree prune`. Anything else
is listed and kept. `--check` lists without removing. stdlib only (I6).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import project_root  # noqa: E402


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def main_branch(project: Path) -> str:
    for name in ("main", "master"):
        if git(project, "rev-parse", "--verify", "-q", name).returncode == 0:
            return name
    return "HEAD"


def worktrees(project: Path) -> list[dict]:
    out = git(project, "worktree", "list", "--porcelain").stdout
    rows, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line.strip():
            if cur:
                rows.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val or True
    return rows[1:]  # the first is the main checkout itself


def plan(project: Path) -> tuple[list[dict], list[tuple[dict, str]]]:
    """(removable, kept with why)."""
    base = main_branch(project)
    remove, keep = [], []
    for w in worktrees(project):
        path = Path(w["worktree"])
        if w.get("locked"):
            keep.append((w, "locked"))
            continue
        if not path.is_dir():
            keep.append((w, "missing — pruned"))
            continue
        head = w.get("HEAD", "")
        if git(project, "merge-base", "--is-ancestor", head, base).returncode != 0:
            keep.append((w, f"has commits not on {base}"))
            continue
        if git(path, "status", "--porcelain").stdout.strip():
            keep.append((w, "uncommitted or untracked changes"))
            continue
        remove.append(w)
    return remove, keep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="remove the worktrees already merged into main")
    ap.add_argument("--prune-merged", action="store_true", help="remove them (default: list)")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    project = Path(args.root).resolve() if args.root else project_root()
    remove, keep = plan(project)
    done = []
    if args.prune_merged:
        for w in remove:
            if git(project, "worktree", "remove", w["worktree"]).returncode == 0:
                branch = str(w.get("branch", "")).removeprefix("refs/heads/")
                if branch:
                    git(project, "branch", "-d", branch)
                done.append(w["worktree"])
            else:
                keep.append((w, "git refused to remove it"))
        git(project, "worktree", "prune")
    verb = "removed" if args.prune_merged else "removable"
    listed = done if args.prune_merged else [w["worktree"] for w in remove]
    print(f"worktrees: {len(listed)} {verb}, {len(keep)} kept")
    for w, why in keep:
        print(f"  kept {w['worktree']} — {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
