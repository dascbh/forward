#!/usr/bin/env python3
"""
init - detecta a stack, entrevista SO o que a deteccao nao resolveu, escreve o
declarativo e compila.

Regras que este comando respeita:
  - stack: detectar, nunca perguntar. Confirmacao em bloco unico, nao pergunta a item.
  - projeto: entrevista uma vez, resultado versionado no repo.
  - desenvolvedor: nao existe como categoria. Preferencia e peso, e peso e do projeto.
  - modo nao-interativo por flags/env: roda em CI sem humano.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detect_stack import derive_depths, detect  # noqa: E402
from fde_lib import Spec, ok, project_root, warn  # noqa: E402

DATA_CLASSES = ["publico", "interno", "pessoal", "financeiro", "saude"]
REVERSIBILITY = ["reversivel", "dificil", "irreversivel"]

# alocacao default do vetor A: soma 100, respeita todos os pisos.
# NAO e recomendacao neutra - e ponto de partida que o cliente move.
DEFAULT_WEIGHTS = {
    "functional_correctness": 26,
    "security_privacy": 14,
    "reliability_resilience": 12,
    "observability": 12,
    "maintainability": 12,
    "performance_scale": 9,
    "usability_accessibility": 8,
    "operational_cost": 7,
}


def ask(prompt: str, options: list[str], default: str, interactive: bool) -> str:
    if not interactive:
        return default
    print(f"\n{prompt}")
    for i, o in enumerate(options, 1):
        mark = " (default)" if o == default else ""
        print(f"  {i}. {o}{mark}")
    raw = input("> ").strip()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw if raw in options else default


def toml_table(name: str, data: dict) -> str:
    lines = [f"[{name}]"]
    for k, v in data.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        elif isinstance(v, list):
            lines.append(f"{k} = {json.dumps(v)}")
        else:
            lines.append(f'{k} = "{v}"')
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--yes", action="store_true", help="nao-interativo (CI)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--data-class", choices=DATA_CLASSES, default=None)
    ap.add_argument("--reversibility", choices=REVERSIBILITY, default=None)
    args = ap.parse_args()

    project = project_root(Path(args.project) if args.project else None)
    interactive = not args.yes
    spec = Spec.load(HERE.parent)

    print(f"\nprojeto: {project}")
    facts = detect(project)

    # confirmacao em BLOCO - nao pergunta a item
    print("\ndetectado (confirme em bloco, nao item a item):")
    for k in ["languages", "test_runners", "has_frontend", "has_database",
              "exposes_api", "has_ci", "has_iac", "embeds_model", "agent_tools"]:
        print(f"  {k:16} {facts[k]}")
    if interactive:
        if input("\ncorreto? [S/n] ").strip().lower().startswith("n"):
            warn("ajuste os arquivos do repo ou edite fde.config.toml depois; seguindo.")

    # so o que a deteccao nao resolve
    answers = {
        "data_class": args.data_class or ask(
            "Classe do dado mais sensivel que este sistema toca:",
            DATA_CLASSES, "interno", interactive),
        "reversibility": args.reversibility or ask(
            "Reversibilidade de um erro em producao:",
            REVERSIBILITY, "reversivel", interactive),
        "user_facing": facts["has_frontend"],
        "has_agent_loop": facts["embeds_model"],
    }

    derived = derive_depths(facts, answers)

    body = [
        "# fde.config.toml - declarativo unico do projeto.",
        "# Versionado. Diff auditavel. Recompilavel com `fde sync`.",
        "#",
        "# NAO existe aqui chave para desligar invariante. Invariantes estao em",
        "# .fde/spec/invariants.toml e nao tem chave. Peso move rigor para cima ou",
        "# redistribui enfase; nunca desce abaixo do piso.",
        "",
        toml_table("project", {"name": args.name or project.name,
                               "kernel_version": spec.invariants["meta"]["kernel_version"]}),
        "",
        toml_table("triage", answers),
        "",
        toml_table("stack", {
            "languages": facts["languages"],
            "test_runners": facts["test_runners"],
            "test_command": "pytest -q" if "pytest" in facts["test_runners"] else "make test",
            "eval_command": "python bin/fde/verify.py --gate eval",
        }),
        "",
        "# ---------------------------------------------------------------------------",
        "# VETOR A - atributos de qualidade. Orcamento FECHADO: soma = 100.",
        "# Isto e o que o cliente aloca e assina. Registro datado do que ele disse",
        "# que importava - e a ordem em que o adversarial vai atacar.",
        "# ---------------------------------------------------------------------------",
        toml_table("weights", DEFAULT_WEIGHTS),
        "",
        "# ---------------------------------------------------------------------------",
        "# VETOR B - dominios tecnicos. DERIVADO da stack + triagem.",
        "# Override em [depths] e upward-only: voce eleva, nunca reduz.",
        "# ---------------------------------------------------------------------------",
        toml_table("derived.depths", derived),
        "",
        "[depths]",
        "# ex.: data_modeling = 3   (permitido: >= derivado)",
        "",
        "[tooling]",
        'force = []   # ex.: ["cursor"] para emitir adapter nao detectado',
    ]

    out = project / "fde.config.toml"
    if out.exists():
        warn(f"{out.name} ja existe - nao sobrescrito. Use `fde sync` para recompilar.")
    else:
        out.write_text("\n".join(body) + "\n", encoding="utf-8")
        ok(f"escrito {out.name} (soma dos pesos = {sum(DEFAULT_WEIGHTS.values())})")

    for d in ["specs", "docs/adr", "evals", "reviews", "promotions"]:
        (project / d).mkdir(parents=True, exist_ok=True)
        (project / d / ".gitkeep").touch()
    ok("estrutura de handoff criada (I7)")

    print("\nproximo: `python bin/compile.py` para emitir os artefatos nativos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
