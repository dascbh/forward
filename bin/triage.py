#!/usr/bin/env python3
"""
triage - sizes the demand and decides which steps activate.

If the full flow runs on a three-line change, the FDE turns the framework off
in week two. So sizing is CODE, not common sense.

What NEVER turns off at any size: the invariants. What varies: how many roles
enter, how many adversarial rounds, whether an ADR is required.
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
    ap.add_argument("--surfaces", type=int, default=1, help="surfaces touched")
    ap.add_argument("--loc", type=int, default=50, help="estimated lines")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()
    spec = Spec.load(project / ".fde" if (project / ".fde" / "spec").exists() else HERE.parent)
    cfg = Config.load(project)

    dc = str(cfg.raw.get("triage", {}).get("data_class", "internal")).lower()
    rev = str(cfg.raw.get("triage", {}).get("reversibility", "reversible")).lower()
    sensitive = dc in {"personal", "financial", "health"}
    irreversible = rev != "reversible"

    size = size_of(args.surfaces, sensitive, irreversible, args.loc)
    plan = dict(SIZES[size])
    plan["size"] = size
    plan["invariants_always_on"] = [i["id"] for i in spec.invariants["invariant"]]

    if args.format == "json":
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    print(f"\nsize: {size.upper()}  (class {dc}, {rev})")
    print(f"active roles: {', '.join(plan['roles'])}")
    print(f"adversarial rounds: {plan['adversarial_rounds']}")
    print(f"requires ADR: {'yes' if plan['adr'] else 'no'}")
    print(f"\nactive invariants (all of them, at any size): "
          f"{', '.join(plan['invariants_always_on'])}")
    print("\nWhat scales with size is the scope covered. The criteria applied do not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
