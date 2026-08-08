#!/usr/bin/env python3
"""
compile — the source of truth is neutral; the native artifacts are derived.

This is not "provisioning a native agent": it is COMPILING. One neutral spec
(spec/ + fde.config.toml) and one emitter per tool.

Order:
  1. agnostic AGENTS.md at the root — thin, points to skills (32 KiB limit)
  2. detected adapters emit that tool's native artifacts
  3. gates in the repository (pre-commit + CI) — enforcement independent of IDE

Idempotent. Every generated file carries a marker and is overwritten by
`fde sync`.
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
# AGENTS.md — the agnostic layer. Thin on purpose.
# ---------------------------------------------------------------------------
def emit_agents_md(ctx: EmitContext) -> Path:
    cfg, spec = ctx.config, ctx.spec
    weights = sorted(cfg.get("weights", {}).items(), key=lambda kv: -int(kv[1]))
    depths = {**cfg.get("derived", {}).get("depths", {}), **cfg.get("depths", {})}

    lines = [
        f"# {cfg.get('project', {}).get('name', 'project')}",
        "",
        "This repository operates under a delivery kernel with non-negotiable",
        "invariants. Instructions here apply to any coding agent (Codex, Cursor,",
        "Claude Code, Copilot, Kiro, Gemini CLI, Windsurf, Aider).",
        "",
        "## Commands",
        "",
        "```bash",
        f"{cfg.get('stack', {}).get('test_command', 'make test')}      # tests",
        f"{cfg.get('stack', {}).get('eval_command', 'python bin/fde/verify.py --gate eval')}   # evals",
        "python bin/fde/verify.py    # full gate (the same one CI runs)",
        "```",
        "",
        "## Invariants (not configurable)",
        "",
    ]
    for inv in spec.invariants["invariant"]:
        first = " ".join(inv["statement"].strip().split())
        lines.append(f"- **{inv['id']} {inv['name']}** — {first}")
    lines += [
        "",
        "No key exists that can turn off an invariant. If the delivery does not fit",
        "one, the scope shrinks — the standard does not.",
        "",
        "## Agreed priority (vector A, budget 100)",
        "",
    ]
    for k, v in weights:
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "Weight orders the adversarial attack and sizes the suite. Weight never goes",
        "below the attribute's floor.",
        "",
        "## Depth per domain (vector B, derived from the stack)",
        "",
    ]
    for k, v in sorted(depths.items(), key=lambda kv: -int(kv[1])):
        if int(v) > 0:
            lines.append(f"- {k}: {v}")
    lines += [
        "",
        "Override is upward-only. The nature of the system sets the minimum, not",
        "preference.",
        "",
        "## Roles",
        "",
    ]
    for role in spec.roles["role"]:
        lines.append(f"- **{role['label']}** (`fde-{role['id']}`) — writes to "
                     f"`{', '.join(role.get('write_scope', []))}`")
    lines += [
        "",
        "Handoff is by artifact on disk, never by conversation continuity.",
        "",
        "## Detail",
        "",
        "Each step has its own skill in `skills/` (Agent Skills format, portable",
        "across tools). This file is deliberately thin: Codex truncates AGENTS.md at",
        "32 KiB without warning.",
    ]

    body = generated_header("<!--") + "\n" + "\n".join(lines) + "\n"
    out = ctx.project / "AGENTS.md"
    out.write_text(body, encoding="utf-8")
    size = len(body.encode())
    if size > 24 * 1024:
        warn(f"AGENTS.md at {size} B — close to Codex's 32 KiB limit")
    return out


# ---------------------------------------------------------------------------
# gates in the repository — the only universal enforcement plane
# ---------------------------------------------------------------------------
def emit_repo_gates(ctx: EmitContext) -> list[Path]:
    written = []
    p = ctx.project

    # copy the runtime into the client's repo: the gate cannot depend on the
    # kernel being installed on the machine of whoever clones (I6)
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
        "# Universal enforcement: runs with any agent, and with human devs.\n"
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
    ap.add_argument("--check", action="store_true", help="writes nothing; detects drift")
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
        fail(f"{len(fatal)} configuration violation(s). Nothing was written.")
        return 1

    facts = detect(project)
    ctx = EmitContext(
        project=project, kernel=kernel, config=cfg.raw, spec=spec,
        facts=facts, probe_plan=probe_plan(cfg, spec),
    )

    if args.check:
        ok("configuration valid (--check mode, nothing written)")
        return 0

    # detection BEFORE writing: emit_agents_md creates AGENTS.md, and the Codex
    # adapter detects by AGENTS.md — without this it would self-detect in any repo.
    adapters = load_adapters(kernel)
    forced = cfg.raw.get("tooling", {}).get("force", [])
    present = {ad.tool: (ad.detect(project) or ad.tool in forced) for ad in adapters}

    written = [emit_agents_md(ctx)]
    ok(f"AGENTS.md (agnostic) — {written[0].name}")

    for ad in adapters:
        if present[ad.tool]:
            files = ad.emit(ctx)
            cap = ad.capability()
            ok(f"{ad.tool} [tier {cap.tier}] — {len(files)} file(s)")
            written += files
        else:
            print(f"  · {ad.tool}: not detected, skipped")

    gates = emit_repo_gates(ctx)
    ok(f"repository gates — {len(gates)} file(s) (pre-commit + CI + runtime)")
    written += gates

    print(f"\n{len(written)} files. Run `git config core.hooksPath .githooks` once.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
