#!/usr/bin/env python3
"""
compile — a fonte da verdade é neutra; os artefatos nativos são derivados.

Não é "provisionar um agente nativo": é COMPILAR. Um spec neutro
(spec/ + fde.config.toml) e um emissor por ferramenta.

Ordem:
  1. AGENTS.md agnóstico na raiz — fino, aponta para skills (limite de 32 KiB)
  2. adapters detectados emitem o nativo daquela ferramenta
  3. gates no repositório (pre-commit + CI) — enforcement que não depende de IDE

Idempotente. Todo arquivo gerado leva marcador e é sobrescrito por `fde sync`.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "adapters"))

from base import EmitContext, generated_header  # noqa: E402
from detect_stack import detect  # noqa: E402
from fde_lib import Config, Spec, fail, ok, probe_plan, project_root, validate, warn  # noqa: E402

ADAPTER_DIRS = ["claude_code", "codex", "cursor"]


def load_adapters(kernel: Path):
    out = []
    for name in ADAPTER_DIRS:
        path = kernel / "adapters" / name / "adapter.py"
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location(f"fde_adapter_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out.append(mod.ADAPTER)
    return out


# ---------------------------------------------------------------------------
# AGENTS.md — a camada agnóstica. Fino de propósito.
# ---------------------------------------------------------------------------
def emit_agents_md(ctx: EmitContext) -> Path:
    cfg, spec = ctx.config, ctx.spec
    weights = sorted(cfg.get("weights", {}).items(), key=lambda kv: -int(kv[1]))
    depths = {**cfg.get("derived", {}).get("depths", {}), **cfg.get("depths", {})}

    lines = [
        f"# {cfg.get('project', {}).get('name', 'projeto')}",
        "",
        "Este repositório opera sob um kernel de entrega com invariantes não negociáveis.",
        "Instruções aqui valem para qualquer agente de código (Codex, Cursor, Claude Code,",
        "Copilot, Kiro, Gemini CLI, Windsurf, Aider).",
        "",
        "## Comandos",
        "",
        "```bash",
        f"{cfg.get('stack', {}).get('test_command', 'make test')}      # teste",
        f"{cfg.get('stack', {}).get('eval_command', 'python bin/fde/verify.py --gate eval')}   # eval",
        "python bin/fde/verify.py    # gate completo (o mesmo que o CI roda)",
        "```",
        "",
        "## Invariantes (não configuráveis)",
        "",
    ]
    for inv in spec.invariants["invariant"]:
        first = " ".join(inv["statement"].strip().split())
        lines.append(f"- **{inv['id']} {inv['name']}** — {first}")
    lines += [
        "",
        "Não existe chave capaz de desligar um invariante. Se a entrega não cabe nele,",
        "o escopo encolhe — o padrão não.",
        "",
        "## Prioridade acordada (vetor A, orçamento 100)",
        "",
    ]
    for k, v in weights:
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "Peso ordena o ataque adversarial e dimensiona a suíte. Peso nunca desce abaixo",
        "do piso do atributo.",
        "",
        "## Profundidade por domínio (vetor B, derivado da stack)",
        "",
    ]
    for k, v in sorted(depths.items(), key=lambda kv: -int(kv[1])):
        if int(v) > 0:
            lines.append(f"- {k}: {v}")
    lines += [
        "",
        "Override é upward-only. A natureza do sistema define o mínimo, não a preferência.",
        "",
        "## Papéis",
        "",
    ]
    for role in spec.roles["role"]:
        lines.append(f"- **{role['label']}** (`fde-{role['id']}`) — escreve em "
                     f"`{', '.join(role.get('write_scope', []))}`")
    lines += [
        "",
        "Handoff é por artefato em disco, nunca por continuidade de conversa.",
        "",
        "## Detalhe",
        "",
        "Cada etapa tem skill própria em `skills/` (formato Agent Skills, portátil entre",
        "ferramentas). Este arquivo é deliberadamente fino: o Codex trunca AGENTS.md em",
        "32 KiB sem avisar.",
    ]

    body = generated_header("<!--") + "\n" + "\n".join(lines) + "\n"
    out = ctx.project / "AGENTS.md"
    out.write_text(body, encoding="utf-8")
    size = len(body.encode())
    if size > 24 * 1024:
        warn(f"AGENTS.md em {size} B — perto do limite de 32 KiB do Codex")
    return out


# ---------------------------------------------------------------------------
# gates no repositório — o único plano de enforcement universal
# ---------------------------------------------------------------------------
def emit_repo_gates(ctx: EmitContext) -> list[Path]:
    written = []
    p = ctx.project

    # cópia do runtime para o repo do cliente: o gate não pode depender do kernel
    # estar instalado na máquina de quem clonar (I6)
    dest = p / "bin" / "fde"
    dest.mkdir(parents=True, exist_ok=True)
    for f in ["fde_lib.py", "verify.py", "guard.py", "doctor.py", "detect_stack.py"]:
        src = ctx.kernel / "bin" / f
        if src.exists():
            (dest / f).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(dest / f)
    ks = p / ".fde" / "spec"
    ks.mkdir(parents=True, exist_ok=True)
    for rel in ["invariants.toml", "roles.toml",
                "dimensions/quality-attributes.toml", "dimensions/technical-domains.toml"]:
        tgt = ks / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tgt.write_text((ctx.kernel / "spec" / rel).read_text(encoding="utf-8"), encoding="utf-8")
        written.append(tgt)

    hook = p / ".githooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        "# " + generated_header().splitlines()[0].lstrip("# ") + "\n"
        "# Enforcement universal: roda com qualquer agente, e com dev humano.\n"
        "exec python3 bin/fde/verify.py --staged\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    written.append(hook)

    wf = p / ".github" / "workflows" / "fde-gate.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(
        generated_header() + "\n"
        "name: fde-gate\n"
        "on: [push, pull_request]\n"
        "jobs:\n"
        "  gate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with: { python-version: '3.12' }\n"
        "      - name: FDE gate\n"
        "        run: python bin/fde/verify.py --all\n",
        encoding="utf-8",
    )
    written.append(wf)
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--check", action="store_true", help="não escreve; detecta drift")
    args = ap.parse_args()

    project = project_root(Path(args.project) if args.project else None)
    kernel = HERE.parent
    spec = Spec.load(kernel)

    try:
        cfg = Config.load(project)
    except FileNotFoundError as e:
        fail(str(e))
        return 1

    viol = validate(cfg, spec)
    fatal = [v for v in viol if v.fatal]
    for v in viol:
        print(f"  [{v.code}] {v.message}")
    if fatal:
        fail(f"{len(fatal)} violação(ões) de configuração. Nada foi escrito.")
        return 1

    facts = detect(project)
    ctx = EmitContext(
        project=project, kernel=kernel, config=cfg.raw, spec=spec,
        facts=facts, probe_plan=probe_plan(cfg, spec),
    )

    if args.check:
        ok("configuração válida (modo --check, nada escrito)")
        return 0

    # detecção ANTES de escrever: emit_agents_md cria AGENTS.md, e o adapter do
    # Codex detecta por AGENTS.md — sem isso ele se auto-detectaria em qualquer repo.
    adapters = load_adapters(kernel)
    forced = cfg.raw.get("tooling", {}).get("force", [])
    present = {ad.tool: (ad.detect(project) or ad.tool in forced) for ad in adapters}

    written = [emit_agents_md(ctx)]
    ok(f"AGENTS.md (agnóstico) — {written[0].name}")

    for ad in adapters:
        if present[ad.tool]:
            files = ad.emit(ctx)
            cap = ad.capability()
            ok(f"{ad.tool} [tier {cap.tier}] — {len(files)} arquivo(s)")
            written += files
        else:
            print(f"  · {ad.tool}: não detectado, pulado")

    gates = emit_repo_gates(ctx)
    ok(f"gates no repositório — {len(gates)} arquivo(s) (pre-commit + CI + runtime)")
    written += gates

    print(f"\n{len(written)} arquivos. Rode `git config core.hooksPath .githooks` uma vez.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
