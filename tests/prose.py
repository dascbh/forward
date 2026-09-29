"""Prose pins that let prose move.

An instruction test pins a rule as the sentence that states it. Matching
that sentence byte for byte made every rewording a test edit (176+ pins,
owner direction 2026-09-29). `ProseTestCase.assertIn` keeps the exact
match as the fast path; on a miss it accepts a short window of the text
that holds every hard token of the sentence — numbers, `code`, ids such as
I1, ADR-0019, FWD-042 — and most of its content words. Rewording, reflowing
or reordering a rule passes; deleting it, or changing a number, a code
span or an id, fails.

Only `assertIn(str, str)` with a prose needle (a space and at least
MIN_PROSE characters) is relaxed. `assertNotIn`, counts and short tokens
stay exact.
"""
from __future__ import annotations

import re
import unittest

MIN_PROSE = 25
CONTENT_SHARE = 0.8

WORD = re.compile(r"[\w'’<>/.-]+|[→×~≤≥]")
HARD = re.compile(
    r"`[^`]+`"                      # code spans
    r"|\b[A-Z]{1,5}-?\d+[a-z]?\b"   # ids: I1, ADR-0019, FWD-042, MNT-9, A1
    r"|~?\d+(?:[.,]\d+)?%?"         # numbers, ~300, 1.5, 80%
    r"|[→×≤≥]"
)
STOP = frozenset("""a an the and or of to in on at by for with from as is are be
been it its this that these those not no never only one each every any all
when then than so if but into onto out up over under about which who whom
whose what where there their them they his her he she we you your our
do does done has have had was were will would can could should must may
""".split())


def _norm(s: str) -> str:
    return " ".join(s.replace("’", "'").split())


def _content(words) -> list[str]:
    out = []
    for w in words:
        w = w.lower().strip(".,;:!?()[]\"'*")
        if len(w) >= 3 and w not in STOP:
            out.append(w)
    return out


def prose_match(needle: str, haystack: str) -> tuple[bool, str]:
    """(matched, reason). Exact containment first; otherwise the best
    window of the haystack is judged on hard tokens and content share."""
    n, h = _norm(needle), _norm(haystack)
    if n in h:
        return True, "exact"
    hard = [t.strip() for t in HARD.findall(n)]
    need = _content(WORD.findall(n))
    if not need:
        return False, "no content words to match"
    spans = [m.span() for m in WORD.finditer(h)]
    size = int(len(WORD.findall(n)) * 1.6) + 6
    best, best_missing = 0.0, hard
    for start in range(0, max(1, len(spans) - size + 1), 3):
        end = spans[min(start + size, len(spans)) - 1][1]
        window = h[spans[start][0]:end]
        missing = [t for t in hard if t not in window]
        have = set(_content(WORD.findall(window)))
        share = sum(1 for w in need if w in have) / len(need)
        if not missing and share >= CONTENT_SHARE:
            return True, f"reworded ({share:.0%} of content words)"
        if share > best:
            best, best_missing = share, missing
    return False, (f"best window holds {best:.0%} of the content words; "
                   f"hard tokens missing: {best_missing or 'none'}")


class ProseTestCase(unittest.TestCase):
    def assertIn(self, member, container, msg=None):  # noqa: N802
        if (isinstance(member, str) and isinstance(container, str)
                and " " in member.strip() and len(member) >= MIN_PROSE):
            ok, why = prose_match(member, container)
            if not ok:
                self.fail(self._formatMessage(
                    msg, f"rule not stated: {member[:120]!r} — {why}"))
            return
        super().assertIn(member, container, msg)
