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

ADR-0014's "Amendment — 2026-08-25 (FWD-018 F12)" replaced the returned
artifact's shape: it is no longer free markdown prose parsed by a
heading-classification heuristic (four review rounds — F2/F3, F8, F11,
F12 — each found a real, reproducible misclassification in that
heuristic, closing one case while leaving an adjacent branch of the same
shape open). It is now structured TOML with seven required top-level
keys (`what_this_is`, `primary_actions`, `action_consequences`,
`unclear_points`, `target_unreachable`, `unreachable_reason`,
`observed_text` — see `agents/fde-walkthrough-evaluator.md`'s "What to
return" for the exact schema and a worked example). A field either
exists at its required type or the file is a malformed artifact,
rejected outright by `parse_perceived_model` — never guessed into a
best-effort shape. This module's role shrinks to `tomllib.load()` plus
schema validation; there is no more classification for anything to be
ambiguous about.

Three of the seven fields are scored — never the free-prose
`what_this_is` field (R7), never `observed_text` (reviews/FWD-018 F10 —
a dedicated, never-scored field where a run quotes target-page text
verbatim, kept apart from its own judgment), and never the exceptional
`target_unreachable` outcome (F7):

    d(A, B) = 0                      if A and B are both empty
    d(A, B) = 1 - |A intersect B| / |A union B|   otherwise
    score   = mean(d(primary_actions), d(action_consequences), d(unclear_points))

Stdlib string/set/tomllib operations only — no embedding, no LLM call,
matching ADR-0010's rejection of anything non-deterministic on a gated
path and ADR-0011's rejection of instructed-not-measured quality.
Deterministic, symmetric, and bounded to [0, 1] as structural properties
of the formula itself, not properties that need separate proving.

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

# The seven required top-level keys of a perceived-model TOML file
# (agents/fde-walkthrough-evaluator.md's "What to return") and the
# Python type each must have. ALL seven are required, in every file,
# always — deliberately not a mix of required and optional keys (ADR-0014
# Aug-25 amendment: an optional key would reintroduce, at the file-shape
# level, the exact ambiguity this schema exists to remove — whether an
# absent key means "not applicable" or "the run forgot it"). `bool` is
# checked with `type(...) is bool`, not `isinstance`, because Python's
# `bool` is a subclass of `int` and TOML's own boolean/integer types must
# not be allowed to silently interchange here.
_REQUIRED_FIELDS: dict[str, type] = {
    "what_this_is": str,
    "primary_actions": list,
    "action_consequences": list,
    "unclear_points": list,
    "target_unreachable": bool,
    "unreachable_reason": str,
    "observed_text": list,
}


class PerceivedModelError(ValueError):
    """Raised when a perceived-model TOML file is malformed: invalid TOML
    syntax, a missing required key, or a key present at the wrong type.
    This is the whole point of the Aug-25 schema change (ADR-0014's
    amendment): a parse failure is a hard, visible rejection, never a
    best-effort guess — it cannot silently misclassify content because it
    does not produce a model at all."""


# ---------------------------------------------------------------------------
# pure cores — no fs, no git; unit-tested directly
# ---------------------------------------------------------------------------
_WS_RE = re.compile(r"\s+")


def normalize_phrase(phrase: str) -> str:
    """R7's exact normalization: strip, lowercase, internal whitespace
    collapsed to one space. The literal comparison two runs are held to —
    no NLP, no fuzzy match, matching FM-2's degeneracy warning in both
    directions. Unchanged by the Aug-25 schema amendment."""
    return _WS_RE.sub(" ", phrase.strip().lower())


def canonicalize_pair(action: str, consequence: str) -> str:
    """Join one `action_consequences` table entry's two already-split
    sides into ONE normalized string for set-membership purposes, so
    agreeing on the action while disagreeing on the consequence still
    counts as divergence on the pair — ADR-0014 section 4's own
    requirement, unchanged by the Aug-25 amendment. Before that amendment
    this function split a single free-text bullet on an arrow character
    to find the two sides; the TOML schema now hands them over already
    split (`{action = "...", consequence = "..."}`), so only the
    normalize-and-join half of the old job remains."""
    return f"{normalize_phrase(action)} -> {normalize_phrase(consequence)}"


def _require_type(data: dict, field: str, expected: type) -> object:
    if field not in data:
        raise PerceivedModelError(f"missing required field: {field!r}")
    value = data[field]
    ok = (type(value) is bool) if expected is bool else isinstance(value, expected)
    if not ok:
        raise PerceivedModelError(
            f"field {field!r} must be a {expected.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def parse_perceived_model(text: str) -> dict:
    """Parse one run's returned perceived-model TOML into
    {"what_this_is": str, "primary_actions": set[str],
    "action_consequences": set[str], "unclear_points": set[str],
    "target_unreachable": bool, "unreachable_reason": str,
    "observed_text": list[str]}.

    ADR-0014's Aug-25 amendment: the input is a TOML document with seven
    required top-level keys (`_REQUIRED_FIELDS`), never free markdown
    prose. Loaded with `tomllib.loads()` and validated field-by-field;
    invalid syntax, a missing key, or a key at the wrong type all raise
    `PerceivedModelError` with a message naming exactly what was wrong —
    there is no fallback, no guess, no partial model. `primary_actions`
    and `unclear_points` are each normalized (`normalize_phrase`) into a
    `set[str]`. `action_consequences` is an array of `{action,
    consequence}` tables; each is canonicalized (`canonicalize_pair`)
    into one `"<action> -> <consequence>"` string and collected into a
    `set[str]`, exactly reproducing R7's existing rule that agreeing on
    the action while disagreeing on the consequence still counts as
    divergence on that pair. `what_this_is` is captured verbatim for
    human reading only; it never reaches `compute_divergence`.
    `observed_text` is kept as a plain list, in file order, exactly as
    written (no lowercasing, no whitespace normalization) so it stays a
    usable verbatim quote rather than a comparison key.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise PerceivedModelError(f"malformed TOML: {e}") from e

    what_this_is = _require_type(data, "what_this_is", str)
    primary_actions_raw = _require_type(data, "primary_actions", list)
    action_consequences_raw = _require_type(data, "action_consequences", list)
    unclear_points_raw = _require_type(data, "unclear_points", list)
    target_unreachable = _require_type(data, "target_unreachable", bool)
    unreachable_reason = _require_type(data, "unreachable_reason", str)
    observed_text_raw = _require_type(data, "observed_text", list)

    for field, items in (("primary_actions", primary_actions_raw),
                         ("unclear_points", unclear_points_raw),
                         ("observed_text", observed_text_raw)):
        for i, item in enumerate(items):
            if not isinstance(item, str):
                raise PerceivedModelError(
                    f"{field}[{i}] must be a string, got {type(item).__name__}")

    pairs: set[str] = set()
    for i, pair in enumerate(action_consequences_raw):
        if not isinstance(pair, dict):
            raise PerceivedModelError(
                f"action_consequences[{i}] must be a table, "
                f"got {type(pair).__name__}")
        for side in ("action", "consequence"):
            if side not in pair:
                raise PerceivedModelError(
                    f"action_consequences[{i}] missing {side!r}")
            if not isinstance(pair[side], str):
                raise PerceivedModelError(
                    f"action_consequences[{i}].{side} must be a string, "
                    f"got {type(pair[side]).__name__}")
        pairs.add(canonicalize_pair(pair["action"], pair["consequence"]))

    return {
        "what_this_is": what_this_is,
        "primary_actions": {normalize_phrase(p) for p in primary_actions_raw},
        "action_consequences": pairs,
        "unclear_points": {normalize_phrase(p) for p in unclear_points_raw},
        "target_unreachable": target_unreachable,
        "unreachable_reason": unreachable_reason,
        "observed_text": list(observed_text_raw),
    }


def slot_distance(a: set, b: set) -> float:
    """d(A, B) — R7: both-empty scores 0 deliberately (two runs that each
    report NOTHING on a slot agree with each other on that slot, not
    "cannot be compared"); Jaccard distance otherwise. Symmetric and
    bounded to [0, 1] by construction — set union/intersection do not
    care which run is "first". Unaffected by the Aug-25 amendment."""
    if not a and not b:
        return 0.0
    union = a | b
    return round(1 - len(a & b) / len(union), 3)


def compute_divergence(model_a: dict, model_b: dict) -> dict:
    """R7's full formula: the unweighted mean of the three slot
    distances, over the enumerable slots only. Deterministic (pure
    string/set ops), symmetric, bounded to [0, 1], and never reads the
    prose "what this is" slot — none of that is asserted separately, all
    four are structural properties of this function. Unaffected by the
    Aug-25 amendment: it consumes the dict `parse_perceived_model`
    returns, not the file format that produced it.

    Returns {"score": float, "per_slot": {slot: {"intersection": int,
    "union": int, "distance": float}}, "status": "measured"|"unreachable"}.

    `status` is "unreachable" whenever either model reports
    `target_unreachable` (F7, reviews/FWD-018): the score is still
    computed, for a human reading the file, but a caller (the gate) MUST
    NOT treat it as evidence of divergence — a run that never reached the
    target is an infra failure, not an interpretation.
    """
    per_slot, distances = {}, []
    for slot in SLOTS:
        a, b = model_a.get(slot, set()), model_b.get(slot, set())
        d = slot_distance(a, b)
        per_slot[slot] = {"intersection": len(a & b), "union": len(a | b), "distance": d}
        distances.append(d)
    score = round(sum(distances) / len(distances), 3)
    status = ("unreachable"
              if model_a.get("target_unreachable") or model_b.get("target_unreachable")
              else "measured")
    return {"score": score, "per_slot": per_slot, "status": status}


def render_divergence_toml(demand: str, score: float, per_slot: dict,
                            intended_model: str, perceived_model_a: str,
                            perceived_model_b: str,
                            threshold: float | None = None,
                            status: str | None = None) -> str:
    """The exact shape ADR-0014 section 3 and skills/fde-walkthrough/SKILL.md
    document — plain, hand-editable, `tomllib`-parseable TOML, never
    produced by anything non-deterministic. `threshold` is omitted
    entirely when the caller has none declared — an absent key, not a
    guessed default (the same silence discipline as [walkthrough] itself).
    `status` is likewise omitted when the run measured normally
    ("measured" or None) and written only for the exceptional case (F7,
    e.g. "unreachable") — an absent key means business as usual.
    `perceived_model_a`/`perceived_model_b` now name `.toml` paths
    (ADR-0014's Aug-25 amendment) — the pointer mechanism itself is
    unchanged, only the extension the caller passes."""
    lines = [f'demand = "{demand}"', f"score = {score}"]
    if status not in (None, "measured"):
        lines.append(f'status = "{status}"')
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
    but it never passes silently (FM-8). Unaffected by the Aug-25
    amendment — it reads divergence.toml files, never a perceived-model
    file directly."""
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
    breaches, unmeasured = [], []
    for f in files:
        rel = f.relative_to(project).as_posix()
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            breaches.append(f"{rel}: unparseable")
            continue
        status = str(data.get("status", "measured")).lower()
        if status != "measured":
            # F7 (reviews/FWD-018): a run that never reached the target is
            # not evidence of divergence — excluded from the breach check
            # entirely, counted as not measured, never as a pass either.
            unmeasured.append(f"{rel}: {status} — excluded from the divergence budget")
            continue
        try:
            score = float(data.get("score"))
        except (TypeError, ValueError):
            breaches.append(f"{rel}: score missing or non-numeric")
            continue
        if score > thr:
            breaches.append(f"{rel}: score {score} > threshold {thr}")
    return True, breaches, unmeasured


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
                    help="compute a divergence.toml from two perceived-model.toml "
                         "files — the mechanical filing step ADR-0014 assigns to "
                         "architecture")
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
        try:
            model_a = parse_perceived_model(a_path.read_text(encoding="utf-8"))
            model_b = parse_perceived_model(b_path.read_text(encoding="utf-8"))
        except PerceivedModelError as e:
            print(f"malformed perceived-model file: {e}", file=sys.stderr)
            return 2
        result = compute_divergence(model_a, model_b)
        threshold = args.threshold
        if threshold is None:
            threshold = load_config(project).get("divergence_threshold")
        toml_text = render_divergence_toml(
            demand=args.demand, score=result["score"], per_slot=result["per_slot"],
            intended_model=args.intended_model or "", perceived_model_a=str(a_path),
            perceived_model_b=str(b_path), threshold=threshold,
            status=result["status"])
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
                status = data.get("status", "measured")
                suffix = "" if status == "measured" else f" status={status}"
                print(f"  {f.relative_to(project)}: score={data.get('score')}{suffix}")
            except tomllib.TOMLDecodeError:
                print(f"  {f.relative_to(project)}: unparseable")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
