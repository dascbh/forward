#!/usr/bin/env python3
"""
guard - PreToolUse hook. Blocks BEFORE the write, not at commit.

Exists only in the `loop` tier. In the other tools the same invariant is
charged later, by the pre-commit. The difference is feedback latency, not
rigor.

Protocol: receives the hook's JSON on stdin; exit 0 allows, exit 2 blocks
with the stderr message going back to the agent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BEHAVIOR = ("src/", "lib/", "app/", "services/", "prompts/")

# write scope per role - mirrors spec/roles.toml
DENIED = {
    "fde-spec": ("src/", "tests/", "infra/"),
    "fde-architecture": ("src/", "tests/"),
    "fde-adversarial": ("src/", "tests/", "evals/", "specs/", "infra/"),
    "fde-promotion": ("src/", "tests/", "evals/", "specs/", "reviews/"),
    "fde-implementation": ("reviews/",),
}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # no readable payload, do not block by accident

    path = (payload.get("tool_input", {}) or {}).get("file_path", "")
    agent = payload.get("agent_name") or payload.get("subagent") or ""
    rel = path.split("/./")[-1]

    for role, denied in DENIED.items():
        if role in agent and rel.startswith(denied):
            print(
                f"[FDE] role {role} does not write to {rel}.\n"
                f"This is design, not an obstacle: the role that judges cannot rewrite\n"
                f"what will be judged. Record the finding or delegate to the right role.",
                file=sys.stderr,
            )
            return 2

    if rel.startswith(BEHAVIOR):
        project = HERE.parent.parent if (HERE.parent.parent / "fde.config.toml").exists() else Path.cwd()
        evals = project / "evals"
        if not evals.exists() or not any(evals.rglob("*")):
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
