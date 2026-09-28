#!/usr/bin/env python3
"""
cycle — declared cycle scope (ADR-0017, FWD-021): the pure core.

A cycle is one declared piece of agent work: `cycles/C-<n>.md` names its
objective, its tasks, its definition of done and a next-cycle list, and
is committed BEFORE the first behavior change it covers. This module
parses a cycle file, computes the done profile, and runs the form (C2),
closure (C3), transition (C4), serial (C5) and disposition (C6) checks.
C1 ("declared before") is ordering in git, so it lives in
`verify.Gate.gate_cycle`, which reads the trees and calls in here.

Pure: no git, no filesystem. Inputs are bytes/texts and plain data, so
every rule is unit-testable without a repository. Header parsing and the
demand join key are graph.py's (MNT-11: one definition, imported, never
copied). The build contract, grammar included, is
specs/FWD-021-cycle-scope/architecture.md. Stdlib only (I6).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from graph import _header_fields, spec_size  # noqa: E402 — MNT-11

CYCLES_DIR = "cycles"
NAME_RE = re.compile(r"C-(0|[1-9][0-9]*)\.md")
HEADER_MAX_LINES = 30

ALWAYS = ("declared-before", "regression-proven", "review-rounds", "residuals")
STAGES = ("live", "published")
ALL_KEYS = ALWAYS + ("promotion",) + STAGES
SIZES = ("XS", "S", "M", "L")
EVIDENCE_LABELS = ("opinion", "usage-data", "user-test", "production")

TASKS, DONE, NEXT, INTAKE = "## Tasks", "## Done when", "## Next cycle", "## Intake"
KNOWN_SECTIONS = (TASKS, DONE, NEXT, INTAKE)

PLACEHOLDER_RE = re.compile(r"^<[^<>]*>$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DEMAND_RE = re.compile(r"([A-Za-z][A-Za-z0-9._-]*)\s*\((XS|S|M|L)\)")
DONE_RE = re.compile(r"\[( |x|-)\] (.*)")
SEP_RE = re.compile(r" — | -- ")
AMENDED_RE = re.compile(r"amended (\d{4}-\d{2}-\d{2}): (.*)")
ACCEPTANCE_RE = re.compile(r"specs/([^/\s`'\"()<>]+)/acceptance\.md")
INTAKE_RE = re.compile(
    r"C-(0|[1-9][0-9]*)#([1-9][0-9]*) (?:(taken|deferred)|dropped(?: — | -- )(.*))")


def _valid_date(s: str) -> date | None:
    if not DATE_RE.fullmatch(s or ""):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def is_placeholder(s: str) -> bool:
    """Unfilled: the whole value is exactly one `<…>` span (ADR-0017,
    'placeholder detection by a byte list' rejected — structural rule)."""
    return bool(PLACEHOLDER_RE.match(s.strip()))


def _amended_ok(text: str) -> bool:
    m = AMENDED_RE.fullmatch(text.strip())
    return bool(m and _valid_date(m.group(1)) and m.group(2).strip())


def token(n: int, k: int) -> str:
    return f"C-{n}#{k}"


def cites(text: str, tok: str) -> bool:
    """`C-3#1` never matches inside `C-3#12`; `C-3` never inside `C-13`."""
    return re.search(r"(?<![0-9A-Za-z-])" + re.escape(tok) + r"(?!\d)", text) is not None


def cycle_number(name: str) -> int | None:
    m = NAME_RE.fullmatch(name)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------
@dataclass
class DoneItem:
    mark: str            # " " open, "x" met, "-" not met
    text: str            # everything after "[m] "

    @property
    def before(self) -> str:
        """Text before the first resolution separator."""
        return SEP_RE.split(self.text, 1)[0]

    @property
    def evidence(self) -> str | None:
        parts = SEP_RE.split(self.text, 1)
        return parts[1].strip() if len(parts) == 2 else None


@dataclass
class Cycle:
    path: str                       # "cycles/C-3.md"
    number: int
    header: dict = field(default_factory=dict)
    tasks: list = field(default_factory=list)
    done: list = field(default_factory=list)       # list[DoneItem]
    nxt: list = field(default_factory=list)
    intake: list = field(default_factory=list)
    sections: set = field(default_factory=set)
    fatal: list = field(default_factory=list)      # grammar: not comparable

    @property
    def closed(self) -> bool:
        return "closed" in self.header

    @property
    def ident(self) -> str:
        return f"C-{self.number}"

    def demands(self) -> list[tuple[str, str]]:
        """(id, size) pairs; malformed entries are C2's to report."""
        out = []
        for part in (self.header.get("demands") or "").split(","):
            m = DEMAND_RE.fullmatch(part.strip())
            if m:
                out.append((m.group(1), m.group(2)))
        return out

    def next_items(self) -> list[str]:
        """The tokenized next-cycle items (`none` carries no token)."""
        return [] if self.nxt == ["none"] else list(self.nxt)


def parse(path: str, data: bytes | str) -> Cycle:
    name = path.rsplit("/", 1)[-1]
    n = cycle_number(name)
    c = Cycle(path=path, number=n if n is not None else -1)
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            c.fatal.append(f"not UTF-8 ({e.reason} at byte {e.start})")
            return c
    else:
        text = data
    lines = text.splitlines()
    head = []
    for line in lines[:HEADER_MAX_LINES]:
        if line.startswith("## "):
            break
        head.append(line)
    c.header = _header_fields("\n".join(head))

    current = None
    for line in lines:
        if line.startswith("## "):
            if line in KNOWN_SECTIONS:
                if line in c.sections:
                    c.fatal.append(f"heading '{line}' appears more than once")
                c.sections.add(line)
                current = line
            else:
                current = None
            continue
        if current is None or not line.startswith("- "):
            continue
        item = line[2:].strip()
        if current == TASKS:
            c.tasks.append(item)
        elif current == NEXT:
            c.nxt.append(item)
        elif current == INTAKE:
            c.intake.append(item)
        else:
            m = DONE_RE.fullmatch(item)
            if not m:
                c.fatal.append(f"'## Done when' line '- {item}' is not "
                               f"'- [ ] <text>', '- [x] <text> — <evidence>' "
                               f"or '- [-] <text> — <reason>'")
                continue
            c.done.append(DoneItem(m.group(1), m.group(2).strip()))
    return c


# ---------------------------------------------------------------------------
# profile (R2): one function
# ---------------------------------------------------------------------------
def profile(sizes, stages) -> set[str]:
    keys = set(ALWAYS)
    if any(s in ("M", "L") for s in sizes):
        keys.add("promotion")
    keys |= {s for s in STAGES if s in (stages or [])}
    return keys


def item_key(item: DoneItem) -> str | None:
    t = item.before.strip()
    m = AMENDED_RE.fullmatch(t)
    if m:
        t = m.group(2).strip()
    for k in ALL_KEYS:
        if t == k or t.startswith(k + " "):
            return k
    return None


def dir_matches(d: str, ident: str) -> bool:
    """`specs/<d>` belongs to demand `ident`: equal, or `ident-…` — so
    FWD-1 never matches FWD-17-x."""
    return d == ident or d.startswith(ident + "-")


def acceptance_paths(c: Cycle) -> list[str]:
    """Every `specs/<dir>/acceptance.md` a done item names for one of the
    cycle's S+ demands — the paths C1 requires in the parent tree."""
    splus = [i for i, s in c.demands() if s != "XS"]
    out = []
    for it in c.done:
        for m in ACCEPTANCE_RE.finditer(it.text):
            if any(dir_matches(m.group(1), i) for i in splus) and m.group(0) not in out:
                out.append(m.group(0))
    return out


def _mentions_id(text: str, ident: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9._-])" + re.escape(ident)
                     + r"(?![A-Za-z0-9_-])(?!\.[A-Za-z0-9])", text) is not None


# ---------------------------------------------------------------------------
# C2 — form
# ---------------------------------------------------------------------------
def check_form(c: Cycle, stages, spec_texts: dict | None = None) -> list[str]:
    """C2 for one cycle. `spec_texts` maps a `specs/<dir>` name to its
    spec.md text in the tree being checked (size agreement)."""
    w = f"C2 {c.path}"
    out = [f"{w}: {f}" for f in c.fatal]
    if c.fatal and not c.header and not c.sections:
        return out   # undecodable: nothing further is readable

    hdr = c.header
    for key in ("cycle", "objective", "opened", "demands"):
        if not hdr.get(key):
            out.append(f"{w}: header '{key}:' missing or empty")
    for key in ("cycle", "objective", "opened", "demands", "closed"):
        if key in hdr and hdr[key] and is_placeholder(hdr[key]):
            out.append(f"{w}: header '{key}:' is an unfilled placeholder")
    ph = {k for k in hdr if hdr[k] and is_placeholder(hdr[k])}

    if hdr.get("cycle") and "cycle" not in ph and hdr["cycle"] != c.ident:
        out.append(f"{w}: header 'cycle: {hdr['cycle']}' does not equal the "
                   f"file's stem {c.ident}")
    opened = None
    if hdr.get("opened") and "opened" not in ph:
        opened = _valid_date(hdr["opened"])
        if opened is None:
            out.append(f"{w}: 'opened: {hdr['opened']}' is not a YYYY-MM-DD date")
    if "closed" in hdr and "closed" not in ph:
        closed = _valid_date(hdr["closed"])
        if closed is None:
            out.append(f"{w}: 'closed: {hdr['closed']}' is not a YYYY-MM-DD date")
        elif opened is not None and closed < opened:
            out.append(f"{w}: closed {closed} is earlier than opened {opened}")

    demands = []
    if hdr.get("demands") and "demands" not in ph:
        seen = set()
        for part in hdr["demands"].split(","):
            m = DEMAND_RE.fullmatch(part.strip())
            if not m:
                out.append(f"{w}: demand '{part.strip()}' is not '<id> (XS|S|M|L)'")
                continue
            if m.group(1) in seen:
                out.append(f"{w}: demand {m.group(1)} is listed twice")
            seen.add(m.group(1))
            demands.append((m.group(1), m.group(2)))

    for sec in (TASKS, DONE, NEXT):
        if sec not in c.sections:
            out.append(f"{w}: section '{sec}' missing")
    if TASKS in c.sections and not c.tasks:
        out.append(f"{w}: '{TASKS}' has no item")
    if DONE in c.sections and not c.done and not any("Done when" in f for f in c.fatal):
        out.append(f"{w}: '{DONE}' has no item")

    for label, items in (("Tasks", c.tasks), ("Next cycle", c.nxt),
                         ("Intake", c.intake)):
        for i, t in enumerate(items, 1):
            if not t:
                out.append(f"{w}: '## {label}' item {i} is empty")
            elif is_placeholder(t):
                out.append(f"{w}: '## {label}' item {i} is an unfilled placeholder")
    for i, it in enumerate(c.done, 1):
        if not it.text:
            out.append(f"{w}: '## Done when' item {i} is empty")
        elif is_placeholder(it.before):
            out.append(f"{w}: '## Done when' item {i} is an unfilled placeholder")
        elif it.mark != " " and not it.evidence:
            out.append(f"{w}: '## Done when' item {i} is marked [{it.mark}] with "
                       f"no ' — <evidence>'")
        if it.before.startswith("amended ") and not _amended_ok(it.before):
            out.append(f"{w}: '## Done when' item {i} is not "
                       f"'amended YYYY-MM-DD: <text>'")
    if "none" in c.nxt and not c.closed:
        out.append(f"{w}: '- none' in '## Next cycle' of an open cycle")
    for i, t in enumerate(c.intake, 1):
        if t and not is_placeholder(t):
            m = INTAKE_RE.fullmatch(t)
            if not m or (m.group(4) is not None and not m.group(4).strip()):
                out.append(f"{w}: '## Intake' item {i} is not 'C-<m>#<k> taken', "
                           f"'C-<m>#<k> deferred' or 'C-<m>#<k> dropped — <reason>'")

    # profile (R2)
    need = profile([s for _, s in demands], stages)
    counts = {k: 0 for k in ALL_KEYS}
    for it in c.done:
        k = item_key(it)
        if k:
            counts[k] += 1
    for k in sorted(need):
        if counts[k] == 0:
            out.append(f"{w}: profile key '{k}' missing from '## Done when'")
        elif counts[k] > 1:
            out.append(f"{w}: profile key '{k}' appears {counts[k]} times")
    for k in STAGES:
        if counts[k] and k not in (stages or []):
            out.append(f"{w}: '{k}' is present but [cycle].stages does not "
                       f"declare it")

    # demand-specific part
    xs = [i for i, s in demands if s == "XS"]
    inline = [it for it in c.done
              if item_key(it) is None and not ACCEPTANCE_RE.search(it.text)]
    for ident, size in demands:
        if size == "XS":
            continue
        if not any(dir_matches(m.group(1), ident)
                   for it in c.done for m in ACCEPTANCE_RE.finditer(it.text)):
            out.append(f"{w}: {size} demand {ident} has no "
                       f"specs/{ident}…/acceptance.md done item")
    if xs and not inline:
        out.append(f"{w}: XS demand(s) {', '.join(xs)} have no inline done item")
    elif len(xs) > 1:
        for ident in xs:
            if not any(_mentions_id(it.text, ident) for it in inline):
                out.append(f"{w}: XS demand {ident} is named by no inline done item")

    # size agreement
    for ident, size in demands:
        for d, text in sorted((spec_texts or {}).items()):
            if not dir_matches(d, ident):
                continue
            s = spec_size(text)
            if s is not None and s != size:
                out.append(f"{w}: {ident} is declared {size} but "
                           f"specs/{d}/spec.md triages it {s}")
    return out


# ---------------------------------------------------------------------------
# C3 — closure
# ---------------------------------------------------------------------------
def check_closure(c: Cycle) -> list[str]:
    if not c.closed:
        return []
    w = f"C3 {c.path}"
    out = []
    for i, it in enumerate(c.done, 1):
        if it.mark == " ":
            out.append(f"{w}: closed with '## Done when' item {i} unresolved")
        elif it.mark == "-":
            want = it.before.strip()
            if not any(want in n for n in c.nxt):
                out.append(f"{w}: not-met item '{want}' is not carried into "
                           f"'## Next cycle'")
    if not c.nxt:
        out.append(f"{w}: closed with an empty '## Next cycle' (write '- none' "
                   f"when nothing is left)")
    elif "none" in c.nxt and len(c.nxt) > 1:
        out.append(f"{w}: '- none' alongside other '## Next cycle' items")
    return out


# ---------------------------------------------------------------------------
# C5 — serial
# ---------------------------------------------------------------------------
def check_serial(cycles: list[Cycle], where: str) -> list[str]:
    """At most one open cycle, and it is the highest-numbered one."""
    opened = sorted(c.number for c in cycles if not c.closed)
    out = []
    if len(opened) > 1:
        out.append(f"C5 {where}: {len(opened)} open cycles "
                   f"({', '.join(f'C-{n}' for n in opened)}) — close one first")
    elif opened and cycles and opened[0] != max(c.number for c in cycles):
        out.append(f"C5 {where}: open cycle C-{opened[0]} is not the "
                   f"highest-numbered cycle")
    return out


# ---------------------------------------------------------------------------
# C4 — frozen declaration
# ---------------------------------------------------------------------------
def _header_sans_closed(c: Cycle) -> dict:
    return {k: v for k, v in c.header.items() if k != "closed"}


def check_transition(path: str, sha: str, before: Cycle | None,
                     after: Cycle | None, parent_numbers=()) -> list[str]:
    """C4: the one allowed change between a parent's version (`before`)
    and a commit's version (`after`) of one cycle file."""
    w = f"C4 {sha[:7]}"
    if before is None and after is None:
        return []
    if before is None:
        out = []
        if after.fatal:
            return [f"{w}: {path} added but cannot be parsed: {after.fatal[0]}"]
        if after.closed:
            out.append(f"{w}: {path} is added already closed — a cycle is "
                       f"added open")
        higher = [n for n in parent_numbers if n >= after.number]
        if higher:
            out.append(f"C5 {sha[:7]}: {path} is numbered at or below the "
                       f"existing C-{max(higher)}")
        return out
    if after is None:
        return [f"{w}: {path} was deleted — a cycle file is never deleted"]
    if before.fatal:
        return [f"{w}: cannot verify transition of {path}: the parent's "
                f"version does not parse ({before.fatal[0]})"]
    if after.fatal:
        return [f"{w}: cannot verify transition of {path}: this version "
                f"does not parse ({after.fatal[0]})"]
    if before.closed:
        return [f"{w}: {path} is closed in the parent and changed — a closed "
                f"cycle never changes"]
    out = []
    if _header_sans_closed(before) != _header_sans_closed(after):
        out.append(f"{w}: {path} header changed — the declaration is frozen "
                   f"from the opening commit")
    if before.tasks != after.tasks:
        out.append(f"{w}: {path} '## Tasks' changed — a discovery goes to "
                   f"'## Next cycle', never into the running cycle")
    if before.intake != after.intake:
        out.append(f"{w}: {path} '## Intake' changed")
    if before.nxt != after.nxt[:len(before.nxt)]:
        out.append(f"{w}: {path} '## Next cycle' item removed or reworded — "
                   f"the list is append-only")
    pd = [(i.mark, i.text) for i in before.done]
    if not after.closed:
        if pd != [(i.mark, i.text) for i in after.done[:len(pd)]]:
            out.append(f"{w}: {path} '## Done when' item removed, reworded or "
                       f"marked while open — the done list is frozen")
        for it in after.done[len(pd):]:
            if it.mark != " " or not _amended_ok(it.text):
                out.append(f"{w}: {path} added done item '{it.text}' is not "
                           f"'- [ ] amended YYYY-MM-DD: <text>'")
        return out
    # open -> closed
    if len(before.done) != len(after.done):
        out.append(f"{w}: {path} closing changed the number of done items "
                   f"({len(before.done)} -> {len(after.done)})")
        return out
    for i, (p, q) in enumerate(zip(before.done, after.done), 1):
        ok = (p.mark == " " and q.mark in ("x", "-")
              and any(q.text.startswith(p.text + s)
                      and q.text[len(p.text) + len(s):].strip()
                      for s in (" — ", " -- ")))
        if not ok:
            out.append(f"{w}: {path} closing rewrote done item {i} — only the "
                       f"mark ([x]/[-]) and an appended ' — <evidence>' may change")
    return out


# ---------------------------------------------------------------------------
# C6 — dispositions
# ---------------------------------------------------------------------------
@dataclass
class Disposition:
    tokens: dict = field(default_factory=dict)   # token -> list of kinds
    breaches: list = field(default_factory=list)
    pending: list = field(default_factory=list)


def check_dispositions(cycles: list[Cycle], scrum_on: bool,
                       backlog_text: str = "") -> dict:
    """C6 over the working tree. Returns {cycle number: Disposition}; each
    Disposition's `breaches` are red, `pending` are reported only."""
    by_n = {c.number: c for c in cycles}
    nums = sorted(by_n)
    result = {}
    backlog_lines = backlog_text.splitlines() if scrum_on else []

    def successor(n):
        later = [m for m in nums if m > n]
        return by_n[later[0]] if later else None

    def predecessor(n):
        earlier = [m for m in nums if m < n]
        return by_n[earlier[-1]] if earlier else None

    # intake lines citing a token that is not the immediate predecessor's
    stray = []
    for c in cycles:
        pred = predecessor(c.number)
        for t in c.intake:
            m = INTAKE_RE.fullmatch(t)
            if not m:
                continue
            n, k = int(m.group(1)), int(m.group(2))
            if pred is None or n != pred.number:
                stray.append(f"C6 {c.path}: intake cites C-{n}#{k}, which is "
                             f"not an item of the immediately previous cycle")
            elif k > len(pred.next_items()):
                stray.append(f"C6 {c.path}: intake cites C-{n}#{k}, which does "
                             f"not exist (C-{n} has {len(pred.next_items())} item(s))")

    for c in cycles:
        if not c.closed:
            continue
        d = Disposition()
        nxt = successor(c.number)
        for k, text in enumerate(c.next_items(), 1):
            tok = token(c.number, k)
            kinds = []
            if nxt is not None:
                for t in nxt.intake:
                    m = INTAKE_RE.fullmatch(t)
                    if not m or token(int(m.group(1)), int(m.group(2))) != tok:
                        continue
                    kind = m.group(3) or "dropped"
                    if kind == "taken" and not any(cites(x, tok) for x in nxt.tasks):
                        d.breaches.append(f"C6 {nxt.path}: {tok} taken, but no "
                                          f"'## Tasks' item cites it")
                    elif kind == "deferred" and not any(cites(x, tok) for x in nxt.nxt):
                        d.breaches.append(f"C6 {nxt.path}: {tok} deferred, but no "
                                          f"'## Next cycle' item cites it")
                    kinds.append(kind)
            unlabelled = False
            for line in backlog_lines:
                if cites(line, tok):
                    if any(lbl in line for lbl in EVIDENCE_LABELS):
                        kinds.append("backlog")
                    else:
                        unlabelled = True
            d.tokens[tok] = kinds
            if len(kinds) > 1:
                d.breaches.append(f"C6 {c.path}: {tok} has {len(kinds)} "
                                  f"dispositions ({', '.join(kinds)}) — exactly "
                                  f"one is allowed")
            elif not kinds:
                why = (" (backlog.md cites it without an evidence label)"
                       if unlabelled else "")
                if scrum_on:
                    d.breaches.append(f"C6 {c.path}: {tok} has no disposition — "
                                      f"capture it in backlog.md with an "
                                      f"evidence label{why}")
                elif nxt is not None:
                    d.breaches.append(f"C6 {c.path}: {tok} has no disposition in "
                                      f"{nxt.ident}'s '## Intake'")
                else:
                    d.pending.append(tok)
        result[c.number] = d
    if stray:
        result.setdefault(-1, Disposition()).breaches.extend(stray)
    return result
