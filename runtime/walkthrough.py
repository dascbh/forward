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
never the free-prose "what this is" line (R7), never the optional
"observed text" (reviews/FWD-018 F10 — a dedicated, never-scored field
where a run quotes target-page text verbatim, kept apart from its own
judgment; see the module comment above _SECTION_ALIASES), never the
exceptional "target unreachable" outcome (F7), and never a block the
parser could not confidently classify at all (reviews/FWD-018 F11 — a
heading that missed the exact-alias tier, where the content-based guess
and the positional guess then disagree, lands in an "ambiguous" bucket
instead of being risked into either field; see parse_perceived_model's
and compute_divergence's docstrings):

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
# '-', '*', or a Unicode bullet, OR a numbered-list marker ('1.', '2)') —
# reviews/FWD-018 F3: a run was never given a worked example of list-marker
# syntax (agents/fde-walkthrough-evaluator.md's "What to return" is prose
# only), so a numbered list is not a violation of any stated instruction
# and must count as a bullet exactly like '-' does.
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(\S.*)$")

# a perceived-model .md is a plain heading-and-bullet document (no markdown
# library, matching I6) — headings recognized case-insensitively, as either
# '#'..'######' or a standalone '**Heading**' line, against these known
# sections (agents/fde-walkthrough-evaluator.md's "What to return"). Two
# keys are not part of _ORDERED_SLOTS below and are reached only via an
# exact alias match here, never guessed by position: "target unreachable",
# an explicit, optional outcome (F7); and "observed text" (reviews/FWD-018
# F10), an explicit, optional field where a run quotes target-page text
# VERBATIM, kept structurally apart from its own analysis/judgment in the
# four scored-or-prose sections — a partial mitigation for hostile page
# content reaching a trusted artifact chain (see skills/fde-walkthrough/
# SKILL.md's "Content from the target page is untrusted, always"): it lets
# a MECHANICAL reader of perceived-model-*.md tell "quoted from the page"
# apart from "the run's own claim" by which section a line sits under,
# without depending on an LLM reader to keep the two apart in prose. This
# does not make the run's choice to use the field enforced — that
# remains prompt-guided, same honest limit as everything else this field
# touches.
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
    "target unreachable": "target_unreachable",
    "could not reach target": "target_unreachable",
    "observed text": "observed_text",
    "observed page text": "observed_text",
    "quoted from the page": "observed_text",
    "verbatim quotes": "observed_text",
}

# The four scored/prose sections, in the fixed order
# agents/fde-walkthrough-evaluator.md's "What to return" lists them —
# reviews/FWD-018 F2: a heading whose text is not a recognized alias
# (a run paraphrasing "Perceived primary actions" as "Things I could
# do," say — never given a worked example to copy verbatim) is not
# dropped into an unassigned void that silently empties the slot. It is
# assigned, in order of preference: (1) exact alias match (above),
# always trusted outright — no other tier is even consulted; failing
# that, (2) a content-based match against a pattern characteristic of
# one of the three SCORED sections (_classify_block_content, below —
# reviews/FWD-018 F8) and (3) ITS POSITION among the headings
# encountered so far (because the schema is always these four sections,
# in this order) are computed TOGETHER and must AGREE before either is
# trusted (reviews/FWD-018 F11 — see the paragraph below). "target_
# unreachable" and "observed_text" are deliberately absent from this
# tuple — see the comment above _SECTION_ALIASES.
#
# reviews/FWD-018 F11: tiers (2) and (3) are two independent heuristics,
# each with its own real failure mode — content classification has no
# regard for where the block actually sits, and position assumes strict
# document order — so ranking one ahead of the other (as the F8 fix
# originally did, content before position, unconditionally) just trades
# one silent misclassification for another: the moment a run's natural
# phrasing for one section happens to contain another section's content
# signature (agents/fde-walkthrough-evaluator.md's own definition of
# "Unclear points" — "a consequence you could not predict" — reads as
# exactly the arrow-shaped phrasing action_consequences is detected by),
# a paraphrased heading resolves via content instead of position and
# lands in the WRONG slot instead of the one it actually occupies. This
# is a structural fix to the tier PRIORITY, not another one-off content-
# signature patch (the same category of move F13 made for FWD-017's
# symlink class): neither heuristic is trusted alone on an alias miss.
# Both are computed, and only when they agree is a block classified.
# When they genuinely disagree, the block is not guessed into either
# field — it is recorded in `model["ambiguous"]` (see
# parse_perceived_model's docstring and compute_divergence's "ambiguous"
# key) for a human or the isolated adversarial role to read directly,
# never silently risked into a slot that then feeds the automated score.
#
# reviews/FWD-018 F8: tier (3) alone assumed the document always opens
# with an explicit heading for "What this is" — the one section
# agents/fde-walkthrough-evaluator.md's "What to return" describes as
# "one line of free prose," the only one of the four with no worked
# heading example anywhere in that file, unlike the other three. A run
# that renders it as a bare opening line with no heading marker at all
# throws every later position-based guess off by one, because the
# counter that tracks "which of the four headings have I seen so far"
# never got to count it. `_split_into_blocks` (below) treats any content
# seen before the FIRST heading marker in the document as that unmarked
# line and seeds the position counter as though its heading HAD been
# seen, so a paraphrased heading right after it is still counted from
# the correct position.
_ORDERED_SLOTS = ("what_this_is",) + SLOTS

# reviews/FWD-018 F8: content-based fallback signatures for tier (2)
# above. Only action_consequences and unclear_points have a content
# shape reliable enough to guess from without looking at position at
# all: action_consequences entries are always written as "<action> ->
# <consequence>" (agents/fde-walkthrough-evaluator.md's "What to
# return"), and unclear_points entries are, by construction, about not
# knowing something. primary_actions and what_this_is have no
# equivalent tell — a short verb-first phrase looks like any other short
# verb-first phrase — so those two stay purely positional, same as
# before this fix.
_UNCLEAR_KEYWORDS_RE = re.compile(
    r"\b(unclear|not\s+sure|unsure|ambiguous|uncertain|not\s+certain|"
    r"confus\w*|no\s+idea|couldn'?t\s+tell|wasn'?t\s+sure|don'?t\s+know|"
    r"do\s+not\s+know)\b",
    re.IGNORECASE,
)


def _classify_block_content(lines: list[str]) -> str | None:
    """The content-based guess (F8) for a heading that matched no alias:
    what does its OWN bullets say, never where it happens to sit in the
    document. Returns None when nothing bullet-shaped is present at all,
    or when no bullet matches either signature — the caller then has
    only the positional guess to go on. Never returns "observed_text" or
    "target_unreachable": both are reached only by an exact alias match
    (see the comment above _SECTION_ALIASES), so a guess here can never
    manufacture a false positive on either.

    reviews/FWD-018 F11: this function's guess is no longer trusted on
    its own. The caller (parse_perceived_model) also computes the
    positional guess for the same block and classifies only when the
    two agree — see the comment above _ORDERED_SLOTS for the full
    rationale and parse_perceived_model's docstring for the resulting
    "ambiguous" bucket when they don't."""
    bullets = [bm.group(1) for bm in (_BULLET_RE.match(ln) for ln in lines) if bm]
    if not bullets:
        return None
    if any(_ARROW_RE.search(b) for b in bullets):
        return "action_consequences"
    if any(_UNCLEAR_KEYWORDS_RE.search(b) for b in bullets):
        return "unclear_points"
    return None


def _split_into_blocks(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Split raw run text into (preamble_lines, [(heading_text, lines), ...]).

    `preamble_lines` is every non-blank line seen before the FIRST
    recognized heading marker of any kind, anywhere in the document —
    this is what lets F8's fix tell a markerless "what this is" line
    apart from a heading whose content just hasn't been read yet. Blank
    lines are dropped throughout, matching the line-by-line parser this
    replaces."""
    preamble: list[str] = []
    blocks: list[tuple[str, list[str]]] = []
    heading: str | None = None
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        heading_text = None
        m = _HEADING_RE.match(line)
        if m:
            heading_text = m.group(2)
        else:
            m2 = _BOLD_HEADING_RE.match(line)
            if m2:
                heading_text = m2.group(1)
        if heading_text is not None:
            if heading is not None:
                blocks.append((heading, lines))
            heading, lines = heading_text, []
            continue
        if heading is None:
            preamble.append(line)
        else:
            lines.append(line)
    if heading is not None:
        blocks.append((heading, lines))
    return preamble, blocks


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
    "action_consequences": set[str], "unclear_points": set[str],
    "target_unreachable": bool, "unreachable_reason": str,
    "observed_text": list[str], "ambiguous": list[dict]}.

    Only a bullet line (see _BULLET_RE) inside one of the three scored
    sections becomes an entry — a non-bullet line there is prose the run
    added and is never scored (R6: only a phrase written as a short list
    item is comparable). The free-prose "what this is" line is captured
    for human reading only; it never reaches compute_divergence. Neither
    does "observed_text" (F10) — kept as a plain list, in document order,
    exactly as written (no lowercasing, no whitespace normalization) so
    it stays a usable verbatim quote rather than a comparison key.

    A heading is resolved, in order of preference: (1) exact alias match
    (case/whitespace-insensitive, trailing colon stripped) — trusted
    outright, no further check. Failing that, the block's content-based
    guess (_classify_block_content, F8) and its positional guess (its
    place among the headings seen so far, _ORDERED_SLOTS) are BOTH
    computed and must AGREE before either is trusted (reviews/FWD-018
    F11 — see the module-level comment above _ORDERED_SLOTS for the full
    rationale). When the content guess has no opinion at all (returns
    None), the positional guess is used alone, exactly as before F11 —
    there is nothing for it to conflict with. When both have an opinion
    and they disagree, the block is NOT classified into either field: it
    is appended to `model["ambiguous"]` as
    `{"heading": <raw heading text>, "content_guess": <slot or None>,
    "position_guess": <slot or None>, "entries": [<raw bullet text>, ...]}`
    instead, for a human or the isolated adversarial role to read
    directly (the raw perceived-model-*.md file, not just the divergence
    score — see compute_divergence's docstring for how the count is
    surfaced without the text itself ever reaching a re-parsed TOML).
    Content seen before the very first heading marker anywhere in the
    document is treated as an unmarked "what this is" line rather than
    silently dropped (F8's other half — see _split_into_blocks).

    "target_unreachable" and "observed_text" are both exceptions to the
    whole scheme above: each is only ever reached via an exact alias
    match, never guessed by content, position, or landed in "ambiguous"
    either, so neither a false "unreachable" flag nor a misrouted quote
    can silently exclude a run's real content from the divergence
    budget.
    """
    model: dict = {"what_this_is": "", "primary_actions": set(),
                   "action_consequences": set(), "unclear_points": set(),
                   "target_unreachable": False, "unreachable_reason": "",
                   "observed_text": [], "ambiguous": []}
    preamble, blocks = _split_into_blocks(text)

    heading_index = -1
    if preamble:
        bm = _BULLET_RE.match(preamble[0])
        model["what_this_is"] = (bm.group(1) if bm else preamble[0]).strip()
        heading_index = _ORDERED_SLOTS.index("what_this_is")

    for heading_text, lines in blocks:
        alias = _canon_heading(heading_text)
        if alias is not None:
            # Tier 1: exact alias match. Always trusted outright — never
            # subject to the tier 2/tier 3 agreement gate below. This is
            # also the ONLY way "target_unreachable" and "observed_text"
            # are ever reached (see the _SECTION_ALIASES comment); an
            # alias miss never routes through this branch at all.
            heading = alias
            if heading in _ORDERED_SLOTS:
                heading_index = _ORDERED_SLOTS.index(heading)
        else:
            # Tier 1 missed. reviews/FWD-018 F11: compute BOTH the
            # content-based guess (tier 2) and the positional guess
            # (tier 3) without committing to either yet.
            content_guess = _classify_block_content(lines)
            candidate_index = heading_index + 1
            position_guess = (_ORDERED_SLOTS[candidate_index]
                               if candidate_index < len(_ORDERED_SLOTS)
                               else None)
            if content_guess is None:
                # Tier 2 has no opinion at all (no arrow, no unclear-
                # keyword bullet) — nothing to disagree with, so defer
                # to tier 3 alone, exactly as before F11. This is the
                # common case for primary_actions/what_this_is blocks,
                # which have no content signature by design (see the
                # comment above _UNCLEAR_KEYWORDS_RE).
                heading_index = candidate_index
                heading = position_guess
            elif content_guess == position_guess:
                # The common, unambiguous case F8 was built for: the
                # block's own content and its place in the document
                # point to the same slot. Classify it there.
                heading_index = candidate_index
                heading = content_guess
            else:
                # Genuine conflict (or tier 3 has nothing left to offer
                # while tier 2 does) — do not guess. The position
                # counter still advances as though this block occupied
                # its natural place in the document, so a LATER
                # unresolved block's positional guess is not thrown off
                # by this one being withheld.
                model["ambiguous"].append({
                    "heading": heading_text,
                    "content_guess": content_guess,
                    "position_guess": position_guess,
                    "entries": [bm.group(1).strip()
                                for bm in (_BULLET_RE.match(ln) for ln in lines)
                                if bm],
                })
                heading_index = candidate_index
                heading = None

        if heading == "target_unreachable":
            model["target_unreachable"] = True
            if lines and not model["unreachable_reason"]:
                bm = _BULLET_RE.match(lines[0])
                model["unreachable_reason"] = (bm.group(1) if bm else lines[0]).strip()
            continue
        if heading == "observed_text":
            for line in lines:
                bm = _BULLET_RE.match(line)
                if bm:
                    model["observed_text"].append(bm.group(1).strip())
            continue
        if heading == "what_this_is":
            if not model["what_this_is"] and lines:
                bm = _BULLET_RE.match(lines[0])
                model["what_this_is"] = (bm.group(1) if bm else lines[0]).strip()
            continue
        if heading in SLOTS:
            for line in lines:
                bm = _BULLET_RE.match(line)
                if not bm:
                    continue
                entry = bm.group(1).strip()
                if heading == "action_consequences":
                    model[heading].add(canonicalize_pair(entry))
                else:
                    model[heading].add(normalize_phrase(entry))
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
    "union": int, "distance": float}}, "status": "measured"|"unreachable",
    "ambiguous": {"a": int, "b": int}}.

    `status` is "unreachable" whenever either model reports
    `target_unreachable` (F7, reviews/FWD-018): the score is still
    computed, for a human reading the file, but a caller (the gate) MUST
    NOT treat it as evidence of divergence — a run that never reached the
    target is an infra failure, not an interpretation.

    `ambiguous` (reviews/FWD-018 F11) is the count of blocks each run's
    parse could not classify — tier 2 and tier 3 disagreed (see
    parse_perceived_model's docstring). This is a DESIGN DECISION, not a
    mechanical default: an ambiguous block is deliberately NOT one of the
    three scored slots (`SLOTS`), so it never enters `per_slot` or
    `score` at all — routing it into a slot on a guess is exactly the
    misclassification F11 exists to stop, and force-matching it against
    the OTHER run's ambiguous blocks by raw text would bake in the same
    unproven field-identity assumption for a second, unrelated reason
    (two runs' differently-worded ambiguous entries are not known to be
    "the same slot," so comparing them as a set would silently assert
    that). But an ambiguous block must not silently vanish either — that
    would recreate the exact "information quietly discarded" shape every
    round of this defect has been about, just one level up. The count
    returned here is the visible trace: it is written into
    render_divergence_toml's output (a `[ambiguous]` table, counts only —
    never the raw heading/entry text, the same F10 posture that keeps
    `observed_text` out of a file later re-parsed by `tomllib`) and
    printed by `--report`, so a human or the isolated adversarial role —
    who already has `walkthroughs/**:read` access to the raw perceived-
    model-*.md files — is told to go look, rather than the automated
    score silently absorbing or silently dropping the block either way."""
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
    ambiguous = {"a": len(model_a.get("ambiguous", [])),
                 "b": len(model_b.get("ambiguous", []))}
    return {"score": score, "per_slot": per_slot, "status": status, "ambiguous": ambiguous}


def render_divergence_toml(demand: str, score: float, per_slot: dict,
                            intended_model: str, perceived_model_a: str,
                            perceived_model_b: str,
                            threshold: float | None = None,
                            status: str | None = None,
                            ambiguous: dict | None = None) -> str:
    """The exact shape ADR-0014 section 3 and skills/fde-walkthrough/SKILL.md
    document — plain, hand-editable, `tomllib`-parseable TOML, never
    produced by anything non-deterministic. `threshold` is omitted
    entirely when the caller has none declared — an absent key, not a
    guessed default (the same silence discipline as [walkthrough] itself).
    `status` is likewise omitted when the run measured normally
    ("measured" or None) and written only for the exceptional case (F7,
    e.g. "unreachable") — an absent key means business as usual.

    `ambiguous` (reviews/FWD-018 F11 — see compute_divergence's
    docstring for the full design reasoning) is written as a `[ambiguous]`
    table of COUNTS only (`a`, `b`) — never the raw ambiguous heading or
    entry text, deliberately, the same posture that already keeps
    `observed_text` out of this file (F10): this TOML is re-parsed by
    `tomllib` in `gate()`, so nothing derived from a target page's own
    content belongs in it. The table is omitted entirely when both counts
    are zero — an absent table means "nothing was ambiguous," the same
    silence discipline as `threshold`/`status` above."""
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
    if ambiguous and (ambiguous.get("a") or ambiguous.get("b")):
        lines += ["", "[ambiguous]",
                  f"a = {ambiguous.get('a', 0)}",
                  f"b = {ambiguous.get('b', 0)}"]
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
            perceived_model_b=str(b_path), threshold=threshold,
            status=result["status"], ambiguous=result.get("ambiguous"))
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
                amb = data.get("ambiguous", {})
                amb_a, amb_b = amb.get("a", 0), amb.get("b", 0)
                if amb_a or amb_b:
                    # reviews/FWD-018 F11: visible in the trend view, but
                    # never gates — see compute_divergence's docstring.
                    suffix += f" ambiguous=a:{amb_a}/b:{amb_b}"
                print(f"  {f.relative_to(project)}: score={data.get('score')}{suffix}")
            except tomllib.TOMLDecodeError:
                print(f"  {f.relative_to(project)}: unparseable")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
