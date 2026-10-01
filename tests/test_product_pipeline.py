"""Instruction evals: installed entry points resolve one portable contract."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ProductPipelineContract(unittest.TestCase):
    def test_installed_entries_resolve_the_shared_contract(self):
        for name in ('fde-build', 'fde-inspect', 'fde-design-system'):
            source = ROOT / 'skills' / name / 'SKILL.md'
            installed = ROOT / '.claude/skills' / name / 'SKILL.md'
            self.assertEqual(source.read_text(), installed.read_text())
            refs = re.findall(r'`(\.fde/spec/[^`]+)`', installed.read_text())
            self.assertTrue(refs, name)
            for ref in refs:
                self.assertTrue((ROOT / ref).is_file(), ref)

    def test_quality_contract_keeps_evidence_and_verdicts_separate(self):
        text = (ROOT / 'spec/product-pipeline.md').read_text()
        for obligation in (
            'Information density', 'Semantic economy', 'Action topology',
            'Visual hierarchy alignment', 'Interaction friction',
            'Task effectiveness', 'Cognitive economy', 'Journey topology',
            'Expectation/feedback alignment', 'Effort and recovery',
            'Design-system adherence is a separate gate',
            'Unknown is never silently pass',
            'self-check never substitutes',
            'MAP gate is advisory', 'signed plans stay frozen',
        ):
            self.assertIn(obligation, text)
        self.assertEqual(text, (ROOT / '.fde/spec/product-pipeline.md').read_text())


class EntriesPointNotCopy(unittest.TestCase):
    def test_the_entry_skills_share_no_paragraph(self):
        # written once in the spec, cited by each entry (MNT-1): the three
        # skills once repeated four paragraphs verbatim
        def paragraphs(name):
            text = (ROOT / 'skills' / name / 'SKILL.md').read_text().split('---', 2)[2]
            return {' '.join(p.split()) for p in text.split('\n\n') if len(p.split()) >= 20}
        a, b, c = (paragraphs(n) for n in ('fde-build', 'fde-inspect', 'fde-design-system'))
        self.assertEqual(a & b, set())
        self.assertEqual(a & c, set())
        self.assertEqual(b & c, set())

    def test_each_entry_says_when_to_use_it(self):
        for name in ('fde-build', 'fde-inspect', 'fde-design-system'):
            head = (ROOT / 'skills' / name / 'SKILL.md').read_text().split('---', 2)[1]
            self.assertIn('Use when', head, name)
