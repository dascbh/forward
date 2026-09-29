#!/usr/bin/env python3
"""
backlog — the interactive backlog panel (owner request, 2026-09-29).

Runs in the owner's own terminal, beside the agent:

    python3 bin/fde/backlog.py [--root .]

Two layers. `Board` reads and edits backlog.md and cycles/ with no
terminal, so every write is tested. The curses UI on top only moves a
cursor and calls Board. Mechanical actions write the files at once:
group items into a draft cycle, merge items, discard, restore, move,
edit. Judgment stays with the agent: `s` on a draft copies the
`/fde-backlog specify C-<n>` command to paste into the conversation.

Writes cover bullet backlogs (`- B-<n> text`), the format every project
uses. A backlog written as a table is shown read-only. Only main assigns
ids (AGENTS.md ## Backlog): the panel never creates one; merge keeps the
first id and retires the others. The panel does not commit; git stays
the owner's.

stdlib only (curses ships with Python on macOS and Linux) — I6.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status  # noqa: E402

BULLET = re.compile(r"^(\s*[-*+]\s+)(\[[^\]]{0,3}\]\s*)?(.*)$")
ITEM_ID = re.compile(r"^[`*]*(B-\d+)[`*]*(?![\w-])\s*[:.)—-]?\s*(.*)$")
GROUP_MARK = status.GROUP_MARK
DISCARD = status.DISCARD


class BoardError(Exception):
    """An action the panel refuses; the message goes to the status line."""


@dataclass
class Item:
    bid: str | None
    text: str
    start: int            # first line of the item's block in backlog.md
    end: int              # one past its last line (continuation lines)
    section: int
    discarded: bool
    grouped: str | None   # `→ C-<n>` mark

    @property
    def label(self) -> str:
        return f"{self.bid} {self.text}" if self.bid else self.text


@dataclass
class Section:
    heading: str
    line: int             # index of the `## ` line; -1 for the preamble
    discarded: bool
    items: list[Item] = field(default_factory=list)


class Board:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "backlog.md"
        self.undo_stack: list[dict[Path, str | None]] = []
        self.reload()

    # -- reading -------------------------------------------------------------
    def reload(self) -> None:
        """Re-read backlog.md from disk (after the agent or git changed it)."""
        text = self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        self.lines = text.split("\n")
        self._parse()

    def _parse(self) -> None:
        """Index the lines in memory: sections and item blocks."""
        self.table = False
        self.sections: list[Section] = [Section("", -1, False)]
        fenced = False
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            if line.lstrip().startswith("```"):
                fenced = not fenced
            elif not fenced and line.startswith("##") and not line.startswith("###"):
                h = line[2:].strip()
                self.sections.append(Section(h, i, status._discarded(h)))
            elif not fenced and re.match(r"^\s*\|\s*[`*]*B-\d+", line):
                self.table = True
            elif not fenced and self.sections[-1].line >= 0:
                m = BULLET.match(line)
                if m and not line.startswith(" "):
                    j = i + 1
                    while (j < len(self.lines) and self.lines[j].startswith("  ")
                           and self.lines[j].strip()):
                        j += 1
                    rest = m.group(3)
                    idm = ITEM_ID.match(rest)
                    bid, body = (idm.group(1), idm.group(2)) if idm else (None, rest)
                    g = GROUP_MARK.search(body)
                    sec = self.sections[-1]
                    sec.items.append(Item(bid, body, i, j, len(self.sections) - 1,
                                          sec.discarded, g.group(1) if g else None))
                    i = j
                    continue
            i += 1

    def items(self, discarded: bool | None = None) -> list[Item]:
        return [it for s in self.sections for it in s.items
                if discarded is None or it.discarded == discarded]

    def find(self, bid: str) -> Item:
        for it in self.items():
            if it.bid == bid:
                return it
        raise BoardError(f"{bid} is not in backlog.md")

    def cycles(self):
        return status.load_cycles(self.root, [])

    def next_cycle_id(self) -> str:
        return status.next_ids(self.root, self.cycles())["cycle_id"]

    # -- writing -------------------------------------------------------------
    def _writable(self) -> None:
        if self.table:
            raise BoardError("backlog.md is a table — the panel writes bullet "
                             "backlogs only; ask the agent")
        if not self.path.is_file():
            raise BoardError("no backlog.md here")

    def _snapshot(self, *extra: Path) -> None:
        snap = {self.path: "\n".join(self.lines)}
        for p in extra:
            snap[p] = p.read_text(encoding="utf-8") if p.is_file() else None
        self.undo_stack.append(snap)
        del self.undo_stack[:-50]

    def _save(self) -> None:
        self.path.write_text("\n".join(self.lines), encoding="utf-8")
        self.reload()

    def undo(self) -> str:
        if not self.undo_stack:
            raise BoardError("nothing to undo")
        for p, text in self.undo_stack.pop().items():
            if text is None:
                if p.is_file():
                    p.unlink()
                    if p.parent != self.root and not any(p.parent.iterdir()):
                        p.parent.rmdir()
            else:
                p.write_text(text, encoding="utf-8")
        self.reload()
        return "undone"

    def _open_items(self, bids: list[str], verb: str) -> list[Item]:
        items = [self.find(b) for b in bids]
        for it in items:
            if it.discarded:
                raise BoardError(f"{it.bid} is discarded — restore it first")
        return sorted(items, key=lambda it: it.start)

    def group(self, bids: list[str], objective: str = "",
              into: str | None = None) -> str:
        """Put items into a draft cycle: a new cycles/C-<n>/plan.md, or the
        `## Items` of an existing draft (the fde-backlog `group` action)."""
        self._writable()
        if not bids:
            raise BoardError("select items first (space)")
        items = self._open_items(bids, "group")
        for it in items:
            if not it.bid:
                raise BoardError("an item without an id cannot be grouped — "
                                 "ids are assigned on main (fde-backlog §3)")
            if it.grouped:
                raise BoardError(f"{it.bid} is already in {it.grouped}")
        lines = [f"- {it.bid} {GROUP_MARK.sub('', it.text).rstrip()}" for it in items]
        if into:
            cyc = next((c for c in self.cycles() if c.id == into), None)
            if cyc is None:
                raise BoardError(f"no cycle {into}")
            if cyc.header.get("state", "").lower() != "draft":
                raise BoardError(f"{into} is not a draft")
            plan = cyc.path / "plan.md" if cyc.path.is_dir() else cyc.path
            self._snapshot(plan)
            text = plan.read_text(encoding="utf-8").rstrip("\n")
            if "\n## Items" not in "\n" + text:
                text += "\n\n## Items\n"
            plan.write_text(_append_to_section(text, "Items", lines) + "\n",
                            encoding="utf-8")
            cid = into
        else:
            if not objective.strip():
                raise BoardError("a new draft needs an objective")
            cid = self.next_cycle_id()
            plan = self.root / "cycles" / cid / "plan.md"
            self._snapshot(plan)
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(f"# {cid}\n\nstate: draft\nobjective: {objective.strip()}"
                            "\n\n## Items\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        for it in items:
            self.lines[it.start] = self.lines[it.start].rstrip() + f" → {cid}"
        self._save()
        return f"{len(items)} item(s) → {cid}"

    def merge(self, bids: list[str]) -> str:
        """Fold items into the first (file order): it keeps its id and gains
        the others' texts; each other id is retired to Discarded as
        `merged into B-<k>`."""
        self._writable()
        items = self._open_items(bids, "merge")
        if len(items) < 2:
            raise BoardError("select two or more items to merge")
        if any(not it.bid for it in items):
            raise BoardError("every merged item needs an id")
        if any(it.grouped for it in items):
            raise BoardError("a grouped item stays as its cycle lists it")
        keep, rest = items[0], items[1:]
        self._snapshot()
        extra = "; ".join(f"{it.bid}: {it.text.strip()}" for it in rest)
        self.lines[keep.start] = self.lines[keep.start].rstrip() + f" [merged {extra}]"
        self._parse()
        for bid in [it.bid for it in rest]:
            self._move_to_discarded(self.find(bid), f"merged into {keep.bid}")
        self._save()
        return f"{', '.join(it.bid for it in rest)} merged into {keep.bid}"

    def discard(self, bid: str, reason: str) -> str:
        self._writable()
        it = self._open_items([bid], "discard")[0]
        if not reason.strip():
            raise BoardError("a discard needs a reason")
        self._snapshot()
        self._move_to_discarded(it, reason.strip())
        self._save()
        return f"{bid} discarded"

    def restore(self, bid: str) -> str:
        self._writable()
        it = self.find(bid)
        if not it.discarded:
            raise BoardError(f"{bid} is not discarded")
        target = next((s for s in self.sections
                       if s.line >= 0 and not s.discarded), None)
        if target is None:
            raise BoardError("no backlog section to restore into")
        self._snapshot()
        block = self.lines[it.start:it.end]
        block[0] = DISCARD.split(block[0], maxsplit=1)[0].rstrip()
        del self.lines[it.start:it.end]
        self._parse()
        target = next(s for s in self.sections if s.line >= 0 and not s.discarded)
        at = (target.items[-1].end if target.items else target.line + 2)
        self.lines[at:at] = block
        self._save()
        return f"{bid} restored to '{target.heading}'"

    def move(self, bid: str, delta: int) -> str:
        """Swap an item with its neighbour in the same section: the file
        order is the owner's priority."""
        self._writable()
        it = self.find(bid)
        items = self.sections[it.section].items
        k = items.index(it)
        j = k + delta
        if not 0 <= j < len(items):
            raise BoardError("already at the edge of its section")
        a, b = sorted((items[k], items[j]), key=lambda x: x.start)
        self._snapshot()
        ablock, bblock = self.lines[a.start:a.end], self.lines[b.start:b.end]
        between = self.lines[a.end:b.start]
        self.lines[a.start:b.end] = bblock + between + ablock
        self._save()
        return f"{bid} moved {'up' if delta < 0 else 'down'}"

    def edit(self, bid: str, text: str) -> str:
        self._writable()
        it = self.find(bid)
        if not text.strip():
            raise BoardError("empty text — discard it instead")
        self._snapshot()
        m = BULLET.match(self.lines[it.start])
        prefix = m.group(1) + (m.group(2) or "")
        self.lines[it.start] = f"{prefix}{it.bid} {text.strip()}" if it.bid \
            else f"{prefix}{text.strip()}"
        self._save()
        return f"{bid} edited"

    def _move_to_discarded(self, it: Item, reason: str) -> None:
        block = self.lines[it.start:it.end]
        block[0] = block[0].rstrip() + f" — discarded: {reason}"
        del self.lines[it.start:it.end]
        self._parse()
        sec = next((s for s in self.sections if s.discarded), None)
        if sec is None:
            while self.lines and not self.lines[-1].strip():
                self.lines.pop()
            self.lines += ["", "## Discarded", ""]
            at = len(self.lines)
        else:
            at = sec.items[-1].end if sec.items else sec.line + 2
        self.lines[at:at] = block
        self._parse()


def _append_to_section(text: str, heading: str, new: list[str]) -> str:
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == f"## {heading}")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    if end == start + 1:
        new = [""] + new
    lines[end:end] = new
    return "\n".join(lines)


# -- rows: what the screen lists (pure, tested) -------------------------------

@dataclass
class Row:
    kind: str             # section | item | cycles | cycle
    text: str
    key: str              # section index, B-id, or C-id
    depth: int = 0
    item: Item | None = None


def build_rows(board: Board, collapsed: set[str], query: str = "") -> list[Row]:
    rows: list[Row] = []
    q = query.lower()
    for i, s in enumerate(board.sections):
        if s.line < 0 or not s.items:
            continue
        key = f"s{i}"
        shown = [it for it in s.items if not q or q in it.label.lower()]
        if q and not shown:
            continue
        open_ = key not in collapsed if not s.discarded else f"+{key}" in collapsed
        mark = "▾" if open_ or q else "▸"
        rows.append(Row("section", f"{mark} {s.heading} ({len(s.items)})", key))
        if open_ or q:
            rows += [Row("item", it.label, it.bid or f"L{it.start}", 1, it)
                     for it in shown]
    cycles = board.cycles()
    if cycles and not q:
        open_ = "cycles" not in collapsed
        rows.append(Row("cycles", f"{'▾' if open_ else '▸'} Cycles ({len(cycles)})",
                        "cycles"))
        if open_:
            for c in sorted(cycles, key=lambda c: -c.n):
                state = c.header.get("state", "?")
                obj = c.header.get("objective", "")
                rows.append(Row("cycle", f"{c.id} · {state} · {obj}", c.id, 1))
    return rows


def detail(board: Board, row: Row) -> list[str]:
    if row.kind == "item" and row.item:
        it = row.item
        out = [it.bid or "(no id)", ""]
        out += board.lines[it.start:it.end]
        out += ["", f"section: {board.sections[it.section].heading}"]
        if it.grouped:
            out.append(f"grouped into {it.grouped}")
        return out
    if row.kind == "cycle":
        root = board.root
        cycles = board.cycles()
        c = next(c for c in cycles if c.id == row.key)
        backlog = status.load_backlog(root, [])
        demands = status.load_demands(root, cycles, [])
        return status.show_cycle(c, backlog, "CYCLE", demands)
    return [row.text]


# -- the terminal UI -----------------------------------------------------------

HELP = """\
move      j/k ↓/↑   PgDn/PgUp   Home/End
select    space  (esc clears)
open      enter  expand a section, open an item or cycle
search    /  then text, enter; esc clears
group     g  selected items → new draft cycle, or an existing draft
merge     m  selected items fold into the first; others retire
discard   d  with a reason          restore   r  (a discarded item)
reorder   J / K  move the item down / up in its section
edit      e  the item's text        undo      u
specify   s  on a draft: copies `/fde-backlog specify C-<n>` for the agent
reload    R  (after the agent or git changed the files)
quit      q"""


def clipboard(text: str) -> bool:
    for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text, text=True, check=False)
            return True
    return False


def run(root: Path) -> int:  # pragma: no cover — needs a terminal
    import curses
    import locale
    locale.setlocale(locale.LC_ALL, "")
    board = Board(root)
    return curses.wrapper(lambda scr: _loop(scr, board))


def _loop(scr, board: Board) -> int:  # pragma: no cover — needs a terminal
    import curses
    curses.curs_set(0)
    curses.use_default_colors()
    try:
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    except curses.error:
        pass
    collapsed: set[str] = set()
    selected: set[str] = set()
    cur, top, query, msg = 0, 0, "", "? for help"
    view: list[str] | None = None
    vtop = 0

    def prompt(label: str, initial: str = "") -> str | None:
        curses.curs_set(1)
        buf = list(initial)
        while True:
            h, w = scr.getmaxyx()
            scr.move(h - 1, 0)
            scr.clrtoeol()
            line = f"{label}{''.join(buf)}"
            scr.addnstr(h - 1, 0, line[-(w - 1):], w - 1)
            scr.refresh()
            ch = scr.get_wch()
            if ch in ("\n", "\r", curses.KEY_ENTER):
                curses.curs_set(0)
                return "".join(buf)
            if ch == "\x1b":
                curses.curs_set(0)
                return None
            if ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                if buf:
                    buf.pop()
            elif isinstance(ch, str) and ch.isprintable():
                buf.append(ch)

    while True:
        h, w = scr.getmaxyx()
        scr.erase()
        rows = build_rows(board, collapsed, query)
        cur = max(0, min(cur, len(rows) - 1))
        n_back = len(board.items(False))
        n_disc = len(board.items(True))
        head = (f" FORWARD · backlog {n_back} · discarded {n_disc} · "
                f"next {board.next_cycle_id()}"
                + (" · read-only (table)" if board.table else "")
                + (f" · /{query}" if query else ""))
        scr.addnstr(0, 0, head.ljust(w - 1), w - 1, curses.A_REVERSE)
        if view is not None:
            body = view[vtop:vtop + h - 3]
            for y, line in enumerate(body, 1):
                scr.addnstr(y, 1, line, w - 2)
            scr.addnstr(h - 2, 0, " j/k scroll · q/esc back".ljust(w - 1), w - 1,
                        curses.color_pair(3))
        else:
            span = h - 3
            if cur < top:
                top = cur
            if cur >= top + span:
                top = cur - span + 1
            for y, r in enumerate(rows[top:top + span], 1):
                i = top + y - 1
                attr = curses.A_BOLD if r.kind in ("section", "cycles") else 0
                if r.item and r.item.discarded:
                    attr |= curses.color_pair(3)
                if r.item and r.item.grouped:
                    attr |= curses.color_pair(1)
                sel = "[x]" if r.key in selected else "[ ]" if r.kind == "item" else "   "
                text = ("  " * r.depth) + (sel + " " if r.kind == "item" else "") + r.text
                if i == cur:
                    attr |= curses.A_REVERSE
                scr.addnstr(y, 0, ("> " if i == cur else "  ") + text, w - 1, attr)
            foot = (f" {len(selected)} selected · g group · m merge · d discard · "
                    "r restore · J/K reorder · e edit · u undo · / search · ? help · q quit")
            scr.addnstr(h - 2, 0, foot.ljust(w - 1), w - 1, curses.color_pair(3))
        scr.addnstr(h - 1, 0, msg[: w - 1], w - 1, curses.color_pair(2))
        scr.refresh()

        ch = scr.get_wch()
        msg = ""
        if view is not None:
            if ch in ("q", "\x1b", "\n", "\r"):
                view = None
            elif ch in ("j", curses.KEY_DOWN):
                vtop = min(vtop + 1, max(0, len(view) - 1))
            elif ch in ("k", curses.KEY_UP):
                vtop = max(0, vtop - 1)
            continue
        row = rows[cur] if rows else None
        try:
            if ch == "q":
                return 0
            elif ch in ("j", curses.KEY_DOWN):
                cur += 1
            elif ch in ("k", curses.KEY_UP):
                cur -= 1
            elif ch == curses.KEY_NPAGE:
                cur += h - 4
            elif ch == curses.KEY_PPAGE:
                cur -= h - 4
            elif ch == curses.KEY_HOME:
                cur = 0
            elif ch == curses.KEY_END:
                cur = len(rows) - 1
            elif ch == curses.KEY_RESIZE:
                pass
            elif ch == "?":
                view, vtop = HELP.split("\n"), 0
            elif ch == " " and row and row.kind == "item":
                selected ^= {row.key}
                cur += 1
            elif ch == "\x1b":
                selected.clear()
                query = ""
            elif ch in ("\n", "\r", curses.KEY_ENTER):
                if row and row.kind in ("section", "cycles"):
                    k = row.key
                    sec_disc = row.kind == "section" and \
                        board.sections[int(k[1:])].discarded
                    flag = f"+{k}" if sec_disc else k
                    collapsed ^= {flag}
                elif row:
                    view, vtop = detail(board, row), 0
            elif ch == "/":
                q = prompt("/")
                if q is not None:
                    query, cur = q, 0
            elif ch == "R":
                board.reload()
                msg = "reloaded"
            elif ch == "u":
                msg = board.undo()
            elif ch == "g":
                ids = sorted(selected) or ([row.key] if row and row.kind == "item" else [])
                drafts = [c.id for c in board.cycles()
                          if c.header.get("state", "").lower() == "draft"]
                hint = f" (or a draft: {', '.join(drafts)})" if drafts else ""
                ans = prompt(f"objective for {board.next_cycle_id()}{hint}: ")
                if ans is not None:
                    into = ans.strip() if ans.strip() in drafts else None
                    msg = board.group(ids, "" if into else ans, into)
                    selected.clear()
            elif ch == "m":
                msg = board.merge(sorted(selected))
                selected.clear()
            elif ch == "d" and row and row.kind == "item" and row.item.bid:
                reason = prompt(f"discard {row.item.bid} — reason: ")
                if reason is not None:
                    msg = board.discard(row.item.bid, reason)
            elif ch == "r" and row and row.kind == "item" and row.item.bid:
                msg = board.restore(row.item.bid)
            elif ch in ("J", "K") and row and row.kind == "item" and row.item.bid:
                msg = board.move(row.item.bid, 1 if ch == "J" else -1)
                cur += 1 if ch == "J" else -1
            elif ch == "e" and row and row.kind == "item" and row.item.bid:
                text = prompt(f"{row.item.bid} ", row.item.text)
                if text is not None:
                    msg = board.edit(row.item.bid, text)
            elif ch == "s" and row and row.kind == "cycle":
                cmd = f"/fde-backlog specify {row.key}"
                msg = (f"copied: {cmd} — paste it to the agent" if clipboard(cmd)
                       else f"paste to the agent: {cmd}")
        except BoardError as e:
            msg = str(e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="interactive backlog panel")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not (root / "backlog.md").is_file():
        print(f"backlog: no backlog.md in {root.resolve()}", file=sys.stderr)
        return 2
    if not sys.stdout.isatty():
        print("backlog: needs a terminal — run it in your own shell; "
              "`status.py --panel` prints the same data", file=sys.stderr)
        return 2
    return run(root)


if __name__ == "__main__":
    sys.exit(main())
