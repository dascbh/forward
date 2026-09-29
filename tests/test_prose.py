"""The prose matcher relaxes wording, never facts (tests/prose.py)."""
from __future__ import annotations

import unittest
from pathlib import Path

from prose import ProseTestCase, prose_match

ROOT = Path(__file__).resolve().parent.parent

RULE = ("A demand is at most about 300 production lines and has exactly one "
        "layer: `front`, `back` or `infra`.")


class TestProseMatch(unittest.TestCase):
    def test_exact_and_reflowed_text_match(self):
        self.assertTrue(prose_match(RULE, "x " + RULE + " y")[0])
        self.assertTrue(prose_match(RULE, RULE.replace(" ", "\n   "))[0])

    def test_a_reworded_rule_matches(self):
        text = ("Each demand has exactly one layer — `front`, `back` or "
                "`infra` — and at most about 300 production lines.")
        ok, why = prose_match(RULE, text)
        self.assertTrue(ok, why)

    def test_a_changed_number_fails(self):
        self.assertFalse(prose_match(RULE, RULE.replace("300", "500"))[0])

    def test_a_changed_code_span_fails(self):
        self.assertFalse(prose_match(RULE, RULE.replace("`infra`", "`ops`"))[0])

    def test_a_changed_id_fails(self):
        rule = "Code starts only inside a signed-off cycle (kernel ADR-0019)."
        self.assertFalse(prose_match(rule, rule.replace("0019", "0018"))[0])

    def test_a_deleted_rule_fails_on_the_real_agents_md(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        rule = "Only a replan asks the owner again."
        self.assertTrue(prose_match(rule, text)[0])
        self.assertFalse(prose_match(rule, text.replace(rule, ""))[0])

    def test_scattered_words_do_not_match(self):
        far = ("A demand is at most about 300 lines. " + "Filler text. " * 60
               + "Production code has exactly one layer: `front`, `back` or "
                 "`infra`.")
        self.assertFalse(prose_match(RULE, far)[0])


class TestProseTestCase(ProseTestCase):
    def test_short_tokens_and_not_in_stay_exact(self):
        with self.assertRaises(AssertionError):
            self.assertIn("B-60", "B-61 only")
        self.assertNotIn("one layer", "two layers")

    def test_a_missing_rule_names_why(self):
        with self.assertRaises(AssertionError) as cm:
            self.assertIn(RULE, "nothing about demands here at all")
        self.assertIn("rule not stated", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
