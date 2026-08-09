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

Honesty note: the role branch fires only when the harness includes a role
identity in the payload (agent_name/subagent). Where it does not, role
scopes are charged later, by the I2/I3 gates at commit — the guard's
always-on protection is the no-suite I1 branch.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULT_BEHAVIOR = ("src/", "lib/", "app/", "services/", "prompts/")
DEFAULT_EVAL = ("evals/", "tests/")

# ALLOWLIST per judging role — mirrors write_scope in spec/roles.toml.
# These roles write ONLY inside their scope; everything else is blocked.
ALLOWED = {
    "fde-spec": ("specs/", "discovery/"),
    "fde-architecture": ("docs/adr/", "specs/"),
    "fde-adversarial": ("reviews/",),
    "fde-promotion": ("promotions/",),
}


def _matches(path: str, entries) -> bool:
    for e in entries:
        e = e.rstrip("/")
        if path == e or path.startswith(e + "/"):
            return True
    return False


def _agent_identity(payload: dict) -> str:
    """Payload identity when the harness sends one; otherwise derive it
    from the worktree the subagent runs in (.claude/worktrees/agent-<id>)
    via the harness metadata (agent-<id>.meta.json, agentType). Absent or
    unreadable metadata degrades to anonymous — never block by accident
    (FWD-005)."""
    agent = payload.get("agent_name") or payload.get("subagent") or ""
    if agent:
        return agent
    cwd = payload.get("cwd") or str(Path.cwd())
    m = re.search(r"\.claude/worktrees/(agent-[0-9a-f]+)", cwd)
    if not m:
        return ""
    meta_root = Path(os.environ.get("FDE_AGENT_META_DIR")
                     or Path.home() / ".claude" / "projects")
    # scoped to THIS project's slug — a global scan could misattribute a
    # same-id agent from another project (review finding, FWD-005)
    slug = str(_project()).replace("/", "-")
    try:
        for meta in meta_root.glob(f"{slug}/*/subagents/{m.group(1)}.meta.json"):
            return json.loads(meta.read_text(encoding="utf-8")).get("agentType") or ""
    except Exception:
        pass
    return ""


def _audit(project: Path, rel: str, agent: str, decision: str, rule: str) -> None:
    """Append to .fde/guard-audit.jsonl. Auditing never affects the
    decision itself (FWD-006)."""
    try:
        d = project / ".fde"
        d.mkdir(exist_ok=True)
        with open(d / "guard-audit.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "path": rel,
                "agent": agent or None,
                "decision": decision,
                "rule": rule,
            }) + "\n")
    except Exception:
        pass


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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # no readable payload, do not block by accident

    path = (payload.get("tool_input", {}) or {}).get("file_path", "")
    agent = _agent_identity(payload)
    if not path:
        return 0

    project = _project()
    gate = _gate(project)
    behavior = tuple(gate.get("behavior_paths") or DEFAULT_BEHAVIOR)
    eval_paths = tuple(gate.get("eval_paths") or DEFAULT_EVAL)

    p = Path(path.split("/./")[-1])
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(project).as_posix()
        except ValueError:
            return 0  # outside the project: not this guard's jurisdiction
    else:
        rel = p.as_posix()

    # a worktree is a full checkout: a write inside .claude/worktrees/
    # agent-<id>/<path> is judged as <path>, else every isolated role is
    # false-blocked from its own handoff artifact (review finding, FWD-005)
    wt = re.match(r"\.claude/worktrees/agent-[0-9a-f]+/(.+)", rel)
    if wt:
        rel = wt.group(1)

    def block(msg: str, rule: str) -> int:
        _audit(project, rel, agent, "block", rule)
        print(msg, file=sys.stderr)
        return 2

    for role, allowed in ALLOWED.items():
        if role in agent and not _matches(rel, allowed):
            return block(
                f"[FDE] role {role} writes only in {', '.join(allowed)} — not {rel}.\n"
                f"This is design, not an obstacle: the role that judges cannot rewrite\n"
                f"what will be judged. Record the finding or delegate to the right role.",
                "role-scope")

    if "fde-implementation" in agent and (
        rel.startswith("reviews/")
        or (rel.startswith("specs/") and rel.endswith("acceptance.md"))
    ):
        return block(
            f"[FDE] role fde-implementation does not write to {rel}: it cannot\n"
            f"rewrite the criteria it will be judged by, nor the findings against it.",
            "implementation-scope")

    if _matches(rel, behavior):
        # .gitkeep is structure, not a suite; a file entry counts if present
        def has_suite(e: str) -> bool:
            d = project / e.rstrip("/")
            if d.is_file():
                return True
            return d.is_dir() and any(
                f.is_file() and f.name != ".gitkeep" for f in d.rglob("*"))
        if not any(has_suite(e) for e in eval_paths):
            return block(
                "[FDE] I1: behavior change before an eval suite exists.\n"
                "Write the failure mode and the evaluator first - the pre-commit will\n"
                "charge for this anyway, and redoing it later costs more.",
                "I1-no-suite")
    if agent.startswith("fde-"):
        # kernel-role allows are signal; anonymous or generic-agent allows
        # are noise (review finding, FWD-006)
        _audit(project, rel, agent, "allow", "in-scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
