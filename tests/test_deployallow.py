"""Kernel ADR-0025: the sign-off is the machine's permission. A signed,
running cycle's deploy commands become narrow allow rules; the close takes
them back; a rule the owner wrote is never touched."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "tests"))

import deployallow  # noqa: E402
from prose import ProseTestCase  # noqa: E402

DEPLOY = """cycle: C-1
date: 2026-09-30

1. **back** — migrations
   - Irreversible: yes: drops a column

## Commands

```sh
# step 1
$ python3 db/run_migrations.py 087_x.sql 088_y.sql
npx cdk deploy DocsStack --exclusively --app <assembly-dir> --require-approval never
aws rds create-db-cluster-snapshot --db-cluster-identifier main --db-cluster-snapshot-identifier pre091-<date>
make build && make deploy
```
"""


def plan_md(state, signed=True):
    return (f"cycle: C-1\nstate: {state}\ndate: 2026-09-30\n"
            + ("signed-off: 2026-09-30 (owner: \"aprovado\")\n" if signed else "") + "\n")


class TestCommands(unittest.TestCase):
    def test_declared_lines_become_rules_and_chains_are_refused(self):
        cmds, refused = deployallow.deploy_commands(DEPLOY)
        self.assertEqual(len(cmds), 3)
        self.assertEqual(refused, ["make build && make deploy"])
        self.assertEqual(deployallow.rule(cmds[0]),
                         "Bash(python3 db/run_migrations.py 087_x.sql 088_y.sql)")
        self.assertEqual(deployallow.rule(cmds[1]),
                         "Bash(npx cdk deploy DocsStack --exclusively --app * "
                         "--require-approval never)")
        self.assertIn("pre091-*", deployallow.rule(cmds[2]))

    def test_no_section_no_commands(self):
        self.assertEqual(deployallow.deploy_commands("cycle: C-1\n`python3 x.py`\n"), ([], []))


class TestProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        (self.p / "cycles" / "C-1").mkdir(parents=True)
        (self.p / "cycles" / "C-1" / "deploy.md").write_text(DEPLOY)
        (self.p / ".claude").mkdir()
        (self.p / ".claude" / "settings.json").write_text(json.dumps(
            {"permissions": {"allow": ["Bash", "Read"], "ask": ["Bash(git push *)"]},
             "hooks": {"PreToolUse": []}}))

    def state(self, state, signed=True):
        (self.p / "cycles" / "C-1" / "plan.md").write_text(plan_md(state, signed))

    def allow(self):
        return json.loads((self.p / ".claude" / "settings.json").read_text())["permissions"]["allow"]

    def run_(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "runtime" / "deployallow.py"),
                               "--root", str(self.p), *args], capture_output=True, text=True)

    def test_sign_off_writes_and_close_takes_back(self):
        self.state("running")
        self.assertEqual(self.run_("--check").returncode, 1)
        self.run_("--write")
        allow = self.allow()
        self.assertIn("Bash(python3 db/run_migrations.py 087_x.sql 088_y.sql)", allow)
        self.assertEqual(allow[:2], ["Bash", "Read"])
        settings = json.loads((self.p / ".claude" / "settings.json").read_text())
        self.assertEqual(settings["permissions"]["ask"], ["Bash(git push *)"])
        self.assertIn("hooks", settings)
        before = self.allow()
        self.run_("--write")
        self.assertEqual(self.allow(), before, "a second write changes nothing")
        self.state("closed")
        self.run_("--write")
        self.assertEqual(self.allow(), ["Bash", "Read"])

    def test_only_a_signed_running_cycle_is_allowed(self):
        for state, signed in (("planned", False), ("running", False), ("draft", False)):
            self.state(state, signed)
            self.assertEqual(deployallow.plan(self.p)["add"], [], state)

    def test_a_rule_the_owner_wrote_is_never_removed(self):
        mine = "Bash(python3 db/run_migrations.py 087_x.sql 088_y.sql)"
        s = json.loads((self.p / ".claude" / "settings.json").read_text())
        s["permissions"]["allow"].append(mine)
        (self.p / ".claude" / "settings.json").write_text(json.dumps(s))
        self.state("running")
        self.run_("--write")
        self.state("abandoned")
        self.run_("--write")
        self.assertIn(mine, self.allow())

    def test_open_permissions_false_keeps_the_prompts(self):
        (self.p / "fde.config.toml").write_text("[tooling]\nopen_permissions = false\n")
        self.state("running")
        self.run_("--write")
        self.assertEqual(self.allow(), ["Bash", "Read"])
        self.assertEqual(self.run_("--check").returncode, 0)


class TestInstructions(ProseTestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_the_decision_and_where_it_runs(self):
        self.assertIn("The sign-off writes the permission.",
                      self.read("docs/adr/0025-the-sign-off-is-the-machines-permission.md"))
        self.assertIn("## Commands", self.read("templates/cycle/deploy.md"))
        self.assertIn("deployallow.py --write", self.read("skills/fde-backlog/SKILL.md"))
        self.assertIn("deployallow.py --check", self.read("agents/fde-promotion.md"))
        self.assertIn("deployallow.py --write", self.read("skills/fde-sync/SKILL.md"))
        self.assertIn("`## Commands` block lists every command the steps run",
                      self.read("agents/fde-spec.md"))


if __name__ == "__main__":
    unittest.main()
