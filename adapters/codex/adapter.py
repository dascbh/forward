"""
Adapter Codex CLI — tier `commit`.

Segundo adapter deliberado: existe para provar que a abstração aguenta. Se ela
quebra aqui, quebra antes de haver catálogo inteiro escrito em cima dela.

Codex lê AGENTS.md nativamente (global em ~/.codex/AGENTS.md, raiz do repo e
diretório de trabalho). Limite default de 32 KiB, truncado em silêncio — por isso
o AGENTS.md raiz é FINO e aponta para skills, nunca carrega o padrão inteiro.
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
                "gate no pre-commit e no CI",
                "handoff por artefato em disco",
            ],
            advisory=[
                "papeis (convencao via AGENTS.md, sem restricao de ferramenta)",
                "isolamento adversarial (instruido; sem garantia da ferramenta)",
            ],
            notes=[
                "AGENTS.md truncado em 32 KiB sem aviso - raiz fina, detalhe em skills/",
                "isolamento adversarial precisa ser forcado por worktree externa: "
                "`fde review --isolate` cria a worktree antes de invocar o agente",
            ],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written = []
        p = ctx.project

        lines = [
            "## Papeis",
            "",
            "Esta ferramenta nao restringe ferramenta por papel. Os papeis abaixo sao",
            "convencao - o enforcement real esta no pre-commit e no CI.",
            "",
        ]
        for role in ctx.spec.roles["role"]:
            lines.append(f"### {role['label']} (`fde-{role['id']}`)")
            lines.append(role["purpose"].strip().splitlines()[0])
            lines.append(f"- escreve em: {', '.join(role.get('write_scope', []))}")
            if role.get("denied_paths"):
                lines.append(f"- nunca escreve em: {', '.join(role['denied_paths'])}")
            if role.get("isolation"):
                lines.append("- **exige isolamento**: rode via `fde review --isolate` "
                             "(worktree separada); sem isso o invariante I2 nao e atendido")
            lines.append("")

        lines += [
            "## Antes de qualquer commit",
            "",
            "```bash",
            "python bin/fde/verify.py",
            "```",
            "",
            "Detalhe de cada etapa esta em `skills/` (formato Agent Skills, portatil).",
        ]

        body = "\n".join(lines)
        out = p / ".codex" / "AGENTS.md"
        written.append(self.write(out, body, comment="<!--"))

        if len(body.encode()) > SIZE_LIMIT:
            print("  ! AGENTS.md excede 32 KiB - sera truncado em silencio pelo Codex")

        return written


ADAPTER = CodexAdapter()
