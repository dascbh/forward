"""S-002 instruction changes stay put and stay in sync (FWD-003/004/007).
The drift-detector pattern: instructions are behavior (ADR-0001), and
these assertions are their eval."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    parts = text.split(f"\n## {heading}", 1)
    assert len(parts) == 2, f"section '{heading}' missing"
    return parts[1].split("\n## ", 1)[0]


class TestPerDemandTriage(unittest.TestCase):
    """FWD-003 R3."""

    def test_skill_defines_per_demand_inputs_with_tiebreaks(self):
        skill = read("skills/fde-triage/SKILL.md")
        for needle in ("judged for THIS demand", "always false",
                       "Unsure → true", "take the larger",
                       "hard to undo"):
            self.assertIn(needle, skill, needle)

    def test_demand_loop_carries_the_rule_identically_in_both_surfaces(self):
        import re
        template = read("templates/AGENTS.md.template")
        agents = read("AGENTS.md")

        def normalized(text: str) -> str:
            # the example demand id is legitimately local (DEM-042 vs FWD-002)
            return re.sub(r"`[A-Z]+-\d+`", "`ID`", section(text, "Demand loop"))

        self.assertEqual(normalized(template), normalized(agents))
        flat = " ".join(section(agents, "Demand loop").split())
        for needle in ("judged for THIS demand", "always false",
                       "Unsure on either → true"):
            self.assertIn(needle, flat, needle)


class TestI1BluntnessDecision(unittest.TestCase):
    """FWD-004: the decision is on record where I1 gets explained."""

    def test_verify_skill_records_the_kept_bluntness(self):
        skill = read("skills/fde-verify/SKILL.md")
        self.assertIn("Known bluntness, kept on purpose", skill)
        self.assertIn("instructions ARE behavior", skill)


class TestExecutionProvenance(unittest.TestCase):
    """FWD-007: the transcript link is asked for wherever findings are made."""

    def test_all_provenance_surfaces_name_agent_transcript(self):
        for rel in ("templates/findings.template.toml",
                    "skills/fde-review/SKILL.md",
                    "agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md"):
            self.assertIn("agent_transcript", read(rel), rel)


class TestRuleLaneIsAParagraphNotATableRow(unittest.TestCase):
    """FWD-019/ADR-0015, R5/R6/FM-6: RULE is introduced in its own
    paragraph, positioned immediately before the existing table/sentence
    it precedes — never a row inside it, never altering a byte of it.
    Pinned literally, not just "still mentions XS somewhere": a table row
    silently added for RULE, or a reworded score sentence, would still
    contain the word XS and pass a looser check."""

    XS_S_M_L_TABLE = (
        "| score | size | active roles | adversarial rounds | ADR |\n"
        "|---|---|---|---|---|\n"
        "| ≤ 1 | XS | implementation, adversarial | 1 | no |\n"
        "| 2–3 | S | spec, implementation, adversarial | 1 | no |\n"
        "| 4–6 | M | spec, implementation, adversarial, promotion | 2 | yes |\n"
        "| ≥ 7 | L | all five | 3 | yes |"
    )

    SCORE_SENTENCE = (
        "score ≤ 1 → **XS**: implementation, adversarial, 1 round ·\n"
        "   2–3 → **S**: + spec · 4–6 → **M**: + promotion, 2 rounds, ADR ·\n"
        "   ≥ 7 → **L**: all six roles, 3 rounds, ADR."
    )

    def test_skill_table_is_unmodified_and_rule_precedes_it_as_prose(self):
        skill = read("skills/fde-triage/SKILL.md")
        self.assertIn(self.XS_S_M_L_TABLE, skill)
        heading = "## Score and size"
        self.assertIn(heading, skill)
        rule_para = skill.index("## RULE")
        table_heading = skill.index(heading)
        self.assertLess(rule_para, table_heading,
                        "RULE must be introduced before the table, never "
                        "inside or after it")
        # never a row: RULE does not appear inside the pinned table block
        # itself (already implied by the exact match above, asserted
        # again directly against the shape a smuggled row would take)
        self.assertNotIn("| RULE |", skill)

    def test_agents_and_template_score_sentence_is_unmodified(self):
        for rel in ("AGENTS.md", "templates/AGENTS.md.template"):
            text = read(rel)
            self.assertIn(self.SCORE_SENTENCE, text, rel)
            rule_para = text.index("RULE, checked mechanically")
            sentence_at = text.index(self.SCORE_SENTENCE)
            self.assertLess(rule_para, sentence_at,
                            f"{rel}: RULE paragraph must precede the "
                            f"score-boundary sentence, never follow it")

    def test_rule_paragraph_is_byte_identical_between_agents_and_template(self):
        import re
        template = read("templates/AGENTS.md.template")
        agents = read("AGENTS.md")

        def rule_paragraph(text: str) -> str:
            start = text.index("**RULE, checked mechanically")
            end = text.index(self.SCORE_SENTENCE)
            return text[start:end]

        self.assertEqual(rule_paragraph(template), rule_paragraph(agents))
        # sanity: the paragraph actually says what R5 requires, at minimum
        para = rule_paragraph(agents)
        for needle in ("Categorically distinct", "data_class", "reversible",
                      "rule_lane_max_loc", "eval_paths",
                      "eval-coverage` gate is completely unchanged",
                      "verified_by` primacy"):
            self.assertIn(needle, para, needle)


class TestGuardAuditDocs(unittest.TestCase):
    """FWD-006 R3: SETUP names the trail and the opt-in telemetry block."""

    def test_setup_documents_audit_file_and_otel_opt_in(self):
        setup = read("SETUP.md")
        self.assertIn("guard-audit.jsonl", setup)
        self.assertIn("CLAUDE_CODE_ENABLE_TELEMETRY", setup)
        self.assertIn("never enable it unasked", setup)

    def test_kernel_gitignores_its_own_audit_trail(self):
        self.assertIn(".fde/guard-audit.jsonl", read(".gitignore"))


if __name__ == "__main__":
    unittest.main()
