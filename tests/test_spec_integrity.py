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

    def test_kernel_version_ships_the_bmad_tracks(self):
        # BMAD-method tracks (owner decision, direct, 2026-09-29): review
        # triage, process knobs, retired names and migrations, run records
        # with their instructions, and kernel ADR-0022 reach clients only
        # through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "docs/adr/0022-a-demand-is-one-goal.md").exists())
        self.assertTrue((ROOT / "spec/retired.toml").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 24, 0))

    def test_kernel_version_ships_the_backlog_panel(self):
        # kernel ADR-0023 (owner request, 2026-09-29): the interactive
        # backlog panel reaches clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/backlog.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 25, 0))

    def test_kernel_version_ships_the_erosion_measures(self):
        # SlopCodeBench v2 (owner decision, direct, 2026-09-29): copies count
        # once, structural erosion for Python, and the ratchet budget reach
        # clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("def structural_erosion",
                      (ROOT / "runtime/erosion.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 26, 0))

    def test_kernel_version_ships_codebench(self):
        # fde-codebench (owner request, 2026-09-29) reaches clients only
        # through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/codebench.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 27, 0))

    def test_kernel_version_ships_codebench_indicators(self):
        # fde-codebench indicators and the MVC layer (owner request,
        # 2026-09-29) reach clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("controller_rule", (ROOT / "runtime/codebench.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 28, 0))

    def test_kernel_version_ships_parallel_cycles_and_reconciling_sync(self):
        # slug ids, ADR-0024 small cycles in parallel, the C-4 gates and a
        # sync that always runs and reconciles (owner, 2026-09-30) reach
        # clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "docs/adr/0024-small-cycles-run-in-parallel.md").exists())
        self.assertTrue((ROOT / "spec/migrations/0.28-0.29-decision-records-tracked.toml").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 29, 0))

    def test_kernel_version_ships_the_product_map(self):
        # fde-map (owner request, 2026-09-30): generator, export, MAP gate
        # and sync check reach clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/productmap.py").exists())
        self.assertTrue((ROOT / "runtime/mapexport.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 30, 0))

    def test_kernel_version_ships_the_suite_effectiveness(self):
        # codebench --mutants and the suite's recorded seconds (owner
        # request, 2026-09-30) reach clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/mutation.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 33, 0))

    def test_kernel_version_ships_the_unasked_suite_measure(self):
        # codebench --tests run by the cycle review with nothing chosen by
        # hand (owner, 2026-09-30) reaches clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("--changed-since", (ROOT / "skills/fde-review/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 34, 0))

    def test_kernel_version_ships_cycle_and_lead_time(self):
        # status.py --flow (owner request, 2026-09-30) reaches clients only
        # through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/flow.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 35, 0))

    def test_kernel_version_ships_the_process_view_in_codebench(self):
        # codebench shows flow and suite measures beside the code (owner
        # request, 2026-09-30) reaching clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("def process_view", (ROOT / "runtime/codebench.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 36, 0))

    def test_kernel_version_ships_delivery_measures_and_the_signed_permission(self):
        # DORA, review and change measures in codebench, and kernel
        # ADR-0025 (deploy commands allowed by the sign-off) reach clients
        # only through a moved version (owner, 2026-09-30)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("def delivery", (ROOT / "runtime/flow.py").read_text())
        self.assertTrue((ROOT / "runtime/deployallow.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 37, 0))

    def test_kernel_version_ships_reversible_migrations(self):
        # kernel ADR-0026 (expand/contract, checkpoint, rehearsal, the
        # MIGRATION warning) reaches clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue(list((ROOT / "docs/adr").glob("0026-*.md")))
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 38, 0))

    def test_kernel_version_ships_the_reconcile_that_does(self):
        # fde-sync's reconcile applies instead of listing (owner,
        # 2026-09-30) reaching clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("Reconcile **does**", (ROOT / "skills/fde-sync/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 38, 1))

    def test_kernel_version_ships_promotion_without_owner_conditions(self):
        # the PROMOTION warning and the no-conditions rule (owner,
        # 2026-10-01) reach clients only through a moved version
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("def gate_promotion_decision", (ROOT / "runtime/verify.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 39, 0))

    def test_kernel_version_ships_the_suite_at_the_rebased_tree(self):
        # two parallel demands with disjoint files broke a client's main
        # after both merged, each green alone (owner, 2026-10-01): the
        # suite runs at the rebased tree when main moved
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        text = " ".join((ROOT / "skills/fde-review/SKILL.md").read_text().split())
        self.assertIn("the suite runs once more at the rebased tree", text)
        self.assertIn("Main unmoved: the recorded run stands", text)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 40, 0))

    def test_kernel_version_ships_promotions_decided_again_at_sync(self):
        # a client's sync restated a promotion with owner conditions in the
        # new vocabulary and kept asking (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        text = " ".join((ROOT / "skills/fde-sync/SKILL.md").read_text().split())
        self.assertIn("never restated in new words", text)
        self.assertIn("withdrawn, not relayed", text)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 40, 1))

    def test_kernel_version_ships_typescript_complexity(self):
        # jscc.py: the front counts in complexity and structural erosion
        # (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/jscc.py").exists())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 41, 0))

    def test_kernel_version_ships_the_erosion_ratchet(self):
        # the ratchet, the bounded loop and the one debt (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        text = " ".join((ROOT / "skills/fde-erosion/SKILL.md").read_text().split())
        self.assertIn("an attempt that does not ends the attempts", text)
        self.assertIn("A second debt is refused while one is open", text)
        self.assertIn("erosion.py --close", (ROOT / "skills/fde-backlog/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 42, 0))

    def test_kernel_version_ships_the_progress_tree(self):
        # status.py --progress (forward-1f, owner request, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("--progress", (ROOT / "runtime/status.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 43, 1))

    def test_kernel_version_ships_verbatim_commands_and_worktree_cleanup(self):
        # a deploy stopped at `cd infra && cdk deploy`, and 95 worktrees left
        # after merges filled a disk through a CDK asset (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        promo = " ".join((ROOT / "agents/fde-promotion.md").read_text().split())
        self.assertIn("runs exactly as written, one tool call per line", promo)
        review = " ".join((ROOT / "skills/fde-review/SKILL.md").read_text().split())
        self.assertIn("After the merge its worktree is removed", review)
        sync = " ".join((ROOT / "skills/fde-sync/SKILL.md").read_text().split())
        self.assertIn("worktrees.py --prune-merged", sync)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 44, 0))

    def test_kernel_version_ships_the_progress_tab_and_chained_step_check(self):
        # backlog.py progress tab and deployallow --check on chained prose
        # steps (forward-1f, owner request, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("progress", (ROOT / "runtime/backlog.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 45, 0))

    def test_kernel_version_ships_the_closing_rail(self):
        # preflight, one decision, closing on a rail, one closing message,
        # closing time measured (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/preflight.py").exists())
        backlog = " ".join((ROOT / "skills/fde-backlog/SKILL.md").read_text().split())
        self.assertIn("Closing runs on a rail", backlog)
        self.assertIn("which are not this cycle's debt", backlog)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 46, 0))

    def test_kernel_version_ships_main_always_deployable(self):
        # kernel ADR-0027: finished cycles waited for the slowest in a joint
        # deploy the shared main forced (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        adr = ROOT / "docs/adr/0027-main-is-always-deployable.md"
        self.assertEqual(adr.read_text(), (ROOT / ".fde/adr" / adr.name).read_text())
        review = " ".join((ROOT / "skills/fde-review/SKILL.md").read_text().split())
        self.assertIn("if the cycle stopped here, would main deploy and behave as today?", review)
        promo = " ".join((ROOT / "agents/fde-promotion.md").read_text().split())
        self.assertIn("a joint deploy exists only when the plan declared it at sign-off", promo)
        self.assertIn("`dark` note", (ROOT / "templates/cycle/plan.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 47, 0))

    def test_kernel_version_ships_the_safer_path_without_asking(self):
        # owner, 2026-10-01: "if you can recommend it, why can't FORWARD?"
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        agents = " ".join((ROOT / "AGENTS.md").read_text().split())
        self.assertIn("narrows the cycle on its own", agents)
        self.assertNotIn("the owner's call: narrow", agents)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 48, 0))

    def test_kernel_version_ships_the_debt_that_covers(self):
        # a client's --debt refused the blocked commit and its debt drifted
        # 13.31 → 18.24 with the window (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("def covered", (ROOT / "runtime/erosion.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 48, 1))

    def test_kernel_version_ships_backlog_hygiene_and_sanitizing_sync(self):
        # findings stay in findings.toml, main is green (quarantine), kernel
        # items tagged, and fde-sync sanitizes the backlog (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        sync = " ".join((ROOT / "skills/fde-sync/SKILL.md").read_text().split())
        self.assertIn("Sanitize, every sync", sync)
        self.assertIn("**Main is green.**", (ROOT / "skills/fde-verify/SKILL.md").read_text())
        self.assertIn("`[kernel]`", (ROOT / "skills/fde-backlog-format/SKILL.md").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 49, 0))

    def test_kernel_version_ships_records_keyed_by_code(self):
        # a process commit no longer sends the suite to run again; red
        # records name their failures; deploy steps say what touches
        # production (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("RECORD_SKIP", (ROOT / "runtime/verify.py").read_text())
        promo = " ".join((ROOT / "agents/fde-promotion.md").read_text().split())
        self.assertIn('"production unchanged"', promo)
        self.assertIn("A rehearsal creates nothing it cannot delete", promo)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 50, 0))

    def test_kernel_version_ships_the_forecast(self):
        # status.py --forecast, shown unasked with every status (owner,
        # 2026-10-01: "no idea how long a cycle will take")
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/forecast.py").exists())
        self.assertIn("--forecast", (ROOT / "skills/fde-status/SKILL.md").read_text())
        self.assertIn("RUNS = 2000", (ROOT / "runtime/forecast.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 51, 2))

    def test_kernel_version_ships_the_review_tail_fix(self):
        # one demand-review round, only high findings patched, an owner
        # question never blocks the session (forward-00, owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertIn("Owner questions pause one demand, never the session",
                      " ".join((ROOT / "AGENTS.md").read_text().split()))
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 52, 0))

    def test_kernel_version_ships_the_two_answers_first(self):
        # "did it finish or not?" (owner, 2026-10-01)
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        promo = " ".join((ROOT / "agents/fde-promotion.md").read_text().split())
        self.assertIn('"Live: yes/no · Closed: yes/no', promo)
        self.assertIn("never handed to the owner", promo)
        self.assertIn("runs in the background WHILE the live checks", promo)
        self.assertIn("remaining steps' `Takes:`", promo)
        self.assertIn("- Takes:", (ROOT / "templates/cycle/deploy.md").read_text())
        self.assertIn("def _counts_for_debt", (ROOT / "runtime/erosion.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 52, 6))

    def test_kernel_version_ships_add_delete_as_a_report(self):
        # owner, 2026-10-01: it gated a project's phase, not its decay
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        keys = (ROOT / "runtime/fde_lib.py").read_text().split("RATCHET_KEYS = (", 1)[1].split(")\n", 1)[0]
        self.assertNotIn('("max_add_delete_ratio"', keys)
        self.assertNotIn("gate_erosion_staged", (ROOT / "runtime/verify.py").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 53, 0))

    def test_kernel_version_ships_use_16(self):
        # forward-00, owner's UX inspection (2026-10-05): the screen speaks
        # the user's next action, never the spec
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        self.assertTrue((ROOT / "runtime/uiprose.py").exists())
        self.assertIn("USE-16", (ROOT / "spec/dimensions/quality-attributes.toml").read_text())
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 56, 0))

    def test_kernel_version_ships_the_priority_instrument(self):
        # owner, 2026-10-06: screens were the sum of their requirements;
        # an experiment on two client screens moved the main content
        # 700-800 px up with no requirement lost
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        d = " ".join((ROOT / "skills/fde-design/SKILL.md").read_text().split())
        for rule in ("## Priority — before the hierarchy (any UI surface)",
                     "The order of the requirements in the text is not the order of the screen",
                     "shows a visible cue of what it hides",
                     "The verdict is against the declared budget, never a universal score",
                     "None may be absent",
                     "at least one of them a disclosure principle",
                     "an element outside the map, or in another layer than the map gives it, is a finding"):
            self.assertIn(rule, d)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 57, 0))

    def test_kernel_version_ships_the_pipeline_as_specified(self):
        # the owner, 2026-10-01: an inspection report template and an
        # "inspection delivers" section had narrowed the approved pipeline —
        # the inspection stopped at a report and skipped augmentation,
        # hypotheses and criticism. Both removed; the spec reaches clients
        # whole (the install had listed spec files and left it out).
        spec_v = load("spec/invariants.toml")["meta"]["kernel_version"]
        setup = " ".join((ROOT / "SETUP.md").read_text().split())
        self.assertIn("EVERY file under `spec/` → `.fde/spec/`", setup)
        self.assertNotIn("templates/discovery", setup)
        self.assertFalse((ROOT / "templates/discovery").exists())
        pipe = (ROOT / "spec/product-pipeline.md").read_text()
        for gone in ("## Running beside other sessions", "## What an inspection delivers"):
            self.assertNotIn(gone, pipe)
        for stage in ("| Discovery augmentation |", "| Hypotheses |", "## Agent autonomy and internal criticism",
                      "**Inspect an existing export:**"):
            self.assertIn(stage, pipe)
        self.assertGreaterEqual(tuple(int(x) for x in spec_v.split(".")),
                                (0, 54, 1))
