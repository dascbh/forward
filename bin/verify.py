#!/usr/bin/env python3
"""
verify — o gate. Um só verificador, três chamadores: pre-commit, CI, mão.

É aqui que o invariante deixa de ser recomendação. Skill é sugestão; o modelo
ignora quando o contexto aperta. Exit code é parede.

Roda com stdlib pura, no ambiente do cliente, sem o kernel instalado (I6).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import Config, Spec, escalated_security_floor, project_root, validate  # noqa: E402

BEHAVIOR_PATHS = ("src/", "lib/", "app/", "services/", "prompts/", "agents/")
EVAL_PATHS = ("evals/", "tests/")


class Gate:
    def __init__(self, project: Path):
        self.project = project
        self.results: list[tuple[str, bool, str]] = []

    def add(self, gid: str, passed: bool, msg: str) -> None:
        self.results.append((gid, passed, msg))

    # -- helpers ----------------------------------------------------------
    def _git(self, *args: str) -> list[str]:
        try:
            out = subprocess.run(
                ["git", *args], cwd=self.project, capture_output=True, text=True, check=False
            )
            return [l for l in out.stdout.splitlines() if l.strip()]
        except FileNotFoundError:
            return []

    def changed(self, staged: bool) -> list[str]:
        if staged:
            return self._git("diff", "--cached", "--name-only")
        return self._git("diff", "--name-only", "HEAD~1..HEAD") or self._git("ls-files")

    # -- I1: eval precede merge -------------------------------------------
    def gate_eval_coverage(self, staged: bool) -> None:
        files = self.changed(staged)
        touched_behavior = [f for f in files if f.startswith(BEHAVIOR_PATHS)]
        touched_eval = [f for f in files if f.startswith(EVAL_PATHS)]
        if not touched_behavior:
            self.add("I1", True, "nenhuma mudança de comportamento nesta alteração")
            return
        if touched_eval:
            self.add("I1", True,
                     f"{len(touched_behavior)} arquivo(s) de comportamento com "
                     f"{len(touched_eval)} arquivo(s) de eval")
            return
        self.add("I1", False,
                 f"{len(touched_behavior)} arquivo(s) de comportamento sem entrada "
                 f"correspondente em evals/ ou tests/: {', '.join(touched_behavior[:3])}"
                 + (" ..." if len(touched_behavior) > 3 else ""))

    # -- I2/I3: revisão adversarial isolada, sem poder corrigir -----------
    def gate_adversarial(self) -> None:
        reviews = list((self.project / "reviews").rglob("findings.toml"))
        if not reviews:
            self.add("I2", False, "nenhum relatório em reviews/**/findings.toml — "
                                  "a revisão adversarial não rodou")
            return
        # o achado precisa declarar contexto isolado e não pode vir da mesma mão
        bad = []
        for r in reviews:
            text = r.read_text(encoding="utf-8", errors="ignore")
            if "context_policy" not in text or "artifact_only" not in text:
                bad.append(str(r.relative_to(self.project)))
        if bad:
            self.add("I2", False, f"relatório sem declaração de isolamento: {', '.join(bad[:3])}")
        else:
            self.add("I2", True, f"{len(reviews)} relatório(s) com isolamento declarado")

        # I3: o papel adversarial não escreveu em código
        authors = self._git("log", "-20", "--format=%s")
        leak = [a for a in authors if "fde-adversarial" in a and "src/" in a]
        self.add("I3", not leak,
                 "papel adversarial sem escrita em código" if not leak
                 else "commit do papel adversarial tocou código — I3 violado")

    # -- I4: critério declarado antes ------------------------------------
    def gate_promotion_criteria(self) -> None:
        specs = list((self.project / "specs").rglob("acceptance.md"))
        if not specs:
            self.add("I4", False, "nenhum specs/**/acceptance.md — critério de aceite "
                                  "não foi declarado")
            return
        undated = [s.name for s in specs if "data:" not in
                   s.read_text(encoding="utf-8", errors="ignore").lower()[:400]]
        self.add("I4", not undated,
                 f"{len(specs)} critério(s) declarado(s)" if not undated
                 else f"critério sem data: {', '.join(undated[:3])}")

    # -- I5: piso de observabilidade -------------------------------------
    def gate_observability(self, cfg: Config, spec: Spec) -> None:
        declared = [k for k, v in cfg.raw.get("weights", {}).items() if int(v) > 0]
        obs = self.project / "observability.toml"
        alt = list(self.project.rglob("*telemetry*")) + list(self.project.rglob("*tracing*"))
        if obs.exists() or alt:
            self.add("I5", True, "sinal de observabilidade presente")
        else:
            self.add("I5", False,
                     f"{len(declared)} atributo(s) declarado(s) sem sinal correspondente — "
                     f"nada disso é verificável em produção")

    # -- I6: o gate roda no cliente --------------------------------------
    def gate_portability(self) -> None:
        runtime = self.project / "bin" / "fde" / "verify.py"
        hook = self.project / ".githooks" / "pre-commit"
        missing = [str(p.relative_to(self.project)) for p in (runtime, hook) if not p.exists()]
        self.add("I6", not missing,
                 "gate autocontido no repositório" if not missing
                 else f"faltando: {', '.join(missing)} — o gate não roda sem o FDE")

    # -- I7: handoff por artefato -----------------------------------------
    def gate_artifact_handoff(self) -> None:
        expected = ["specs", "docs/adr", "evals", "reviews"]
        missing = [d for d in expected if not (self.project / d).exists()]
        self.add("I7", len(missing) <= 1,
                 "estrutura de handoff presente" if len(missing) <= 1
                 else f"diretórios de handoff ausentes: {', '.join(missing)}")

    # -- config ------------------------------------------------------------
    def gate_config(self, cfg: Config, spec: Spec) -> None:
        viol = validate(cfg, spec)
        self.add("CFG", not viol,
                 "configuração válida" if not viol
                 else "; ".join(f"[{v.code}] {v.message.splitlines()[0]}" for v in viol[:3]))
        floor = escalated_security_floor(cfg, spec)
        w = int(cfg.weights.get("security_privacy", 0))
        self.add("CFG-SEC", w >= floor,
                 f"segurança {w} >= piso {floor} (classe de dado "
                 f"{cfg.raw.get('triage', {}).get('data_class', 'interno')})"
                 if w >= floor else
                 f"segurança {w} < piso escalado {floor} pela classe de dado — "
                 f"a triagem eleva o piso e o peso não desce isso")

    def report(self, fmt: str) -> int:
        failed = [r for r in self.results if not r[1]]
        if fmt == "json":
            print(json.dumps(
                {"passed": not failed,
                 "gates": [{"id": g, "passed": p, "detail": m} for g, p, m in self.results]},
                indent=2, ensure_ascii=False))
        else:
            print()
            for gid, passed, msg in self.results:
                mark = "\033[32m✓\033[0m" if passed else "\033[31m✗\033[0m"
                print(f" {mark} {gid:8} {msg}")
            print()
            if failed:
                print(f"\033[31m{len(failed)} gate(s) reprovado(s).\033[0m "
                      f"Invariantes não têm chave de bypass — o escopo encolhe, o padrão não.")
            else:
                print("\033[32mtodos os gates aprovados.\033[0m")
        return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="modo pre-commit")
    ap.add_argument("--all", action="store_true", help="modo CI: tudo")
    ap.add_argument("--gate", default=None, help="um gate específico")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()
    kernel_spec = project / ".fde"
    spec = Spec.load(kernel_spec if (kernel_spec / "spec").exists() else HERE.parent)
    try:
        cfg = Config.load(project)
    except FileNotFoundError as e:
        print(f"\033[31m✗\033[0m {e}", file=sys.stderr)
        return 1

    g = Gate(project)
    only = args.gate

    def want(name: str) -> bool:
        return only is None or only == name

    if want("config"):
        g.gate_config(cfg, spec)
    if want("eval-coverage") or want("eval"):
        g.gate_eval_coverage(staged=args.staged)
    if not args.staged:  # pre-commit fica rápido; o resto é CI
        if want("adversarial-isolation"):
            g.gate_adversarial()
        if want("promotion-criteria"):
            g.gate_promotion_criteria()
        if want("observability"):
            g.gate_observability(cfg, spec)
        if want("portability"):
            g.gate_portability()
        if want("artifact-handoff"):
            g.gate_artifact_handoff()

    return g.report(args.format)


if __name__ == "__main__":
    raise SystemExit(main())
