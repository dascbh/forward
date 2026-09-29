#!/usr/bin/env python3
"""
status — the cycle and backlog view (FWD-024, FWD-027).

Reads the cycles — a directory `cycles/C-<n>/` whose `plan.md` holds the
header lines, or the old single file `cycles/C-<n>.md` — and `backlog.md`,
and prints where the project stands: the running cycle with its done
progress, demands, artifacts and the backlog lines it produced, drafts and
planned cycles on one line each, every ended cycle on one line, then the
backlog by section with its `B-<n>` ids. Warnings come first.

A cycle's state (ADR-0019 rule 9): a `closed:` or `abandoned:` header line
with a value ends it, whatever `state:` says (a disagreement warns);
otherwise the first word of `state:` decides; otherwise it is running.
More than one running cycle is a warning; drafts may be many. A directory
cycle's progress is plan.md's acceptance criteria against promotion.md
(`- A1 — <evidence> — met`).

A draft's `## Items` (the B-ids fde-backlog grouped) are read; a backlog
item marked `→ C-<n>` is grouped into that cycle, and one B-id in two
cycles warns. `next` gives the next free ids: B-<n> one more than the
highest seen in backlog.md or any cycle, C-<n> one more than the highest
directory or old file.

A report, never a gate (ADR-0018): exit 0 on any content, exit 2 only for
a bad argument. Read-only, stdlib only, no git.

  python3 bin/fde/status.py              # everything
  python3 bin/fde/status.py --cycle C-3  # one cycle in full
  python3 bin/fde/status.py --backlog    # backlog only
  python3 bin/fde/status.py --cycles     # cycles only
  python3 bin/fde/status.py --format json  # the same content as JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^([A-Za-z_]+)\s*:\s*(.*)$")
DONE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([^\]]{0,3})\]\s*(.*)$")
BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
CYCLE_FILE = re.compile(r"^C-(\d+)\.md$", re.IGNORECASE)
CYCLE_DIR = re.compile(r"^C-(\d+)$", re.IGNORECASE)
END_KEYS = ("closed", "abandoned")
STATES = ("draft", "planned", "running", "closed", "abandoned")
ARTIFACTS = ("plan.md", "deploy.md", "board.md", "review.md", "promotion.md")
BACKLOG_ID = re.compile(r"^[`*]*(B-\d+)[`*]*(?![\w-])\s*[:.)\u2014-]?\s*(.*)$")
ID_CELL = re.compile(r"[`*]*(B-\d+)[`*]*")
ID_LIKE = re.compile(r"(?<![\w-])B-\d+")
CHECKBOX = re.compile(r"^\[[^\]]{0,3}\]\s*")
LOOSE_ID = re.compile(r"^(?:#+|\d+[.)])\s*(?:\[[^\]]{0,3}\]\s*)?[`*]*(B-\d+)")
CRITERION = re.compile(r"^[-*+]\s+[`*]*([A-Z]+\d+)\b")
DEMAND_ID = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")
# grouping marks a backlog item with the cycle it went into: `→ C-<n>`
GROUP_MARK = re.compile(r"(?:\u2192|->)\s*(C-\d+)(?!\d)")
ANY_B_ID = re.compile(r"(?<![\w-])B-(\d+)(?!\d)")
NONE_CELL = {"", "-", "\u2014", "\u2013", "none", "n/a"}
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


def _cells(row: str) -> list[str]:
    return [c.strip().replace("\\|", "|")
            for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


def _is_separator(row: str) -> bool:
    return set(row.strip()) <= set("|-: ")


def _demands_table(lines: list[str]) -> list[dict]:
    """Rows of the plan's `## Demands` table: id, layer, depends on. Columns
    are found by their header names; without a header the first cell is the
    id."""
    rows = [line.strip() for line in lines if line.strip().startswith("|")]
    cols: dict[str, int | None] = {"id": 0, "layer": None, "depends": None}
    if len(rows) > 1 and _is_separator(rows[1]):
        for i, name in enumerate(c.lower() for c in _cells(rows[0])):
            if name == "id":
                cols["id"] = i
            elif name == "layer":
                cols["layer"] = i
            elif name.startswith("depends"):
                cols["depends"] = i
        rows = rows[2:]
    out = []
    for row in rows:
        if _is_separator(row):
            continue
        cells = _cells(row)

        def cell(key):
            i = cols[key]
            return cells[i].strip("`* ") if i is not None and i < len(cells) else ""
        did = cell("id")
        if not did:
            continue
        dep = cell("depends")
        deps = [] if dep.lower() in NONE_CELL else \
            [d.strip("`* ") for d in re.split(r"[,;]", dep) if d.strip("`* ")]
        out.append({"id": did, "layer": cell("layer"), "depends_on": deps})
    return out


class Cycle:
    def __init__(self, path: Path, n: int, directory: Path | None = None):
        self.id, self.n = f"C-{n}", n
        self.layout = "directory" if directory else "file"
        self.path = directory or path
        self.artifacts = [a for a in ARTIFACTS
                          if directory and (directory / a).is_file()]
        text = _read(path)
        self.text = text
        sections = _sections(text)
        self.header: dict[str, str] = {}
        for line in sections[0][1]:
            m = HEADER.match(line.strip())
            if m:
                self.header.setdefault(m.group(1).lower(), m.group(2).strip())
        self.done: list[tuple[str, str]] = []
        self.criteria: list[tuple[str, str]] = []
        self.legacy_next: list[str] = []
        self.misplaced_end: list[str] = []
        self.demand_rows: list[dict] = []
        self.items: list[dict] = []
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
            elif h.startswith("acceptance criteria"):
                wrapping = False
                for line in lines:
                    m = CRITERION.match(line)
                    if m:
                        text = BULLET.match(line).group(1).replace("**", "").strip()
                        self.criteria.append((m.group(1), text))
                        wrapping = True
                    elif wrapping and line[:1].isspace() and line.strip() \
                            and not BULLET.match(line):
                        cid, text = self.criteria[-1]  # a wrapped criterion line
                        self.criteria[-1] = (cid, f"{text} {line.strip()}")
                    elif line.strip():
                        wrapping = False  # the criterion's first paragraph ends
            elif h.startswith("demands"):
                self.demand_rows += _demands_table(lines)
            elif h == "items":
                for line in lines:
                    m = BULLET.match(line)
                    if m:
                        rest = CHECKBOX.sub("", m.group(1).strip(), count=1)
                        idm = BACKLOG_ID.match(rest)
                        self.items.append(
                            {"id": idm.group(1), "text": idm.group(2).strip()} if idm
                            else {"id": None, "text": rest})
            elif h.startswith("next cycle"):
                for line in lines:
                    m = BULLET.match(line)
                    if m:
                        self.legacy_next.append(m.group(1).strip())
        self.done_source = "done when"
        if directory and self.criteria:
            met = _met_criteria(directory / "promotion.md")
            self.done = [("x" if cid in met else " ", text) for cid, text in self.criteria]
            self.done_source = "criteria"

    @property
    def objective(self) -> str:
        return self.header.get("objective", "")

    @property
    def declared_state(self) -> str:
        """The first word of `state:`, so `planned (signed off …)` reads as
        planned."""
        words = re.findall(r"[a-z]+", self.header.get("state", "").lower())
        return words[0] if words else ""

    @property
    def end_key(self) -> str:
        """The first of closed:/abandoned: carrying a value in the header."""
        for key in END_KEYS:
            if self.header.get(key):
                return key
        return ""

    @property
    def state(self) -> str:
        if self.end_key:
            return self.end_key
        if self.declared_state in STATES:
            return self.declared_state
        return "running"

    @property
    def ended(self) -> str:
        """'closed <date>' / 'abandoned <date>' for an ended cycle, else ''."""
        if self.state not in END_KEYS:
            return ""
        return f"{self.state} {self.header.get(self.state, '')}".strip()

    @property
    def demands(self) -> list[dict]:
        """The plan's `## Demands` table; for an old file, the ids named on
        its `demands:` line."""
        if self.demand_rows:
            return self.demand_rows
        ids: list[str] = []
        for did in DEMAND_ID.findall(self.header.get("demands", "")):
            if did not in ids:
                ids.append(did)
        return [{"id": d, "layer": "", "depends_on": []} for d in ids]

    @property
    def pending(self) -> int:
        return sum(1 for mark, _ in self.done if mark not in ("x", "-"))

    @property
    def counts(self) -> dict:
        return {"met": sum(1 for mark, _ in self.done if mark == "x"),
                "declined": sum(1 for mark, _ in self.done if mark == "-"),
                "pending": self.pending, "total": len(self.done)}

    @property
    def progress(self) -> str:
        k = self.counts
        out = f"{k['met']}/{k['total']} met"
        if k["declined"]:
            out += f", {k['declined']} declined"
        if k["pending"]:
            out += f", {k['pending']} pending"
        return out


def _met_criteria(path: Path) -> set[str]:
    """Criterion ids promotion.md marks met: a bullet whose first token is
    the id and whose last `—` field is `met` (`- A1 — <evidence> — met`)."""
    met = set()
    for line in _read(path).splitlines():
        m = CRITERION.match(line.strip())
        if m and re.split(r"\s[\u2014\u2013-]\s", line.strip())[-1] \
                .strip(" .*`").lower() == "met":
            met.add(m.group(1))
    return met


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
        if p.name.startswith("."):
            continue
        if p.is_dir():
            m = CYCLE_DIR.match(p.name)
            if not m:
                problems.append(f"cycles/{p.name} is not named C-<n> and is not read")
                continue
            if not (p / "plan.md").is_file():
                problems.append(f"cycles/{p.name}/ has no plan.md — its state and "
                                "objective cannot be read")
            found.append(Cycle(p / "plan.md", int(m.group(1)), directory=p))
            continue
        if not p.is_file():
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


def _item(line: str, full: str, bid: str | None, text: str,
          cells: list[str] | None = None) -> dict:
    """One backlog item: `line` the display (clipped when shown), `full` the
    whole row (a cycle named in any cell counts), `text` the item's own
    text, unclipped, `cells` a table row's cells."""
    marks = GROUP_MARK.findall(full)
    return {"line": line, "shown": _clip(line), "full": full, "id": bid,
            "text": GROUP_MARK.sub("", text).strip() if marks else text,
            "cells": cells, "cycle": marks[-1].upper() if marks else None}


def load_backlog(root: Path, problems: list[str] | None = None):
    """(section, [item]) in file order; None when backlog.md is absent. The
    one id format: `B-<n>` is the first cell of a table row or the first
    token of a bullet (after a checkbox), backticks or bold optional. A
    B-<n> anywhere else an id could be read warns into `problems`."""
    p = root / "backlog.md"
    if not p.is_file():
        return None
    problems = problems if problems is not None else []
    text = _read(p)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        text = text[end + 4:] if end != -1 else text

    def loose(bid: str, line: str):
        problems.append(f"backlog.md: {bid} in '{_clip(line.strip())}' is not read as an "
                        "id — an id is the first cell of a table row or the first "
                        "token of a bullet")
    out = []
    for heading, lines in _sections(text):
        m = LOOSE_ID.match(heading)
        if m:
            loose(m.group(1), "## " + heading)
        items = []
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("|"):
                cells = _cells(s)
                if all(set(c) <= set("-: ") for c in cells):
                    continue  # separator
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt.startswith("|") and set(nxt) <= set("|-: "):
                    continue  # header row
                if len(cells) >= 2:
                    m = ID_CELL.fullmatch(cells[0])
                    if m:
                        items.append(_item(f"{m.group(1)} {cells[1]}", s, m.group(1),
                                           cells[1], cells))
                        continue
                    first = ID_LIKE.match(cells[0].lstrip("`*"))
                    later = [ID_CELL.fullmatch(c) for c in cells[1:]]
                    later = [x.group(1) for x in later if x]
                    if first or later:
                        loose(first.group(0) if first else later[0], s)
                    items.append(_item(f"#{cells[0]} {cells[1]}", s, None, cells[1], cells))
                continue
            m = BULLET.match(line)
            if m:
                content = m.group(1).strip()
                rest = CHECKBOX.sub("", content, count=1)
                idm = BACKLOG_ID.match(rest)
                if idm:
                    items.append(_item(f"{idm.group(1)} {idm.group(2)}".strip(), content,
                                       idm.group(1), idm.group(2)))
                    continue
                like = ID_LIKE.match(rest.lstrip("`*"))
                if like:
                    loose(like.group(0), s)
                items.append(_item(content, content, None, content))
                continue
            m = LOOSE_ID.match(s)
            if m:
                loose(m.group(1), s)
        if items:
            out.append((heading or "(before any section)", items))
    return out


def warnings(cycles: list[Cycle], backlog, problems: list[str]) -> list[str]:
    out = list(problems)
    open_ = [c for c in cycles if c.state == "running"]
    if len(open_) > 1:
        out.append(f"{len(open_)} cycles open: {', '.join(c.id for c in open_)}"
                   " — one runs to the end before another opens")
    for c in cycles:
        if not c.objective:
            out.append(f"{c.id} has no objective: line")
        running = c.state == "running"
        if "state" in c.header and c.declared_state not in STATES:
            out.append(f"{c.id} has state: {c.header['state'] or '(empty)'} — not one "
                       f"of {', '.join(STATES)}; read as {c.state}")
        elif c.declared_state and c.end_key and c.declared_state != c.end_key:
            out.append(f"{c.id} has state: {c.declared_state} and a {c.end_key}: "
                       f"line — {c.end_key}: wins")
        for key in END_KEYS:
            if running and key in c.header and not c.header[key]:
                out.append(f"{c.id} has an empty {key}: line and still counts as open")
        if running and c.misplaced_end:
            out.append(f"{c.id} has a {c.misplaced_end[0]}: line below its header — "
                       "it counts only among the lines before the first ##")
        elif running and c.done and not c.pending:
            if c.done_source == "criteria":
                out.append(f"{c.id} has every criterion met in promotion.md but no "
                           "closed: line")
            else:
                out.append(f"{c.id} has no pending done item but no closed: line")
        if c.legacy_next and not c.ended:
            out.append(f"{c.id} keeps a ## Next cycle list ({len(c.legacy_next)} "
                       "lines) — under AGENTS.md ## Cycle those lines belong in backlog.md")
    if backlog is None:
        out.append("no backlog.md — discoveries outside a cycle have nowhere to go")
    ids: dict[str, int] = {}
    for _, items in backlog or []:
        for it in items:
            if it["id"]:
                ids[it["id"]] = ids.get(it["id"], 0) + 1
    for bid, k in ids.items():
        if k > 1:
            out.append(f"{bid} is used by {k} backlog items — an id names one item")
    grouped: dict[str, set[str]] = {}
    for c in cycles:
        for it in c.items:
            if it["id"]:
                grouped.setdefault(it["id"], set()).add(c.id)
    for _, items in backlog or []:
        for it in items:
            if it["id"] and it["cycle"]:
                grouped.setdefault(it["id"], set()).add(it["cycle"])
    for bid, cids in sorted(grouped.items(), key=lambda kv: _num(kv[0])):
        if len(cids) > 1:
            out.append(f"{bid} is grouped into "
                       f"{', '.join(sorted(cids, key=_num))} — an item belongs "
                       "to one cycle")
    return out


def _num(tag: str) -> int:
    return int(tag.rsplit("-", 1)[1])


def next_ids(root: Path, cycles: list[Cycle]) -> dict:
    """The next free ids: one more than the highest `B-<n>` seen anywhere —
    backlog.md or any cycle — and than the highest cycle number, directory
    or old single file. Ids are never reused."""
    texts = [_read(root / "backlog.md")] + [c.text for c in cycles]
    b = max((int(n) for t in texts for n in ANY_B_ID.findall(t)), default=0)
    n = max((c.n for c in cycles), default=0)
    return {"backlog_id": f"B-{b + 1}", "cycle_id": f"C-{n + 1}"}


def owned_lines(cid: str, backlog, key: str = "shown") -> list[str]:
    """Backlog lines that came from the cycle (origin `(C-<n>)`); the
    grouping mark `→ C-<n>` is not an origin."""
    tok = cycle_token(cid)
    return [it[key] for heading, items in backlog or []
            for it in items
            if tok.search(heading) or tok.search(GROUP_MARK.sub("", it["full"]))]


def _item_lines(c: Cycle) -> list[str]:
    return [f"    - {_clip((it['id'] or '(no id)') + ' ' + it['text'])}"
            for it in c.items]


def show_cycle(c: Cycle, backlog, title: str) -> list[str]:
    out = [f"{title} {c.id} ({c.ended or c.state})",
           f"  objective: {_clip(c.objective) or '—'}"]
    if c.layout == "directory":
        out.append(f"  artifacts: {', '.join(c.artifacts) or '—'}")
    if c.header.get("demands"):
        out.append(f"  demands:   {_clip(c.header['demands'])}")
    if c.demand_rows:
        out.append(f"  demands:   {len(c.demand_rows)}")
        for d in c.demand_rows:
            line = f"    {_clip(d['id'])}  {_clip(d['layer']) or '—'}"
            if d["depends_on"]:
                line += f"  depends on {_clip(', '.join(d['depends_on']))}"
            out.append(line)
    if c.items:
        out.append(f"  items:     {len(c.items)}")
        out += _item_lines(c)
    label = "criteria: " if c.done_source == "criteria" else "done when:"
    out.append(f"  {label} {c.progress}")
    out += [f"    [{m}] {_clip(t)}" for m, t in c.done]
    owned = owned_lines(c.id, backlog)
    if owned:
        out.append(f"  backlog lines from {c.id}: {len(owned)}")
        out += [f"    - {t}" for t in owned]
    if c.legacy_next:
        out.append(f"  ## Next cycle (old format): {len(c.legacy_next)} lines")
        out += [f"    - {_clip(t)}" for t in c.legacy_next]
    return out


def show_cycles(cycles: list[Cycle], backlog, nxt: dict) -> list[str]:
    open_ = [c for c in cycles if c.state == "running"]
    out = []
    for c in open_:
        out += show_cycle(c, backlog, "OPEN CYCLE") + [""]
    if not open_:
        out += ["no open cycle", ""]
    waiting = [c for c in cycles if c.state in ("draft", "planned")]
    if waiting:
        out.append("DRAFT AND PLANNED")
        for c in waiting:
            out.append(f"  {c.id}  {c.state}  {_clip(c.objective)}".rstrip())
            out += _item_lines(c)
        out.append("")
    ended = [c for c in cycles if c.ended]
    if ended:
        out.append("CYCLES")
        out += [f"  {c.id}  {c.ended}  {c.progress}  {_clip(c.objective)}"
                for c in reversed(ended)]
        out.append("")
    return out + [f"next cycle id: {nxt['cycle_id']}", ""]


def show_backlog(backlog, nxt: dict) -> list[str]:
    if backlog is None:
        return ["BACKLOG", "  (no backlog.md)", ""]
    total = sum(len(items) for _, items in backlog)
    out = [f"BACKLOG ({total} items, next id {nxt['backlog_id']})"]
    for heading, items in backlog:
        out.append(f"  {heading}")
        out += [f"    - {it['shown']}" for it in items]
    return out + [""]


def as_json(cycles: list[Cycle], backlog, warns: list[str], parts,
            nxt: dict) -> dict:
    """The text view's content; `parts` names which of cycles/backlog."""
    data: dict = {"warnings": warns, "next": nxt}
    if "cycles" in parts:
        data["cycles"] = [{
            "id": c.id, "state": c.state, "ended": c.ended, "layout": c.layout,
            "objective": c.objective, "demands": c.demands, "items": c.items,
            "done": dict(c.counts, source=c.done_source,
                         items=[{"mark": m, "text": t} for m, t in c.done]),
            "artifacts": c.artifacts,
            "backlog_lines": owned_lines(c.id, backlog, "line"),
            "legacy_next": c.legacy_next,
        } for c in cycles]
    if "backlog" in parts:
        data["backlog"] = None if backlog is None else {"sections": [
            {"heading": heading, "items": [
                {"id": it["id"], "text": it["text"], "cells": it["cells"],
                 "cycle": it["cycle"]} for it in items]}
            for heading, items in backlog]}
    return data


def emit_json(data: dict) -> int:
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle and backlog view")
    ap.add_argument("--root", default=".", help="project root (default: cwd)")
    part = ap.add_mutually_exclusive_group()
    part.add_argument("--cycle", metavar="C-N", help="one cycle in full")
    part.add_argument("--backlog", action="store_true", help="backlog only")
    part.add_argument("--cycles", action="store_true", help="cycles only")
    ap.add_argument("--format", choices=("text", "json"), default="text",
                    help="text (default) or json with the same content")
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
    backlog = load_backlog(root, problems)
    nxt = next_ids(root, cycles)

    if args.cycle:
        match = [c for c in cycles if c.id.lower() == args.cycle.strip().lower()]
        if not match:
            print(f"status: no cycle {args.cycle} in cycles/", file=sys.stderr)
            return 2
        if args.format == "json":
            return emit_json(as_json(match, backlog, warnings(cycles, backlog, problems),
                                     ("cycles",), nxt))
        print("\n".join(show_cycle(match[0], backlog, "CYCLE")))
        return 0

    warns = warnings(cycles, backlog, problems)
    if args.format == "json":
        parts = [p for p, off in (("cycles", args.backlog), ("backlog", args.cycles))
                 if not off]
        return emit_json(as_json(cycles, backlog, warns, parts, nxt))
    out = [f"WARNING {w}" for w in warns]
    if out:
        out.append("")
    if not args.backlog:
        out += show_cycles(cycles, backlog, nxt)
    if not args.cycles:
        out += show_backlog(backlog, nxt)
    sys.stdout.write("\n".join(out).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
