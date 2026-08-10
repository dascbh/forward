"""FWD-010: the curated UI reference base and the divergence discipline.
The base is criteria + pointers; these assertions are what keep it from
degrading into an encyclopedia or a component dump."""
from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "spec" / "references" / "ui-patterns.toml"
REQUIRED = ("job", "platform", "canonical", "fits_when", "fails_when",
            "states", "a11y")


def load() -> dict:
    with open(BASE, "rb") as fh:
        return tomllib.load(fh)


class TestReferenceBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load()
        cls.systems = {s["id"] for s in cls.d["system"]}

    def test_systems_declare_what_they_are_best_at(self):
        self.assertGreaterEqual(len(self.d["system"]), 5)
        for s in self.d["system"]:
            for key in ("label", "best_at", "study_when"):
                self.assertTrue(s.get(key), f"{s['id']}.{key}")

    def test_pattern_ids_are_unique(self):
        ids = [p["id"] for p in self.d["pattern"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_pattern_carries_the_full_decision_criteria(self):
        for p in self.d["pattern"]:
            for key in REQUIRED:
                self.assertTrue(p.get(key), f"{p['id']}.{key} missing")
            self.assertGreaterEqual(len(p["states"]), 2, p["id"])

    def test_every_canonical_reference_resolves_to_a_declared_system(self):
        for p in self.d["pattern"]:
            unknown = set(p["canonical"]) - self.systems
            self.assertFalse(unknown, f"{p['id']} cites unknown {unknown}")

    def test_platform_values_are_known(self):
        for p in self.d["pattern"]:
            self.assertIn(p["platform"], ("web", "mobile", "all"), p["id"])

    def test_directories_are_declared_for_when_no_entry_fits(self):
        # USE-11 sends the reader somewhere when nothing fits; that
        # somewhere has to exist and say what it is good for
        dirs = self.d.get("directory", [])
        self.assertGreaterEqual(len(dirs), 3)
        ids = [x["id"] for x in dirs]
        self.assertEqual(len(ids), len(set(ids)))
        for x in dirs:
            self.assertTrue(x["url"].startswith("https://"), x["id"])
            self.assertTrue(x.get("use_for"), x["id"])

    def test_every_pattern_justifies_its_existence(self):
        # the curation rule ("earns a place by recurrence") applies to
        # EVERY entry or it is not a rule — recurrence measured, or a
        # stated rationale
        for p in self.d["pattern"]:
            self.assertTrue(p.get("recurrence") or p.get("rationale"),
                            f"{p['id']} justifies nothing")

    def test_recurrence_claims_carry_a_number_source_and_as_of_date(self):
        # counts drift; a number with no source and no date is folklore
        # by the next release (review finding, FWD-011)
        for p in self.d["pattern"]:
            if "recurrence" not in p:
                continue
            r = p["recurrence"]
            self.assertRegex(r, r"\d", p["id"])
            self.assertRegex(r, r"component\.gallery|m3\.material\.io|HIG",
                             p["id"])
            self.assertRegex(r, r"checked \d{4}-\d{2}-\d{2}", p["id"])

    def test_systems_declare_a_market_and_more_than_one_is_covered(self):
        # a base drawn only from anglo systems exports their conventions
        # as universal; the invariant is declared coverage, not a word
        markets = set()
        for s in self.d["system"]:
            self.assertTrue(s.get("market"), f"{s['id']} declares no market")
            markets.add(s["market"])
        self.assertGreaterEqual(len(markets), 3, sorted(markets))
        self.assertTrue(markets - {"global"}, "only global systems listed")

    def test_every_system_is_reachable_from_some_pattern(self):
        # a system no pattern cites cannot be found by the documented
        # selection order — a dead entry (review finding, FWD-011)
        cited = set()
        for p in self.d["pattern"]:
            cited |= set(p["canonical"])
        dead = self.systems - cited
        self.assertFalse(dead, f"systems no pattern cites: {sorted(dead)}")

    def test_every_system_points_somewhere(self):
        for s in self.d["system"]:
            self.assertTrue(s.get("url", "").startswith("https://"), s["id"])

    def test_the_base_records_when_it_was_last_checked(self):
        self.assertRegex(self.d["meta"]["sources_checked"], r"\d{4}-\d{2}-\d{2}")

    def test_one_pattern_per_job_no_contradicting_pair(self):
        # two entries for the same job contradict each other sooner or
        # later (the nav pair did, FWD-011 F5)
        jobs = [p["job"] for p in self.d["pattern"]]
        self.assertEqual(len(jobs), len(set(jobs)))
        nav = [p["id"] for p in self.d["pattern"] if "navigation" in p["id"]]
        self.assertEqual(len(nav), 1, nav)

    def test_the_base_contains_no_component_code(self):
        # criteria and pointers only (ADR-0012). The guard must catch what
        # a contributor would actually paste: JSX/HTML, arrow or classic
        # components, CSS rule blocks, SwiftUI/Kotlin declarations.
        self.assertFalse(self._code_hits(BASE.read_text(encoding="utf-8")))

    @staticmethod
    def _code_hits(text: str) -> list:
        patterns = [
            r"```",                              # fenced block
            r"</\w+>|<\w+[^>]*/>",               # closing or self-closing tag
            r"=>\s*[({]",                        # arrow component/function
            r"\bfunction\s+\w+\s*\(",            # classic function
            r"\bconst\s+\w+\s*=\s*\(",           # const component
            r"\bclass\s+\w+\s*[({:]",            # class decl
            r"\bstruct\s+\w+\s*:\s*View",        # SwiftUI
            r"\bfun\s+\w+\s*\(.*\)\s*\{",        # Kotlin
            r"[.#][\w-]+\s*\{[^}]*:",            # CSS rule block
            r"\b(import|export)\s+[{\w]",        # module syntax
        ]
        return [p for p in patterns if re.search(p, text, re.M)]

    def test_the_code_guard_actually_catches_pasted_components(self):
        # the guard is only worth having if it fires — a guard nobody
        # tested against real input is theater (review finding, FWD-010)
        samples = [
            'x = "const Btn = ({label}) => (<button>{label}</button>)"',
            'x = "function Table(props) { return null }"',
            'x = ".card { padding: 8px; }"',
            'x = "struct CardView: View { var body: some View { Text(1) } }"',
            'x = "import { Dialog } from radix"',
            'x = """```tsx\nfoo\n```"""',
        ]
        for s in samples:
            self.assertTrue(self._code_hits(s), f"guard missed: {s[:40]}")

    def test_base_is_installed_byte_identical(self):
        installed = ROOT / ".fde" / "spec" / "references" / "ui-patterns.toml"
        self.assertTrue(installed.exists(), "reference base not installed")
        self.assertEqual(BASE.read_text(encoding="utf-8"),
                         installed.read_text(encoding="utf-8"))


class TestDivergenceDiscipline(unittest.TestCase):
    """R1/R2/R3 live in the skill; these keep them from being edited away."""

    @classmethod
    def setUpClass(cls):
        cls.skill = (ROOT / "skills" / "fde-design" / "SKILL.md").read_text()

    def test_skill_names_all_five_lenses_and_the_distinct_rule(self):
        for lens in ("subtract", "invert", "analogous", "constraint-first",
                     "object-first"):
            self.assertIn(lens, self.skill, lens)
        self.assertIn("share a lens count as one", self.skill)

    def test_skill_requires_the_reframe(self):
        self.assertIn("How might we", self.skill)
        self.assertIn("reframe", self.skill.lower())

    def test_skill_scales_alternatives_by_size(self):
        self.assertRegex(self.skill, r"XS / S \|.*\| none")
        self.assertRegex(self.skill, r"\| M \|.*\| 2, from distinct lenses")
        self.assertRegex(self.skill, r"\| L \|.*\| 3, from distinct lenses")

    def test_skill_points_at_the_curated_base_and_forbids_default_novelty(self):
        self.assertIn("references/ui-patterns.toml", self.skill)
        self.assertIn("Novelty is a declared cost", self.skill)
        self.assertIn("design/patterns.md", self.skill)  # client extension


class TestCatalogGrowth(unittest.TestCase):
    def test_use_10_to_12_exist_and_are_well_formed(self):
        with open(ROOT / "spec" / "dimensions" / "quality-attributes.toml", "rb") as fh:
            attrs = tomllib.load(fh)["attribute"]
        use = next(a for a in attrs if a["id"] == "usability_accessibility")
        ids = {re.match(r"^(USE-\d+)", p).group(1)
               for p in use["heuristic_principles"]}
        for pid in ("USE-10", "USE-11", "USE-12"):
            self.assertIn(pid, ids)


if __name__ == "__main__":
    unittest.main()
