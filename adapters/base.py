"""
Contrato de adapter.

A camada de INSTRUÇÃO é agnóstica (AGENTS.md + SKILL.md são padrões governados
pela Agentic AI Foundation). A camada de ENFORCEMENT não é, e nunca vai ser:
hook, restrição de ferramenta por papel e isolamento em worktree são
implementação de cada ferramenta, com capacidade desigual.

Por isso o invariante mora no REPOSITÓRIO (pre-commit + CI), não na ferramenta.
O adapter é conveniência: puxa o gate para dentro do loop do agente e dá
feedback mais rápido. Se não existir adapter para a ferramenta, o padrão continua
valendo — só chega mais tarde, no commit em vez de na escrita.

Três tiers, declarados honestamente por `fde doctor`:

  loop      — hook + restrição de ferramenta por papel. Bloqueio antes da escrita.
  commit    — sem hook, mas há subagente/worktree. Papéis reais, gate no git.
  advisory  — só arquivo de instrução. Papéis são convenção, gate é o CI.

Prometer paridade e entregar teatro em três de cinco ferramentas é o que queima
framework aberto. Declarar o tier é honestidade que gera confiança.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TIERS = ("loop", "commit", "advisory")

GEN_MARK = "FDE-KERNEL:GENERATED"


def generated_header(comment: str = "#") -> str:
    lines = [
        f"{GEN_MARK} — não edite à mão.",
        "Fonte da verdade: fde.config.toml + spec/. Regenere com `fde sync`.",
        "Edição manual aqui é sobrescrita e detectada como drift.",
    ]
    if comment == "<!--":
        return "<!--\n" + "\n".join(lines) + "\n-->\n"
    return "".join(f"{comment} {l}\n" for l in lines)


@dataclass
class Capability:
    tool: str
    tier: str
    enforced: list[str] = field(default_factory=list)   # bloqueia de fato
    advisory: list[str] = field(default_factory=list)   # só recomenda
    notes: list[str] = field(default_factory=list)


@dataclass
class EmitContext:
    project: Path
    kernel: Path
    config: dict
    spec: object
    facts: dict
    probe_plan: list


class Adapter:
    tool = "abstract"

    def detect(self, project: Path) -> bool:          # a ferramenta está em uso aqui?
        raise NotImplementedError

    def capability(self) -> Capability:
        raise NotImplementedError

    def emit(self, ctx: EmitContext) -> list[Path]:    # arquivos escritos
        raise NotImplementedError

    # ---- helpers ----
    @staticmethod
    def write(path: Path, content: str, comment: str = "#") -> Path:
        """
        Escreve com marcador de gerado.

        Frontmatter YAML tem que ser a PRIMEIRA coisa do arquivo — cabeçalho antes
        dele quebra o parse e o agente perde name/disallowedTools/isolation.
        Nesse caso o marcador entra depois do bloco de frontmatter.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        header = generated_header(comment)
        if content.startswith("---\n"):
            end = content.find("\n---\n", 4)
            if end != -1:
                cut = end + len("\n---\n")
                content = content[:cut] + "\n" + header + content[cut:]
                path.write_text(content, encoding="utf-8")
                return path
        path.write_text(header + "\n" + content, encoding="utf-8")
        return path
