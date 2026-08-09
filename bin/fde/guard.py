#!/usr/bin/env python3
"""
guard - PreToolUse hook. Blocks BEFORE the write, not at commit.

Exists only in the `loop` tier. In the other tools the same invariant is
charged later, by the pre-commit. The difference is feedback latency, not
rigor.

Protocol: receives the hook's JSON on stdin; exit 0 allows, exit 2 blocks
with the stderr message going back to the agent.

Hooks deliver ABSOLUTE file paths; gate paths and role scopes are
repo-relative. Everything is normalized against the project root before
matching — without that, no prefix ever matches and the guard is theater.
"""
from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT_BEHAVIOR = ("src/", "lib/", "app/", "services/", "prompts/")
DEFAULT_EVAL = ("evals/", "tests/")

# write scope per role - mirrors spec/roles.toml
DENIED = {
    "fde-spec": ("src/", "tests/", "infra/"),
    "fde-architecture": ("src/", "tests/"),
    "fde-adversarial": ("src/", "tests/", "evals/", "specs/", "infra/"),
    "fde-promotion": ("src/", "tests/", "evals/", "specs/", "reviews/"),
    "fde-implementation": ("reviews/",),
}

# roles that must never write production code, wherever [gate] says it lives
CODE_DENIED = ("fde-spec", "fde-architecture", "fde-adversarial", "fde-promotion")


def _project() -> Path:
    for cand in [HERE.parent.parent, Path.cwd(), *Path.cwd().parents]:
        if (cand / "fde.config.toml").exists():
            return cand
    return Path.cwd()


def _gate(project: Path) -> dict:
    try:
        with open(project / "fde.config.toml", "rb") as fh:
            return tomllib.load(fh).get("gate", {}) or {}
    except Exception:
        return {}


def _prefixes(items, default: tuple) -> tuple:
    if not items:
        return default
    return tuple(p if p.endswith("/") else p + "/" for p in items)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # no readable payload, do not block by accident

    path = (payload.get("tool_input", {}) or {}).get("file_path", "")
    agent = payload.get("agent_name") or payload.get("subagent") or ""
    if not path:
        return 0

    project = _project()
    gate = _gate(project)
    behavior = _prefixes(gate.get("behavior_paths"), DEFAULT_BEHAVIOR)
    eval_paths = _prefixes(gate.get("eval_paths"), DEFAULT_EVAL)

    p = Path(path.split("/./")[-1])
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(project).as_posix()
        except ValueError:
            return 0  # outside the project: not this guard's jurisdiction
    else:
        rel = p.as_posix()

    for role, denied in DENIED.items():
        if role in agent and (
            rel.startswith(denied)
            or (role in CODE_DENIED and rel.startswith(behavior))
        ):
            print(
                f"[FDE] role {role} does not write to {rel}.\n"
                f"This is design, not an obstacle: the role that judges cannot rewrite\n"
                f"what will be judged. Record the finding or delegate to the right role.",
                file=sys.stderr,
            )
            return 2

    if rel.startswith(behavior):
        # .gitkeep is structure, not a suite
        has_suite = any(
            (project / e).exists()
            and any(f.is_file() and f.name != ".gitkeep" for f in (project / e).rglob("*"))
            for e in eval_paths
        )
        if not has_suite:
            print(
                "[FDE] I1: behavior change before an eval suite exists.\n"
                "Write the failure mode and the evaluator first - the pre-commit will\n"
                "charge for this anyway, and redoing it later costs more.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
