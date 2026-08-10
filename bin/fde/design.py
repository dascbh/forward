#!/usr/bin/env python3
"""
design — the divergence gate.

FWD-010 shipped the two-diamond discipline as instruction and its own
review proved the point of ADR-0011/ADR-0012 against it: prose the model
can ignore is not a countermeasure. So divergence produces an ARTIFACT
(`specs/<demand-id>/design/alternatives.md`) and this module is what
consumes it — the same shape as the erosion budget and the traceability
graph: declared on disk, checked deterministically.

What it checks, and only this (impossible states, never incomplete ones):
a demand that HAS design artifacts and is sized M or L must record at
least two How-Might-We framings and the size's number of alternatives,
each tagged with a DISTINCT lens and a hypothesis, plus what each discard
traded. XS/S UI demands are exempt by design (ceremony stays
proportional, FWD-003).

Pure stdlib.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import project_root  # noqa: E402

LENSES = ("subtract", "invert", "analogous", "constraint-first", "object-first")
REQUIRED_ALTERNATIVES = {"m": 2, "l": 3}   # xs/s: exempt
SIZE_RE = re.compile(r"\*\*(XS|S|M|L)\*\*")
LENS_RE = re.compile(r"^\s*[-*]?\s*lens\s*:\s*([a-z-]+)", re.I | re.M)
# a framing is a LIST ITEM, so a heading plus one bullet cannot pass as two
HMW_RE = re.compile(r"^\s*[-*+]\s*.*(?:how might we|\bHMW\b)", re.I | re.M)
HYPOTHESIS_RE = re.compile(r"^\s*[-*]?\s*hypothesis\s*:\s*\S", re.I | re.M)
TRADED_RE = re.compile(r"^\s*[-*]?\s*traded\s*:\s*\S", re.I | re.M)
CHOSE_RE = re.compile(r"^\s*[-*]?\s*chose\s*:\s*\S", re.I | re.M)


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def demand_size(spec_md: Path) -> str | None:
    """Size from the Triage line only (not the first bold token anywhere)."""
    for line in _read(spec_md).splitlines():
        if "triage" in line.lower():
            m = SIZE_RE.search(line)
            return m.group(1).lower() if m else None
    return None


def has_design_surface(demand_dir: Path) -> bool:
    d = demand_dir / "design"
    return d.is_dir() and any(d.iterdir())


def check_alternatives(text: str, required: int) -> list:
    """Structural check of an alternatives.md. Returns breach messages."""
    out = []
    if len(HMW_RE.findall(text)) < 2:
        out.append("fewer than two 'How might we' framings — the reframe is "
                   "the generative move, not the render (USE-12)")
    lenses = [l.lower() for l in LENS_RE.findall(text)]
    unknown = sorted({l for l in lenses if l not in LENSES})
    if unknown:
        out.append(f"unknown lens {unknown} — one of {list(LENSES)}")
    distinct = {l for l in lenses if l in LENSES}
    if len(distinct) < required:
        out.append(f"{len(distinct)} distinct lens(es), {required} required — "
                   f"alternatives sharing a lens count as one (USE-10)")
    if len(HYPOTHESIS_RE.findall(text)) < len(lenses):
        out.append("an alternative has no 'Hypothesis:' — what it bets improves")
    if not CHOSE_RE.search(text):
        out.append("no 'Chose:' line — the convergence is not recorded")
    if lenses and len(TRADED_RE.findall(text)) < max(0, len(lenses) - 1):
        out.append("a discarded alternative has no 'Traded:' — the discard is "
                   "the evidence that makes the choice auditable (USE-10)")
    return out


def breaches(project: Path) -> list:
    """Every M/L demand with a design surface must carry its divergence."""
    out = []
    specs = project / "specs"
    if not specs.is_dir():
        return out
    for d in sorted(p for p in specs.iterdir() if p.is_dir()):
        if not has_design_surface(d):
            continue
        size = demand_size(d / "spec.md")
        required = REQUIRED_ALTERNATIVES.get(size or "", 0)
        if not required:
            continue          # xs/s (or unsized): exempt by design
        alt = d / "design" / "alternatives.md"
        if not alt.is_file():
            out.append(f"{d.name}: design surface sized {size.upper()} with no "
                       f"design/alternatives.md — converged without diverging")
            continue
        for b in check_alternatives(_read(alt), required):
            out.append(f"{d.name}: {b}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    found = breaches(project_root())
    print("\n".join(f"  ✗ {b}" for b in found) if found
          else "every M/L design surface records its divergence")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
