"""FM-2/R2: the spec and every surface derived from it stay coherent."""
from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PREFIX_TO_ATTRIBUTE = {
    "USE": "usability_accessibility",
    "DOM": "functional_correctness",
    "MNT": "maintainability",
    "OBS": "observability",
    "SEC": "security_privacy",
    "REL": "reliability_resilience",
    "PERF": "performance_scale",
    "COST": "operational_cost",
}

MODES = {"empirical", "adversarial", "heuristic"}


def load(rel: str) -> dict:
    with open(ROOT / rel, "rb") as fh:
        return tomllib.load(fh)


def frontmatter_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    self_check = text.startswith("---\n")
    assert self_check, f"{path} has no frontmatter"
    for line in text.split("\n---\n", 1)[0].splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{path} frontmatter has no name")


class TestInvariants(unittest.TestCase):
    def test_ids_are_i1_to_i8_and_names_unique(self):
        inv = load("spec/invariants.toml")["invariant"]
        self.assertEqual([i["id"] for i in inv],
                         [f"I{n}" for n in range(1, 9)])
        names = [i["name"] for i in inv]
        self.assertEqual(len(names), len(set(names)))

    def test_floor_keys_exist(self):
        floors = load("spec/invariants.toml")["floors"]
        for key in ("functional_correctness", "observability",
                    "security_privacy", "default_quality_floor",
                    "qa_test_strategy", "default_domain_floor"):
            self.assertIn(key, floors)


class TestQualityAttributes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.attrs = load("spec/dimensions/quality-attributes.toml")["attribute"]

    def test_every_attribute_declares_valid_verified_by(self):
        for a in self.attrs:
            self.assertTrue(a.get("verified_by"), a["id"])
            self.assertTrue(set(a["verified_by"]) <= MODES, a["id"])

    def test_heuristic_verified_attributes_carry_a_catalog(self):
        for a in self.attrs:
            if "heuristic" in a["verified_by"]:
                self.assertTrue(a.get("heuristic_principles"), a["id"])

    def test_principle_ids_are_unique_and_prefixed_to_their_attribute(self):
        seen = set()
        for a in self.attrs:
            for p in a.get("heuristic_principles", []):
                m = re.match(r"^([A-Z]+)-(\d+) ", p)
                self.assertIsNotNone(m, p[:40])
                pid = f"{m.group(1)}-{m.group(2)}"
                self.assertNotIn(pid, seen, pid)
                seen.add(pid)
                self.assertEqual(PREFIX_TO_ATTRIBUTE[m.group(1)], a["id"], pid)

    def test_adversarial_verified_attributes_carry_probes(self):
        for a in self.attrs:
            if "adversarial" in a["verified_by"]:
                self.assertTrue(a.get("adversarial_probes"), a["id"])


class TestRolesAgentsSkills(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles = load("spec/roles.toml")["role"]

    def test_five_roles_with_write_scope(self):
        self.assertEqual({r["id"] for r in self.roles},
                         {"spec", "architecture", "implementation",
                          "adversarial", "promotion"})
        for r in self.roles:
            self.assertTrue(r.get("write_scope"), r["id"])
        adv = next(r for r in self.roles if r["id"] == "adversarial")
        self.assertTrue(adv["isolation"])

    def test_every_role_has_an_agent_file_with_matching_name(self):
        for r in self.roles:
            path = ROOT / "agents" / f"fde-{r['id']}.md"
            self.assertTrue(path.exists(), path)
            self.assertEqual(frontmatter_name(path), f"fde-{r['id']}")

    def test_every_skill_directory_matches_its_frontmatter_name(self):
        for d in sorted((ROOT / "skills").iterdir()):
            if d.is_dir():
                self.assertEqual(frontmatter_name(d / "SKILL.md"), d.name)


class TestTemplatesAndVersions(unittest.TestCase):
    def test_templates_carry_their_placeholders(self):
        agents = (ROOT / "templates" / "AGENTS.md.template").read_text()
        for ph in ("{{PROJECT_NAME}}", "{{TEST_COMMAND}}",
                   "{{INVARIANTS_LIST}}", "{{WEIGHTS_LIST}}",
                   "{{DEPTHS_LIST}}"):
            self.assertIn(ph, agents, ph)
        gate = (ROOT / "templates" / "fde-gate.yml").read_text()
        self.assertIn("{{TEST_COMMAND}}", gate)
        config = (ROOT / "templates" / "fde.config.template.toml").read_text()
        for ph in ("{{DATA_CLASS}}", "{{BEHAVIOR_PATHS}}", "{{EVAL_PATHS}}"):
            self.assertIn(ph, config, ph)

    def test_kernel_version_is_synced_everywhere(self):
        # every file that carries the version. Listed because each has a
        # different key and shape; the installed mirrors (.fde/**) are
        # covered by the byte-identity tests, not here.
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        carriers = {
            ".claude-plugin/plugin.json": r'"version":\s*"([^"]+)"',
            "templates/fde.config.template.toml": r'kernel_version = "([^"]+)"',
            "fde.config.toml": r'kernel_version = "([^"]+)"',
            "spec/references/ui-patterns.toml": r'spec_version = "([^"]+)"',
        }
        for rel, pat in carriers.items():
            path = ROOT / rel
            if not path.exists():
                continue
            m = re.search(pat, path.read_text())
            self.assertIsNotNone(m, rel)
            self.assertEqual(m.group(1), spec_v, rel)
