#!/usr/bin/env python3
"""
triage - dimensiona a demanda e decide quais etapas ativam.

Se o fluxo completo roda numa mudanca de tres linhas, o FDE desliga o framework
na segunda semana. Entao o sizing e CODIGO, nao bom senso.

O que NUNCA desliga em nenhum tamanho: os invariantes. O que varia: quantos
papeis entram, quantas rodadas de adversarial, se exige ADR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import Config, Spec, project_root  # noqa: E402

SIZES = {
    "xs": dict(roles=["implementation", "adversarial"], adversarial_rounds=1, adr=False),
    "s":  dict(roles=["spec", "implementation", "adversarial"], adversarial_rounds=1, adr=False),
    "m":  dict(roles=["spec", "implementation", "adversarial", "promotion"], adversarial_rounds=2, adr=True),
    "l":  dict(roles=["spec", "architecture", "implementation", "adversarial", "promotion"], adversarial_rounds=3, adr=True),
}


def size_of(surfaces: int, sensitive: bool, irreversible: bool, loc: int) -> str:
    score = 0
    score += min(3, surfaces)
    score += 2 if sensitive else 0
    score += 2 if irreversible else 0
    score += 0 if loc < 50 else (1 if loc < 300 else 2)
    if score <= 1:
        return "xs"
    if score <= 3:
        return "s"
    if score <= 6:
        return "m"
    return "l"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surfaces", type=int, default=1, help="superficies tocadas")
    ap.add_argument("--loc", type=int, default=50, help="linhas estimadas")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()
    spec = Spec.load(project / ".fde" if (project / ".fde" / "spec").exists() else HERE.parent)
    cfg = Config.load(project)

    dc = str(cfg.raw.get("triage", {}).get("data_class", "interno")).lower()
    rev = str(cfg.raw.get("triage", {}).get("reversibility", "reversivel")).lower()
    sensitive = dc in {"pessoal", "financeiro", "saude"}
    irreversible = rev != "reversivel"

    size = size_of(args.surfaces, sensitive, irreversible, args.loc)
    plan = dict(SIZES[size])
    plan["size"] = size
    plan["invariants_always_on"] = [i["id"] for i in spec.invariants["invariant"]]

    if args.format == "json":
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    print(f"\ntamanho: {size.upper()}  (classe {dc}, {rev})")
    print(f"papeis ativos: {', '.join(plan['roles'])}")
    print(f"rodadas adversariais: {plan['adversarial_rounds']}")
    print(f"exige ADR: {'sim' if plan['adr'] else 'nao'}")
    print(f"\ninvariantes ativos (todos, em qualquer tamanho): "
          f"{', '.join(plan['invariants_always_on'])}")
    print("\nO que escala com o tamanho e o escopo coberto. O criterio aplicado nao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
