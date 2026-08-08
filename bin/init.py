#!/usr/bin/env python3
"""
init - detects the stack, interviews ONLY what detection did not resolve,
writes the declarative config, and compiles.

Rules this command respects:
  - stack: detect, never ask. Confirmation in a single block, not per item.
  - project: interview once, result versioned in the repo.
  - developer: does not exist as a category. Preference is weight, and weight
    belongs to the project.
  - non-interactive mode via flags/env: runs in CI with no human.
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

DATA_CLASSES = ["public", "internal", "personal", "financial", "health"]
REVERSIBILITY = ["reversible", "difficult", "irreversible"]

# default vector A allocation: sums to 100, respects every floor.
# NOT a neutral recommendation - a starting point the client moves.
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
    ap.add_argument("--yes", action="store_true", help="non-interactive (CI)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--data-class", choices=DATA_CLASSES, default=None)
    ap.add_argument("--reversibility", choices=REVERSIBILITY, default=None)
    args = ap.parse_args()

    project = project_root(Path(args.project) if args.project else None)
    interactive = not args.yes
    spec = Spec.load(HERE.parent)

    print(f"\nproject: {project}")
    facts = detect(project)

    # confirmation in a BLOCK - not per item
    print("\ndetected (confirm as a block, not item by item):")
    for k in ["languages", "test_runners", "has_frontend", "has_database",
              "exposes_api", "has_ci", "has_iac", "embeds_model", "agent_tools"]:
        print(f"  {k:16} {facts[k]}")
    if interactive:
        if input("\ncorrect? [Y/n] ").strip().lower().startswith("n"):
            warn("adjust the repo files or edit fde.config.toml later; moving on.")

    # only what detection cannot resolve
    answers = {
        "data_class": args.data_class or ask(
            "Class of the most sensitive data this system touches:",
            DATA_CLASSES, "internal", interactive),
        "reversibility": args.reversibility or ask(
            "Reversibility of a production mistake:",
            REVERSIBILITY, "reversible", interactive),
        "user_facing": facts["has_frontend"],
        "has_agent_loop": facts["embeds_model"],
    }

    derived = derive_depths(facts, answers)

    body = [
        "# fde.config.toml - the project's single declarative file.",
        "# Versioned. Auditable diff. Recompilable with `fde sync`.",
        "#",
        "# There is NO key here to turn off an invariant. Invariants live in",
        "# .fde/spec/invariants.toml and have no key. Weight moves rigor upward or",
        "# redistributes emphasis; it never goes below the floor.",
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
        "# VECTOR A - quality attributes. CLOSED budget: sum = 100.",
        "# This is what the client allocates and signs. A dated record of what they",
        "# said mattered - and the order in which the adversarial will attack.",
        "# ---------------------------------------------------------------------------",
        toml_table("weights", DEFAULT_WEIGHTS),
        "",
        "# ---------------------------------------------------------------------------",
        "# VECTOR B - technical domains. DERIVED from stack + triage.",
        "# Override in [depths] is upward-only: you raise, never reduce.",
        "# ---------------------------------------------------------------------------",
        toml_table("derived.depths", derived),
        "",
        "[depths]",
        "# e.g.: data_modeling = 3   (allowed: >= derived)",
        "",
        "[tooling]",
        'force = []   # e.g.: ["cursor"] to emit an undetected adapter',
    ]

    out = project / "fde.config.toml"
    if out.exists():
        warn(f"{out.name} already exists - not overwritten. Use `fde sync` to recompile.")
    else:
        out.write_text("\n".join(body) + "\n", encoding="utf-8")
        ok(f"wrote {out.name} (weights sum = {sum(DEFAULT_WEIGHTS.values())})")

    for d in ["specs", "docs/adr", "evals", "reviews", "promotions"]:
        (project / d).mkdir(parents=True, exist_ok=True)
        (project / d / ".gitkeep").touch()
    ok("handoff structure created (I7)")

    print("\nnext: `python bin/compile.py` to emit the native artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
