#!/usr/bin/env python3
"""
deployallow — the cycle sign-off becomes the permission the machine sees.

    python3 bin/fde/deployallow.py            # what would change
    python3 bin/fde/deployallow.py --write    # apply it to .claude/settings.json
    python3 bin/fde/deployallow.py --check    # exit 1 when a rule is missing

The owner signs a cycle once, and that approval covers every deploy step,
irreversible ones included (kernel ADR-0019). Claude Code's auto mode does
not read plan.md: it suspends broad allow rules (`Bash`) and judges a
production migration or deploy on its own, so a signed deploy stopped half
way (auris C-4, 2026-09-30). Narrow allow rules are resolved before the
classifier, so this writes one `Bash(<command>)` rule per command a signed,
running cycle's deploy.md declares under `## Commands`, and removes them
when the cycle ends.

`## Commands` holds one command per line in a fenced block, exactly as the
deploy agent will run it; a `<placeholder>` becomes `*`. A line that
chains commands (`&&`, `||`, `;`, `|`, `$(`, backtick) is refused: split
it, so each rule names one command.

Only rules this script wrote are ever removed; it records them in
.fde/deploy-allow.json. `[tooling] open_permissions = false` in
fde.config.toml means the owner keeps the prompts: nothing is written.
Stdlib only (I6).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fde_lib import cycle_dirs, plan_header  # noqa: E402

SETTINGS = Path(".claude") / "settings.json"
LEDGER = Path(".fde") / "deploy-allow.json"
CHAINED = re.compile(r"&&|\|\||;|\||\$\(|`")
PLACEHOLDER = re.compile(r"<[^<>]+>")


def deploy_commands(deploy_text: str) -> tuple[list[str], list[str]]:
    """(commands, refused) from the fenced block(s) under `## Commands`."""
    m = re.search(r"^## Commands\s*$(.*?)(?=^## |\Z)", deploy_text, re.M | re.S)
    if not m:
        return [], []
    cmds, refused = [], []
    for block in re.findall(r"```[^\n]*\n(.*?)```", m.group(1), re.S):
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("$ "):
                line = line[2:].strip()
            if not line or line.startswith("#"):
                continue
            (refused if CHAINED.search(line) else cmds).append(line)
    return cmds, refused


def chained_in_prose(deploy_text: str, commands: list[str]) -> list[str]:
    """Backticked spans outside `## Commands` that chain a declared command
    (`cd infra && npx cdk deploy X`): the agent runs the chained form, it
    matches no rule, and the deploy stops for a permission."""
    prose = re.split(r"^## Commands\s*$", deploy_text, maxsplit=1, flags=re.M)[0]
    heads = [" ".join(PLACEHOLDER.sub("", c).split()[:3]) for c in commands]
    out = []
    for span in re.findall(r"`([^`\n]+)`", prose):
        if CHAINED.search(span) and any(h and h in span for h in heads):
            out.append(span.strip())
    return sorted(dict.fromkeys(out))


def rule(command: str) -> str:
    """`Bash(<command>)`, each `<placeholder>` a `*` wildcard."""
    return f"Bash({' '.join(PLACEHOLDER.sub('*', command).split())})"


def signed_running(plan_text: str) -> bool:
    return (plan_header(plan_text, "state").lower().startswith("running")
            and bool(plan_header(plan_text, "signed-off")))


def desired(project: Path) -> tuple[dict, dict, list, dict]:
    """({cycle: rules}, {cycle: refused lines}, [running cycles with no
    `## Commands`]) for the signed, running cycles."""
    want, refused, bare, chained = {}, {}, [], {}
    for cid, cdir in sorted(cycle_dirs(project).items()):
        plan, deploy = cdir / "plan.md", cdir / "deploy.md"
        if not plan.is_file() or not signed_running(plan.read_text(encoding="utf-8", errors="ignore")):
            continue
        text = deploy.read_text(encoding="utf-8", errors="ignore") if deploy.is_file() else ""
        cmds, bad = deploy_commands(text)
        if not cmds and not bad:
            bare.append(cid)
        if cmds:
            want[cid] = sorted(dict.fromkeys(rule(c) for c in cmds))
        if bad:
            refused[cid] = bad
        loose = chained_in_prose(text, cmds)
        if loose:
            chained[cid] = loose
    return want, refused, bare, chained


def permissions_open(project: Path) -> bool:
    try:
        cfg = tomllib.loads((project / "fde.config.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return True
    return (cfg.get("tooling") or {}).get("open_permissions", True) is not False


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def plan(project: Path) -> dict:
    """What `--write` would do: the rules to add and to remove."""
    want, refused, bare, chained = desired(project)
    settings = _load(project / SETTINGS, {})
    allow = list((settings.get("permissions") or {}).get("allow") or [])
    owned = _load(project / LEDGER, {})
    want_all = {r for rules in want.values() for r in rules}
    owned_all = {r for rules in owned.values() for r in rules}
    return {
        "open": permissions_open(project),
        "want": want, "refused": refused, "no_commands": bare, "chained_prose": chained,
        "add": sorted(want_all - set(allow)),
        "remove": sorted(owned_all - want_all),
        "missing": sorted(want_all - set(allow)),
    }


def write(project: Path, p: dict) -> None:
    path = project / SETTINGS
    settings = _load(path, {})
    perms = settings.setdefault("permissions", {})
    allow = [r for r in perms.get("allow") or [] if r not in set(p["remove"])]
    allow += [r for r in p["add"] if r not in allow]
    perms["allow"] = allow
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # own only what this script added or already owned: a rule the owner
    # wrote by hand is never adopted, so it is never removed at a close
    owned = {r for rules in _load(project / LEDGER, {}).values() for r in rules}
    mine = owned | set(p["add"])
    ledger = project / LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({cid: [r for r in rules if r in mine]
                                  for cid, rules in p["want"].items()},
                                 indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deploy commands of signed cycles as allow rules")
    ap.add_argument("--root", default=".")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="apply to .claude/settings.json")
    mode.add_argument("--check", action="store_true", help="exit 1 when a rule is missing")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)
    project = Path(args.root).resolve()
    p = plan(project)
    if args.format == "json":
        print(json.dumps(p, indent=2, ensure_ascii=False))
    else:
        if not p["open"]:
            print("deployallow: [tooling] open_permissions = false — the owner keeps the "
                  "prompts; nothing is written")
        for cid, rules in p["want"].items():
            print(f"{cid}: {len(rules)} deploy command(s) allowed by its sign-off")
        for cid, bad in p["refused"].items():
            print(f"{cid}: refused (chains commands — split it): " + "; ".join(bad))
        for cid, spans in p["chained_prose"].items():
            shown = [s if len(s) <= 80 else s[:79] + "…" for s in spans[:3]]
            more = f" (+{len(spans) - 3} more)" if len(spans) > 3 else ""
            print(f"{cid}: {len(spans)} step(s) chain a declared command, so they match no "
                  f"rule — one command per call, `cd` on its own line:")
            for sp in shown:
                print(f"    {sp}")
            if more:
                print(f"   {more}")
        for cid in p["no_commands"]:
            print(f"{cid}: deploy.md has no `## Commands` — its deploy steps are not allowed")
        for r in p["add"]:
            print(f"  + {r}")
        for r in p["remove"]:
            print(f"  - {r}")
        if not (p["add"] or p["remove"]):
            print("deployallow: settings already match the signed cycles")
    if args.check:
        return 1 if (p["open"] and (p["missing"] or p["refused"] or p["no_commands"]
                                    or p["chained_prose"])) else 0
    if args.write and p["open"] and (p["add"] or p["remove"]):
        write(project, p)
        print(f"deployallow: wrote {SETTINGS} (+{len(p['add'])} -{len(p['remove'])}) and {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
