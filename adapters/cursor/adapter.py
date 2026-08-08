"""
Adapter Cursor - tier `commit`.

Cursor le AGENTS.md e CLAUDE.md na raiz e aplica como regra ao lado de
.cursor/rules. Emitimos MDC apenas para escopo por glob, que e o que o AGENTS.md
nao faz - o resto vem do arquivo agnostico, sem duplicacao.
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
            enforced=["gate no pre-commit e no CI"],
            advisory=["papeis por escopo de glob (MDC)", "isolamento adversarial"],
            notes=["regra MDC ativa por glob - usada so para escopo, nao para duplicar padrao"],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written = []
        p = ctx.project
        rule = (
            "---\n"
            "description: Gate de eval do FDE kernel (I1)\n"
            "globs: src/**\n"
            "alwaysApply: false\n"
            "---\n\n"
            "Mudanca de comportamento em `src/` exige entrada correspondente em `evals/`\n"
            "na mesma mudanca. O pre-commit bloqueia se faltar - escrever o eval depois\n"
            "significa refazer o trabalho.\n\n"
            "Criterio de aceite: `specs/<demand-id>/acceptance.md`.\n"
        )
        written.append(self.write(p / ".cursor" / "rules" / "fde-eval-gate.mdc", rule, comment="<!--"))
        return written


ADAPTER = CursorAdapter()
