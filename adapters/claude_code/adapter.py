"""
Claude Code adapter — `loop` tier, highest fidelity available.

Uses: agents/ with denied_tools and isolation:worktree, PreToolUse hooks for
blocking before the write, CLAUDE.md with @AGENTS.md as the bridge.

AGENTS.md → CLAUDE.md bridge: the `@AGENTS.md` import on the first line is the
recommended option and safe on Windows (symlinks break there). Sources diverge
on whether Claude Code already reads AGENTS.md natively; the import works
either way.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from base import Adapter, Capability, EmitContext  # noqa: E402


class ClaudeCodeAdapter(Adapter):
    tool = "claude-code"

    def detect(self, project: Path) -> bool:
        return (project / "CLAUDE.md").exists() or (project / ".claude").is_dir()

    def capability(self) -> Capability:
        return Capability(
            tool=self.tool,
            tier="loop",
            enforced=[
                "denied_tools per role (agents/ frontmatter)",
                "isolation: worktree on the adversarial role",
                "PreToolUse hook: blocks before the write",
                "gate at pre-commit and in CI",
            ],
            advisory=[
                "adversarial probe order (derived from vector A, instructed via prompt)",
            ],
            notes=[
                "plugin agents do not support hooks/mcpServers/permissionMode "
                "(security restriction) — hooks go at the project level",
                "the only valid isolation value is 'worktree'",
            ],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written: list[Path] = []
        p = ctx.project

        # 1. bridge to the agnostic AGENTS.md
        written.append(self.write(
            p / "CLAUDE.md",
            "@AGENTS.md\n\n"
            "## Claude Code-specific layer\n\n"
            "This project's roles live in `.claude/agents/`. Each one has a write\n"
            "scope restricted by design — if a role cannot edit a path, that is\n"
            "intentional, not an impediment to work around.\n\n"
            "Before any commit: `python bin/fde/verify.py`.\n",
        ))

        # 2. one subagent per role, with real restrictions
        for role in ctx.spec.roles["role"]:
            fm = [
                "---",
                f"name: fde-{role['id']}",
                f"description: {role['label']} — {role['purpose'].strip().splitlines()[0]}",
                "model: inherit",
            ]
            denied = list(role.get("denied_tools", []))
            if denied:
                fm.append(f"disallowedTools: {', '.join(denied)}")
            if role.get("isolation"):
                fm.append(f"isolation: {role.get('isolation_mode', 'worktree')}")
            fm.append("---")

            body = [
                f"# {role['label']}",
                "",
                role["purpose"].strip(),
                "",
                "## Inputs (read these; do not invent context beyond them)",
                *[f"- `{i}`" for i in role.get("inputs", [])],
                "",
                "## Outputs (write only here)",
                *[f"- `{o}`" for o in role.get("outputs", [])],
                "",
                "## Denied paths",
                *[f"- `{d}`" for d in role.get("denied_paths", [])],
                "",
                f"Invariants this role upholds: {', '.join(role.get('satisfies', []))}",
            ]

            if role["id"] == "adversarial":
                body += [
                    "",
                    "## Probe order",
                    "Derived from vector A weights. Do not reorder for convenience.",
                    "",
                ]
                for step in ctx.probe_plan:
                    flag = "BLOCKS MERGE" if step["blocking"] else "records finding"
                    body.append(f"### {step['label']} — weight {step['weight']}, "
                                f"{step['rounds']} round(s) — {flag}")
                    body += [f"- {pr}" for pr in step["probes"]]
                    body.append("")
                body += [
                    "## Rules of conduct",
                    "You received the artifact and the specification. You did NOT receive the",
                    "builder's reasoning — if you feel you need it, that is the finding.",
                    "You do not fix. You record in `reviews/<demand-id>/findings.toml`.",
                    "Your success is measured in failures found, not approvals given.",
                ]

            written.append(self.write(
                p / ".claude" / "agents" / f"fde-{role['id']}.md",
                "\n".join(fm) + "\n\n" + "\n".join(body) + "\n",
                comment="<!--",
            ))

        # 3. blocking hook before the write
        hook = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python bin/fde/guard.py --stdin",
                            }
                        ],
                    }
                ]
            }
        }
        path = p / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(hook, indent=2) + "\n", encoding="utf-8")
        written.append(path)

        return written


ADAPTER = ClaudeCodeAdapter()
