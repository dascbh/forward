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
    def test_every_runtime_module_is_identical_in_bin_fde(self):
        # ALL of runtime/, discovered — not a hardcoded list that silently
        # omits new modules (erosion.py, graph.py) whose CI-executed copy
        # could then drift (review finding, FWD-009)
        modules = sorted(p.name for p in (ROOT / "runtime").glob("*.py"))
        self.assertIn("erosion.py", modules)
        self.assertIn("graph.py", modules)
        for f in modules:
            installed = ROOT / "bin" / "fde" / f
            self.assertTrue(installed.exists(), f"{f} not installed in bin/fde/")
            self.assertEqual(read(ROOT / "runtime" / f), read(installed), f)

    def test_fde_spec_is_identical_to_spec(self):
        # discovered, not enumerated (S-004 retro): a new spec file must
        # not be able to ship without its installed copy
        for src in sorted((ROOT / "spec").rglob("*.toml")):
            rel = src.relative_to(ROOT / "spec")
            installed = ROOT / ".fde" / "spec" / rel
            self.assertTrue(installed.exists(), f"{rel} not installed")
            self.assertEqual(read(src), read(installed), str(rel))

    def test_no_orphan_files_in_the_installed_copies(self):
        # the walk is bidirectional: a file deleted from the source but
        # left installed is drift the one-directional check never sees
        for installed in sorted((ROOT / ".fde" / "spec").rglob("*.toml")):
            rel = installed.relative_to(ROOT / ".fde" / "spec")
            self.assertTrue((ROOT / "spec" / rel).exists(),
                            f"orphan installed copy: {rel}")
        for installed in sorted((ROOT / "bin" / "fde").glob("*.py")):
            self.assertTrue((ROOT / "runtime" / installed.name).exists(),
                            f"orphan runtime copy: {installed.name}")


class TestPluginDistribution(unittest.TestCase):
    """The repo is both marketplace and plugin, so `/plugin install
    forward@forward` resolves. These keep the two manifests agreeing."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.plugin = json.loads(read(ROOT / ".claude-plugin" / "plugin.json"))
        cls.market = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))

    def test_marketplace_lists_this_repo_as_its_plugin(self):
        entries = self.market["plugins"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["source"], ".", "the repo is its own plugin")
        # `/plugin install <plugin>@<marketplace>` — both names are used
        self.assertEqual(entry["name"], self.plugin["name"])
        self.assertEqual(self.market["name"], self.plugin["name"])

    def test_manifests_require_no_second_version_carrier(self):
        # the plugin entry deliberately omits `version` so plugin.json
        # stays the single source (MNT-1); a version here would be a
        # fifth carrier to keep in sync
        self.assertNotIn("version", self.market["plugins"][0])
        self.assertTrue(self.plugin.get("version"))

    def test_the_manifests_pass_the_real_validator(self):
        # asserting the schema against itself proved nothing: `owner` as a
        # bare string passed the suite and failed `claude plugin validate`
        # (review finding, FWD-014). Skipped where the CLI is absent — CI
        # containers have no claude binary — so this hardens local work
        # without becoming a false red.
        import shutil, subprocess
        if not shutil.which("claude"):
            self.skipTest("claude CLI not available")
        r = subprocess.run(["claude", "plugin", "validate", "."],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("warning", (r.stdout + r.stderr).lower())

    def test_owner_and_author_are_objects_not_strings(self):
        # the exact shape the validator rejects, pinned so the CLI-less
        # path still catches it
        self.assertIsInstance(self.market["owner"], dict)
        self.assertTrue(self.market["owner"].get("name"))
        self.assertIsInstance(self.plugin["author"], dict)
        self.assertTrue(self.plugin["author"].get("name"))

    def test_the_published_licence_has_a_file_behind_it(self):
        # the manifests advertise Apache-2.0 in a public catalogue
        self.assertEqual(self.plugin["license"], "Apache-2.0")
        licence = ROOT / "LICENSE"
        self.assertTrue(licence.exists(), "licence published without a LICENSE file")
        self.assertIn("Apache License", read(licence))

    def test_the_plugin_ships_the_skills_and_roles_it_promises(self):
        # a plugin install must carry fde-init (the bootstrap skill the
        # project-level install deliberately excludes) and the five roles
        skills = {d.name for d in (ROOT / "skills").iterdir() if d.is_dir()}
        self.assertIn("fde-init", skills)
        self.assertIn("fde-sync", skills)
        roles = {p.stem for p in (ROOT / "agents").glob("fde-*.md")}
        self.assertEqual(len(roles), 5, sorted(roles))


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
