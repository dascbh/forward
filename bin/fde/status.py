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

HEADER = re.compile(r"^([A-Za-z_]+)\s*:\s*(.*)$")
DONE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([^\]]{0,3})\]\s*(.*)$")
BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
CYCLE_FILE = re.compile(r"^C-(\d+)\.md$", re.IGNORECASE)
END_KEYS = ("closed", "abandoned")
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
    """(heading, lines) per `##` section; the part before the first one
    has heading ''. Lines inside ``` fences are dropped."""
    out: list[tuple[str, list[str]]] = [("", [])]
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("##") and not line.startswith("###"):
            out.append((line[2:].strip(), []))
        else:
            out[-1][1].append(line)
    return out


def _mark(raw: str) -> str:
    """x met · - declined by the user · ' ' pending · anything else is shown
    as written and counts as pending."""
    m = raw.strip().lower()
    return m if m in ("x", "-") else (" " if not m else raw)


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
        self.legacy_next: list[str] = []
        self.misplaced_end: list[str] = []
        for heading, lines in sections[1:]:
            h = heading.lower()
            for line in lines:
                m = HEADER.match(line.strip())
                if m and m.group(1).lower() in END_KEYS and m.group(2).strip():
                    self.misplaced_end.append(m.group(1).lower())
            if h.startswith("done when"):
                for line in lines:
                    m = DONE.match(line)
                    if m:
                        self.done.append((_mark(m.group(1)), m.group(2).strip()))
            elif h.startswith("next cycle"):
                for line in lines:
                    m = BULLET.match(line)
                    if m:
                        self.legacy_next.append(m.group(1).strip())

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
    def pending(self) -> int:
        return sum(1 for mark, _ in self.done if mark not in ("x", "-"))

    @property
    def progress(self) -> str:
        met = sum(1 for mark, _ in self.done if mark == "x")
        declined = sum(1 for mark, _ in self.done if mark == "-")
        out = f"{met}/{len(self.done)} met"
        if declined:
            out += f", {declined} declined"
        if self.pending:
            out += f", {self.pending} pending"
        return out


def load_cycles(root: Path, problems: list[str]) -> list[Cycle]:
    d = root / "cycles"
    if not d.is_dir():
        return []
    try:
        entries = sorted(d.iterdir())
    except OSError as e:
        problems.append(f"cycles/ cannot be read: {e.strerror or e}")
        return []
    found = []
    for p in entries:
        if p.name.startswith(".") or not p.is_file():
            continue
        m = CYCLE_FILE.match(p.name)
        if not m:
            problems.append(f"cycles/{p.name} is not named C-<n>.md and is not read")
            continue
        found.append(Cycle(p, int(m.group(1))))
    seen: dict[str, int] = {}
    for c in found:
        seen[c.id] = seen.get(c.id, 0) + 1
    for cid, k in seen.items():
        if k > 1:
            problems.append(f"{k} files in cycles/ read as {cid}")
    return sorted(found, key=lambda c: c.n)


def load_backlog(root: Path) -> list[tuple[str, list[str]]] | None:
    """(section, [(shown, full)]) in file order; None when backlog.md is
    absent. `full` is the whole row, so a cycle named in any cell counts."""
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
                cells = [c.strip().replace("\\|", "|")
                         for c in re.split(r"(?<!\\)\|", s.strip().strip("|"))]
                if all(set(c) <= set("-: ") for c in cells):
                    continue  # separator
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt.startswith("|") and set(nxt) <= set("|-: "):
                    continue  # header row
                if len(cells) >= 2:
                    items.append((_clip(f"#{cells[0]} {cells[1]}"), s))
                continue
            m = BULLET.match(line)
            if m:
                items.append((_clip(m.group(1)), m.group(1)))
        if items:
            out.append((heading or "(before any section)", items))
    return out


def warnings(cycles: list[Cycle], backlog, problems: list[str]) -> list[str]:
    out = list(problems)
    open_ = [c for c in cycles if not c.ended]
    if len(open_) > 1:
        out.append(f"{len(open_)} cycles open: {', '.join(c.id for c in open_)}"
                   " — one runs to the end before another opens")
    for c in cycles:
        if not c.objective:
            out.append(f"{c.id} has no objective: line")
        for key in END_KEYS:
            if key in c.header and not c.header[key]:
                out.append(f"{c.id} has an empty {key}: line and still counts as open")
        if c.misplaced_end and not c.ended:
            out.append(f"{c.id} has a {c.misplaced_end[0]}: line below its header — "
                       "it counts only among the lines before the first ##")
        elif not c.ended and c.done and not c.pending:
            out.append(f"{c.id} has no pending done item but no closed: line")
        if c.legacy_next and not c.ended:
            out.append(f"{c.id} keeps a ## Next cycle list ({len(c.legacy_next)} "
                       "lines) — under AGENTS.md ## Cycle those lines belong in backlog.md")
    if backlog is None:
        out.append("no backlog.md — discoveries outside a cycle have nowhere to go")
    return out


def owned_lines(cid: str, backlog) -> list[str]:
    tok = cycle_token(cid)
    return [shown for heading, items in backlog or []
            for shown, full in items if tok.search(heading) or tok.search(full)]


def show_cycle(c: Cycle, backlog, title: str) -> list[str]:
    out = [f"{title} {c.id}" + (f" ({c.ended})" if c.ended else ""),
           f"  objective: {_clip(c.objective) or '—'}"]
    if c.header.get("demands"):
        out.append(f"  demands:   {_clip(c.header['demands'])}")
    out.append(f"  done when: {c.progress}")
    out += [f"    [{m}] {_clip(t)}" for m, t in c.done]
    owned = owned_lines(c.id, backlog)
    if owned:
        out.append(f"  backlog lines from {c.id}: {len(owned)}")
        out += [f"    - {t}" for t in owned]
    if c.legacy_next:
        out.append(f"  ## Next cycle (old format): {len(c.legacy_next)} lines")
        out += [f"    - {_clip(t)}" for t in c.legacy_next]
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
        out += [f"    - {shown}" for shown, _ in items]
    return out + [""]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle and backlog view")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    part = ap.add_mutually_exclusive_group()
    part.add_argument("--cycle", metavar="C-N", help="one cycle in full")
    part.add_argument("--backlog", action="store_true", help="backlog only")
    part.add_argument("--cycles", action="store_true", help="cycles only")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    root = Path(args.root)
    if not root.is_dir():
        print(f"status: --root {args.root} is not a directory", file=sys.stderr)
        return 2
    problems: list[str] = []
    cycles = load_cycles(root, problems)
    backlog = load_backlog(root)

    if args.cycle:
        match = [c for c in cycles if c.id.lower() == args.cycle.strip().lower()]
        if not match:
            print(f"status: no cycles/{args.cycle}.md", file=sys.stderr)
            return 2
        print("\n".join(show_cycle(match[0], backlog, "CYCLE")))
        return 0

    out = [f"WARNING {w}" for w in warnings(cycles, backlog, problems)]
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
