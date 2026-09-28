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

When each check runs is the gate's business (architecture.md, "Revision
— round 3" governing over every earlier revision): an open cycle is judged in the working tree and at the
commit that adds it; a closed cycle is judged once, at its closing
commit, against that commit's parent configuration — never re-judged
later against today's config.

Pure: no git, no filesystem. Inputs are bytes/texts and plain data, so
every rule is unit-testable without a repository. Header parsing, the
declared spec size and the stage set are imported, never copied
(MNT-11, F15). Every breach names its legal way out (F16). Stdlib only
(I6).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import CYCLE_STAGES  # noqa: E402 — F15, one stage set
from graph import _header_fields, spec_header_size  # noqa: E402 — MNT-11

CYCLES_DIR = "cycles"
NAME_RE = re.compile(r"C-(0|[1-9][0-9]*)\.md")
HEADER_MAX_LINES = 30

ALWAYS = ("declared-before", "regression-proven", "review-rounds", "residuals")
STAGES = CYCLE_STAGES
ALL_KEYS = ALWAYS + ("promotion",) + tuple(STAGES)
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

# the legal ways out (F16) — every breach ends with one
FIX_OPEN = ("fix it before committing; once committed, amend while the "
            "opening commit is still HEAD, else close this cycle with [-] "
            "items and open the next")
FIX_CLOSE = "fix the closing commit before pushing (the cycle is still open in its parent)"
FIX_OPENING = "fix the opening commit before pushing, or close it and open the next"


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


def norm_id(s: str) -> str:
    """One demand id, however written: uppercased, every digit run read
    as an integer — `fwd-050`, `FWD-50` and `FWD-050` are one id (F2)."""
    return re.sub(r"\d+", lambda m: str(int(m.group(0))), s.upper())


def dir_matches(d: str, ident: str) -> bool:
    """`specs/<d>` belongs to demand `ident`: equal after normalization,
    or `ident-…` — so FWD-1 never matches FWD-17-x."""
    nd, ni = norm_id(d), norm_id(ident)
    return nd == ni or nd.startswith(ni + "-")


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
                     + r"(?![A-Za-z0-9_-])(?!\.[A-Za-z0-9])", text,
                     re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# C2 — form
# ---------------------------------------------------------------------------
def check_form(c: Cycle, stages, spec_texts: dict | None = None,
               where: str | None = None, fix: str = FIX_OPEN) -> list[str]:
    """C2 for one cycle. `spec_texts` maps each `specs/<dir>` name that
    matches a listed demand to its spec.md text (None when the directory
    has no spec.md) in the tree being checked; None skips size agreement
    (C1's parent-tree check never re-judges size, R1c). `where` defaults
    to the cycle's path; `fix` is the way out appended to each breach."""
    w = f"C2 {where or c.path}"
    out = [f"{w}: {f}" for f in c.fatal]
    if c.fatal and not c.header and not c.sections:
        return [f"{b} — {fix}" for b in out]   # undecodable: nothing further

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
            if norm_id(m.group(1)) in seen:
                out.append(f"{w}: demand {m.group(1)} is listed twice")
            seen.add(norm_id(m.group(1)))
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
    if not c.closed and any(it.mark != " " for it in c.done):
        # F11: a pre-ticked open cycle could never close legally
        out.append(f"{w}: an open cycle is declared unresolved — remove the "
                   f"marks before committing")
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
            out.append(f"{w}: profile key '{k}' missing from '## Done when' "
                       f"(while open, append '- [ ] amended YYYY-MM-DD: {k}')")
        elif counts[k] > 1:
            out.append(f"{w}: profile key '{k}' appears {counts[k]} times")
    for k in STAGES:
        if counts[k] and k not in (stages or []):
            out.append(f"{w}: '{k}' is present but [cycle].stages does not "
                       f"declare it (declare the stage, or resolve the item "
                       f"[-] at close)")

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

    if spec_texts is not None:
        out += check_size(demands, spec_texts, w)
    return [f"{b} — {fix}" for b in out]


def check_size(demands, spec_texts: dict, w: str) -> list[str]:
    """R1c: a demand with a matching `specs/<dir>/` must declare the same
    size in that spec.md's `size:` header. Ambiguous or unreadable is red."""
    out = []
    for ident, size in demands:
        dirs = sorted(d for d in spec_texts if dir_matches(d, ident))
        if len(dirs) > 1:
            out.append(f"{w}: {ident} matches {len(dirs)} spec directories "
                       f"({', '.join(dirs)}) — name the demand unambiguously")
            continue
        if not dirs:
            continue
        d = dirs[0]
        text = spec_texts[d]
        if text is None:
            out.append(f"{w}: specs/{d}/spec.md is absent — add it with a "
                       f"\"size: {size}\" header, or correct demands:")
            continue
        s = spec_header_size(text)
        if s is None:
            out.append(f"{w}: add \"size: {size}\" to specs/{d}/spec.md's "
                       f"header, or correct demands:")
        elif s != size:
            out.append(f"{w}: {ident} is declared {size} but specs/{d}/spec.md "
                       f"says size: {s} — correct demands: or the spec's size:")
    return out


# ---------------------------------------------------------------------------
# C3 — closure (run once, at the closing commit)
# ---------------------------------------------------------------------------
def check_closure(c: Cycle, where: str | None = None, fix: str = FIX_CLOSE) -> list[str]:
    if not c.closed:
        return []
    w = f"C3 {where or c.path}"
    out = []
    for i, it in enumerate(c.done, 1):
        if it.mark == " ":
            out.append(f"{w}: closed with '## Done when' item {i} unresolved")
    # F12: one next-cycle item per not-met item, matched by prefix
    unmet = sorted((it.before.strip() for it in c.done if it.mark == "-"),
                   key=len, reverse=True)
    used: set[int] = set()
    for t in unmet:
        k = next((j for j, n in enumerate(c.nxt)
                  if j not in used and n.startswith(t)), None)
        if k is None:
            out.append(f"{w}: not-met item \"{t}\" needs its own next-cycle "
                       f"item starting with its text")
        else:
            used.add(k)
    if not c.nxt:
        out.append(f"{w}: closed with an empty '## Next cycle' (write '- none' "
                   f"when nothing is left)")
    elif "none" in c.nxt and len(c.nxt) > 1:
        out.append(f"{w}: '- none' alongside other '## Next cycle' items")
    return [f"{b} — {fix}" for b in out]


# ---------------------------------------------------------------------------
# C5 — serial
# ---------------------------------------------------------------------------
def check_serial(cycles: list[Cycle], where: str) -> list[str]:
    """At most one open cycle, and it is the highest-numbered one."""
    opened = sorted(c.number for c in cycles if not c.closed)
    out = []
    if len(opened) > 1:
        out.append(f"C5 {where}: {len(opened)} open cycles "
                   f"({', '.join(f'C-{n}' for n in opened)}) — close one "
                   f"first; {FIX_OPENING}")
    elif opened and cycles and opened[0] != max(c.number for c in cycles):
        out.append(f"C5 {where}: open cycle C-{opened[0]} is not the "
                   f"highest-numbered cycle — {FIX_OPENING}")
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
    later = ("the declaration is frozen; close this cycle with [-] items "
             "and reasons, and open the next")
    if before is None and after is None:
        return []
    if before is None:
        out = []
        if after.fatal:
            return [f"{w}: {path} added but cannot be parsed: {after.fatal[0]} "
                    f"— {FIX_OPENING}"]
        if after.closed:
            out.append(f"{w}: {path} is added already closed — a cycle is "
                       f"added open, then closed in a later commit")
        higher = [n for n in parent_numbers if n >= after.number]
        if higher:
            out.append(f"C5 {sha[:7]}: {path} is numbered at or below the "
                       f"existing C-{max(higher)} — number it C-{max(parent_numbers) + 1}")
        return out
    if after is None:
        return [f"{w}: {path} was deleted — a cycle file is never deleted; "
                f"restore it"]
    if before.fatal:
        return [f"{w}: cannot verify transition of {path}: the parent's "
                f"version does not parse ({before.fatal[0]}) — restore a "
                f"parseable parent version before pushing"]
    if after.fatal:
        return [f"{w}: cannot verify transition of {path}: this version "
                f"does not parse ({after.fatal[0]}) — fix this commit before "
                f"pushing"]
    if before.closed:
        return [f"{w}: {path} is closed in the parent and changed — a closed "
                f"cycle never changes; revert the edit"]
    out = []
    if _header_sans_closed(before) != _header_sans_closed(after):
        out.append(f"{w}: {path} header changed — {later}")
    if before.tasks != after.tasks:
        out.append(f"{w}: {path} '## Tasks' changed — a discovery goes to "
                   f"'## Next cycle', never into the running cycle; {later}")
    if before.intake != after.intake:
        out.append(f"{w}: {path} '## Intake' changed — {later}")
    if before.nxt != after.nxt[:len(before.nxt)]:
        out.append(f"{w}: {path} '## Next cycle' item removed or reworded — "
                   f"the list is append-only; restore the items")
    pd = [(i.mark, i.text) for i in before.done]
    if not after.closed:
        if pd != [(i.mark, i.text) for i in after.done[:len(pd)]]:
            out.append(f"{w}: {path} '## Done when' item removed, reworded or "
                       f"marked while open — {later}")
        for it in after.done[len(pd):]:
            if it.mark != " " or not _amended_ok(it.text):
                out.append(f"{w}: {path} added done item '{it.text}' is not "
                           f"'- [ ] amended YYYY-MM-DD: <text>' — rewrite it "
                           f"in that form")
        return out
    # open -> closed
    if len(before.done) != len(after.done):
        out.append(f"{w}: {path} closing changed the number of done items "
                   f"({len(before.done)} -> {len(after.done)}) — {FIX_CLOSE}")
        return out
    for i, (p, q) in enumerate(zip(before.done, after.done), 1):
        if p.mark == q.mark == " " and p.text == q.text:
            continue   # left unresolved: C3's "unresolved" breach names it
        ok = (p.mark == " " and q.mark in ("x", "-")
              and any(q.text.startswith(p.text + s)
                      and q.text[len(p.text) + len(s):].strip()
                      for s in (" — ", " -- ")))
        if not ok:
            out.append(f"{w}: {path} closing rewrote done item {i} — only the "
                       f"mark ([x]/[-]) and an appended ' — <evidence>' may "
                       f"change; {FIX_CLOSE}")
    return out


# ---------------------------------------------------------------------------
# C6 — dispositions, checked at the transition where they happen (R1e)
# ---------------------------------------------------------------------------
def captured(backlog_text: str, tok: str) -> bool:
    """A labelled backlog.md line cites `tok`."""
    return any(cites(line, tok) and any(lbl in line for lbl in EVIDENCE_LABELS)
               for line in backlog_text.splitlines())


def check_capture(c: Cycle, backlog_text: str, sha: str) -> list[str]:
    """Scrum on, at the open→closed transition: every item except `none`
    is cited, with an evidence label, in the closing commit's own
    backlog.md. Afterwards the backlog is groomed freely."""
    out = []
    for k, _t in enumerate(c.next_items(), 1):
        tok = token(c.number, k)
        if not captured(backlog_text, tok):
            out.append(f"C6 {sha[:7]}: {tok} is not captured in the closing "
                       f"commit's backlog.md — add a line citing {tok} with an "
                       f"evidence label ({', '.join(EVIDENCE_LABELS)}) in the "
                       f"same commit")
    return out


def captured_tokens(c: Cycle, backlog_text: str) -> set[str]:
    """The tokens of closed cycle `c` that `backlog_text` (backlog.md as it
    stood at c's closing commit) cites on a labelled line."""
    return {token(c.number, k) for k in range(1, len(c.next_items()) + 1)
            if captured(backlog_text, token(c.number, k))}


def check_opening(new: Cycle, tree: list[Cycle], closing_backlog: str,
                  sha: str) -> list[str]:
    """C6 at the absent→open transition of `new`, whatever the scrum mode
    (R2e). `tree` is the parent's cycles; `closing_backlog` is backlog.md
    at the predecessor's closing commit. Every predecessor item except
    `none` is disposed of exactly once: captured there, or in `new`'s
    Intake as taken/deferred/dropped. A captured item, or an item of an
    older cycle, may appear only as `taken` — a pull — and a token may be
    pulled once across all cycles (F25)."""
    w = f"C6 {sha[:7]} {new.ident}"
    by_n = {c.number: c for c in tree}
    closed_below = [c for c in tree if c.closed and c.number < new.number]
    pred = max(closed_below, key=lambda c: c.number) if closed_below else None
    caught = captured_tokens(pred, closing_backlog) if pred else set()
    taken_before = set()
    for c in tree:
        if c.number == new.number:
            continue
        for t in c.intake:
            m = INTAKE_RE.fullmatch(t)
            if m and m.group(3) == "taken":
                taken_before.add(token(int(m.group(1)), int(m.group(2))))
    out, seen = [], {}
    for t in new.intake:
        m = INTAKE_RE.fullmatch(t)
        if not m:
            continue   # C2 reports the grammar
        n, k, kind = int(m.group(1)), int(m.group(2)), (m.group(3) or "dropped")
        tok = token(n, k)
        src = by_n.get(n)
        if src is None or not src.closed or k > len(src.next_items()):
            out.append(f"{w}: intake cites {tok}, which names no item of a closed "
                       f"cycle — correct the token in this opening commit")
            continue
        seen[tok] = seen.get(tok, 0) + 1
        pull_only = tok in caught or pred is None or n != pred.number
        if pull_only and kind != "taken":
            why = "is already captured in the backlog" if tok in caught else \
                "is not an item of the previous cycle"
            out.append(f"{w}: {tok} {why}, so it may appear only as 'taken' (a "
                       f"pull) — change it to '{tok} taken' or remove it")
        if kind == "taken" and tok in taken_before:
            out.append(f"{w}: {tok} was already taken by an earlier cycle — "
                       f"remove it from '## Intake'")
        if kind == "taken" and not any(cites(x, tok) for x in new.tasks):
            out.append(f"{w}: {tok} taken, but no '## Tasks' item cites it — "
                       f"cite {tok} in the task that takes it")
        if kind == "deferred" and not any(cites(x, tok) for x in new.nxt):
            out.append(f"{w}: {tok} deferred, but no '## Next cycle' item cites "
                       f"it — re-list it there with {tok}")
    for tok, count in seen.items():
        if count > 1:
            out.append(f"{w}: {tok} appears {count} times in '## Intake' — keep "
                       f"exactly one")
    if pred is not None:
        for k in range(1, len(pred.next_items()) + 1):
            tok = token(pred.number, k)
            if tok not in caught and tok not in seen:
                out.append(f"{w}: {tok} has no disposition — add it to ## Intake "
                           f"(taken/deferred/dropped) in this opening commit")
    return out


KINDS = ("captured", "taken", "deferred", "dropped", "pending", "missing")


def disposition_report(cycles: list[Cycle], closing_backlogs: dict) -> dict:
    """Report only (F28): per closed cycle n, each item's one kind —
    captured (backlog.md at n's closing commit, `closing_backlogs[n]`),
    else the next cycle's Intake verdict, else pending (no later cycle)
    or missing (a later cycle, no disposition). The kinds sum to the
    item count. {n: {kind: [tokens]}}"""
    by_n = {c.number: c for c in cycles}
    nums = sorted(by_n)
    out = {}
    for c in cycles:
        if not c.closed:
            continue
        later = [n for n in nums if n > c.number]
        succ = by_n[later[0]] if later else None
        verdict = {}
        for t in (succ.intake if succ else []):
            m = INTAKE_RE.fullmatch(t)
            if m and int(m.group(1)) == c.number:
                verdict.setdefault(token(c.number, int(m.group(2))), m.group(3) or "dropped")
        caught = captured_tokens(c, closing_backlogs.get(c.number, ""))
        kinds = {k: [] for k in KINDS}
        for k in range(1, len(c.next_items()) + 1):
            tok = token(c.number, k)
            kind = ("captured" if tok in caught else verdict.get(tok)
                    or ("pending" if succ is None else "missing"))
            kinds[kind].append(tok)
        out[c.number] = kinds
    return out
