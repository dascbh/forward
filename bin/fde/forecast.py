#!/usr/bin/env python3
"""
forecast — when a running cycle will likely end, from the project's own
history (owner, 2026-10-01: "I have no idea how long a cycle will take").

Reference-class forecasting, the way Kanban teams forecast delivery: no
estimate is asked of anyone; the project's past says how long its work
takes. Two distributions, both measured from git and the boards:
- a demand: from its first board line to its merge (status.py);
- a closing: from a cycle's last merge to its close (flow.py).

For each running cycle, every demand not merged gets the rest of the
median if it has begun (never less than a tenth of it), the whole median
if not; demands wait for the demands they depend on, and a cycle that
waits for another (`depends:`) starts when that one's build ends. The
build ends at the last demand; the closing is added, less what has run
of it. Two answers: likely (p50) and pessimistic (p85, every remaining
piece at its 85th percentile). Fewer than 3 past demands: no forecast —
a number from nothing is a guess; fewer than 3 closings: the forecast
stops at the last merge and says so. Wall-clock hours.
stdlib only (I6).
"""
from __future__ import annotations

import statistics
import time
from pathlib import Path

import flow
import status

MIN_SAMPLES = 3
WEEK = 7 * 86400


def _pct(values: list[float], q: float) -> float:
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def history(root: Path) -> dict:
    """Seconds per merged demand, and per closing, over every cycle."""
    demands, closings = [], []
    cycles = status.load_cycles(root, [])
    for c in cycles:
        if c.state not in ("running", "closed") or c.layout != "directory":
            continue
        p = status.cycle_progress(root, c)
        # a merge line written later than the merge (backfilled) reads
        # late: git's own merge time wins when it is earlier
        on_main = status.merged_on_main(root, [d["id"] for d in p["demands"] if d["merged"]])
        for d in p["demands"]:
            if d["merged"] and d["started"] and d["last"]:
                end = min(d["last"], on_main.get(d["id"], d["last"]))
                took = end - d["started"]
                if 0 < took < WEEK:
                    demands.append(took)
    for r in flow.measure(root)["cycles"]:
        if r["state"] == "closed" and r.get("closing_h") is not None and r["closing_h"] > 0:
            closings.append(r["closing_h"] * 3600)
    return {"demands": demands, "closings": closings}


def forecast(root: Path, now: int | None = None) -> dict:
    now = now or int(time.time())
    h = history(root)
    if len(h["demands"]) < MIN_SAMPLES:
        return {"enough": False, "demands": len(h["demands"]), "closings": len(h["closings"]),
                "cycles": []}
    q = {"p50": 0.5, "p85": 0.85}
    dem = {k: _pct(h["demands"], v) for k, v in q.items()}
    # too few closings: forecast the last merge only, and say so
    with_close = len(h["closings"]) >= MIN_SAMPLES
    clo = {k: (_pct(h["closings"], v) if with_close else 0.0) for k, v in q.items()}
    cycles = [c for c in status.load_cycles(root, []) if c.state == "running"
              and c.layout == "directory"]
    progress = {c.id: status.cycle_progress(root, c) for c in cycles}
    memo: dict = {}

    def build_end(cid: str, k: str, seen=()) -> float:
        """When the cycle's last demand merges, at quantile k."""
        if (cid, k) in memo:
            return memo[(cid, k)]
        p = progress.get(cid)
        if p is None or cid in seen:
            return now
        start = max([now] + [build_end(w, k, seen + (cid,)) for w in p.get("waits", [])])
        fin: dict = {}
        ds = {d["id"]: d for d in p["demands"]}

        def done_at(did: str, chain=()) -> float:
            if did in fin:
                return fin[did]
            d = ds[did]
            if d["merged"]:
                fin[did] = d["last"] or now
                return fin[did]
            after = max([start] + [done_at(w, chain + (did,)) for w in d.get("waits", [])
                                   if w in ds and w not in chain])
            if d["begun"] and d["started"]:
                left = max(dem[k] - (now - d["started"]), dem[k] / 10)
                fin[did] = max(after, now) + left
            else:
                fin[did] = after + dem[k]
            return fin[did]
        ends = [done_at(i) for i in ds]
        memo[(cid, k)] = max(ends) if ends else now
        return memo[(cid, k)]

    out = []
    for c in cycles:
        p = progress[c.id]
        row = {"cycle": c.id, "title": p["title"], "remaining": sum(not d["merged"] for d in p["demands"])}
        for k in q:
            b = build_end(c.id, k)
            all_merged = all(d["merged"] for d in p["demands"]) and p["demands"]
            ran = (now - b) if all_merged and b <= now else 0
            row[k] = int(max(b, now) + (max(clo[k] - ran, clo[k] / 10) if with_close else 0))
        out.append(row)
    return {"enough": True, "with_closing": with_close, "now": now, "demands": len(h["demands"]),
            "closings": len(h["closings"]),
            "demand_h": {k: round(v / 3600, 1) for k, v in dem.items()},
            "closing_h": {k: round(v / 3600, 1) for k, v in clo.items()},
            "cycles": out}


def _when(ts: int, now: int) -> str:
    lt = time.localtime(ts)
    day = "" if time.localtime(now).tm_yday == lt.tm_yday else time.strftime("%a ", lt)
    hours = (ts - now) / 3600
    span = f"{hours:.0f}h" if hours >= 1.5 else f"{max(hours * 60, 1):.0f}m"
    return f"{day}{time.strftime('%H:%M', lt)} (in {span})"


def render(f: dict) -> list[str]:
    if not f["enough"]:
        return [f"forecast: not enough history yet ({f['demands']} merged demands, "
                f"{f['closings']} closings; {MIN_SAMPLES} of each needed)"]
    closing = (f"{f['closings']} closings (median {f['closing_h']['p50']}h, p85 "
               f"{f['closing_h']['p85']}h)" if f.get("with_closing") else
               f"{f['closings']} closing(s) — too few: the times below are the last "
               "merge, the closing comes on top")
    out = [f"Forecast — from this project's own history: {f['demands']} demands "
           f"(median {f['demand_h']['p50']}h, p85 {f['demand_h']['p85']}h), {closing}", ""]
    for r in f["cycles"]:
        out.append(f"  {r['cycle']:5} likely {_when(r['p50'], f['now'])} · at worst "
                   f"{_when(r['p85'], f['now'])} · {r['remaining']} demand(s) to merge")
    return out
