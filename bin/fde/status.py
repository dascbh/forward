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
(`- A1 — <evidence> — met`; `— declined` or `— limit` settles a criterion
on the budget-spent path). A closed directory cycle without promotion.md,
or with a criterion not settled there, warns.

A draft's `## Items` (the B-ids fde-backlog grouped) are read; a backlog
item marked `→ C-<n>` is grouped into that cycle, and one B-id in two
cycles warns. `next` gives the next free ids: B-<n> one more than the
highest seen in backlog.md or any cycle, C-<n> one more than the highest
directory or old file.

The demands (FWD-034): every `specs/<id>/` (bare or `<id>-<slug>`), linked
to a cycle by a plan's `## Demands` table or an old file's `demands:`
line, else by the spec's own `cycle:` line (one naming no cycle on disk
warns and the demand is loose), else loose; its review summary from
`reviews/<id>[-<slug>]/findings.toml` (a malformed file is named, never
raised); its promotion from the cycle's promotion.md or the old
`promotions/<id>[-<slug>]/`. Each cycle also carries its artifact paths.
The panel's Overview ends with a suggested next action; it folds warnings
after ten.

A report, never a gate (ADR-0018): exit 0 on any content, exit 2 only for
a bad argument. Read-only, stdlib only, no git.

  python3 bin/fde/status.py              # everything
  python3 bin/fde/status.py --cycle C-3  # one cycle in full
  python3 bin/fde/status.py --demand FWD-7  # one demand: spec, findings, ADRs
  python3 bin/fde/status.py --panel      # overview, backlog, cycles, demands,
                                         # discarded: markdown, from the JSON
  python3 bin/fde/status.py --backlog    # backlog only
  python3 bin/fde/status.py --cycles     # cycles only
  python3 bin/fde/status.py --format json  # the same content as JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
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
UNSECTIONED = "Unsectioned"  # backlog items above the first `##`


def _read(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _clip(text: str, width: int = WIDTH) -> str:
    """One line of at most `width` characters, cut at a word boundary."""
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    cut = text[:width - 1]
    space = cut.rfind(" ")
    if space >= width // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:·—–-") + "…"


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
        self.unsettled: list[str] = []
        if directory and self.criteria:
            marks = _promotion_marks(directory / "promotion.md")
            self.done = [(marks.get(cid, " "), text) for cid, text in self.criteria]
            self.unsettled = [cid for cid, _ in self.criteria if cid not in marks]
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


# promotion.md's last `—` field of a criterion bullet: met, or settled on
# the budget-spent path (declined by the owner, or a declared limit)
PROMOTION_MARKS = {"met": "x", "declined": "-", "limit": "-"}


def _promotion_marks(path: Path) -> dict[str, str]:
    """Criterion id -> mark ('x' met, '-' declined) for each bullet of
    promotion.md whose first token is the id and whose last `—` field is
    `met`, `declined` or `limit` (`- A1 — <evidence> — met`)."""
    marks: dict[str, str] = {}
    for line in _read(path).splitlines():
        m = CRITERION.match(line.strip())
        last = m and re.split(r"\s[\u2014\u2013-]\s", line.strip())[-1] \
            .strip(" .*`").lower()
        if last in PROMOTION_MARKS:
            marks[m.group(1)] = PROMOTION_MARKS[last]
    return marks


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
            out.append((heading or UNSECTIONED, items))
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
        if c.layout == "directory" and c.state == "closed":
            if "promotion.md" not in c.artifacts:
                out.append(f"{c.id} is closed without promotion.md")
            elif c.unsettled:
                out.append(f"{c.id} is closed with criteria not met: "
                           f"{', '.join(c.unsettled)}")
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


def show_cycle(c: Cycle, backlog, title: str,
               demands: list[dict] | None = None) -> list[str]:
    """The cycle in full; with `demands`, each of its demands carries its
    review and promotion, as the panel's table does."""
    out = [f"{title} {c.id} ({c.ended or c.state})",
           f"  objective: {_clip(c.objective) or '—'}"]
    if c.layout == "directory":
        out.append(f"  artifacts: {', '.join(c.artifacts) or '—'}")
    if c.header.get("demands"):
        out.append(f"  demands:   {_clip(c.header['demands'])}")
    by_id = {d["id"]: d for d in demands or []}
    rows = c.demand_rows if c.demand_rows or demands is None else c.demands
    named = {r["id"].upper() for r in rows}
    rows = rows + [{"id": d["id"], "layer": d["layer"], "depends_on": []}
                   for d in demands or [] if d["cycle"] == c.id and d["id"] not in named]
    if rows:
        out.append(f"  demands:   {len(rows)}")
        for r in rows:
            d = by_id.get(r["id"].upper())
            line = f"    {_clip(r['id'])}  {_clip(r['layer'] or (d or {}).get('layer', '')) or '—'}"
            if r["depends_on"]:
                line += f"  depends on {_clip(', '.join(r['depends_on']))}"
            if demands is not None:
                line += f"  {_review_cell(d)} · promotion {_promotion_cell(d)}"
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


# --- demands (FWD-034) -------------------------------------------------------

SPEC_DIR = re.compile(r"^([A-Za-z][A-Za-z0-9]*-\d+)(?![0-9])(?:-.*)?$")
ADR_REF = re.compile(r"\bADR-(\d+)\b")
ADR_FILE = re.compile(r"^(\d+)-.*\.md$")


def _rel(root: Path, p: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def cycle_paths(root: Path, c: Cycle) -> list[str]:
    """The cycle's artifact files, then its cycle review files."""
    if c.layout == "directory":
        out = [_rel(root, c.path / a) for a in c.artifacts]
    else:
        out = [_rel(root, c.path)]
    rev = root / "reviews" / c.id
    try:
        out += [_rel(root, p) for p in sorted(rev.iterdir())
                if p.is_file() and p.suffix == ".toml"]
    except OSError:
        pass
    return out


def _spec_fields(text: str) -> dict[str, str]:
    """`key: value` pairs of the spec's lines before its first `##`, a line
    split on `·` (`cycle: C-12 · layer: back · follows: ADR-0020`); the
    first of each key wins."""
    out: dict[str, str] = {}
    for line in _sections(text)[0][1]:
        for part in line.split("·"):
            m = HEADER.match(part.strip())
            if m:
                out.setdefault(m.group(1).lower(), m.group(2).strip())
    return out


def _decision(path: Path) -> str:
    """The `decision:` line of a promotion file, among its first lines."""
    for line in _read(path).splitlines()[:30]:
        m = HEADER.match(line.strip())
        if m and m.group(1).lower() == "decision":
            return m.group(2).strip()
    return ""


def _finding_title(f: dict) -> str:
    for key in ("title", "probe", "evidence"):
        v = f.get(key)
        if isinstance(v, str) and v.strip():
            return _clip(next(line for line in v.splitlines() if line.strip()))
    return ""


def demand_dir(root: Path, kind: str, did: str) -> Path | None:
    """`<kind>/<id>/`, else the first `<kind>/<id>-<slug>/` in name order —
    matched as spec directories are (`FWD-40` never takes `FWD-400-x`)."""
    bare = root / kind / did
    if bare.is_dir():
        return bare
    try:
        entries = sorted(p for p in (root / kind).iterdir() if p.is_dir())
    except OSError:
        return None
    for p in entries:
        m = SPEC_DIR.match(p.name)
        if m and m.group(1).upper() == did.upper():
            return p
    return None


def load_findings(root: Path, did: str):
    """(summary, findings) of `reviews/<id>[-<slug>]/findings.toml`; (None,
    []) when absent. A file that cannot be read as TOML, or a `finding`
    that is not a list of tables, is named in `error`, never raised."""
    d = demand_dir(root, "reviews", did)
    p = d / "findings.toml" if d else None
    if p is None or not p.is_file():
        return None, []
    summary: dict = {"path": _rel(root, p), "findings": None, "by_severity": {},
                     "blocking": 0, "error": None}
    try:
        data = tomllib.loads(_read(p))
    except (tomllib.TOMLDecodeError, ValueError) as e:
        summary["error"] = f"not valid TOML: {_clip(str(e))}"
        return summary, []
    rows = data.get("finding", [])
    if not isinstance(rows, list):
        rows, summary["error"] = [], "`finding` is not a list of [[finding]] tables"
    findings = []
    for i, f in enumerate(rows, 1):
        if not isinstance(f, dict):
            summary["error"] = "a `finding` entry is not a table"
            continue
        sev = f.get("severity")
        sev = sev.strip().lower() if isinstance(sev, str) and sev.strip() else "unset"
        fid = f.get("id")
        findings.append({"id": _clip(str(fid)) if fid not in (None, "") else f"#{i}",
                         "severity": sev, "blocking": f.get("blocking") is True,
                         "title": _finding_title(f)})
    summary["findings"] = len(findings)
    for f in findings:
        summary["by_severity"][f["severity"]] = \
            summary["by_severity"].get(f["severity"], 0) + 1
    summary["blocking"] = sum(1 for f in findings if f["blocking"])
    return summary, findings


def _promotion(root: Path, did: str, cycle: Cycle | None):
    """The cycle's promotion.md, else the old `promotions/<id>[-<slug>]/`
    file."""
    if cycle and cycle.layout == "directory" and "promotion.md" in cycle.artifacts:
        p = cycle.path / "promotion.md"
        return {"path": _rel(root, p), "decision": _clip(_decision(p))}
    d = demand_dir(root, "promotions", did)
    if d is None:
        return None
    try:
        files = sorted(p for p in d.iterdir() if p.is_file() and p.suffix == ".md")
    except OSError:
        return None
    if not files:
        return None
    p = d / "decision.md" if (d / "decision.md") in files else files[0]
    return {"path": _rel(root, p), "decision": _clip(_decision(p))}


def load_demands(root: Path, cycles: list[Cycle], problems: list[str],
                 findings: dict[str, list[dict]] | None = None) -> list[dict]:
    """Every `specs/<id>/` (bare or `<id>-<slug>`), in id order, with its
    cycle link, review summary and promotion. Old layout: the directory
    holds acceptance.md (before kernel ADR-0019). Each demand's findings
    go to `findings` by id when given, so no caller parses them again."""
    d = root / "specs"
    try:
        entries = sorted(p for p in d.iterdir() if p.is_dir()
                         and not p.name.startswith("."))
    except OSError:
        return []
    linked: dict[str, tuple[Cycle, dict]] = {}
    for c in cycles:
        for row in c.demands:
            linked.setdefault(row["id"].upper(), (c, row))
    by_id = {c.id: c for c in cycles}
    out: list[dict] = []
    seen: dict[str, str] = {}
    for p in entries:
        m = SPEC_DIR.match(p.name)
        if not m:
            continue
        did = m.group(1).upper()
        if did in seen:
            problems.append(f"specs/{seen[did]} and specs/{p.name} both read as "
                            f"{did}; the first is used")
            continue
        seen[did] = p.name
        spec = p / "spec.md"
        fields = _spec_fields(_read(spec)) if spec.is_file() else {}
        cid, cycle, source, layer, dangling = None, None, None, "", None
        if did in linked:
            cycle, row = linked[did]
            cid, source, layer = cycle.id, "plan", row["layer"]
        else:
            cm = re.match(r"[`*]*(C-\d+)(?!\d)", fields.get("cycle", ""), re.I)
            if cm and cm.group(1).upper() in by_id:
                cid, source = cm.group(1).upper(), "spec"
                cycle = by_id[cid]
            elif cm:  # a link to no cycle on disk: listed as loose, named
                dangling = cm.group(1).upper()
                problems.append(f"specs/{p.name}/spec.md links {dangling}, which is not "
                                f"in cycles/ — {did} is listed as loose")
        review, rows = load_findings(root, did)
        if findings is not None:
            findings[did] = rows
        follows = []
        for n in ADR_REF.findall(fields.get("follows", "")):
            if f"ADR-{n}" not in follows:
                follows.append(f"ADR-{n}")
        out.append({
            "id": did, "dir": _rel(root, p),
            "spec": _rel(root, spec) if spec.is_file() else None,
            "layout": "old" if (p / "acceptance.md").is_file() else "new",
            "cycle": cid, "cycle_source": source, "loose": cid is None,
            "dangling_cycle": dangling,
            "layer": _clip(layer or fields.get("layer", "")),
            "follows": follows, "review": review,
            "promotion": _promotion(root, did, cycle),
        })
    return sorted(out, key=lambda x: (x["id"].rsplit("-", 1)[0], _num(x["id"])))


def adr_files(root: Path) -> dict[int, Path]:
    try:
        files = sorted((root / "docs" / "adr").iterdir())
    except OSError:
        return {}
    out: dict[int, Path] = {}
    for p in files:
        m = ADR_FILE.match(p.name)
        if m and p.is_file():
            out.setdefault(int(m.group(1)), p)
    return out


def show_demand(root: Path, d: dict, findings: list[dict]) -> list[str]:
    out = [f"DEMAND {d['id']}"]
    link = "none (loose)" if d["loose"] else \
        f"{d['cycle']} ({'plan' if d['cycle_source'] == 'plan' else 'spec cycle: line'})"
    out.append(f"  cycle:     {link}")
    out.append(f"  layer:     {d['layer'] or '—'}")
    out.append(f"  layout:    {d['layout']}  {d['dir']}")
    out.append(f"  spec:      {d['spec'] or '(no spec.md)'}")
    rev = d["review"]
    if rev is None:
        out.append("  review:    none")
    elif rev["findings"] is None:
        out.append(f"  review:    {rev['path']} — {rev['error']}")
    else:
        sev = ", ".join(f"{k} {s}" for s, k in rev["by_severity"].items())
        out.append(f"  review:    {rev['path']} — {rev['findings']} findings"
                   f"{f' ({sev})' if sev else ''}, {rev['blocking']} blocking")
        if rev["error"]:
            out.append(f"    ({rev['error']})")
        out += [f"    {f['id']}  {f['severity']}  {'blocking' if f['blocking'] else '—'}"
                f"  {f['title'] or '—'}" for f in findings]
    pro = d["promotion"]
    out.append(f"  promotion: {pro['path']} — {pro['decision'] or '(no decision: line)'}"
               if pro else "  promotion: none")
    adrs = adr_files(root)
    if d["follows"]:
        out.append("  follows:")
        for ref in d["follows"]:
            p = adrs.get(int(ref.split("-")[1]))
            if p is None:
                out.append(f"    {ref}  (no file in docs/adr/)")
                continue
            title = next((line for line in _read(p).splitlines() if line.strip()), "")
            out.append(f"    {ref}  {_rel(root, p)} — {_clip(title.lstrip('# '))}")
    else:
        out.append("  follows:   —")
    if d["spec"]:
        out += ["", f"SPEC {d['spec']}", _read(root / d["spec"]).rstrip()]
    return out


def as_json(cycles: list[Cycle], backlog, warns: list[str], parts,
            nxt: dict, root: Path | None = None,
            demands: list[dict] | None = None) -> dict:
    """The text view's content; `parts` names which of cycles/backlog."""
    data: dict = {"warnings": warns, "next": nxt}
    if "cycles" in parts:
        data["cycles"] = [{
            "id": c.id, "state": c.state, "ended": c.ended, "layout": c.layout,
            "objective": c.objective, "demands": c.demands, "items": c.items,
            "done": dict(c.counts, source=c.done_source,
                         items=[{"mark": m, "text": t} for m, t in c.done]),
            "artifacts": c.artifacts,
            "artifact_paths": cycle_paths(root, c) if root else [],
            "backlog_lines": owned_lines(c.id, backlog, "line"),
            "legacy_next": c.legacy_next,
        } for c in cycles]
        if demands is not None:
            data["demands"] = demands
    if "backlog" in parts:
        data["backlog"] = None if backlog is None else {"sections": [
            {"heading": heading, "items": [
                {"id": it["id"], "text": it["text"], "cells": it["cells"],
                 "cycle": it["cycle"]} for it in items]}
            for heading, items in backlog]}
    return data


# --- the panel (FWD-035, ADR-0020) ------------------------------------------

BLOCK_START = re.compile(r"^(?:[#>\-+*=<`~_]|\d+[.)])")
DISCARD = re.compile(r"\s*[—–-]*\s*discarded\s*:\s*", re.IGNORECASE)


def _md(text, full: bool = False, inline: bool = False) -> str:
    """File text made safe for one markdown line: whitespace collapsed,
    clipped (unless `full`), table pipes escaped, a leading block marker
    (heading, quote, list, fence, html) escaped (FM1) — unless `inline`:
    text that never starts a line keeps its first character, so a bold
    `**decision**` stays bold."""
    t = " ".join(str(text or "").split()) if full else _clip(str(text or ""))
    t = t.replace("\\|", "|").replace("|", "\\|")
    if inline or not BLOCK_START.match(t):
        return t
    return "\\" + t


def _discarded(heading: str) -> bool:
    return heading.strip().lower().startswith("discarded")


def _review_cell(d: dict | None) -> str:
    if d is None:
        return "no spec"
    rev = d["review"]
    if rev is None:
        return "not reviewed"
    if rev["findings"] is None:
        return "findings.toml unreadable"
    if rev["blocking"]:
        return (f"{_n(rev['blocking'], 'blocking finding')} recorded "
                f"({rev['findings']} in all)")
    return f"{_n(rev['findings'], 'finding')} recorded, none blocking"


def _loose_label(d: dict) -> str:
    """Why a loose demand has no cycle, in the owner's words."""
    if d.get("dangling_cycle"):
        return f"no cycle ({d['dangling_cycle']} not in cycles/)"
    return "legacy layout (no cycle)" if d["layout"] == "old" else "no cycle"


def _n(k: int, word: str) -> str:
    return f"{k} {word}{'' if k == 1 else 's'}"


PROMOTION_CELL = 40


def _promotion_cell(d: dict | None) -> str:
    """The decision up to its first dash, cut at a word; a bold the cut
    leaves open is closed after the ellipsis."""
    if d is None or not d["promotion"]:
        return "—"
    decision = d["promotion"]["decision"] or ""
    first = re.split(r"\s[—–]\s", decision)[0].strip()
    if not first:
        return "(no decision: line)"
    cell = _clip(first, PROMOTION_CELL)
    if cell.count("**") % 2:
        cell += "**"
    return cell


def panel_counts(data: dict) -> dict:
    """The numbers the Overview states, from the JSON (FM4)."""
    sections = (data.get("backlog") or {}).get("sections", [])
    states: dict[str, int] = {}
    for c in data.get("cycles", []):
        states[c["state"]] = states.get(c["state"], 0) + 1
    demands = data.get("demands", [])
    return {
        "backlog": sum(len(s["items"]) for s in sections if not _discarded(s["heading"])),
        "discarded": sum(len(s["items"]) for s in sections if _discarded(s["heading"])),
        "cycles": len(data.get("cycles", [])),
        "running": states.get("running", 0), "planned": states.get("planned", 0),
        "draft": states.get("draft", 0),
        "ended": states.get("closed", 0) + states.get("abandoned", 0),
        "demands": len(demands), "loose": sum(1 for d in demands if d["loose"]),
    }


def _progress(c: dict) -> str:
    """One word for every cycle: criteria (directory) and done items (old
    file) both read `done <met>/<total>`."""
    k = c["done"]
    out = f"done {k['met']}/{k['total']}"
    if k["declined"]:
        out += f", {k['declined']} declined"
    return out


WARN_FOLD = 10


def next_action(data: dict) -> str:
    """The next step the state suggests: finish the running cycle, else sign
    off a planned one, else specify a draft, else group the backlog."""
    cycles = data.get("cycles", [])
    running = [c for c in cycles if c["state"] == "running"]
    if running:
        c = running[0]
        cid, pending = c["id"], c["done"]["pending"]
        unreviewed = [d["id"] for d in data.get("demands", [])
                      if d["cycle"] == cid and d["spec"] and d["review"] is None]
        if unreviewed:
            return f"review {', '.join(unreviewed)} ({cid})"
        if c["layout"] == "file":
            return (f"finish {cid} ({_n(pending, 'done item')} pending)" if pending
                    else f"close {cid}")
        if "review.md" not in c["artifacts"]:
            return f"run the cycle review of {cid}"
        if pending:
            word = "criterion" if pending == 1 else "criteria"
            return f"promote and close {cid} ({pending} {word} pending)"
        return f"close {cid} (every criterion met)"
    planned = [c["id"] for c in cycles if c["state"] == "planned"]
    if planned:
        return f"sign off {planned[0]} (planned)"
    drafts = [c["id"] for c in cycles if c["state"] == "draft"]
    if drafts:
        return f"specify a draft ({', '.join(drafts[:3])}{'…' if len(drafts) > 3 else ''})"
    free = sum(1 for s in (data.get("backlog") or {}).get("sections", [])
               if not _discarded(s["heading"]) for it in s["items"] if not it["cycle"])
    if free:
        return f"group backlog items into a draft ({free} ungrouped)"
    return "capture the next idea in backlog.md"


def _item_line(it: dict, indent: str = "") -> str:
    mark = f" → {it['cycle']}" if it.get("cycle") else ""
    return f"{indent}- {it['id'] or '(no id)'} {_md(it['text'])}{mark}"


def _cycle_full(c: dict, by_id: dict[str, dict]) -> list[str]:
    out = [f"### {c['id']} · {c['ended'] or c['state']} · {_progress(c)}", "",
           f"- objective: {_md(c['objective']) or '—'}"]
    if c["items"]:
        out.append(f"- items ({len(c['items'])}):")
        out += [_item_line(it, "  ") for it in c["items"]]
    rows = [(r["id"], r["layer"]) for r in c["demands"]]
    named = {r[0].upper() for r in rows}
    rows += [(d["id"], d["layer"]) for d in by_id.values()
             if d["cycle"] == c["id"] and d["id"] not in named]
    if rows:
        out += [f"- demands ({len(rows)}):", "",
                "| id | layer | review | promotion |", "|---|---|---|---|"]
        for did, layer in rows:
            d = by_id.get(did.upper())
            if not layer and d is not None:
                layer = d["layer"]
            out.append(f"| {_md(did)} | {_md(layer) or '—'} | "
                       f"{_review_cell(d)} | {_md(_promotion_cell(d), inline=True)} |")
        out.append("")
    out.append(f"- artifacts: {_md(', '.join(c['artifact_paths'])) or '—'}")
    return out + [""]


def render_panel(data: dict) -> list[str]:
    """The five sections, rendered only from `data` — the same dict
    `--format json` prints (FM4). Running and planned cycles in full,
    drafts with their items, ended cycles and loose demands one line each,
    every item clipped to one line (FM3)."""
    k = panel_counts(data)
    cycles = data.get("cycles", [])
    by_id = {d["id"]: d for d in data.get("demands", [])}
    running = [c for c in cycles if c["state"] == "running"]
    planned = [c for c in cycles if c["state"] == "planned"]
    drafts = [c for c in cycles if c["state"] == "draft"]
    ended = [c for c in cycles if c["ended"]]
    warns = data.get("warnings", [])
    out = ["## Overview", ""]
    out += [f"- running: {c['id']} — {_md(c['objective'], full=True) or '—'} — "
            f"{_progress(c)}" for c in running] or ["- running: none"]
    out.append("- planned: " + (", ".join(c["id"] for c in planned) or "none"))
    out.append("- drafts: " + (", ".join(c["id"] for c in drafts) or "none"))
    out.append(f"- warnings: {len(warns) or 'none'}")
    out += [f"  - {_md(w)}" for w in warns[:WARN_FOLD]]
    if len(warns) > WARN_FOLD:
        out.append(f"  - … {len(warns) - WARN_FOLD} more (status.py --format json)")
    out.append(f"- next: {_md(next_action(data))}")
    nxt = data.get("next", {})
    out.append(f"- next ids: {nxt.get('backlog_id', '—')} · {nxt.get('cycle_id', '—')}")
    out.append(f"- counts: backlog {k['backlog']} · discarded {k['discarded']} · "
               f"cycles {k['cycles']} ({k['running']} running, {k['planned']} planned, "
               f"{k['draft']} draft, {k['ended']} ended) · demands {k['demands']} "
               f"({k['loose']} loose)")

    out += ["", f"## Backlog ({k['backlog']})", ""]
    backlog = data.get("backlog")
    if backlog is None:
        out.append("(no backlog.md)")
    for s in (backlog or {}).get("sections", []):
        if _discarded(s["heading"]):
            continue
        out += [f"### {_md(s['heading'])}", ""]
        out += [_item_line(it) for it in s["items"]] + [""]

    out += ["", f"## Cycles ({k['cycles']})", ""]
    for c in running + planned:
        out += _cycle_full(c, by_id)
    if drafts:
        out += [f"### Drafts ({len(drafts)})", ""]
        for c in drafts:
            out.append(f"- {c['id']} — {_md(c['objective']) or '—'}")
            out += [_item_line(it, "  ") for it in c["items"]]
        out.append("")
    if ended:
        out += [f"### Ended ({len(ended)})", ""]
        for c in reversed(ended):
            n = sum(1 for d in by_id.values() if d["cycle"] == c["id"])
            out.append(f"- {c['id']} · {_md(c['ended'])} · {_progress(c)} · "
                       f"{_n(n, 'demand')} · {_md(c['objective']) or '—'}")
        out.append("")
    if not cycles:
        out += ["(no cycles)", ""]

    loose = [d for d in by_id.values() if d["loose"]]
    out += ["", f"## Demands ({k['demands']}, {k['loose']} loose)", ""]
    out.append("Loose demands (no cycle links them) below; a linked demand shows "
               "under its cycle, an ended cycle's as a count. `--demand <id>` "
               "opens any one.")
    out.append("")
    for d in loose:
        out.append(f"- {_md(d['id'])} · {_md(_loose_label(d))} · {_review_cell(d)} · "
                   f"promotion {_md(_promotion_cell(d), inline=True)}")

    out += ["", f"## Discarded ({k['discarded']})", ""]
    for s in (backlog or {}).get("sections", []):
        if not _discarded(s["heading"]):
            continue
        for it in s["items"]:
            parts = DISCARD.split(it["text"], maxsplit=1)
            text, reason = parts if len(parts) == 2 else (it["text"], "")
            out.append(f"- {it['id'] or '(no id)'} {_md(text)} — "
                       f"{_md(reason) or '(no reason)'}")
    return [line for i, line in enumerate(out)
            if line or (i and out[i - 1])]  # no double blank line


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
    part.add_argument("--demand", metavar="ID",
                      help="one demand: spec, findings, promotion, ADRs")
    part.add_argument("--panel", action="store_true",
                      help="the whole panel as markdown sections")
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
    found: dict[str, list[dict]] = {}
    demands = load_demands(root, cycles, problems, found)

    if args.cycle is not None:  # an empty id is a bad argument, not no argument
        match = [c for c in cycles if c.id.lower() == args.cycle.strip().lower()]
        if not match:
            print(f"status: no cycle {args.cycle!r} in cycles/", file=sys.stderr)
            return 2
        if args.format == "json":
            return emit_json(as_json(match, backlog, warnings(cycles, backlog, problems),
                                     ("cycles",), nxt, root,
                                     [d for d in demands if d["cycle"] == match[0].id]))
        print("\n".join(show_cycle(match[0], backlog, "CYCLE", demands)))
        return 0

    if args.demand is not None:
        match = [d for d in demands if d["id"] == args.demand.strip().upper()]
        if not match:
            print(f"status: no demand {args.demand!r} in specs/", file=sys.stderr)
            return 2
        findings = found.get(match[0]["id"], [])
        if args.format == "json":
            return emit_json({"warnings": warnings(cycles, backlog, problems),
                              "demand": dict(match[0], findings=findings)})
        sys.stdout.write("\n".join(show_demand(root, match[0], findings)) + "\n")
        return 0

    warns = warnings(cycles, backlog, problems)
    if args.panel:
        data = as_json(cycles, backlog, warns, ("cycles", "backlog"), nxt, root, demands)
        if args.format == "json":
            return emit_json(data)
        sys.stdout.write("\n".join(render_panel(data)).rstrip() + "\n")
        return 0
    if args.format == "json":
        parts = [p for p, off in (("cycles", args.backlog), ("backlog", args.cycles))
                 if not off]
        return emit_json(as_json(cycles, backlog, warns, parts, nxt, root, demands))
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
