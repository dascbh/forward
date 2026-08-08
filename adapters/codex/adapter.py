"""
Codex CLI adapter — `commit` tier.

Deliberate second adapter: it exists to prove the abstraction holds. If it
breaks here, it breaks before a whole catalog gets written on top of it.

Codex reads AGENTS.md natively (global in ~/.codex/AGENTS.md, repo root, and
working directory). Default limit of 32 KiB, silently truncated — which is why
the root AGENTS.md is THIN and points to skills, never carrying the whole
standard.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from base import Adapter, Capability, EmitContext  # noqa: E402

SIZE_LIMIT = 32 * 1024


class CodexAdapter(Adapter):
    tool = "codex"

    def detect(self, project: Path) -> bool:
        return (project / ".codex").exists() or (project / "AGENTS.md").exists()

    def capability(self) -> Capability:
        return Capability(
            tool=self.tool,
            tier="commit",
            enforced=[
                "gate at pre-commit and in CI",
                "handoff by artifact on disk",
            ],
            advisory=[
                "roles (convention via AGENTS.md, no tool restriction)",
                "adversarial isolation (instructed; no guarantee from the tool)",
            ],
            notes=[
                "AGENTS.md truncated at 32 KiB without warning - thin root, detail in skills/",
                "adversarial isolation must be forced by an external worktree: "
                "`fde review --isolate` creates the worktree before invoking the agent",
            ],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written = []
        p = ctx.project

        lines = [
            "## Roles",
            "",
            "This tool does not restrict tools per role. The roles below are",
            "convention - the real enforcement is in the pre-commit and in CI.",
            "",
        ]
        for role in ctx.spec.roles["role"]:
            lines.append(f"### {role['label']} (`fde-{role['id']}`)")
            lines.append(role["purpose"].strip().splitlines()[0])
            lines.append(f"- writes to: {', '.join(role.get('write_scope', []))}")
            if role.get("denied_paths"):
                lines.append(f"- never writes to: {', '.join(role['denied_paths'])}")
            if role.get("isolation"):
                lines.append("- **requires isolation**: run via `fde review --isolate` "
                             "(separate worktree); without it, invariant I2 is not met")
            lines.append("")

        lines += [
            "## Before any commit",
            "",
            "```bash",
            "python bin/fde/verify.py",
            "```",
            "",
            "Detail for each step lives in `skills/` (Agent Skills format, portable).",
        ]

        body = "\n".join(lines)
        out = p / ".codex" / "AGENTS.md"
        written.append(self.write(out, body, comment="<!--"))

        if len(body.encode()) > SIZE_LIMIT:
            print("  ! AGENTS.md exceeds 32 KiB - Codex will silently truncate it")

        return written


ADAPTER = CodexAdapter()
