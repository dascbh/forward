#!/usr/bin/env python3
"""
walkthrough — the stdlib divergence metric for first-contact evidence.

ADR-0014 (FWD-018): two independent, blind `walkthrough-evaluator` runs
each return a perceived model of a running target — what the interface
communicated it is, what it implies you can do, and what it implies
happens if you do it. Neither run can reach this repository at all (a
`tools:` allowlist enforces that structurally — spec/roles.toml, not
this module); this module only consumes the two runs' RETURNED text,
once an orchestrating role (`architecture`, per ADR-0014's "Where
walkthroughs/** write access lands") has persisted it to
`walkthroughs/<demand-id>/`.

Three enumerable slots of the perceived-model schema
(agents/fde-walkthrough-evaluator.md's "What to return") are scored —
never the free-prose "what this is" line (R7):

    d(A, B) = 0                      if A and B are both empty
    d(A, B) = 1 - |A intersect B| / |A union B|   otherwise
    score   = mean(d(primary_actions), d(action_consequences), d(unclear_points))

Stdlib string/set operations only — no embedding, no LLM call, matching
ADR-0010's rejection of anything non-deterministic on a gated path and
ADR-0011's rejection of instructed-not-measured quality. Deterministic,
symmetric, and bounded to [0, 1] as structural properties of the formula
itself, not properties that need separate proving.

Thresholds are project-specific, so they are DECLARED in [walkthrough]
(I4 pattern) and the gate is silent when undeclared — the exact
discipline [erosion] already established (AGENTS.md): absent section,
gate silent; enabled with no threshold declared, "not measured", never a
vacuous pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fde_lib import project_root  # noqa: E402

SLOTS = ("primary_actions", "action_consequences", "unclear_points")


# ---------------------------------------------------------------------------
# pure cores — no fs, no git; unit-tested directly
# ---------------------------------------------------------------------------
_ARROW_RE = re.compile(r"\s*(?:->|→)\s*")
_WS_RE = re.compile(r"\s+")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_BOLD_HEADING_RE = re.compile(r"^\s{0,3}\*\*\s*(.+?)\s*\*\*\s*:?\s*$")
_BULLET_RE = re.compile(r"^\s*[-*•]\s+(\S.*)$")

# a perceived-model .md is a plain heading-and-bullet document (no markdown
# library, matching I6) — headings recognized case-insensitively, as either
# '#'..'######' or a standalone '**Heading**' line, against these four
# sections (agents/fde-walkthrough-evaluator.md's "What to return")
_SECTION_ALIASES = {
    "what this is": "what_this_is",
    "perceived primary actions": "primary_actions",
    "primary actions": "primary_actions",
    "perceived actions": "primary_actions",
    "perceived action -> consequence": "action_consequences",
    "action -> consequence": "action_consequences",
    "perceived action -> consequence pairs": "action_consequences",
    "action -> consequence pairs": "action_consequences",
    "unclear points": "unclear_points",
}


def normalize_phrase(phrase: str) -> str:
    """R7's exact normalization: strip, lowercase, internal whitespace
    collapsed to one space. The literal comparison two runs are held to —
    no NLP, no fuzzy match, matching FM-2's degeneracy warning in both
    directions."""
    return _WS_RE.sub(" ", phrase.strip().lower())


def canonicalize_pair(phrase: str) -> str:
    """An action -> consequence entry, canonicalized on BOTH sides of the
    arrow before rejoining — 'Buy Product -> Ships Free' and
    'buy product->ships free' collapse to the same set member, but
    agreeing on the action while disagreeing on the consequence still
    counts as divergence on the pair, exactly as ADR-0014 section 4
    requires. A phrase with no arrow at all falls back to a whole-phrase
    normalize rather than raising — a malformed entry still participates
    in the count deterministically."""
    parts = _ARROW_RE.split(phrase, maxsplit=1)
    if len(parts) != 2:
        return normalize_phrase(phrase)
    action, consequence = parts
    return f"{normalize_phrase(action)} -> {normalize_phrase(consequence)}"


def _canon_heading(raw: str) -> str | None:
    t = _ARROW_RE.sub(" -> ", raw.strip().rstrip(":").strip())
    t = _WS_RE.sub(" ", t).lower()
    return _SECTION_ALIASES.get(t)


def parse_perceived_model(text: str) -> dict:
    """Parse one run's returned perceived model into
    {"what_this_is": str, "primary_actions": set[str],
    "action_consequences": set[str], "unclear_points": set[str]}.

    Only a bullet line ('-', '*', or a Unicode bullet) inside one of the
    three scored sections becomes an entry — a non-bullet line there is
    prose the run added and is never scored (R6: only a phrase written as
    a short list item is comparable). The free-prose "what this is" line
    is captured for human reading only; it never reaches compute_divergence.
    """
    model: dict = {"what_this_is": "", "primary_actions": set(),
                   "action_consequences": set(), "unclear_points": set()}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        heading = None
        m = _HEADING_RE.match(line)
        if m:
            heading = _canon_heading(m.group(2))
        else:
            m2 = _BOLD_HEADING_RE.match(line)
            if m2:
                heading = _canon_heading(m2.group(1))
        if heading:
            current = heading
            continue
        if current == "what_this_is":
            if not model["what_this_is"]:
                bm = _BULLET_RE.match(line)
                model["what_this_is"] = (bm.group(1) if bm else line).strip()
            continue
        if current in SLOTS:
            bm = _BULLET_RE.match(line)
            if not bm:
                continue
            entry = bm.group(1).strip()
            if current == "action_consequences":
                model[current].add(canonicalize_pair(entry))
            else:
                model[current].add(normalize_phrase(entry))
    return model


def slot_distance(a: set, b: set) -> float:
    """d(A, B) — R7: both-empty scores 0 deliberately (two runs that each
    report NOTHING on a slot agree with each other on that slot, not
    "cannot be compared"); Jaccard distance otherwise. Symmetric and
    bounded to [0, 1] by construction — set union/intersection do not
    care which run is "first"."""
    if not a and not b:
        return 0.0
    union = a | b
    return round(1 - len(a & b) / len(union), 3)


def compute_divergence(model_a: dict, model_b: dict) -> dict:
    """R7's full formula: the unweighted mean of the three slot
    distances, over the enumerable slots only. Deterministic (pure
    string/set ops), symmetric, bounded to [0, 1], and never reads the
    prose "what this is" slot — none of that is asserted separately, all
    four are structural properties of this function.

    Returns {"score": float, "per_slot": {slot: {"intersection": int,
    "union": int, "distance": float}}}."""
    per_slot, distances = {}, []
    for slot in SLOTS:
        a, b = model_a.get(slot, set()), model_b.get(slot, set())
        d = slot_distance(a, b)
        per_slot[slot] = {"intersection": len(a & b), "union": len(a | b), "distance": d}
        distances.append(d)
    score = round(sum(distances) / len(distances), 3)
    return {"score": score, "per_slot": per_slot}


def render_divergence_toml(demand: str, score: float, per_slot: dict,
                            intended_model: str, perceived_model_a: str,
                            perceived_model_b: str,
                            threshold: float | None = None) -> str:
    """The exact shape ADR-0014 section 3 and skills/fde-walkthrough/SKILL.md
    document — plain, hand-editable, `tomllib`-parseable TOML, never
    produced by anything non-deterministic. `threshold` is omitted
    entirely when the caller has none declared — an absent key, not a
    guessed default (the same silence discipline as [walkthrough] itself)."""
    lines = [f'demand = "{demand}"', f"score = {score}"]
    if threshold is not None:
        lines.append(f"threshold = {threshold}")
    lines += [f'intended_model = "{intended_model}"',
              f'perceived_model_a = "{perceived_model_a}"',
              f'perceived_model_b = "{perceived_model_b}"',
              "", "[per_slot]"]
    for slot in SLOTS:
        s = per_slot[slot]
        lines.append(f'{slot} = {{ intersection = {s["intersection"]}, '
                     f'union = {s["union"]}, distance = {s["distance"]} }}')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# fs / config — the opt-in budget gate, [erosion]'s exact silence discipline
# ---------------------------------------------------------------------------
def load_config(project: Path) -> dict:
    cfg = project / "fde.config.toml"
    if not cfg.exists():
        return {}
    try:
        return tomllib.loads(cfg.read_text(encoding="utf-8")).get("walkthrough", {}) or {}
    except tomllib.TOMLDecodeError:
        return {}


def find_divergence_files(project: Path) -> list:
    d = project / "walkthroughs"
    if not d.is_dir():
        return []
    return sorted(d.glob("*/divergence.toml"))


def gate(project: Path) -> tuple[bool, list, list]:
    """Return (declared, breaches, unmeasured) — [erosion]'s exact shape.
    declared=False means [walkthrough] is absent or not enabled: the gate
    stays silent (never a false wall). declared=True with two empty
    lists means measured and within budget. unmeasured is what the
    config declared with nothing yet to check it against — it passes,
    but it never passes silently (FM-8)."""
    cfg = load_config(project)
    if not cfg.get("enabled"):
        return False, [], []
    threshold = cfg.get("divergence_threshold")
    if threshold is None:
        return True, [], ["divergence_threshold"]
    try:
        thr = float(threshold)
    except (TypeError, ValueError):
        return True, [], ["divergence_threshold (not a number)"]
    files = find_divergence_files(project)
    if not files:
        return True, [], ["divergence.toml (none found under walkthroughs/**)"]
    breaches = []
    for f in files:
        rel = f.relative_to(project).as_posix()
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            breaches.append(f"{rel}: unparseable")
            continue
        try:
            score = float(data.get("score"))
        except (TypeError, ValueError):
            breaches.append(f"{rel}: score missing or non-numeric")
            continue
        if score > thr:
            breaches.append(f"{rel}: score {score} > threshold {thr}")
    return True, breaches, []


def verdict(breaches: list, unmeasured: list) -> str:
    if breaches:
        return "; ".join(breaches)
    if unmeasured:
        return ("within budget, but not measured: " + ", ".join(unmeasured) +
                " — the declared threshold had nothing to check")
    return "within the declared divergence budget"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--compute", nargs=2, metavar=("PERCEIVED_A", "PERCEIVED_B"),
                    help="compute a divergence.toml from two raw perceived-model files "
                         "— the mechanical filing step ADR-0014 assigns to architecture")
    ap.add_argument("--demand", default=None)
    ap.add_argument("--intended-model", dest="intended_model", default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--out", default=None, help="write the rendered TOML here instead of stdout")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    project = project_root()

    if args.compute:
        if not args.demand:
            print("--compute requires --demand <id>", file=sys.stderr)
            return 2
        a_path, b_path = Path(args.compute[0]), Path(args.compute[1])
        model_a = parse_perceived_model(a_path.read_text(encoding="utf-8"))
        model_b = parse_perceived_model(b_path.read_text(encoding="utf-8"))
        result = compute_divergence(model_a, model_b)
        threshold = args.threshold
        if threshold is None:
            threshold = load_config(project).get("divergence_threshold")
        toml_text = render_divergence_toml(
            demand=args.demand, score=result["score"], per_slot=result["per_slot"],
            intended_model=args.intended_model or "", perceived_model_a=str(a_path),
            perceived_model_b=str(b_path), threshold=threshold)
        if args.out:
            Path(args.out).write_text(toml_text, encoding="utf-8")
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(toml_text, end="")
        return 0

    if args.gate:
        declared, breaches, unmeasured = gate(project)
        if not declared:
            print("no [walkthrough] budget declared — walkthrough mode off")
            return 0
        print(verdict(breaches, unmeasured))
        return 1 if breaches else 0

    if args.report:
        cfg = load_config(project)
        files = find_divergence_files(project)
        print("\nwalkthrough divergence signals\n")
        if cfg:
            print(f"  [walkthrough] enabled={cfg.get('enabled', False)} "
                 f"divergence_threshold={cfg.get('divergence_threshold', 'undeclared')}")
        else:
            print("  no [walkthrough] section declared — trend not gated")
        if not files:
            print("  no walkthroughs/**/divergence.toml found")
        for f in files:
            try:
                data = tomllib.loads(f.read_text(encoding="utf-8", errors="ignore"))
                print(f"  {f.relative_to(project)}: score={data.get('score')}")
            except tomllib.TOMLDecodeError:
                print(f"  {f.relative_to(project)}: unparseable")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
