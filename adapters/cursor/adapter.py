"""
Cursor adapter - `commit` tier.

Cursor reads AGENTS.md and CLAUDE.md at the root and applies them as rules
alongside .cursor/rules. We emit MDC only for glob scoping, which is what
AGENTS.md does not do - the rest comes from the agnostic file, no duplication.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from base import Adapter, Capability, EmitContext  # noqa: E402


class CursorAdapter(Adapter):
    tool = "cursor"

    def detect(self, project: Path) -> bool:
        return (project / ".cursor").is_dir() or (project / ".cursorrules").exists()

    def capability(self) -> Capability:
        return Capability(
            tool=self.tool,
            tier="commit",
            enforced=["gate at pre-commit and in CI"],
            advisory=["roles scoped by glob (MDC)", "adversarial isolation"],
            notes=["MDC rule activates by glob - used only for scoping, not to duplicate the standard"],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written = []
        p = ctx.project
        rule = (
            "---\n"
            "description: FDE kernel eval gate (I1)\n"
            "globs: src/**\n"
            "alwaysApply: false\n"
            "---\n\n"
            "A behavior change in `src/` requires a corresponding entry in `evals/`\n"
            "within the same change. The pre-commit blocks if it is missing - writing\n"
            "the eval afterwards means redoing the work.\n\n"
            "Acceptance criteria: `specs/<demand-id>/acceptance.md`.\n"
        )
        written.append(self.write(p / ".cursor" / "rules" / "fde-eval-gate.mdc", rule, comment="<!--"))
        return written


ADAPTER = CursorAdapter()
