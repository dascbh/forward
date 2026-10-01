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
closing is the last demand merged → closed (or now), and its share of
the cycle; deploy stops are the board's lines of a deploy that stopped;
lead time is request → closed. Cycles linked by `depends:` are one
objective (kernel ADR-0024: a large objective is several small cycles,
the fde-build/fde-inspect pipeline); its lead time runs from its first
request to its last cycle closed. Wall-clock hours, nights included.

Beside them, DORA's delivery measures (2024 report), with a closed cycle
as the deployment — closing requires it deployed or published:
- deployment frequency: cycles closed per week, and in the last 30 days;
- lead time for changes: from each commit to the gate's roots
  (`[gate]` paths), since the first sign-off, to the first cycle closed
  after it (when it reached production); later commits are pending;
- change failure: a `git revert` of a commit that had already reached
  production; failed deployment recovery time runs from that close to
  the revert. A backlog origin `(C-<n>)` was measured and rejected as a
  proxy: it marks debt and follow-ups found from a cycle as well as
  defects (half the closed cycles of one client would have "failed").
And the review's own measures (`reviews/*/findings.toml`): findings per
demand, how many blocked, rounds until it passed, the first-pass share.
It reports; it never gates. stdlib only (I6).
"""
from __future__ import annotations

import re
import statistics
import time
import tomllib
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


MERGED = re.compile(r"\bmerged?\b|mergiad|mesclad")
DEPLOY_STOP = re.compile(r"deploy.*(parad|stopp|halt|blocked|bloquead|não iniciad|not started|falh|failed)"
                         r"|(parad|stopped|halted).*deploy", re.I)


def closing(root: Path, c: status.Cycle, end: int | None) -> tuple[float | None, int]:
    """(hours from the last demand merged to the close — or to now —, deploy
    stops on the board). A merge line written later than its merge reads
    late: the close then looks shorter, never longer."""
    try:
        events = status.board_events(root, c)
    except Exception:  # noqa: BLE001 — a measure, never a crash
        return None, 0
    ids = {d.get("id") for d in c.demands if d.get("id")}
    merged = {}
    for e in events:
        if e["who"] in ids and e["at"] and MERGED.search(e["text"]):
            merged.setdefault(e["who"], e["at"])
    stops = sum(1 for e in events if DEPLOY_STOP.search(e["text"]))
    if not ids or len(merged) < len(ids):
        return None, stops
    last = max(merged.values())
    return _h(last, end or int(time.time())), stops


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
        if c.state in ("running", "closed"):
            close_h, stops = closing(root, c, end if c.state == "closed" else None)
            rows[-1]["closing_h"], rows[-1]["deploy_stops"] = close_h, stops
            total = _h(signed, end if c.state == "closed" else now)
            rows[-1]["closing_pct"] = (round(100 * close_h / total) if close_h is not None
                                       and total else None)
        else:
            rows[-1]["closing_h"], rows[-1]["deploy_stops"], rows[-1]["closing_pct"] = None, 0, None
    return {"cycles": rows, "objectives": objectives(rows, now),
            "median": {k: _median(rows, k) for k in
                       ("wait_signoff_h", "cycle_time_h", "lead_time_h", "closing_pct")}}


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


WEEK, MONTH = 7 * 86400, 30 * 86400


def delivery(root: Path, d: dict | None = None) -> dict:
    """DORA's measures with a closed cycle as the deployment."""
    d = d or measure(root)
    now = int(time.time())
    closes = sorted(r["ended"] for r in d["cycles"] if r["state"] == "closed" and r["ended"])
    first = (fde_lib._git(root, "log", "--reverse", "--format=%ct", "--", "fde.config.toml") or "").split()
    since = int(first[0]) if first else (closes[0] if closes else now)
    weeks = max((now - since) / WEEK, 1)
    out: dict = {"deploys": len(closes), "deploys_per_week": round(len(closes) / weeks, 1),
                 "deploys_last_30d": sum(1 for t in closes if t >= now - MONTH)}
    # lead time for changes: each code commit to the first close at or after it
    signed = [r["signed"] for r in d["cycles"] if r["signed"]]
    start = min(signed) if signed else since
    import erosion
    scope = erosion.churn_scope(root) or ()
    stamps = [int(t) for t in (fde_lib._git(root, "log", "--no-merges", "--format=%ct",
                                            f"--since=@{start}", "--", *scope) or "").split()]
    leads, pending = [], 0
    for t in stamps:
        nxt = next((c for c in closes if c >= t), None)
        if nxt is None:
            pending += 1
        else:
            leads.append((nxt - t) / 3600)
    out["change_lead_time_h"] = round(statistics.median(leads), 1) if leads else None
    out["commits_pending"] = pending
    # change failure: a revert of a commit that had already reached production
    reverts, recover = [], []
    log = fde_lib._git(root, "log", "--no-merges", "--format=%H %ct%n%b%x00",
                       f"--since=@{start}") or ""
    for block in log.split("\0"):
        head, _, body = block.strip().partition("\n")
        m = re.search(r"This reverts commit ([0-9a-f]{7,40})", body)
        if not head or not m:
            continue
        rts = int(head.split()[1])
        orig = (fde_lib._git(root, "show", "-s", "--format=%ct", m.group(1)) or "").strip()
        if not orig.isdigit():
            continue
        shipped = next((c for c in closes if c >= int(orig)), None)
        if shipped is not None and shipped <= rts:
            reverts.append(m.group(1)[:8])
            recover.append((rts - shipped) / 3600)
    out["failed_changes"] = reverts
    out["change_failure_pct"] = round(100 * len(reverts) / len(stamps), 1) if stamps else None
    out["recovery_h"] = round(statistics.median(recover), 1) if recover else None
    return out


ROUND_TABLE = re.compile(r"^(round|rodada)_?\d+$", re.I)


def reviews(root: Path) -> dict:
    """Findings per demand, blockers, rounds until it passed."""
    rows = []
    for f in sorted((root / "reviews").glob("*/findings.toml")):
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            continue
        meta = data.get("meta") or {}
        findings = [x for x in data.get("finding", []) if isinstance(x, dict)]
        tables = sum(1 for k, v in data.items() if ROUND_TABLE.match(k) and isinstance(v, dict))
        rounds = max([v for v in (meta.get("round"), meta.get("rounds_completed"))
                      if isinstance(v, int) and not isinstance(v, bool)] + [tables + 1 if tables else 1])
        rows.append({"demand": f.parent.name, "kind": str(meta.get("kind") or "?"),
                     "findings": len(findings),
                     "blocking": sum(1 for x in findings if x.get("blocking") is True),
                     "rounds": rounds})
    if not rows:
        return {"demands": 0}
    total = sum(r["findings"] for r in rows)
    return {"demands": len(rows),
            "findings_per_demand": round(statistics.median(r["findings"] for r in rows), 1),
            "blocking_pct": round(100 * sum(r["blocking"] for r in rows) / total) if total else 0,
            "rounds_median": statistics.median(r["rounds"] for r in rows),
            "first_pass_pct": round(100 * sum(1 for r in rows if r["rounds"] == 1 and not r["blocking"])
                                    / len(rows)),
            "by_kind": {k: sum(1 for r in rows if r["kind"] == k) for k in sorted({r["kind"] for r in rows})}}


def render(d: dict) -> list[str]:
    f = lambda v: f"{v:.1f}h" if v is not None else "-"
    out = ["Flow (from git: request → plan → sign-off → closed)", "",
           f"  {'cycle':7}{'state':10}{'items':>6}{'wait sign-off':>15}"
           f"{'cycle time':>12}{'lead time':>11}{'running for':>13}{'closing':>14}{'deploy stops':>14}"]
    for r in d["cycles"]:
        out.append(f"  {r['cycle']:7}{r['state']:10}{r['items']:>6}{f(r['wait_signoff_h']):>15}"
                   f"{f(r['cycle_time_h']):>12}{f(r['lead_time_h']):>11}{f(r['running_for_h']):>13}"
                   f"{(f(r.get('closing_h')) + (' ' + str(r['closing_pct']) + '%' if r.get('closing_pct') is not None else '')):>14}"
                   f"{r.get('deploy_stops', 0):>14}")
    m = d["median"]
    out += ["", f"  median over closed cycles: wait sign-off {f(m['wait_signoff_h'])} · "
                f"cycle time {f(m['cycle_time_h'])} · lead time {f(m['lead_time_h'])} · "
                f"closing {m['closing_pct'] if m['closing_pct'] is not None else '-'}% of the cycle "
                "(target under 20%; deploy stops caused by the plan: 0)"]
    if d["objectives"]:
        out += ["", "  objectives (cycles joined by depends:)"]
        for o in d["objectives"]:
            span = (f"lead time {f(o['lead_time_h'])}" if o["lead_time_h"] is not None
                    else f"open for {f(o['open_for_h'])}")
            out.append(f"    {', '.join(o['cycles'])}: {o['closed']}/{len(o['cycles'])} closed · {span}")
    return out
