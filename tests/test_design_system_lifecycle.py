"""DS lifecycle instruction evals: discovery before authority, bounded adoption."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class DesignSystemLifecycle(unittest.TestCase):
    def test_installed_skill_resolves_all_contracts(self):
        text = (ROOT / 'skills/fde-design-system/SKILL.md').read_text()
        self.assertEqual(text, (ROOT / '.claude/skills/fde-design-system/SKILL.md').read_text())
        for path in re.findall(r'`(\.fde/spec/[^`]+)`', text):
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertIn('.fde/spec/design-system-lifecycle.md', text)

    def test_state_actions_require_evidence_and_bounded_adoption(self):
        text = (ROOT / 'spec/design-system-lifecycle.md').read_text()
        for obligation in (
            '| Absent |', '| Implicit |', '| Fragmented |', '| Explicit |',
            'Discover before choosing', 'Consolidate before officializing',
            'Implementation drift', 'Foundation gap', 'Foundation defect',
            'Legitimate variation', 'incremental compatibility/migration',
            'pinned revision', 'Retire aliases/components only after consumer search',
            'Unknown evidence is never silently pass',
            'Passing adherence cannot close a UI/UX failure',
            'Reviewers only write findings',
        ):
            self.assertIn(obligation, " ".join(text.split()))
        self.assertEqual(text, (ROOT / '.fde/spec/design-system-lifecycle.md').read_text())

    def test_shared_pipeline_delegates_ds_detail(self):
        text = (ROOT / 'spec/product-pipeline.md').read_text()
        section = text.split('## Design system lifecycle', 1)[1].split('## Artifacts', 1)[0]
        self.assertIn('.fde/spec/design-system-lifecycle.md', section)
        self.assertNotIn('| Absent |', section)
