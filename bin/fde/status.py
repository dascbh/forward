#!/usr/bin/env python3
"""
status — the cycle and backlog view (FWD-024).

Reads `cycles/C-<n>.md` and `backlog.md` and prints where the project
stands: the open cycle with its done progress and the backlog lines it
produced, every closed cycle on one line, then the backlog by section.
Warnings come first.

A report, never a gate (ADR-0018): exit 0 on any content, exit 2 only for
a bad argument. Read-only, stdlib only, no git.

  python3 bin/fde/status.py              # everything
  python3 bin/fde/status.py --cycle C-3  # one cycle in full
  python3 bin/fde/status.py --backlog    # backlog only
  python3 bin/fde/status.py --cycles     # cycles only
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^([A-Za-z_]+):\s*(.*)$")
DONE = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s*(.*)$")
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
CYCLE_FILE = re.compile(r"^C-(\d+)\.md$")
WIDTH = 110


def _read(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= WIDTH else text[:WIDTH - 1] + "…"


def _sections(text: str) -> list[tuple[str, list[str]]]:
    """(heading, lines) per `## ` section; the part before the first one
    has heading ''."""
    out: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((line[3:].strip(), []))
        else:
            out[-1][1].append(line)
    return out


def cycle_token(cid: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(cid) + r"(?!\d)")


class Cycle:
    def __init__(self, path: Path, n: int):
        self.id, self.n = f"C-{n}", n
        text = _read(path)
        sections = _sections(text)
        self.header: dict[str, str] = {}
        for line in sections[0][1]:
            m = HEADER.match(line.strip())
            if m:
                self.header.setdefault(m.group(1).lower(), m.group(2).strip())
        self.done: list[tuple[str, str]] = []
        for heading, lines in sections[1:]:
            if heading.lower().startswith("done when"):
                for line in lines:
                    m = DONE.match(line)
                    if m:
                        self.done.append((m.group(1).lower(), m.group(2).strip()))

    @property
    def objective(self) -> str:
        return self.header.get("objective", "")

    @property
    def ended(self) -> str:
        if self.header.get("closed"):
            return "closed " + self.header["closed"]
        if self.header.get("abandoned"):
            return "abandoned " + self.header["abandoned"]
        return ""

    @property
    def progress(self) -> str:
        met = sum(1 for mark, _ in self.done if mark == "x")
        return f"{met}/{len(self.done)}"


def load_cycles(root: Path) -> list[Cycle]:
    d = root / "cycles"
    if not d.is_dir():
        return []
    found = []
    for p in d.iterdir():
        m = CYCLE_FILE.match(p.name)
        if m and p.is_file():
            found.append(Cycle(p, int(m.group(1))))
    return sorted(found, key=lambda c: c.n)


def load_backlog(root: Path) -> list[tuple[str, list[str]]] | None:
    """(section, items) in file order; None when backlog.md is absent."""
    p = root / "backlog.md"
    if not p.is_file():
        return None
    text = _read(p)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[end + 4:] if end != -1 else text
    out = []
    for heading, lines in _sections(text):
        items = []
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("|"):
                cells = [c.strip() for c in s.strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):
                    continue  # separator
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt.startswith("|") and set(nxt) <= set("|-: "):
                    continue  # header row
                if len(cells) >= 2:
                    items.append(_clip(f"#{cells[0]} {cells[1]}"))
                continue
            m = BULLET.match(line)
            if m:
                items.append(_clip(m.group(1)))
        if items:
            out.append((heading or "(top)", items))
    return out


def warnings(cycles: list[Cycle], backlog) -> list[str]:
    out = []
    open_ = [c for c in cycles if not c.ended]
    if len(open_) > 1:
        out.append(f"{len(open_)} cycles open: {', '.join(c.id for c in open_)}"
                   " — one runs to the end before another opens")
    for c in cycles:
        if not c.objective:
            out.append(f"{c.id} has no objective: line")
        if not c.ended and c.done and all(m == "x" for m, _ in c.done):
            out.append(f"{c.id} has every done item met but no closed: line")
    if backlog is None:
        out.append("no backlog.md — discoveries outside a cycle have nowhere to go")
    return out


def owned_lines(cid: str, backlog) -> list[str]:
    tok = cycle_token(cid)
    return [item for heading, items in backlog or []
            for item in items if tok.search(heading) or tok.search(item)]


def show_cycle(c: Cycle, backlog, title: str) -> list[str]:
    out = [f"{title} {c.id}" + (f" ({c.ended})" if c.ended else ""),
           f"  objective: {_clip(c.objective) or '—'}"]
    if c.header.get("demands"):
        out.append(f"  demands:   {_clip(c.header['demands'])}")
    out.append(f"  done when: {c.progress} done")
    out += [f"    [{m}] {_clip(t)}" for m, t in c.done]
    owned = owned_lines(c.id, backlog)
    if owned:
        out.append(f"  backlog lines from {c.id}: {len(owned)}")
        out += [f"    - {t}" for t in owned]
    return out


def show_cycles(cycles: list[Cycle], backlog) -> list[str]:
    open_ = [c for c in cycles if not c.ended]
    out = []
    for c in open_:
        out += show_cycle(c, backlog, "OPEN CYCLE") + [""]
    if not open_:
        out += ["no open cycle", ""]
    ended = [c for c in cycles if c.ended]
    if ended:
        out.append("CYCLES")
        out += [f"  {c.id}  {c.ended}  {c.progress}  {_clip(c.objective)}"
                for c in reversed(ended)]
        out.append("")
    return out


def show_backlog(backlog) -> list[str]:
    if backlog is None:
        return ["BACKLOG", "  (no backlog.md)", ""]
    total = sum(len(items) for _, items in backlog)
    out = [f"BACKLOG ({total} items)"]
    for heading, items in backlog:
        out.append(f"  {heading}")
        out += [f"    - {t}" for t in items]
    return out + [""]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle and backlog view")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    part = ap.add_mutually_exclusive_group()
    part.add_argument("--cycle", metavar="C-N", help="one cycle in full")
    part.add_argument("--backlog", action="store_true", help="backlog only")
    part.add_argument("--cycles", action="store_true", help="cycles only")
    args = ap.parse_args(argv)

    root = Path(args.root)
    cycles = load_cycles(root)
    backlog = load_backlog(root)

    if args.cycle:
        match = [c for c in cycles if c.id.lower() == args.cycle.strip().lower()]
        if not match:
            print(f"status: no cycles/{args.cycle}.md", file=sys.stderr)
            return 2
        print("\n".join(show_cycle(match[0], backlog, "CYCLE")))
        return 0

    out = [f"WARNING {w}" for w in warnings(cycles, backlog)]
    if out:
        out.append("")
    if not args.backlog:
        out += show_cycles(cycles, backlog)
    if not args.cycles:
        out += show_backlog(backlog)
    sys.stdout.write("\n".join(out).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
