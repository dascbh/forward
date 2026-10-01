#!/usr/bin/env python3
"""
forecast — when a running cycle will likely end, from the project's own
history (owner, 2026-10-01: "I have no idea how long a cycle will take").

Reference-class forecasting, the way Kanban teams forecast delivery: no
estimate is asked of anyone; the project's past says how long its work
takes. Two distributions, both measured from git and the boards:
- a demand: from its first board line to its merge (status.py);
- a closing: from a cycle's last merge to its close (flow.py).

Monte Carlo, 2,000 runs: in each, every demand not merged draws a
duration from the past ones (a begun demand draws from those longer than
what it has run, minus that); demands wait for the demands they depend
on — a demand in review draws from the past review → merge times, since
it is near its merge whatever its build took — a cycle that waits for another (`depends:`) starts when that one's
build ends, and a closing is drawn the same way. The likely end (p50) and
the pessimistic one (p85) are read from the 2,000 totals — never a sum of
pessimistic pieces, which no run would ever see (a first version summed
them and read a day for a half-day's work). A cycle whose draws ran out
of history — fewer than 3 past values longer than what it has run — or a
project with fewer than 8 past demands or closings is marked low
confidence: the numbers move a lot as history grows. Fewer than 3 past demands: no forecast —
a number from nothing is a guess; fewer than 3 closings: the forecast
stops at the last merge and says so. Wall-clock hours.
stdlib only (I6).
"""
from __future__ import annotations

import random
import re
import statistics
import time
from pathlib import Path

import flow
import status

MIN_SAMPLES = 3
RUNS = 2000  # Monte Carlo simulations of the remaining work
CONFIDENT = 8  # past demands and closings below this: the forecast says it is thin
WEEK = 7 * 86400


def _pct(values: list[float], q: float) -> float:
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    k = (len(values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


LATE = re.compile(r"review|revis|triag|suite exit 0|record-suite|su[ií]te exit 0")


def _late_since(d: dict) -> int | None:
    """When a demand reached its late phases (suite done, review), from its
    board lines: what is left after that is review, fixes, merge."""
    at = [e["at"] for e in d.get("events", []) if e.get("at") and LATE.search(e["text"].lower())]
    return min(at) if at else None


def history(root: Path) -> dict:
    """Seconds per merged demand, from review to merge, and per closing."""
    demands, tails, closings = [], [], []
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
                    late = _late_since(d)
                    if late and d["started"] <= late < end:
                        tails.append(end - late)
    for r in flow.measure(root)["cycles"]:
        if r["state"] == "closed" and r.get("closing_h") is not None and r["closing_h"] > 0:
            closings.append(r["closing_h"] * 3600)
    return {"demands": demands, "tails": tails, "closings": closings}


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
    rng = random.Random(7)  # the same history gives the same forecast
    thin: set = set()  # cycles whose draws ran out of history

    tails = h.get("tails") or []

    def draw_left(d: dict | None, cid: str = "") -> float:
        """A demand's remaining time, drawn from the past. In review or
        later: from the past review → merge times longer than its time in
        review (a demand in review is near its merge, whatever its build
        took). Building: from the past whole durations longer than what it
        has run. Not begun: any past duration."""
        if d is None:
            return rng.choice(h["demands"])
        late = _late_since(d)
        if late and len(tails) >= MIN_SAMPLES:
            pool, elapsed = tails, now - late
        else:
            pool, elapsed = h["demands"], now - d["started"]
        longer = [x - elapsed for x in pool if x > elapsed]
        if len(longer) < MIN_SAMPLES:
            thin.add(cid)  # past almost all of this project's history
        return rng.choice(longer) if longer else _pct(pool, 0.5) / 10

    def simulate() -> dict:
        memo: dict = {}

        def build_end(cid: str, seen=()) -> float:
            if cid in memo:
                return memo[cid]
            p = progress.get(cid)
            if p is None or cid in seen:
                return now
            start = max([now] + [build_end(w, seen + (cid,)) for w in p.get("waits", [])])
            ds = {d["id"]: d for d in p["demands"]}
            fin: dict = {}

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
                    fin[did] = max(after, now) + draw_left(d, cid)
                else:
                    fin[did] = after + draw_left(None, cid)
                return fin[did]
            ends = [done_at(i) for i in ds]
            memo[cid] = max(ends) if ends else now
            return memo[cid]

        out = {}
        for c in cycles:
            p = progress[c.id]
            b = build_end(c.id)
            closing = 0.0
            if with_close:
                all_merged = bool(p["demands"]) and all(d["merged"] for d in p["demands"])
                ran = (now - b) if all_merged and b <= now else 0
                longer = [x - ran for x in h["closings"] if x > ran]
                if len(longer) < MIN_SAMPLES:
                    thin.add(c.id)
                closing = rng.choice(longer) if longer else clo["p50"] / 10
            out[c.id] = max(b, now) + closing
        return out

    runs = [simulate() for _ in range(RUNS)]
    rows = []
    for c in cycles:
        p = progress[c.id]
        ends = [r[c.id] for r in runs]
        rows.append({"cycle": c.id, "title": p["title"],
                     "remaining": sum(not d["merged"] for d in p["demands"]),
                     "p50": int(_pct(ends, 0.5)), "p85": int(_pct(ends, 0.85)),
                     "low_confidence": c.id in thin or len(h["closings"]) < CONFIDENT
                     or len(h["demands"]) < CONFIDENT})
    return {"enough": True, "with_closing": with_close, "now": now, "runs": RUNS,
            "demands": len(h["demands"]), "closings": len(h["closings"]),
            "demand_h": {k: round(v / 3600, 1) for k, v in dem.items()},
            "closing_h": {k: round(v / 3600, 1) for k, v in clo.items()},
            "cycles": rows}


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
                   f"{_when(r['p85'], f['now'])} · {r['remaining']} demand(s) to merge"
                   + ("  — low confidence: little history, or past most of it"
                      if r.get("low_confidence") else ""))
    return out
