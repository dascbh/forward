#!/usr/bin/env python3
"""
uiprose — explanatory sentences living in the interface (USE-16).

    python3 bin/fde/uiprose.py              # every screen, most prose first
    python3 bin/fde/uiprose.py --changed    # only what this branch adds vs main
    python3 bin/fde/uiprose.py --format json

A UI sentence is visible text of 8 words or more that reads as a sentence
(ends in punctuation or carries a parenthesis). Labels, buttons and short
help pass unseen. Each one listed is judged against USE-16: keep it only
when it serves the user's next action; a sentence that explains a rule,
restates a criterion or an ADR, or narrates what the system does is spec
prose living in the interface. A report, never a gate. Stdlib only (I6).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

UI_SUFFIXES = (".tsx", ".jsx", ".vue", ".svelte", ".html")
SKIP = re.compile(r"(^|/)(node_modules|dist|build|\.next|coverage|tests?|__tests__|\.fde|"
                  r"\.claude|bin|specs|docs|evals|reviews|cycles)(/|$)|\.(test|spec|stories)\.")
TEXT = re.compile(r'"([^"\n]{30,})"|\'([^\'\n]{30,})\'|`([^`\n]{30,})`|>\s*([^<>{}\n]{30,}?)\s*<')
MIN_WORDS = 8


def sentences(source: str) -> list[str]:
    """Visible-looking sentences in one UI file."""
    out = []
    for groups in TEXT.findall(source):
        t = " ".join("".join(groups).split())
        words = re.findall(r"[^\W\d_]{2,}", t)
        if len(words) < MIN_WORDS or "${" in t or re.search(r"[{};=]|\w\(\)|=>|className", t):
            continue
        if re.search(r"[.!?:)]$|\(", t):
            out.append(t)
    return out


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def ui_files(root: Path) -> list[Path]:
    listed = _git(root, "ls-files").splitlines()
    rels = listed or [str(p.relative_to(root)) for p in root.rglob("*")]
    return [root / r for r in rels if r.endswith(UI_SUFFIXES) and not SKIP.search(r)]


def added_lines(root: Path, base: str = "main") -> dict[str, str]:
    """{path: added text} on this branch since it left `base`, plus the
    working tree."""
    out: dict[str, list[str]] = {}
    cur = None
    for line in (_git(root, "diff", "-U0", f"{base}...HEAD") + _git(root, "diff", "-U0")).splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
        elif cur and line.startswith("+") and not line.startswith("+++"):
            out.setdefault(cur, []).append(line[1:])
    # a new file not yet committed is in no diff: all of it is added
    for rel in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        try:
            out[rel] = [(root / rel).read_text(encoding="utf-8", errors="ignore")]
        except OSError:
            continue
    return {p: "\n".join(v) for p, v in out.items()
            if p.endswith(UI_SUFFIXES) and not SKIP.search(p)}


def report(root: Path, changed: bool) -> dict:
    if changed:
        per = {p: sentences(t) for p, t in added_lines(root).items()}
    else:
        per = {}
        for f in ui_files(root):
            try:
                per[str(f.relative_to(root))] = sentences(f.read_text(encoding="utf-8",
                                                                      errors="ignore"))
            except OSError:
                continue
    per = {p: s for p, s in per.items() if s}
    total = sum(len(s) for s in per.values())
    lengths = sorted(len(x.split()) for s in per.values() for x in s)
    return {"scope": "changed" if changed else "all", "sentences": total,
            "median_words": lengths[len(lengths) // 2] if lengths else 0,
            "files": dict(sorted(per.items(), key=lambda kv: -len(kv[1])))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="explanatory sentences in the UI (USE-16)")
    ap.add_argument("--root", default=".")
    ap.add_argument("--changed", action="store_true", help="only what this branch adds vs main")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--limit", type=int, default=10, help="files listed in text mode")
    args = ap.parse_args(argv)
    r = report(Path(args.root).resolve(), args.changed)
    if args.format == "json":
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0
    print(f"uiprose ({r['scope']}): {r['sentences']} explanatory sentence(s) of "
          f"{MIN_WORDS}+ words, median {r['median_words']} words — judge each against USE-16")
    for path, items in list(r["files"].items())[: args.limit]:
        print(f"  {len(items):3}  {path}")
        if args.changed:
            for s in items:
                print(f"         {s[:140]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
