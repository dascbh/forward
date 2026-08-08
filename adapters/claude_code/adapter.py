"""
Adapter Claude Code — tier `loop`, maior fidelidade disponível.

Usa: agents/ com denied_tools e isolation:worktree, hooks PreToolUse para
bloqueio antes da escrita, CLAUDE.md com @AGENTS.md como ponte.

Ponte AGENTS.md → CLAUDE.md: o import `@AGENTS.md` na primeira linha é a opção
recomendada e segura no Windows (symlink quebra lá). Fontes divergem sobre se o
Claude Code já lê AGENTS.md nativamente; o import funciona nos dois casos.
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
                "denied_tools por papel (agents/ frontmatter)",
                "isolation: worktree no papel adversarial",
                "PreToolUse hook: bloqueio antes da escrita",
                "gate no pre-commit e no CI",
            ],
            advisory=[
                "ordem de sondagem do adversarial (derivada do vetor A, instruída via prompt)",
            ],
            notes=[
                "agentes de plugin não suportam hooks/mcpServers/permissionMode "
                "(restrição de segurança) — hooks vão no nível de projeto",
                "único valor válido de isolation é 'worktree'",
            ],
        )

    def emit(self, ctx: EmitContext) -> list[Path]:
        written: list[Path] = []
        p = ctx.project

        # 1. ponte para o AGENTS.md agnóstico
        written.append(self.write(
            p / "CLAUDE.md",
            "@AGENTS.md\n\n"
            "## Camada específica do Claude Code\n\n"
            "Os papéis deste projeto estão em `.claude/agents/`. Cada um tem escopo de\n"
            "escrita restrito por design — se um papel não consegue editar um caminho,\n"
            "isso é intencional, não impedimento a contornar.\n\n"
            "Antes de qualquer commit: `python bin/fde/verify.py`.\n",
        ))

        # 2. um subagente por papel, com restrição real
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
                "## Entradas (leia; não invente contexto fora daqui)",
                *[f"- `{i}`" for i in role.get("inputs", [])],
                "",
                "## Saídas (escreva só aqui)",
                *[f"- `{o}`" for o in role.get("outputs", [])],
                "",
                "## Caminhos negados",
                *[f"- `{d}`" for d in role.get("denied_paths", [])],
                "",
                f"Invariantes que este papel sustenta: {', '.join(role.get('satisfies', []))}",
            ]

            if role["id"] == "adversarial":
                body += [
                    "",
                    "## Ordem de sondagem",
                    "Derivada dos pesos do vetor A. Não reordene por conveniência.",
                    "",
                ]
                for step in ctx.probe_plan:
                    flag = "TRAVA MERGE" if step["blocking"] else "registra achado"
                    body.append(f"### {step['label']} — peso {step['weight']}, "
                                f"{step['rounds']} rodada(s) — {flag}")
                    body += [f"- {pr}" for pr in step["probes"]]
                    body.append("")
                body += [
                    "## Regra de conduta",
                    "Você recebeu artefato e especificação. Você NÃO recebeu o raciocínio de",
                    "quem construiu — se achar que precisa dele, isso é o achado.",
                    "Você não corrige. Registra em `reviews/<demand-id>/findings.toml`.",
                    "Seu sucesso é medido em falhas encontradas, não em aprovações dadas.",
                ]

            written.append(self.write(
                p / ".claude" / "agents" / f"fde-{role['id']}.md",
                "\n".join(fm) + "\n\n" + "\n".join(body) + "\n",
                comment="<!--",
            ))

        # 3. hook de bloqueio antes da escrita
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
