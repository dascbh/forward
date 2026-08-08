#!/usr/bin/env python3
"""
doctor - mostra o tier daquela ferramenta e o que esta DE FATO enforcado.

Parece acessorio e e o comando mais importante politicamente: e ele que impede
o FDE de achar que tem parede quando tem so recomendacao.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _find_adapters(start: Path) -> Path | None:
    # doctor roda tanto do kernel (bin/) quanto copiado no repo do cliente
    # (bin/fde/). Procura adapters/ subindo a arvore.
    for cand in [start, *start.parents][:5]:
        if (cand / "adapters" / "base.py").exists():
            return cand
    return None


KERNEL = _find_adapters(HERE) or HERE.parent
sys.path.insert(0, str(KERNEL / "adapters"))

from fde_lib import Config, Spec, project_root  # noqa: E402

ADAPTERS = ["claude_code", "codex", "cursor"]
TIER_LABEL = {
    "loop": "bloqueia antes da escrita",
    "commit": "bloqueia no commit",
    "advisory": "so instrucao + CI",
}


def load(name: str):
    p = KERNEL / "adapters" / name / "adapter.py"
    if not p.exists():
        return None
    s = importlib.util.spec_from_file_location(f"a_{name}", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.ADAPTER


def main() -> int:
    project = project_root()
    print(f"\nprojeto: {project}")

    cfgok = (project / "fde.config.toml").exists()
    print(f"config:  {'fde.config.toml' if cfgok else 'AUSENTE - rode `fde init`'}\n")

    print("ferramentas agenticas detectadas neste repositorio:\n")
    any_found = False
    for name in ADAPTERS:
        ad = load(name)
        if not ad:
            continue
        found = ad.detect(project)
        cap = ad.capability()
        if not found:
            print(f"  · {cap.tool:14} nao detectado")
            continue
        any_found = True
        print(f"  ● {cap.tool:14} tier {cap.tier} - {TIER_LABEL[cap.tier]}")
        for e in cap.enforced:
            print(f"      \033[32mENFORCADO\033[0m  {e}")
        for a in cap.advisory:
            print(f"      \033[33msugerido \033[0m  {a}")
        for n in cap.notes:
            print(f"      nota      {n}")
        print()

    if not any_found:
        print("  nenhuma. O padrao ainda vale: pre-commit + CI sao independentes de IDE.\n")

    print("enforcement universal (independe de ferramenta):")
    for f, label in [
        (project / ".githooks" / "pre-commit", "pre-commit"),
        (project / ".github" / "workflows" / "fde-gate.yml", "CI"),
        (project / "bin" / "fde" / "verify.py", "runtime do gate no repo (I6)"),
    ]:
        mark = "\033[32mok\033[0m" if f.exists() else "\033[31mausente\033[0m"
        print(f"  {mark:20} {label}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
