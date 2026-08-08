#!/usr/bin/env python3
"""
review - dispara a revisao adversarial em contexto isolado.

O isolamento e o ponto. Sem worktree separada, o revisor ve o thread que produziu
o codigo e concorda com ele mesmo - modo de falha mais provavel do framework
inteiro. Nas ferramentas que nao tem isolamento nativo, este comando FORCA por
git worktree, do lado de fora.

Ordem de ataque derivada do vetor A. Nao reordenavel por conveniencia.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import Config, Spec, ok, probe_plan, project_root, warn  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("demand_id")
    ap.add_argument("--isolate", action="store_true",
                    help="cria git worktree limpa (obrigatorio fora do tier loop)")
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    project = project_root()
    spec = Spec.load(project / ".fde" if (project / ".fde" / "spec").exists() else HERE.parent)
    cfg = Config.load(project)
    plan = probe_plan(cfg, spec)

    print(f"\nplano de sondagem - demanda {args.demand_id}")
    print("(ordem derivada dos pesos do vetor A; sucesso e achado, nao aprovacao)\n")
    for step in plan:
        flag = "TRAVA MERGE" if step["blocking"] else "registra"
        print(f"  {step['label']:34} peso {step['weight']:>3}  "
              f"{step['rounds']} rodada(s)  [{flag}]")
        for pr in step["probes"]:
            print(f"      - {pr}")
        print()

    if args.plan_only:
        return 0

    out = project / "reviews" / args.demand_id
    out.mkdir(parents=True, exist_ok=True)
    findings = out / "findings.toml"
    if not findings.exists():
        findings.write_text(
            "# Relatorio de revisao adversarial\n"
            "# Este arquivo e escrito pelo papel adversarial e por mais ninguem.\n\n"
            "[meta]\n"
            f'demand_id = "{args.demand_id}"\n'
            'context_policy = "artifact_only"   # I2: sem contexto de quem construiu\n'
            'isolation_mode = "worktree"\n'
            "rounds_planned = " + str(sum(s["rounds"] for s in plan)) + "\n\n"
            "# [[finding]]\n"
            '# attribute = "security_privacy"\n'
            '# severity  = "critica"   # critica | alta | media | baixa\n'
            '# probe     = "injecao via conteudo observado"\n'
            '# evidence  = "caminho:linha ou passo reproduzivel"\n'
            '# blocking  = true\n',
            encoding="utf-8")
        ok(f"esqueleto em {findings.relative_to(project)}")

    if args.isolate:
        wt = project.parent / f".fde-review-{args.demand_id}"
        r = subprocess.run(["git", "worktree", "add", "--detach", str(wt)],
                           cwd=project, capture_output=True, text=True)
        if r.returncode == 0:
            ok(f"worktree isolada: {wt}")
            print("  Rode o papel adversarial DENTRO dela. Ele deve ver artefato + spec,")
            print("  e nada do raciocinio de quem construiu.")
        else:
            warn(f"worktree nao criada: {r.stderr.strip()[:200]}")
            warn("sem isolamento, I2 nao e atendido e o gate vai reprovar")
    else:
        warn("--isolate nao usado. No tier `loop` o adapter cuida disso; fora dele,")
        warn("o isolamento nao existe e o achado nao e confiavel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
