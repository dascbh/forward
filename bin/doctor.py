#!/usr/bin/env python3
"""
doctor - shows each tool's tier and what is ACTUALLY enforced.

Looks like an accessory and is politically the most important command: it is
what keeps the FDE from thinking they have a wall when they only have a
recommendation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _find_adapters(start: Path) -> Path | None:
    # doctor runs both from the kernel (bin/) and copied into the client repo
    # (bin/fde/). Looks for adapters/ walking up the tree.
    for cand in [start, *start.parents][:5]:
        if (cand / "adapters" / "base.py").exists():
            return cand
    return None


KERNEL = _find_adapters(HERE) or HERE.parent
sys.path.insert(0, str(KERNEL / "adapters"))

from fde_lib import Config, Spec, project_root  # noqa: E402

ADAPTERS = ["claude_code", "codex", "cursor"]
TIER_LABEL = {
    "loop": "blocks before the write",
    "commit": "blocks at commit",
    "advisory": "instruction + CI only",
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
    print(f"\nproject: {project}")

    cfgok = (project / "fde.config.toml").exists()
    print(f"config:  {'fde.config.toml' if cfgok else 'MISSING - run `fde init`'}\n")

    print("agentic tools detected in this repository:\n")
    any_found = False
    for name in ADAPTERS:
        ad = load(name)
        if not ad:
            continue
        found = ad.detect(project)
        cap = ad.capability()
        if not found:
            print(f"  · {cap.tool:14} not detected")
            continue
        any_found = True
        print(f"  ● {cap.tool:14} tier {cap.tier} - {TIER_LABEL[cap.tier]}")
        for e in cap.enforced:
            print(f"      \033[32mENFORCED\033[0m   {e}")
        for a in cap.advisory:
            print(f"      \033[33madvisory\033[0m   {a}")
        for n in cap.notes:
            print(f"      note       {n}")
        print()

    if not any_found:
        print("  none. The standard still holds: pre-commit + CI are IDE-independent.\n")

    print("universal enforcement (tool-independent):")
    for f, label in [
        (project / ".githooks" / "pre-commit", "pre-commit"),
        (project / ".github" / "workflows" / "fde-gate.yml", "CI"),
        (project / "bin" / "fde" / "verify.py", "gate runtime in the repo (I6)"),
    ]:
        mark = "\033[32mok\033[0m" if f.exists() else "\033[31mmissing\033[0m"
        print(f"  {mark:20} {label}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
