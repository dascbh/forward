#!/usr/bin/env python3
"""
review - triggers the adversarial review in an isolated context.

Isolation is the point. Without a separate worktree, the reviewer sees the
thread that produced the code and agrees with itself - the most likely failure
mode of the whole framework. In tools without native isolation, this command
FORCES it via git worktree, from the outside.

Attack order derived from vector A. Not reorderable for convenience.
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
                    help="creates a clean git worktree (mandatory outside the loop tier)")
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    project = project_root()
    spec = Spec.load(project / ".fde" if (project / ".fde" / "spec").exists() else HERE.parent)
    cfg = Config.load(project)
    plan = probe_plan(cfg, spec)

    print(f"\nprobe plan - demand {args.demand_id}")
    print("(order derived from vector A weights; success is findings, not approval)\n")
    for step in plan:
        flag = "BLOCKS MERGE" if step["blocking"] else "records"
        print(f"  {step['label']:34} weight {step['weight']:>3}  "
              f"{step['rounds']} round(s)  [{flag}]")
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
            "# Adversarial review report\n"
            "# This file is written by the adversarial role and by no one else.\n\n"
            "[meta]\n"
            f'demand_id = "{args.demand_id}"\n'
            'context_policy = "artifact_only"   # I2: no builder context\n'
            'isolation_mode = "worktree"\n'
            "rounds_planned = " + str(sum(s["rounds"] for s in plan)) + "\n\n"
            "# [[finding]]\n"
            '# attribute = "security_privacy"\n'
            '# severity  = "critical"   # critical | high | medium | low\n'
            '# probe     = "injection via observed content"\n'
            '# evidence  = "path:line or reproducible step"\n'
            '# blocking  = true\n',
            encoding="utf-8")
        ok(f"skeleton at {findings.relative_to(project)}")

    if args.isolate:
        wt = project.parent / f".fde-review-{args.demand_id}"
        r = subprocess.run(["git", "worktree", "add", "--detach", str(wt)],
                           cwd=project, capture_output=True, text=True)
        if r.returncode == 0:
            ok(f"isolated worktree: {wt}")
            print("  Run the adversarial role INSIDE it. It must see artifact + spec,")
            print("  and nothing of the builder's reasoning.")
        else:
            warn(f"worktree not created: {r.stderr.strip()[:200]}")
            warn("without isolation, I2 is not met and the gate will fail")
    else:
        warn("--isolate not used. In the `loop` tier the adapter handles it; outside it,")
        warn("there is no isolation and the finding is not trustworthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
