"""FM-2/F4: the installed copies this repo executes are change-controlled —
they must be identical to their sources (or provably derived from them)."""
from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestRuntimeCopies(unittest.TestCase):
    def test_bin_fde_is_identical_to_runtime(self):
        for f in ("fde_lib.py", "verify.py", "guard.py"):
            self.assertEqual(read(ROOT / "runtime" / f),
                             read(ROOT / "bin" / "fde" / f), f)

    def test_fde_spec_is_identical_to_spec(self):
        for rel in ("invariants.toml", "roles.toml",
                    "dimensions/quality-attributes.toml",
                    "dimensions/technical-domains.toml"):
            self.assertEqual(read(ROOT / "spec" / rel),
                             read(ROOT / ".fde" / "spec" / rel), rel)


class TestClaudeLayerCopies(unittest.TestCase):
    def test_skills_are_installed_identically_except_init(self):
        for d in sorted((ROOT / "skills").iterdir()):
            if not d.is_dir():
                continue
            installed = ROOT / ".claude" / "skills" / d.name / "SKILL.md"
            if d.name == "fde-init":
                self.assertFalse(installed.exists(),
                                 "fde-init must not be installed in-project")
            else:
                self.assertEqual(read(d / "SKILL.md"), read(installed), d.name)

    def test_generic_role_files_are_installed_identically(self):
        for role in ("spec", "architecture", "implementation", "promotion"):
            self.assertEqual(read(ROOT / "agents" / f"fde-{role}.md"),
                             read(ROOT / ".claude" / "agents" / f"fde-{role}.md"),
                             role)

    def test_adversarial_is_concretized_to_this_repos_weights(self):
        with open(ROOT / "fde.config.toml", "rb") as fh:
            cfg = tomllib.load(fh)
        text = read(ROOT / ".claude" / "agents" / "fde-adversarial.md")
        for attr, w in cfg["weights"].items():
            rounds = max(1, round(int(w) / 10))
            self.assertIn(f"weight {w}, {rounds} round", text, attr)
            if int(w) >= 15:
                blocking_line = re.search(
                    rf"weight {w}, {rounds} rounds? — BLOCKS MERGE", text)
                self.assertIsNotNone(blocking_line, f"{attr} must block")


class TestGeneratedSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ROOT / "fde.config.toml", "rb") as fh:
            cls.cfg = tomllib.load(fh)
        with open(ROOT / "spec" / "invariants.toml", "rb") as fh:
            cls.inv = tomllib.load(fh)

    def test_agents_md_lists_every_invariant_from_the_spec(self):
        text = read(ROOT / "AGENTS.md")
        for i in self.inv["invariant"]:
            self.assertIn(f"**{i['id']} {i['name']}**", text, i["id"])

    def test_agents_md_carries_this_repos_weights_and_test_command(self):
        text = read(ROOT / "AGENTS.md")
        self.assertIn(self.cfg["stack"]["test_command"], text)
        for attr, w in self.cfg["weights"].items():
            self.assertIn(f"- {attr}: {w}", text, attr)

    def test_workflow_runs_tests_and_a_ranged_gate_on_full_history(self):
        wf = read(ROOT / ".github" / "workflows" / "fde-gate.yml")
        self.assertIn(self.cfg["stack"]["test_command"], wf)
        self.assertIn("fetch-depth: 0", wf)
        self.assertIn("--since", wf)
        self.assertNotIn("{{TEST_COMMAND}}", wf)

    def test_kernel_version_matches_the_spec_here_too(self):
        self.assertEqual(self.cfg["project"]["kernel_version"],
                         self.inv["meta"]["kernel_version"])


if __name__ == "__main__":
    unittest.main()
