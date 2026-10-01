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


def run(root: Path, start_tab: str = "backlog") -> int:  # pragma: no cover — needs a terminal
    import curses
    import locale
    locale.setlocale(locale.LC_ALL, "")
    board = Board(root)
    return curses.wrapper(lambda scr: _loop(scr, board, start_tab))


class Panel:
    """The panel's state and its keys. Drawing needs curses; the keys do
    not, so `handle` is tested with a scripted prompt."""

    def __init__(self, board: Board, prompt, keys: dict | None = None):
        self.board, self.prompt = board, prompt
        self.collapsed: set[str] = set()
        self.selected: set[str] = set()
        self.cur, self.top, self.query, self.msg = 0, 0, "", "? for help"
        self.view: list[str] | None = None
        self.vtop, self.page = 0, 20
        k = keys or {}
        self.actions = {
            "j": self.down, k.get("down"): self.down, "k": self.up, k.get("up"): self.up,
            k.get("npage"): lambda r: self.move_cursor(self.page),
            k.get("ppage"): lambda r: self.move_cursor(-self.page),
            k.get("home"): lambda r: self.move_cursor(-10 ** 6),
            k.get("end"): lambda r: self.move_cursor(10 ** 6),
            "?": self.help, " ": self.toggle_select, "\x1b": self.clear,
            "\n": self.open, "\r": self.open, k.get("enter"): self.open,
            "/": self.search, "R": self.reload, "u": self.undo, "g": self.group,
            "m": self.merge, "d": self.discard, "r": self.restore,
            "J": lambda r: self.reorder(r, 1), "K": lambda r: self.reorder(r, -1),
            "e": self.edit, "s": self.specify,
        }
        self.actions.pop(None, None)

    @property
    def rows(self) -> list[Row]:
        return build_rows(self.board, self.collapsed, self.query)

    def handle(self, ch) -> bool:
        """Apply one key; False when the panel should close."""
        self.msg = ""
        if self.view is not None:
            if ch in ("q", "\x1b", "\n", "\r"):
                self.view = None
            elif ch in ("j", "k") or ch in self.actions and self.actions[ch] in (self.down, self.up):
                step = 1 if ch == "j" or self.actions.get(ch) == self.down else -1
                self.vtop = max(0, min(self.vtop + step, len(self.view) - 1))
            return True
        if ch == "q":
            return False
        rows = self.rows
        self.cur = max(0, min(self.cur, len(rows) - 1))
        action = self.actions.get(ch)
        if action:
            try:
                action(rows[self.cur] if rows else None)
            except BoardError as e:
                self.msg = str(e)
        return True

    @staticmethod
    def item_id(row: Row | None) -> str | None:
        return row.item.bid if row and row.kind == "item" and row.item else None

    def move_cursor(self, n):
        self.cur = max(0, min(self.cur + n, len(self.rows) - 1))

    def down(self, row):
        self.move_cursor(1)

    def up(self, row):
        self.move_cursor(-1)

    def help(self, row):
        self.view, self.vtop = HELP.split("\n"), 0

    def toggle_select(self, row):
        if row and row.kind == "item":
            self.selected ^= {row.key}
            self.move_cursor(1)

    def clear(self, row):
        self.selected.clear()
        self.query = ""

    def open(self, row):
        if row and row.kind in ("section", "cycles"):
            discarded = row.kind == "section" and self.board.sections[int(row.key[1:])].discarded
            self.collapsed ^= {f"+{row.key}" if discarded else row.key}
        elif row:
            self.view, self.vtop = detail(self.board, row), 0

    def search(self, row):
        q = self.prompt("/")
        if q is not None:
            self.query, self.cur = q, 0

    def reload(self, row):
        self.board.reload()
        self.msg = "reloaded"

    def undo(self, row):
        self.msg = self.board.undo()

    def group(self, row):
        ids = sorted(self.selected) or ([row.key] if row and row.kind == "item" else [])
        drafts = [c.id for c in self.board.cycles()
                  if c.header.get("state", "").lower() == "draft"]
        hint = f" (or a draft: {', '.join(drafts)})" if drafts else ""
        ans = self.prompt(f"objective for {self.board.next_cycle_id()}{hint}: ")
        if ans is not None:
            into = ans.strip() if ans.strip() in drafts else None
            self.msg = self.board.group(ids, "" if into else ans, into)
            self.selected.clear()

    def merge(self, row):
        self.msg = self.board.merge(sorted(self.selected))
        self.selected.clear()

    def discard(self, row):
        bid = self.item_id(row)
        reason = self.prompt(f"discard {bid} — reason: ") if bid else None
        if reason is not None:
            self.msg = self.board.discard(bid, reason)

    def restore(self, row):
        if self.item_id(row):
            self.msg = self.board.restore(self.item_id(row))

    def reorder(self, row, step):
        if self.item_id(row):
            self.msg = self.board.move(self.item_id(row), step)
            self.move_cursor(step)

    def edit(self, row):
        bid = self.item_id(row)
        text = self.prompt(f"{bid} ", row.item.text) if bid else None
        if text is not None:
            self.msg = self.board.edit(bid, text)

    def specify(self, row):
        if row and row.kind == "cycle":
            cmd = f"/fde-backlog specify {row.key}"
            self.msg = (f"copied: {cmd} — paste it to the agent" if clipboard(cmd)
                        else f"paste to the agent: {cmd}")


# -- progress tab: running cycles you can navigate (owner request 2026-10-01)
# Read-only. The same model and wording as `status.py --progress`
# (status.cycle_progress, progress_lines, demand_detail), so the two never
# disagree. Tab switches between the backlog and this tab.

class ProgressRow:
    def __init__(self, kind: str, key: str, text: str, depth: int = 0, demand=None):
        self.kind, self.key, self.text, self.depth, self.demand = kind, key, text, depth, demand


class Progress:
    """Cycles fold and unfold; a demand opens its detail. Keys are handled
    here, without curses, so they are tested with a scripted sequence."""

    REFRESH = 30  # seconds between automatic reloads

    def __init__(self, root: Path, clock=None):
        import time
        self.root, self.clock = Path(root), clock or time.time
        self.open: set[str] = set()
        self.cur, self.top = 0, 0
        self.view: list[str] | None = None
        self.vtop = 0
        self.loaded_at = 0.0
        self.cycles: list[dict] = []
        self.reload()
        if self.cycles:
            self.open.add(self.cycles[0]["id"])

    def reload(self) -> None:
        import status
        cycles = status.load_cycles(self.root, [])
        self.cycles = [status.cycle_progress(self.root, c) for c in cycles if c.state == "running"]
        self.loaded_at = self.clock()

    def maybe_refresh(self) -> bool:
        if self.clock() - self.loaded_at >= self.REFRESH:
            self.reload()
            return True
        return False

    def rows(self) -> list[ProgressRow]:
        import status
        now = int(self.clock())
        out = []
        for p in self.cycles:
            opened = p["id"] in self.open
            head = (f"{'▼' if opened else '▶'} {p['id']}  {status._cut(p['title'], 60)}"
                    + (f"   {status._dur(now - p['began'])}" if p["began"] else ""))
            if not opened:
                head += f"   {status.cycle_summary(p)}"
            out.append(ProgressRow("cycle", p["id"], head))
            if not opened:
                continue
            out.append(ProgressRow("info", p["id"], "cycle: " + status.phase_arrow(
                status.CYCLE_PHASES, p["phases_done"], p["current"]), 1))
            out.append(ProgressRow("info", p["id"], status.cycle_summary(p), 1))
            for d in p["demands"]:
                mark, phrase, _ = status.demand_status(d, now)
                out.append(ProgressRow("demand", d["id"],
                                       f"{mark} {d['id']:<9} {status._cut(d['what'] or '—', 44):<44}  {phrase}",
                                       1, d))
            for line in status.deploy_lines(p):
                out.append(ProgressRow("info", p["id"], line.strip(), 2 if line.startswith("    ") else 1))
            out.append(ProgressRow("info", p["id"], f"next: {status.cycle_next(p)}", 1))
        return out or [ProgressRow("info", "", "no running cycle")]

    def handle(self, ch) -> bool:
        """Apply one key; False to quit the panel."""
        import status
        if self.view is not None:
            if ch in ("q", "\x1b", "\n", "\r", "h", "left", "d"):
                self.view = None
            elif ch in ("j", "down"):
                self.vtop = min(self.vtop + 1, max(0, len(self.view) - 1))
            elif ch in ("k", "up"):
                self.vtop = max(0, self.vtop - 1)
            return True
        if ch == "q":
            return False
        rows = self.rows()
        self.cur = max(0, min(self.cur, len(rows) - 1))
        row = rows[self.cur]
        if ch in ("j", "down"):
            self.cur = min(self.cur + 1, len(rows) - 1)
        elif ch in ("k", "up"):
            self.cur = max(0, self.cur - 1)
        elif ch in ("\n", "\r", "l", "right", "d"):
            if row.kind == "cycle":
                self.open ^= {row.key}
            elif row.kind == "demand":
                self.view, self.vtop = status.demand_detail(row.demand, int(self.clock())), 0
        elif ch in ("h", "left"):
            if row.key in self.open:
                self.open.discard(row.key)
                self.cur = next(i for i, r in enumerate(self.rows())
                                if r.kind == "cycle" and r.key == row.key)
        elif ch == "r":
            self.reload()
        return True


def _loop(scr, board: Board, start_tab: str = "backlog") -> int:  # pragma: no cover — needs a terminal
    import curses
    curses.curs_set(0)
    curses.use_default_colors()
    try:
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
    except curses.error:
        pass

    def prompt(label: str, initial: str = "") -> str | None:
        curses.curs_set(1)
        buf = list(initial)
        while True:
            h, w = scr.getmaxyx()
            scr.move(h - 1, 0)
            scr.clrtoeol()
            scr.addnstr(h - 1, 0, f"{label}{''.join(buf)}"[-(w - 1):], w - 1)
            scr.refresh()
            ch = scr.get_wch()
            if ch in ("\n", "\r", curses.KEY_ENTER, "\x1b"):
                curses.curs_set(0)
                return None if ch == "\x1b" else "".join(buf)
            if ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                buf = buf[:-1]
            elif isinstance(ch, str) and ch.isprintable():
                buf.append(ch)

    panel = Panel(board, prompt, {"down": curses.KEY_DOWN, "up": curses.KEY_UP,
                                  "npage": curses.KEY_NPAGE, "ppage": curses.KEY_PPAGE,
                                  "home": curses.KEY_HOME, "end": curses.KEY_END,
                                  "enter": curses.KEY_ENTER})
    progress = Progress(board.root)
    tab = "progress" if start_tab == "progress" else "backlog"
    names = {curses.KEY_DOWN: "down", curses.KEY_UP: "up", curses.KEY_LEFT: "left",
             curses.KEY_RIGHT: "right", curses.KEY_ENTER: "\n"}
    scr.timeout(1000)
    while True:
        if tab == "progress":
            progress.maybe_refresh()
            _draw_progress(scr, progress, curses)
        else:
            _draw(scr, panel, curses)
        try:
            ch = scr.get_wch()
        except curses.error:
            continue  # timeout: redraw (and refresh the progress tab)
        if ch == "\t":
            tab = "backlog" if tab == "progress" else "progress"
            continue
        if tab == "progress":
            if not progress.handle(names.get(ch, ch)):
                return 0
        elif not panel.handle(ch):
            return 0


def _draw(scr, p: Panel, curses) -> None:  # pragma: no cover — needs a terminal
    h, w = scr.getmaxyx()
    p.page = max(1, h - 4)
    scr.erase()
    rows = p.rows
    p.cur = max(0, min(p.cur, len(rows) - 1))
    b = p.board
    head = (f" FORWARD · backlog {len(b.items(False))} · discarded {len(b.items(True))} · "
            f"next {b.next_cycle_id()}" + (" · read-only (table)" if b.table else "")
            + (f" · /{p.query}" if p.query else ""))
    scr.addnstr(0, 0, head.ljust(w - 1), w - 1, curses.A_REVERSE)
    if p.view is not None:
        for y, line in enumerate(p.view[p.vtop:p.vtop + h - 3], 1):
            scr.addnstr(y, 1, line, w - 2)
        foot = " j/k scroll · q/esc back"
    else:
        span = h - 3
        p.top = min(max(p.top, p.cur - span + 1), p.cur)
        for y, r in enumerate(rows[p.top:p.top + span], 1):
            here = p.top + y - 1 == p.cur
            attr = (curses.A_BOLD if r.kind in ("section", "cycles") else 0) \
                | (curses.color_pair(3) if r.item and r.item.discarded else 0) \
                | (curses.color_pair(1) if r.item and r.item.grouped else 0) \
                | (curses.A_REVERSE if here else 0)
            sel = ("[x] " if r.key in p.selected else "[ ] ") if r.kind == "item" else ""
            scr.addnstr(y, 0, ("> " if here else "  ") + "  " * r.depth + sel + r.text, w - 1, attr)
        foot = (f" {len(p.selected)} selected · g group · m merge · d discard · "
                "r restore · J/K reorder · e edit · u undo · / search · ? help · q quit")
    scr.addnstr(h - 2, 0, foot.ljust(w - 1), w - 1, curses.color_pair(3))
    scr.addnstr(h - 1, 0, p.msg[: w - 1], w - 1, curses.color_pair(2))
    scr.refresh()


def _draw_progress(scr, p: Progress, curses) -> None:  # pragma: no cover — needs a terminal
    import time
    h, w = scr.getmaxyx()
    scr.erase()
    head = (f" FORWARD · progress · ✓ done  ▸ now  · to come"
            f"   updated {time.strftime('%H:%M:%S', time.localtime(p.loaded_at))}")
    scr.addnstr(0, 0, head.ljust(w - 1), w - 1, curses.A_REVERSE)
    if p.view is not None:
        import textwrap
        wrapped = [part for line in p.view
                   for part in (textwrap.wrap(line, w - 4, subsequent_indent="      ") or [""])]
        p.vtop = min(p.vtop, max(0, len(wrapped) - 1))
        for y, line in enumerate(wrapped[p.vtop:p.vtop + h - 3], 1):
            scr.addnstr(y, 1, line, w - 2)
        foot = " j/k scroll · h/←/q back"
    else:
        rows = p.rows()
        p.cur = max(0, min(p.cur, len(rows) - 1))
        span = h - 3
        p.top = min(max(p.top, p.cur - span + 1), p.cur)
        for y, r in enumerate(rows[p.top:p.top + span], 1):
            here = p.top + y - 1 == p.cur
            attr = (curses.A_BOLD if r.kind == "cycle" else 0) \
                | (curses.color_pair(3) if r.kind == "info" else 0) \
                | (curses.A_REVERSE if here else 0)
            scr.addnstr(y, 0, ("❯ " if here else "  ") + "  " * r.depth + r.text, w - 1, attr)
        foot = (" j/k move · enter/→ open · ← close · d demand detail · r refresh "
                f"(auto {p.REFRESH}s) · Tab backlog · q quit")
    scr.addnstr(h - 2, 0, foot.ljust(w - 1), w - 1, curses.color_pair(3))
    scr.refresh()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="interactive backlog panel")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    ap.add_argument("--progress", action="store_true",
                    help="open on the progress tab (running cycles); Tab switches")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not (root / "backlog.md").is_file():
        print(f"backlog: no backlog.md in {root.resolve()}", file=sys.stderr)
        return 2
    if not sys.stdout.isatty():
        print("backlog: needs a terminal — run it in your own shell; "
              "`status.py --panel` prints the same data", file=sys.stderr)
        return 2
    return run(root, "progress" if args.progress else "backlog")


if __name__ == "__main__":
    sys.exit(main())
