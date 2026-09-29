"""FM-2/R2: the spec and every surface derived from it stay coherent."""
from __future__ import annotations

import importlib.util
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_guard_allowed() -> dict:
    """Load runtime/guard.py's ALLOWED dict without shelling out — the
    module has no side effects at import time (main() only runs under
    __main__)."""
    spec = importlib.util.spec_from_file_location(
        "_guard_for_spec_integrity_test", ROOT / "runtime" / "guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ALLOWED


def load_guard_shared() -> tuple:
    """runtime/guard.py's SHARED: the paths every role writes (FWD-032)."""
    spec = importlib.util.spec_from_file_location(
        "_guard_shared_for_spec_integrity_test", ROOT / "runtime" / "guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SHARED

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

    def test_six_roles_with_write_scope(self):
        self.assertEqual({r["id"] for r in self.roles},
                         {"spec", "architecture", "implementation",
                          "adversarial", "promotion", "walkthrough-evaluator"})
        # walkthrough-evaluator is the ONE permitted-empty write_scope
        # (ADR-0014, FM-5): structurally incapable of writing anywhere,
        # by design, not by omission. Every other role's non-empty
        # assertion must still fail on regression.
        for r in self.roles:
            if r["id"] == "walkthrough-evaluator":
                self.assertEqual(r.get("write_scope"), [], r["id"])
            else:
                self.assertTrue(r.get("write_scope"), r["id"])
        adv = next(r for r in self.roles if r["id"] == "adversarial")
        self.assertTrue(adv["isolation"])
        wte = next(r for r in self.roles if r["id"] == "walkthrough-evaluator")
        self.assertTrue(wte["isolation"])
        self.assertEqual(wte.get("satisfies"), [])

    def test_write_scope_has_matching_guard_allowed_entry(self):
        """Regression guard for the drift risk ADR-0014 §7 names directly:
        runtime/guard.py's ALLOWED dict is hand-maintained, not derived
        from spec/roles.toml (FM-5/FM-1). Checks the four judging roles
        that appear in both files (spec, architecture, adversarial,
        promotion — implementation and walkthrough-evaluator are not
        ALLOWED-dict roles). For each, every write_scope prefix declared
        in roles.toml must have a matching enforcement entry in guard.py's
        ALLOWED tuple for that role: a roles.toml grant with no matching
        guard.py entry is an unenforced write scope, exactly the gap
        ADR-0014's own decision (§7) went unapplied until this fix."""
        allowed = load_guard_allowed()
        checked_any = False
        for r in self.roles:
            agent = f"fde-{r['id']}"
            if agent not in allowed:
                continue
            checked_any = True
            guard_prefixes = {p.rstrip("/") + "/" for p in allowed[agent]}
            for entry in r["write_scope"]:
                if entry in load_guard_shared():
                    continue  # enforced for every role by guard.SHARED
                prefix = entry[:-2] if entry.endswith("**") else entry
                prefix = prefix.rstrip("/") + "/"
                self.assertIn(
                    prefix, guard_prefixes,
                    f"{r['id']}: write_scope {entry!r} has no matching "
                    f"runtime/guard.py ALLOWED entry for {agent!r}")
        self.assertTrue(checked_any)

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

    def test_kernel_version_moves_with_what_it_ships(self):
        # clients pick changes up through `claude plugin update`, which only
        # sees a moved version: a kernel shipping ADR-0018's review budget
        # and FWD-022's cycle section must not still claim 0.15.x
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "docs/adr/0018-review-is-a-budget-not-a-loop.md")
                        .exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 16, 0))

    def test_kernel_version_ships_the_cycle_view(self):
        # FWD-023/024: the run-to-the-end cycle and status.py reach clients
        # only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/status.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 17, 0))

    def test_kernel_version_ships_open_permissions(self):
        # FWD-025: clients receive the install allow list only through a
        # moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("open_permissions", (ROOT / "templates/fde.config.template.toml").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 18, 0))

    def test_kernel_version_ships_the_cycle_model(self):
        # C-5 / kernel ADR-0019: clients receive backlog > cycle > demand only
        # through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "templates/cycle/plan.md").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 19, 0))

    def test_kernel_version_ships_the_terminal_panel(self):
        # C-12 / kernel ADR-0020: clients receive --panel only through a
        # moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("--panel", (ROOT / "skills/fde-backlog/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 20, 0))

    def test_kernel_version_ships_review_by_weight(self):
        # C-13 / kernel ADR-0021: clients receive review by weight only
        # through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn('kind = "code"', (ROOT / "skills/fde-review/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 21, 0))

    def test_kernel_version_ships_the_clean_backlog(self):
        # C-14: the AGENTS.md skeleton, the [backlog] switch and .fde/adr
        # reach clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "skills/fde-backlog-format/SKILL.md").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 22, 0))

    def test_kernel_version_ships_the_spec_kit_tracks(self):
        # tracks A-C (owner decision, direct, 2026-09-29): recorded runs,
        # waves and prose-tolerant pins reach clients only through a moved
        # version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "tests/prose.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 23, 0))
