#!/usr/bin/env python3
"""
guard - hook PreToolUse. Bloqueio ANTES da escrita, nao no commit.

Existe so no tier `loop`. Nas outras ferramentas o mesmo invariante e cobrado
mais tarde, pelo pre-commit. A diferenca e latencia de feedback, nao rigor.

Protocolo: recebe JSON do hook no stdin; exit 0 permite, exit 2 bloqueia com a
mensagem no stderr voltando para o agente.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BEHAVIOR = ("src/", "lib/", "app/", "services/", "prompts/")

# escopo de escrita por papel - espelha spec/roles.toml
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
        return 0  # sem payload legivel, nao bloqueia por acidente

    path = (payload.get("tool_input", {}) or {}).get("file_path", "")
    agent = payload.get("agent_name") or payload.get("subagent") or ""
    rel = path.split("/./")[-1]

    for role, denied in DENIED.items():
        if role in agent and rel.startswith(denied):
            print(
                f"[FDE] papel {role} nao escreve em {rel}.\n"
                f"Isso e desenho, nao obstaculo: o papel que julga nao pode reescrever\n"
                f"o que sera julgado. Registre o achado ou delegue ao papel correto.",
                file=sys.stderr,
            )
            return 2

    if rel.startswith(BEHAVIOR):
        project = HERE.parent.parent if (HERE.parent.parent / "fde.config.toml").exists() else Path.cwd()
        evals = project / "evals"
        if not evals.exists() or not any(evals.rglob("*")):
            print(
                "[FDE] I1: mudanca de comportamento antes de existir suite de eval.\n"
                "Escreva o failure mode e o evaluator primeiro - o pre-commit vai\n"
                "cobrar isso de qualquer forma, e depois custa refazer.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
