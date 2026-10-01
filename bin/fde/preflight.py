#!/usr/bin/env python3
"""
preflight — every defect of a cycle's deploy plan in one list, before
the deploy starts (owner, 2026-10-01). A client's signed deploy stopped
four times in production, each stop a different defect of its own
deploy.md: a wrong command, a chained step no rule matched, a health
address answering 404, a permission. Run once, before the promotion
decision, it names them all at once; the spec role fixes them in one
pass and the deploy runs once.

Checks, none of them writing anything anywhere:
- `## Commands` exists, no line chains (`&&`, `;`, `|`), no prose step
  chains a declared command (deployallow.py);
- each command's program is on PATH; a script or file it names exists;
  `cd <dir>` names a directory that exists;
- every rule the commands need is in `.claude/settings.json`
  (`deployallow.py --check`), unless permissions are closed;
- each fixed http(s) address in the plan answers a GET below 400
  (`--offline` skips this; an address with a `<placeholder>` is listed,
  not fetched).
A `<placeholder>` is a value the deploy fills at run time, never a
defect. stdlib only (I6). Exit 1 when anything is found.
"""
from __future__ import annotations

import argparse
import re
import shlex
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deployallow  # noqa: E402
from fde_lib import cycle_dirs, project_root  # noqa: E402

URL = re.compile(r"https?://[^\s`'\"<>)\]]+[^\s`'\"<>)\].,;:]")
RUNNERS = {"bash", "sh", "zsh", "python", "python3", "node", "npx", "uv", "poetry", "pnpm",
           "npm", "yarn", "make", "env", "sudo", "time"}


def _exists(project: Path, cwd: Path, token: str) -> bool:
    if deployallow.PLACEHOLDER.search(token) or "PLACEHOLDER" in token:
        return True  # filled at run time
    return (cwd / token).exists() or (project / token).exists()


def command_defects(project: Path, commands: list[str]) -> list[str]:
    """Programs off PATH, missing scripts and directories, followed with
    the `cd` lines in order so a relative path is read where it runs."""
    out, cwd = [], project
    for line in commands:
        try:
            words = shlex.split(deployallow.PLACEHOLDER.sub("PLACEHOLDER", line))
        except ValueError as e:
            out.append(f"`{line}` does not parse: {e}")
            continue
        while words and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
            words = words[1:]  # `TZ=UTC aws …`: an environment prefix, not the program
        if not words:
            continue
        if words[0] == "cd":
            target = words[1] if len(words) > 1 else ""
            if target and target != "PLACEHOLDER":
                d = (cwd / target)
                if not d.is_dir():
                    out.append(f"`{line}`: directory {target} does not exist")
                else:
                    cwd = d.resolve()
            continue
        prog = words[0]
        if "PLACEHOLDER" in prog:
            continue
        if "/" in prog:
            if not _exists(project, cwd, prog):
                out.append(f"`{line}`: {prog} does not exist")
        elif shutil.which(prog) is None:
            out.append(f"`{line}`: {prog} is not on PATH")
        if prog in RUNNERS or prog.endswith(("python", "python3")):
            script = next((w for w in words[1:] if not w.startswith("-")), None)
            if script and re.search(r"\.(sh|py|js|ts|mjs)$", script) and not _exists(project, cwd, script):
                out.append(f"`{line}`: {script} does not exist")
    return out


def url_defects(text: str, offline: bool) -> tuple[list[str], list[str]]:
    """(defects, not fetched): fixed addresses that do not answer below 400."""
    bad, skipped = [], []
    for url in sorted(set(URL.findall(text))):
        if "PLACEHOLDER" in url or "{" in url or "*" in url or offline:
            skipped.append(url)
            continue
        try:
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "fde-preflight"})
            with urllib.request.urlopen(req, timeout=8) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
            e.close()
        except (urllib.error.URLError, OSError, ValueError) as e:
            bad.append(f"{url} does not answer ({getattr(e, 'reason', e)})")
            continue
        if code >= 400:
            bad.append(f"{url} answers {code}")
    return bad, skipped


def preflight(project: Path, cycle: str, offline: bool = False) -> dict:
    cdir = cycle_dirs(project).get(cycle)
    deploy = cdir / "deploy.md" if cdir else None
    if deploy is None or not deploy.is_file():
        return {"cycle": cycle, "defects": [f"{cycle} has no deploy.md"], "not_fetched": []}
    text = deploy.read_text(encoding="utf-8", errors="ignore")
    text_no_comments = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    cmds, refused = deployallow.deploy_commands(text_no_comments)
    defects = []
    if not cmds and not refused:
        defects.append("no `## Commands` block: the deploy has nothing to run as written")
    defects += [f"`{c}` chains commands — one per line" for c in refused]
    defects += [f"prose step `{s}` chains a declared command — run the lines as listed"
                for s in deployallow.chained_in_prose(text_no_comments, cmds)]
    defects += command_defects(project, cmds)
    p = deployallow.plan(project)
    if p["open"]:
        mine = set(deployallow.rule(c) for c in cmds)
        defects += [f"no allow rule for `{r}` (deployallow.py --write)"
                    for r in p["missing"] if r in mine]
    prose = re.split(r"^## Commands\s*$", text_no_comments, maxsplit=1, flags=re.M)[0]
    bad, skipped = url_defects(deployallow.PLACEHOLDER.sub("PLACEHOLDER", prose), offline)
    defects += bad
    return {"cycle": cycle, "defects": defects, "not_fetched": skipped, "commands": len(cmds)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="every defect of a deploy plan, before it runs")
    ap.add_argument("cycle", help="C-<n>")
    ap.add_argument("--offline", action="store_true", help="do not fetch the plan's addresses")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    project = Path(args.root).resolve() if args.root else project_root()
    r = preflight(project, args.cycle, args.offline)
    if r["defects"]:
        print(f"preflight {args.cycle}: {len(r['defects'])} defect(s) — fix them all, then run again")
        for d in r["defects"]:
            print(f"  ✗ {d}")
    else:
        print(f"preflight {args.cycle}: {r.get('commands', 0)} command(s), nothing found")
    if r["not_fetched"]:
        print(f"  ({len(r['not_fetched'])} address(es) not fetched: placeholders or --offline)")
    return 1 if r["defects"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
