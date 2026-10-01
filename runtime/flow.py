#!/usr/bin/env python3
"""
flow — how long the work takes, from git alone (owner request,
2026-09-30): cycle time measures a cycle's execution, lead time the whole
pipeline, from the request to the closed (promoted, deployed) cycle.

Nothing new to fill in. The dates in plan.md carry the day, and a cycle
often fits in one; the commits carry the minute. For each cycle:
- request: the first commit that put any of its `## Items` (B-<n>) in
  backlog.md; no item, its first plan commit;
- planned: the first commit of its plan;
- signed: the first commit where its state reads `running`;
- closed: the first commit where it reads closed (or abandoned).

Cycle time is signed → closed; the owner's wait is planned → signed;
lead time is request → closed. Cycles linked by `depends:` are one
objective (kernel ADR-0024: a large objective is several small cycles,
the fde-build/fde-inspect pipeline); its lead time runs from its first
request to its last cycle closed. Wall-clock hours, nights included.
It reports; it never gates. stdlib only (I6).
"""
from __future__ import annotations

import re
import statistics
import time
from pathlib import Path

import fde_lib
import status

STATE = re.compile(r"^(state|closed|abandoned):\s*(.*)$", re.I | re.M)


def state_of(text: str) -> str:
    """The cycle's state as status.Cycle reads it: a closed:/abandoned:
    value wins, else the first word of state:."""
    head = text.split("\n## ", 1)[0]
    found = {k.lower(): v.strip() for k, v in STATE.findall(head)}
    for key in ("closed", "abandoned"):
        if found.get(key):
            return key
    words = re.findall(r"[a-z]+", found.get("state", "").lower())
    return words[0] if words else ""


def plan_path(root: Path, c: status.Cycle) -> str:
    p = c.path / "plan.md" if c.layout == "directory" else c.path
    return p.relative_to(root).as_posix()


def transitions(root: Path, rel: str) -> dict[str, int]:
    """{'planned': ts, '<state>': first ts it was read} over the plan's commits."""
    log = (fde_lib._git(root, "log", "--reverse", "--format=%H %ct", "--", rel) or "").split("\n")
    out: dict[str, int] = {}
    for line in filter(None, log):
        sha, ts = line.split()
        out.setdefault("planned", int(ts))
        st = state_of(fde_lib._git(root, "show", f"{sha}:{rel}") or "")
        if st:
            out.setdefault(st, int(ts))
    return out


def item_ids(c: status.Cycle) -> list[str]:
    """Every B-<n> in the plan's `## Items`, bullets or running prose."""
    m = re.search(r"^## Items\s*$(.*?)(?=^## |\Z)", c.text, re.M | re.S | re.I)
    found = re.findall(r"\bB-\d+\b", m.group(1)) if m else []
    found += [it["id"] for it in c.items if it.get("id")]
    return list(dict.fromkeys(found))


def requested(root: Path, ids: list[str]) -> int | None:
    """The first commit that wrote any of these backlog ids in backlog.md."""
    first = []
    for bid in ids:
        out = (fde_lib._git(root, "log", "--reverse", "--format=%ct", "-G",
                            rf"(^|[ \[(]){re.escape(bid)}([^0-9a-z-]|$)", "--", "backlog.md") or "").split()
        if out:
            first.append(int(out[0]))
    return min(first) if first else None


def _h(a: int | None, b: int | None) -> float | None:
    return round((b - a) / 3600, 1) if a is not None and b is not None and b >= a else None


def measure(root: Path) -> dict:
    cycles = status.load_cycles(root, [])
    now = int(time.time())
    rows = []
    for c in cycles:
        t = transitions(root, plan_path(root, c))
        ids = item_ids(c)
        req = requested(root, ids) or t.get("planned")
        end = t.get("closed") or t.get("abandoned")
        signed = t.get("running")
        rows.append({
            "cycle": c.id, "state": c.state, "items": len(ids),
            "depends": status.cycle_depends(c) or [],
            "request": req, "planned": t.get("planned"), "signed": signed, "ended": end,
            "wait_signoff_h": _h(t.get("planned"), signed),
            "cycle_time_h": _h(signed, end) if c.state == "closed" else None,
            "lead_time_h": _h(req, end) if c.state == "closed" else None,
            "running_for_h": _h(signed, now) if c.state == "running" else None,
        })
    return {"cycles": rows, "objectives": objectives(rows, now),
            "median": {k: _median(rows, k) for k in
                       ("wait_signoff_h", "cycle_time_h", "lead_time_h")}}


def _median(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if r[key] is not None]
    return round(statistics.median(vals), 1) if vals else None


def objectives(rows: list[dict], now: int) -> list[dict]:
    """Cycles joined by depends: (either direction), two or more."""
    by = {r["cycle"]: r for r in rows}
    parent = {c: c for c in by}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    for r in rows:
        for d in r["depends"]:
            if d in by:
                parent[find(r["cycle"])] = find(d)
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(find(r["cycle"]), []).append(r)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        live = [m for m in members if m["state"] != "abandoned"]
        if not live:
            continue
        start = min((m["request"] for m in live if m["request"]), default=None)
        done = all(m["state"] == "closed" for m in live)
        end = max((m["ended"] for m in live if m["ended"]), default=None)
        out.append({"cycles": [m["cycle"] for m in sorted(live, key=lambda m: int(m["cycle"][2:]))],
                    "closed": sum(m["state"] == "closed" for m in live),
                    "lead_time_h": _h(start, end) if done else None,
                    "open_for_h": None if done else _h(start, now)})
    return out


def render(d: dict) -> list[str]:
    f = lambda v: f"{v:.1f}h" if v is not None else "-"
    out = ["Flow (from git: request → plan → sign-off → closed)", "",
           f"  {'cycle':7}{'state':10}{'items':>6}{'wait sign-off':>15}"
           f"{'cycle time':>12}{'lead time':>11}{'running for':>13}"]
    for r in d["cycles"]:
        out.append(f"  {r['cycle']:7}{r['state']:10}{r['items']:>6}{f(r['wait_signoff_h']):>15}"
                   f"{f(r['cycle_time_h']):>12}{f(r['lead_time_h']):>11}{f(r['running_for_h']):>13}")
    m = d["median"]
    out += ["", f"  median over closed cycles: wait sign-off {f(m['wait_signoff_h'])} · "
                f"cycle time {f(m['cycle_time_h'])} · lead time {f(m['lead_time_h'])}"]
    if d["objectives"]:
        out += ["", "  objectives (cycles joined by depends:)"]
        for o in d["objectives"]:
            span = (f"lead time {f(o['lead_time_h'])}" if o["lead_time_h"] is not None
                    else f"open for {f(o['open_for_h'])}")
            out.append(f"    {', '.join(o['cycles'])}: {o['closed']}/{len(o['cycles'])} closed · {span}")
    return out
