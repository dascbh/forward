"""Kernel ADR-0026: a migration is reversible by construction. The plan
declares expand/contract, a checkpoint, a rehearsal on a clone and the
rollback; a missing field warns and never fails."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from prose import ProseTestCase  # noqa: E402
from support import commit_all, make_project  # noqa: E402

PLAN = "cycle: C-1\nstate: {state}\ndate: 2026-09-30\nsigned-off: 2026-09-30\n"
STEP = """cycle: C-1
date: 2026-09-30

## Step 2 — migration 087_x.sql

`python3 db/run_migrations.py 087_x.sql`
{fields}
"""
FIELDS = """- Migration: expand
- Checkpoint: `aws rds create-db-cluster-snapshot --db-cluster-snapshot-identifier pre087-<date>`
- Rehearsal: `python3 db/rehearse.py 087_x.sql` — evidence evals/C-1/rehearsal.md
- Rollback: code
"""


class TestMigrationGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = make_project(self.tmp.name)
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        commit_all(self.p, "init")

    def write(self, state, fields):
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN.format(state=state))
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(STEP.format(fields=fields))

    def gate(self):
        r = subprocess.run([sys.executable, "bin/fde/verify.py", "--gate", "migration",
                            "--format", "json"], cwd=self.p, capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)["gates"][0]

    def test_a_migration_without_its_protection_warns_and_never_fails(self):
        self.write("running", "- Rollback: rerun\n")
        code, g = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(g.get("warning"))
        self.assertIn("C-1 (Migration, Checkpoint, Rehearsal)", g["detail"])

    def test_a_declared_migration_passes(self):
        self.write("running", FIELDS)
        code, g = self.gate()
        self.assertEqual(code, 0)
        self.assertFalse(g.get("warning"), g)

    def test_an_ended_cycle_and_the_template_comment_are_not_read(self):
        self.write("closed", "")
        self.assertFalse(self.gate()[1].get("warning"))
        tpl = (ROOT / "templates" / "cycle" / "deploy.md").read_text()
        (self.p / "cycles" / "C-1" / "plan.md").write_text(PLAN.format(state="running"))
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(tpl)
        self.assertFalse(self.gate()[1].get("warning"),
                         "the template's own ADR-0026 comment is not a migration")


class TestInstructions(ProseTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_the_decision_reaches_planner_template_promotion_and_sync(self):
        adr = self.read("docs/adr/0026-a-migration-is-reversible-by-construction.md")
        self.assertIn("Expand, then contract, in separate cycles.", adr)
        self.assertIn("Nothing here blocks.", adr)
        for field in ("Migration: expand | contract | data", "Checkpoint:", "Rehearsal:",
                      "Rollback: code | down <file> (rehearsed) | forward-fix"):
            self.assertIn(field, self.read("templates/cycle/deploy.md"))
        self.assertIn("A schema change is expand/contract (kernel ADR-0026)",
                      self.read("agents/fde-spec.md"))
        self.assertIn("Missing evidence is written as a limit, never a hold",
                      self.read("agents/fde-promotion.md"))
        sync = self.read("skills/fde-sync/SKILL.md")
        self.assertIn("each migration step's protection (kernel ADR-0026)", sync)
        self.assertIn("build them now in the project as a direct-lane change", sync)
        self.assertIn("The sync builds it, the owner does not coordinate it.", adr)


if __name__ == "__main__":
    unittest.main()
