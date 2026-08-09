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
