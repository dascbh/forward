"""FWD-021 (ADR-0017 and its round-1 revision): declared cycle scope — the
`cycle` gate, its pure core (runtime/cycle.py), validate() rule 6c, the
graph's cycle node, and the instruction layer. Contract:
specs/FWD-021-cycle-scope/architecture.md, "Revision — round 1" governing.

Every red case asserts the check label (C1..C6) and the reason, and the
reds a reader acts on also assert the way out (F16).

Speed (F14): each fixture variant is built once per process (make_project
+ git init) and copied per test, and the gate is called in-process through
`verify.Gate.gate_cycle`. Only the cases about `main()` itself — output
silence, the dispatch-level git-failure backstop, this repository — go
through a subprocess."""
from __future__ import annotations

import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT, commit_all, git_out, make_project, run_git, verify

sys.path.insert(0, str(ROOT / "runtime"))
import cycle  # noqa: E402
import graph  # noqa: E402
import verify as vmod  # noqa: E402
from fde_lib import (Config, Spec, cycle_config_violations, gate_paths,  # noqa: E402
                     validate)

XS_DONE = ("declared-before", "regression-proven", "review-rounds", "residuals",
           "the thing works")
S_DONE = ("declared-before", "regression-proven", "review-rounds", "residuals",
          "specs/FWD-040-x/acceptance.md")
BIG = "".join(f"line {i}\n" for i in range(20))   # never RULE-eligible (>= 10)
SMALL = "x = 2\n"                                  # RULE-eligible
BACKLOG = "---\ngoal: g\ndate: 2026-10-01\n---\n\n# Backlog\n\n"


def cyc(n, demands="FWD-030 (XS)", done=XS_DONE, tasks=("do the thing",),
        nxt=(), closed=None, intake=None, opened="2026-10-01", marks=None):
    lines = [f"cycle: C-{n}", "objective: the thing works", f"opened: {opened}",
             f"demands: {demands}"]
    if closed:
        lines.append(f"closed: {closed}")
    lines += ["", "## Tasks"] + [f"- {t}" for t in tasks]
    lines += ["", "## Done when"]
    for i, d in enumerate(done):
        m = (marks or {}).get(i)
        lines.append(f"- [{m[0]}] {d} — {m[1]}" if m else f"- [ ] {d}")
    lines += ["", "## Next cycle"] + [f"- {t}" for t in nxt]
    if intake is not None:
        lines += ["", "## Intake"] + [f"- {t}" for t in intake]
    return "\n".join(lines) + "\n"


def closed_cyc(n, nxt=("none",), **kw):
    """C-n as closed, every done item met with evidence."""
    done = kw.pop("done", XS_DONE)
    return cyc(n, done=done, nxt=nxt, closed="2026-10-02",
               marks={i: ("x", "evidence") for i in range(len(done))}, **kw)


def write(p: Path, rel: str, text: str) -> None:
    f = p / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def skill_blocks() -> list[str]:
    text = (ROOT / "skills/fde-triage/SKILL.md").read_text(encoding="utf-8")
    # fenced blocks carry their own `## ` lines, so the section ends at the
    # next heading the skill declares, not at the first `## `
    sec = text.split("\n## Cycle — declared scope", 1)[1].split("\n## What never scales", 1)[0]
    return re.findall(r"```\n(.*?)```", sec, re.S)


def has(out: list[str], needle: str) -> bool:
    return any(needle in b for b in out)


_TEMPLATES: dict = {}
_TMP = tempfile.mkdtemp(prefix="fwd021-")


def _template(**kw) -> Path:
    key = tuple(sorted((k, repr(v)) for k, v in kw.items()))
    if key not in _TEMPLATES:
        d = Path(tempfile.mkdtemp(dir=_TMP))
        p = make_project(d, **kw)
        write(p, "src/a.py", "x = 1\n")
        _TEMPLATES[key] = p
    return _TEMPLATES[key]


def tearDownModule():
    shutil.rmtree(_TMP, True)


class Result:
    def __init__(self, results):
        self.results = results
        self.returncode = 1 if any(not ok for _g, ok, _m in results) else 0
        self.stdout = "\n".join(f"{g} {m}" for g, ok, m in results)


class Fixture(unittest.TestCase):
    def project(self, **kw) -> Path:
        kw.setdefault("cycle", True)
        d = Path(tempfile.mkdtemp(dir=_TMP)) / "p"
        shutil.copytree(_template(**kw), d)
        return d

    def gate(self, p, since=None, explicit=False) -> Result:
        """In-process: the same Gate method main() dispatches, with the
        same GitOpFailure backstop shape run_gate applies."""
        cfg = Config.load(p)
        bp, ep = gate_paths(cfg.raw)
        g = vmod.Gate(p, bp, ep)
        try:
            g.gate_cycle(cfg, since=since, explicit=explicit)
        except vmod.GitOpFailure as e:
            g.add("CYCLE", False, f"CYCLE could not run: {e}")
        return Result(g.results)

    def assertRed(self, r, *needles):
        self.assertEqual(r.returncode, 1, r.stdout)
        for n in needles:
            self.assertIn(n, r.stdout, r.stdout)

    def assertGreen(self, r, *needles):
        self.assertEqual(r.returncode, 0, r.stdout)
        for n in needles:
            self.assertIn(n, r.stdout, r.stdout)

    def set_config(self, p, extra: str, base: str | None = None):
        cfg = base if base is not None else (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg + extra)

    def disable(self, p):
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("[cycle]\nenabled = true", "[cycle]\nenabled = false"))


# ---------------------------------------------------------------------------
# C1 — declared before
# ---------------------------------------------------------------------------
class TestC1DeclaredBefore(Fixture):
    def test_no_cycle_in_parent_is_red_and_names_the_way_out(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle — open one in an "
                       f"earlier commit, or declare \"FORWARD: RULE — <reason>\"")

    def test_only_a_closed_cycle_in_parent_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close C-1")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {sha[:7]}: no open cycle")
        self.assertNotIn("C4", r.stdout)

    def test_acceptance_in_the_same_commit_as_code_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-040 (S)", done=S_DONE))
        root = commit_all(p, "init")
        write(p, "specs/FWD-040-x/spec.md", "size: S\n")
        write(p, "specs/FWD-040-x/acceptance.md", "date: 2026-10-01\n")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "spec and code together")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}",
                       "specs/FWD-040-x/acceptance.md is absent from the parent tree",
                       "commit acceptance.md in an earlier commit")

    def test_acceptance_in_an_earlier_commit_is_green(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-040 (S)", done=S_DONE))
        root = commit_all(p, "init")
        write(p, "specs/FWD-040-x/spec.md", "size: S\n")
        write(p, "specs/FWD-040-x/acceptance.md", "date: 2026-10-01\n")
        commit_all(p, "spec first")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        self.assertGreen(self.gate(p, root), "1 behavior commit(s) examined")

    def test_rule_exemption_needs_the_claim(self):
        # F7: eligible without the claim is red; with it, green and counted
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", SMALL)
        sha = commit_all(p, "typo")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle", "FORWARD: RULE")
        q = self.project()
        root = commit_all(q, "init")
        write(q, "src/a.py", SMALL)
        commit_all(q, "FORWARD: RULE — typo")
        self.assertGreen(self.gate(q, root, explicit=True), "(1 RULE-exempt",
                         "1 behavior commit(s) in range RULE-exempt")

    def test_rule_claiming_ineligible_commit_with_no_cycle_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "FORWARD: RULE — says it is small")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")

    def test_child_of_the_enabling_commit_needs_a_cycle(self):
        p = self.project(cycle=False)
        root = commit_all(p, "init")
        self.set_config(p, "\n[cycle]\nenabled = true\n")
        write(p, "src/a.py", BIG)
        enabling = commit_all(p, "enable the mode, with code")   # not examined
        write(p, "src/a.py", BIG + BIG)
        child = commit_all(p, "code after enabling")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {child[:7]}: no open cycle")
        self.assertNotIn(enabling[:7], r.stdout)

    def test_two_open_cycles_in_the_parent_are_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        write(p, "cycles/C-2.md", cyc(2))
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: 2 open cycles in the parent tree")

    def test_malformed_open_cycle_in_parent_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, done=("declared-before", "the thing works")))
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        write(p, "cycles/C-1.md", cyc(1))   # the working tree is fine; history is not
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {sha[:7]}: the parent's open C-1 fails its form: C2 "
                          f"cycles/C-1.md: profile key")

    def test_non_behavior_commit_needs_no_cycle(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "docs/notes.md", BIG)
        commit_all(p, "docs")
        self.assertGreen(self.gate(p, root), "0 behavior commit(s) examined")

    def test_narrowing_behavior_paths_with_the_code_is_red(self):
        # F8: the commit is judged by its parent's behavior_paths
        p = self.project()
        root = commit_all(p, "init")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace('behavior_paths = ["src/"]',
                                                'behavior_paths = ["lib/"]'))
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "narrow and ship")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")

    def test_a_behavior_commit_cannot_open_a_cycle(self):
        # F9: close + open + code in one commit is red; close + code is green
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        write(p, "cycles/C-2.md", cyc(2, demands="FWD-031 (XS)", intake=()))
        write(p, "src/b.py", BIG)
        sha = commit_all(p, "close, open and ship")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: a behavior commit opens "
                       f"cycles/C-2.md: commit the new cycle first, then the code")
        q = self.project()
        write(q, "cycles/C-1.md", cyc(1))
        root = commit_all(q, "init")
        write(q, "cycles/C-1.md", closed_cyc(1))
        write(q, "src/b.py", BIG)
        commit_all(q, "last code, and close")
        self.assertGreen(self.gate(q, root), "1 behavior commit(s) examined")

    def test_a_quoted_path_is_still_a_behavior_path(self):
        # F10: NUL-separated file lists
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/ação.py", BIG)
        sha = commit_all(p, "non-ascii name")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")


# ---------------------------------------------------------------------------
# F1 — examination follows the cycles, not only the flag
# ---------------------------------------------------------------------------
class TestExaminationFollowsCycles(Fixture):
    def test_disable_act_reenable_sandwich_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        self.disable(p)
        commit_all(p, "X: switch the mode off")
        write(p, "src/a.py", BIG)
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4] + ("something already true",)))
        y = commit_all(p, "Y: act and reword")
        self.set_config(p, "", (p / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("enabled = false", "enabled = true"))
        commit_all(p, "Z: switch it back on")
        self.assertRed(self.gate(p, root), f"C4 {y[:7]}: cycles/C-1.md '## Done when'")

    def test_sandwich_with_only_closed_cycles_is_red_at_the_code(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close")
        self.disable(p)
        commit_all(p, "X: off")
        write(p, "src/a.py", BIG)
        y = commit_all(p, "Y: code")
        self.set_config(p, "", (p / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("enabled = false", "enabled = true"))
        commit_all(p, "Z: on")
        self.assertRed(self.gate(p, root), f"C1 {y[:7]}: no open cycle")

    def test_merged_side_branch_sandwich_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        main = git_out(p, "rev-parse", "--abbrev-ref", "HEAD")
        run_git(p, "checkout", "-q", "-b", "side")
        self.disable(p)
        commit_all(p, "X: off")
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4] + ("it runs",)))
        write(p, "src/a.py", BIG)
        y = commit_all(p, "Y")
        self.set_config(p, "", (p / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("enabled = false", "enabled = true"))
        commit_all(p, "Z: on")
        run_git(p, "checkout", "-q", main)
        write(p, "docs/n.md", "n\n")
        commit_all(p, "main moves")
        run_git(p, "merge", "-q", "--no-ff", "-m", "merge side", "side")
        self.assertRed(self.gate(p, root), f"C4 {y[:7]}")

    def test_pre_opt_in_history_is_not_examined(self):
        # no cycle file and flag off in the parent: never examined, even
        # with the flag toggled around the work
        p = self.project(cycle=False)
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code, no cycle, mode off")
        self.set_config(p, "\n[cycle]\nenabled = false\n")
        commit_all(p, "flag present, off")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("enabled = false", "enabled = true"))
        commit_all(p, "enable")
        self.assertGreen(self.gate(p, root), "0 behavior commit(s) examined")


# ---------------------------------------------------------------------------
# C2 — form
# ---------------------------------------------------------------------------
class TestC2Form(unittest.TestCase):
    def form(self, text, stages=(), specs=None, name="cycles/C-1.md"):
        return cycle.check_form(cycle.parse(name, text.encode()), list(stages), specs)

    def test_valid_xs_cycle_has_no_breach(self):
        self.assertEqual(self.form(cyc(1)), [])

    def test_the_skill_schema_is_red_on_every_field(self):
        schema = skill_blocks()[0]
        out = self.form(schema)
        for key in ("cycle", "objective", "opened", "demands"):
            self.assertTrue(has(out, f"header '{key}:' is an unfilled placeholder"), (key, out))
        items = [l for l in schema.splitlines() if l.startswith("- ")]
        self.assertEqual(len(items), 6)
        flagged = [b for b in out if "' item " in b and "unfilled placeholder" in b]
        self.assertEqual(len(flagged), len(items), out)
        self.assertTrue(all(b.startswith("C2 cycles/C-1.md: ") for b in out))

    def test_every_breach_names_a_way_out(self):
        out = self.form(cyc(1, tasks=()))
        self.assertTrue(out and all(b.endswith(cycle.FIX_OPEN) for b in out), out)

    def test_missing_header_and_section_are_red(self):
        text = cyc(1).replace("objective: the thing works\n", "").replace("## Tasks\n- do the thing\n", "")
        out = self.form(text)
        self.assertTrue(has(out, "C2 cycles/C-1.md: header 'objective:' missing or empty"))
        self.assertTrue(has(out, "C2 cycles/C-1.md: section '## Tasks' missing"))

    def test_empty_section_is_red(self):
        self.assertTrue(has(self.form(cyc(1, tasks=())), "'## Tasks' has no item"))

    def test_cycle_header_must_equal_the_stem(self):
        self.assertTrue(has(self.form(cyc(1), name="cycles/C-2.md"),
                            "does not equal the file's stem C-2"))

    def test_bad_dates_and_demands_are_red(self):
        out = self.form(cyc(1, opened="20261001", demands="FWD-030 (XL), FWD-030 (XS), fwd-30 (S)"))
        self.assertTrue(has(out, "'opened: 20261001' is not a YYYY-MM-DD date"))
        self.assertTrue(has(out, "demand 'FWD-030 (XL)' is not"))
        self.assertTrue(has(out, "demand fwd-30 is listed twice"))   # normalized
        out = self.form(closed_cyc(1).replace("closed: 2026-10-02", "closed: 2026-09-01"))
        self.assertTrue(has(out, "is earlier than opened"), out)

    def test_missing_and_duplicate_profile_keys_are_red(self):
        out = self.form(cyc(1, done=("declared-before", "declared-before", "review-rounds",
                                     "residuals", "the thing works")))
        self.assertTrue(has(out, "profile key 'regression-proven' missing from '## Done "
                                 "when' (while open, append '- [ ] amended YYYY-MM-DD: "
                                 "regression-proven')"))
        self.assertTrue(has(out, "profile key 'declared-before' appears 2 times"))

    def test_promotion_is_required_at_m(self):
        self.assertTrue(has(self.form(cyc(1, demands="FWD-040 (M)", done=S_DONE)),
                            "profile key 'promotion' missing"))

    def test_undeclared_stage_key_is_red_and_declared_one_is_required(self):
        self.assertTrue(has(self.form(cyc(1, done=XS_DONE + ("live checks pass",))),
                            "'live' is present but [cycle].stages does not declare it"))
        self.assertTrue(has(self.form(cyc(1), stages=("published",)),
                            "profile key 'published' missing"))
        self.assertEqual(self.form(cyc(1, done=XS_DONE + ("published on PyPI",)),
                                   stages=("published",)), [])

    def test_s_demand_needs_its_acceptance_path(self):
        self.assertTrue(has(self.form(cyc(1, demands="FWD-040 (S)")),
                            "S demand FWD-040 has no specs/FWD-040…/acceptance.md"))
        # the id boundary: FWD-4 is not FWD-40-x's demand
        self.assertTrue(has(self.form(cyc(1, demands="FWD-4 (S)", done=S_DONE)),
                            "S demand FWD-4 has no"))

    def test_xs_demand_needs_an_inline_item(self):
        self.assertTrue(has(self.form(cyc(1, done=XS_DONE[:4])),
                            "XS demand(s) FWD-030 have no inline done item"))
        self.assertTrue(has(self.form(cyc(1, demands="FWD-030 (XS), FWD-031 (XS)",
                                          done=XS_DONE[:4] + ("FWD-030 passes",))),
                            "XS demand FWD-031 is named by no inline done item"))

    def test_malformed_done_line_is_red(self):
        text = cyc(1).replace("- [ ] the thing works", "- the thing works")
        self.assertTrue(has(self.form(text), "'## Done when' line '- the thing works' is not"))

    def test_open_cycle_with_marks_is_red(self):
        # F11
        text = cyc(1).replace("- [ ] the thing works", "- [x] the thing works — done")
        self.assertTrue(has(self.form(text), "an open cycle is declared unresolved — "
                                             "remove the marks before committing"))

    def test_bad_intake_line_is_red(self):
        self.assertTrue(has(self.form(cyc(1, intake=("C-0#1 maybe later",))),
                            "'## Intake' item 1 is not"))

    def test_undecodable_file_is_red(self):
        out = cycle.check_form(cycle.parse("cycles/C-1.md", b"cycle: C-1\n\xff\xfe\n"), [], None)
        self.assertTrue(out and out[0].startswith("C2 cycles/C-1.md: not UTF-8"), out)


class TestSize(unittest.TestCase):
    """F2 / R1c: the declared `size:` header, normalized ids."""

    def form(self, demands, specs):
        return cycle.check_form(cycle.parse("cycles/C-1.md", cyc(1, demands=demands).encode()),
                                [], specs)

    def test_size_header_absent_is_red_with_the_fix(self):
        self.assertTrue(has(self.form("FWD-050 (XS)", {"FWD-050-x": "Triage: **XS**\n"}),
                            "add \"size: XS\" to specs/FWD-050-x/spec.md's header, "
                            "or correct demands:"))

    def test_spec_md_absent_is_red(self):
        self.assertTrue(has(self.form("FWD-050 (XS)", {"FWD-050-x": None}),
                            "specs/FWD-050-x/spec.md is absent"))

    def test_mismatch_is_red_under_any_spelling_of_the_id(self):
        for ident in ("FWD-050", "fwd-050", "FWD-50"):
            out = self.form(f"{ident} (XS)", {"FWD-050-x": "# t\n\nsize: M\n\n## Problem\n"})
            self.assertTrue(has(out, f"{ident} is declared XS but specs/FWD-050-x/spec.md "
                                     f"says size: M"), (ident, out))

    def test_matching_size_is_green_and_two_directories_are_red(self):
        self.assertEqual(self.form("FWD-050 (XS)", {"FWD-050-x": "size: xs\n"}), [])
        self.assertTrue(has(self.form("FWD-050 (XS)", {"FWD-050-x": "size: XS\n",
                                                       "FWD-50-y": "size: XS\n"}),
                            "FWD-050 matches 2 spec directories"))

    def test_xs_without_a_spec_directory_imposes_nothing(self):
        self.assertEqual(self.form("FWD-050 (XS)", {}), [])

    def test_norm_id(self):
        self.assertEqual(cycle.norm_id("fwd-050"), cycle.norm_id("FWD-50"))
        self.assertTrue(cycle.dir_matches("FWD-050-x", "fwd-50"))
        self.assertFalse(cycle.dir_matches("FWD-17-x", "FWD-1"))


class TestC2InTheGate(Fixture):
    def test_tracked_stray_is_red_and_untracked_dropping_ignored(self):
        # F13
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        write(p, "cycles/.DS_Store", "junk\n")
        self.assertGreen(self.gate(p))        # untracked: ignored
        run_git(p, "add", "cycles/C-1.md")
        self.assertGreen(self.gate(p))
        run_git(p, "add", "-f", "cycles/.DS_Store")
        self.assertRed(self.gate(p), "C2 cycles/.DS_Store: stray entry", "git rm it")

    def test_undecodable_tracked_cycle_file_is_red(self):
        p = self.project()
        (p / "cycles").mkdir()
        (p / "cycles/C-1.md").write_bytes(b"cycle: C-1\n\xff\n")
        run_git(p, "add", "-A")
        self.assertRed(self.gate(p), "C2 cycles/C-1.md: not UTF-8")

    def test_open_cycle_size_is_checked_in_the_working_tree(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-050 (XS)"))
        write(p, "specs/FWD-050-y/spec.md", "size: M\n")
        run_git(p, "add", "-A")
        self.assertRed(self.gate(p), "FWD-050 is declared XS but specs/FWD-050-y/spec.md "
                                     "says size: M")

    def test_size_is_checked_at_add_against_the_adding_tree(self):
        p = self.project()
        write(p, "specs/FWD-050-y/spec.md", "size: M\n")
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-050 (XS)"))
        sha = commit_all(p, "open as XS")
        write(p, "specs/FWD-050-y/spec.md", "size: XS\n")   # the working tree hides it
        run_git(p, "add", "-A")
        self.assertRed(self.gate(p, root), f"C2 {sha[:7]} cycles/C-1.md: FWD-050 is declared XS")


# ---------------------------------------------------------------------------
# closed cycles are judged once, at their closing commit (F3, R1d)
# ---------------------------------------------------------------------------
class TestClosedCyclesJudgedOnce(Fixture):
    def closed_repo(self, done=XS_DONE, stages=None):
        p = self.project(stages=stages)
        write(p, "cycles/C-1.md", cyc(1, done=done))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1, done=done))
        commit_all(p, "close")
        return p, root

    def test_adding_a_stage_after_close_is_green(self):
        p, root = self.closed_repo()
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("[cycle]\nenabled = true",
                                                '[cycle]\nenabled = true\nstages = ["published"]'))
        commit_all(p, "start publishing")
        self.assertGreen(self.gate(p, root))

    def test_removing_a_stage_after_close_is_green(self):
        p, root = self.closed_repo(done=XS_DONE + ("live checks pass",), stages=["live"])
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace('stages = ["live"]', "stages = []"))
        commit_all(p, "stop deploying")
        self.assertGreen(self.gate(p, root))

    def test_the_same_change_while_open_is_red_with_the_way_out(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("[cycle]\nenabled = true",
                                                '[cycle]\nenabled = true\nstages = ["published"]'))
        self.assertRed(self.gate(p), "profile key 'published' missing",
                       "append '- [ ] amended YYYY-MM-DD: published'")

    def test_closure_runs_at_the_closing_commit(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        marks = {i: ("x", "e") for i in range(5)}
        marks[4] = ("-", "ran out of time")
        write(p, "cycles/C-1.md", cyc(1, closed="2026-10-02", nxt=("x",), marks=marks))
        sha = commit_all(p, "close without carrying")
        self.assertRed(self.gate(p, root), f"C3 {sha[:7]} cycles/C-1.md: not-met item",
                       "fix the closing commit before pushing")

    def test_closing_form_is_judged_against_the_parent_config(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4]))   # malformed at add? root: not examined
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1, done=XS_DONE[:4]))
        sha = commit_all(p, "close")
        self.assertRed(self.gate(p, root), f"C2 {sha[:7]} cycles/C-1.md: XS demand(s) FWD-030 "
                                           f"have no inline done item")


# ---------------------------------------------------------------------------
# C3 — closure
# ---------------------------------------------------------------------------
class TestC3Closure(unittest.TestCase):
    def closure(self, text):
        return cycle.check_closure(cycle.parse("cycles/C-1.md", text.encode()))

    def unmet(self, nxt, which=(4,)):
        marks = {i: ("x", "e") for i in range(5)}
        for i in which:
            marks[i] = ("-", "ran out of time")
        return cyc(1, closed="2026-10-02", nxt=nxt, marks=marks)

    def test_well_closed_cycle_is_green(self):
        self.assertEqual(self.closure(closed_cyc(1)), [])

    def test_unresolved_item_at_close_is_red(self):
        text = closed_cyc(1).replace("- [x] residuals — evidence", "- [ ] residuals")
        self.assertTrue(has(self.closure(text),
                            "C3 cycles/C-1.md: closed with '## Done when' item 4 unresolved"))

    def test_not_met_item_needs_its_own_next_item_starting_with_it(self):
        self.assertTrue(has(self.closure(self.unmet(("something else",))),
                            "not-met item \"the thing works\" needs its own next-cycle item"))
        self.assertTrue(has(self.closure(self.unmet(("again: the thing works",))),
                            "needs its own next-cycle item"))   # contained, not a prefix
        self.assertEqual(self.closure(self.unmet(("the thing works, again",))), [])

    def test_one_next_item_cannot_carry_two_not_met_items(self):
        # F12
        text = self.unmet(("the thing works residuals",), which=(3, 4))
        self.assertTrue(has(self.closure(text), "needs its own next-cycle item"))
        text = self.unmet(("the thing works later", "residuals later"), which=(3, 4))
        self.assertEqual(self.closure(text), [])

    def test_none_alongside_other_items_is_red(self):
        self.assertTrue(has(self.closure(closed_cyc(1, nxt=("none", "a thing"))),
                            "'- none' alongside other '## Next cycle' items"))

    def test_empty_next_cycle_at_close_is_red(self):
        self.assertTrue(has(self.closure(closed_cyc(1, nxt=())), "empty '## Next cycle'"))



# ---------------------------------------------------------------------------
# C4 — frozen declaration
# ---------------------------------------------------------------------------
class TestC4Frozen(Fixture):
    def opened(self, **kw):
        p = self.project(**kw)
        write(p, "cycles/C-1.md", cyc(1))
        return p, commit_all(p, "init: open C-1")

    def test_task_added_mid_cycle_is_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, tasks=("do the thing", "and a side quest")))
        sha = commit_all(p, "grow")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md '## Tasks' changed",
                       "close this cycle with [-] items")

    def test_header_value_changed_is_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1).replace("the thing works\n", "anything\n", 1))
        sha = commit_all(p, "reword objective")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md header changed")

    def test_amended_done_append_is_green(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE + ("amended 2026-10-01: also y",)))
        commit_all(p, "amend")
        self.assertGreen(self.gate(p, root))

    def test_unmarked_done_append_is_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE + ("also y",)))
        sha = commit_all(p, "append")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md added done item "
                                           f"'also y' is not")

    def test_reworded_done_item_is_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4] + ("the thing mostly works",)))
        sha = commit_all(p, "weaken")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md '## Done when' "
                                           f"item removed, reworded")

    def test_rule_eligible_reword_is_still_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4] + ("the thing may work",)))
        sha = commit_all(p, "FORWARD: RULE — tiny")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}")

    def test_next_cycle_append_is_green_and_removal_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", cyc(1, nxt=("found a bug in x",)))
        commit_all(p, "note a discovery")
        self.assertGreen(self.gate(p, root))
        write(p, "cycles/C-1.md", cyc(1))
        sha = commit_all(p, "forget it")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md '## Next cycle' "
                                           f"item removed or reworded")

    def test_cycle_file_deleted_is_red(self):
        p, root = self.opened()
        (p / "cycles/C-1.md").unlink()
        sha = commit_all(p, "delete")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md was deleted")

    def test_closing_transition_is_green_and_closed_edit_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close")
        self.assertGreen(self.gate(p, root))
        write(p, "cycles/C-1.md", closed_cyc(1).replace("objective: the thing works",
                                                        "objective: the thing worked"))
        sha = commit_all(p, "edit after close")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md is closed in the "
                                           f"parent and changed")

    def test_closing_that_rewrites_an_item_is_red(self):
        p, root = self.opened()
        write(p, "cycles/C-1.md", closed_cyc(1).replace("- [x] the thing works — evidence",
                                                        "- [x] something easier — evidence"))
        sha = commit_all(p, "close dishonestly")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md closing rewrote "
                                           f"done item 5")

    def test_cycle_added_closed_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        sha = commit_all(p, "add closed")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md is added already closed")

    def test_cycle_added_with_marks_is_red(self):
        # F11, at the adding commit
        p = self.project()
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", cyc(1).replace("- [ ] the thing works",
                                                 "- [x] the thing works — done"))
        sha = commit_all(p, "pre-ticked")
        self.assertRed(self.gate(p, root), f"C2 {sha[:7]} cycles/C-1.md: an open cycle is "
                                           f"declared unresolved")

    def test_unparseable_parent_version_cannot_be_verified(self):
        p = self.project()
        (p / "cycles").mkdir()
        (p / "cycles/C-1.md").write_bytes(b"\xff\xfe")
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", cyc(1))
        sha = commit_all(p, "fix")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cannot verify transition")


# ---------------------------------------------------------------------------
# C5 — serial
# ---------------------------------------------------------------------------
class TestC5Serial(Fixture):
    def test_second_cycle_opened_while_one_is_open_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-2.md", cyc(2))
        commit_all(p, "open another")
        self.assertRed(self.gate(p, root), "C5 cycles/: 2 open cycles (C-1, C-2)")

    def test_new_cycle_numbered_below_an_existing_one_is_red(self):
        p = self.project()
        write(p, "cycles/C-5.md", closed_cyc(5))
        root = commit_all(p, "init")
        write(p, "cycles/C-3.md", cyc(3))
        sha = commit_all(p, "open a low number")
        r = self.gate(p, root)
        self.assertRed(r, f"C5 {sha[:7]}: cycles/C-3.md is numbered at or below the "
                          f"existing C-5 — number it C-6")
        self.assertIn("C5 cycles/: open cycle C-3 is not the highest-numbered cycle", r.stdout)

    def test_serial_pure(self):
        a = cycle.parse("cycles/C-1.md", closed_cyc(1).encode())
        b = cycle.parse("cycles/C-2.md", cyc(2).encode())
        self.assertEqual(cycle.check_serial([a, b], "x"), [])


# ---------------------------------------------------------------------------
# C6 — dispositions, at the transitions (F5, R1e)
# ---------------------------------------------------------------------------
class TestC6Dispositions(Fixture):
    def open_one(self, scrum):
        p = self.project(scrum=scrum)
        write(p, "backlog.md", BACKLOG)
        write(p, "cycles/C-1.md", cyc(1, nxt=("a bug in x",)))
        return p, commit_all(p, "init")

    def test_scrum_on_close_without_capture_is_red(self):
        p, root = self.open_one(True)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        sha = commit_all(p, "close")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]}: C-1#1 is not captured in the "
                       f"closing commit's backlog.md", "in the same commit")

    def test_scrum_on_capture_without_label_is_red(self):
        p, root = self.open_one(True)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        write(p, "backlog.md", BACKLOG + "- fix the bug in x (C-1#1)\n")
        commit_all(p, "close")
        self.assertRed(self.gate(p, root), "C-1#1 is not captured")

    def test_scrum_on_capture_then_grooming_then_pull_is_green(self):
        p, root = self.open_one(True)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        write(p, "backlog.md", BACKLOG + "- fix the bug in x (C-1#1) · usage-data\n")
        commit_all(p, "close and capture")
        self.assertGreen(self.gate(p, root, explicit=True), "backlog 1")
        write(p, "backlog.md", BACKLOG)
        commit_all(p, "groom: row removed")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix the bug (C-1#1)",), intake=("C-1#1 taken",)))
        commit_all(p, "open C-2, pulling C-1#1")
        self.assertGreen(self.gate(p, root, explicit=True), "taken 1")

    def test_scrum_on_intake_must_be_a_pull(self):
        p, root = self.open_one(True)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        write(p, "backlog.md", BACKLOG + "- x (C-1#1) · opinion\n")
        commit_all(p, "close and capture")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 dropped — dup",)))
        sha = commit_all(p, "open C-2")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} cycles/C-2.md: C-1#1 dropped — "
                                           f"with [scrum] on, an intake item is a pull")

    def test_scrum_off_next_cycle_must_cover_every_item(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x", "b")))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix a (C-1#1)",), intake=("C-1#1 taken",)))
        sha = commit_all(p, "open C-2, forgetting C-1#2")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} cycles/C-2.md: C-1#2 of C-1 has no "
                                           f"disposition", "before committing")

    def test_scrum_off_taken_deferred_dropped_are_green(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x", "b", "c")))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix a (C-1#1)",), nxt=("b still (C-1#2)",),
                                      intake=("C-1#1 taken", "C-1#2 deferred",
                                              "C-1#3 dropped — not worth it")))
        commit_all(p, "open C-2")
        self.assertGreen(self.gate(p, root, explicit=True), "taken 1, deferred 1, dropped 1")

    def test_taken_without_a_citing_task_and_missing_token_are_red(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 taken", "C-1#4 dropped — x")))
        sha = commit_all(p, "open C-2")
        r = self.gate(p, root)
        self.assertRed(r, f"C6 {sha[:7]} cycles/C-2.md: C-1#1 taken, but no '## Tasks' item "
                          f"cites it", "intake cites C-1#4, which does not exist")

    def test_pending_in_the_working_tree_is_reported_not_red(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        commit_all(p, "close")
        self.assertGreen(self.gate(p, root, explicit=True), "C-1 closed: 1 next-cycle item(s)", "pending 1",
                         "C-1#1 a bug in x", "no open cycle — 0 behavior commit(s)")

    def test_token_boundary(self):
        self.assertTrue(cycle.cites("see C-3#1.", "C-3#1"))
        self.assertFalse(cycle.cites("see C-3#12", "C-3#1"))
        self.assertFalse(cycle.cites("see C-13#1", "C-3#1"))


# ---------------------------------------------------------------------------
# R10 — merges and fail-closed; F4/F17 — the range
# ---------------------------------------------------------------------------
class TestR10(Fixture):
    def branch(self, p):
        return git_out(p, "rev-parse", "--abbrev-ref", "HEAD")

    def test_merge_with_no_own_change_is_green_and_counted(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "side")
        write(p, "src/b.py", BIG)
        commit_all(p, "side code")
        run_git(p, "checkout", "-q", main)
        write(p, "src/c.py", BIG)
        commit_all(p, "main code")
        run_git(p, "merge", "-q", "--no-ff", "-m", "merge side", "side")
        self.assertGreen(self.gate(p, root), "1 merge(s) with no own change",
                         "2 behavior commit(s) examined")

    def test_evil_merge_without_a_cycle_in_one_parent_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "side")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "open C-1")
        run_git(p, "checkout", "-q", main)
        run_git(p, "merge", "-q", "--no-ff", "--no-commit", "side")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "evil merge")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]} (merge, parent {root[:7]}): "
                                           f"no open cycle")

    def test_unparseable_parent_config_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", good + "\n[[[ not toml\n")
        commit_all(p, "break config")
        write(p, "fde.config.toml", good)
        sha = commit_all(p, "fix config")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: parent config fde.config.toml "
                                           f"is not valid TOML")

    def test_invalid_cycle_section_in_parent_config_is_red(self):
        p = self.project(cycle=False)
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", "cycle = 1\n" + good)
        root = commit_all(p, "init")
        write(p, "fde.config.toml", good + "\n[cycle]\nenabled = true\n")
        sha = commit_all(p, "fix it")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: parent config [cycle] must be a "
                                           f"table", "[CYCLE-TYPE]")
        q = self.project()
        root = commit_all(q, "init")
        self.set_config(q, "", (q / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("[cycle]\nenabled = true", '[cycle]\nenabled = true\nstages = ["beta"]'))
        commit_all(q, "bad stage")
        write(q, "docs/x.md", "x\n")
        sha = commit_all(q, "anything")
        self.assertRed(self.gate(q, root), f"C1 {sha[:7]}: parent config [cycle] stages",
                       "[CYCLE-STAGES]")

    def test_range_is_named_and_never_silently_narrowed(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        bad = commit_all(p, "code, no cycle")
        write(p, "docs/readme.md", "x\n")
        head = commit_all(p, "harmless")
        self.assertGreen(self.gate(p), f"range last commit only ({head[:7]})")
        self.assertRed(self.gate(p, "0" * 40), f"C1 {bad[:7]}: no open cycle")
        self.assertRed(self.gate(p, "1" * 40), "CYCLE range: --since 1111111111111111111111111111111111111111 "
                       "does not resolve", "--since <merge-base>")
        self.assertGreen(self.gate(p, bad), f"range {bad[:7]}..{head[:7]}")
        self.assertRed(self.gate(p, root), f"C1 {bad[:7]}: no open cycle")


class TestMainBackstops(Fixture):
    """Through main(): the dispatch-level GitOpFailure backstop."""

    def test_git_failure_is_red_through_run_gate(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        bindir = Path(tempfile.mkdtemp(dir=_TMP))
        real = shutil.which("git")
        shim = bindir / "git"
        shim.write_text("#!/bin/sh\ncase \" $* \" in\n  *' ls-tree '*)\n"
                        "    echo 'fake git: simulated ls-tree failure' >&2\n    exit 128\n"
                        "    ;;\nesac\n" f"exec \"{real}\" \"$@\"\n")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
        r = verify(p, "--gate", "cycle", env=env)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("CYCLE could not run: a git operation failed", r.stdout)
        self.assertIn("ls-tree", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


# ---------------------------------------------------------------------------
# R9 — silence and compatibility
# ---------------------------------------------------------------------------
class TestR9Silence(Fixture):
    def test_all_is_byte_identical_with_the_gate_present_and_absent(self):
        p = self.project(cycle=False)
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        write(p, "tests/test_a.py", "pass\n")
        commit_all(p, "code")
        with_gate = verify(p, "--all", "--since", root)
        v = p / "bin/fde/verify.py"
        text = v.read_text(encoding="utf-8")
        dispatch = ('        if want("cycle"):\n'
                    '            run_gate(g.gate_cycle, cfg, since=args.since,\n'
                    '                     explicit=(only == "cycle"), gid="CYCLE")\n')
        self.assertIn(dispatch, text)
        v.write_text(text.replace(dispatch, ""), encoding="utf-8")
        (p / "bin/fde/cycle.py").unlink()
        without = verify(p, "--all", "--since", root)
        self.assertEqual(with_gate.stdout, without.stdout)
        self.assertEqual(with_gate.returncode, without.returncode)
        self.assertNotIn("CYCLE", with_gate.stdout)

    def test_gate_cycle_off_prints_one_not_in_force_pass(self):
        p = self.project(cycle=False)
        commit_all(p, "init")
        r = self.gate(p, explicit=True)
        self.assertEqual(r.results, [("CYCLE", True,
                                      "cycle mode off — declared-scope gate not in force")])
        self.assertEqual(self.gate(p, explicit=False).results, [])

    def test_enabled_must_be_strictly_true(self):
        p = self.project(cycle=False)
        self.set_config(p, '\n[cycle]\nenabled = "true"\n')
        commit_all(p, "init")
        self.assertIn("not in force", self.gate(p, explicit=True).stdout)

    def test_this_repository_since_root_stays_green(self):
        root = git_out(ROOT, "rev-list", "--max-parents=0", "HEAD").splitlines()[-1]
        r = verify(ROOT, "--gate", "cycle", "--since", root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# R2 / R12 — profile and the ceremony budget
# ---------------------------------------------------------------------------
class TestProfileAndCeremony(unittest.TestCase):
    def test_profile_is_one_function_of_sizes_and_stages(self):
        base = {"declared-before", "regression-proven", "review-rounds", "residuals"}
        self.assertEqual(cycle.profile(["XS"], []), base)
        self.assertEqual(cycle.profile(["S"], []), base)
        self.assertEqual(cycle.profile(["XS", "M"], []), base | {"promotion"})
        self.assertEqual(cycle.profile(["L"], ["live", "published"]),
                         base | {"promotion", "live", "published"})

    def test_item_key_reads_amended_and_resolved_items(self):
        it = cycle.DoneItem("x", "amended 2026-10-01: review-rounds 2 — findings.toml")
        self.assertEqual(cycle.item_key(it), "review-rounds")
        self.assertIsNone(cycle.item_key(cycle.DoneItem(" ", "promotions matter")))

    def test_the_skill_minimal_example_is_valid_and_within_budget(self):
        example = skill_blocks()[1]
        self.assertLessEqual(len(example.splitlines()), 20)
        c = cycle.parse("cycles/C-12.md", example.encode())
        self.assertEqual(cycle.check_form(c, [], {}), [])
        self.assertEqual(cycle.check_closure(c), [])
        self.assertEqual(cycle.check_serial([c], "cycles/"), [])

    def test_this_repository_c1_is_valid(self):
        c = cycle.parse("cycles/C-1.md", (ROOT / "cycles/C-1.md").read_bytes())
        specs = {"FWD-021-cycle-scope": (ROOT / "specs/FWD-021-cycle-scope/spec.md")
                 .read_text(encoding="utf-8")}
        self.assertEqual(cycle.check_form(c, [], specs), [])


# ---------------------------------------------------------------------------
# validate() rule 6c, one validator (F15)
# ---------------------------------------------------------------------------
class TestValidateCycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = Spec.load(ROOT)

    def codes(self, section):
        raw = {"cycle": section}
        return {v.code for v in validate(Config(path=Path("x"), raw=raw), self.spec)
                if v.code.startswith("CYCLE")}

    def test_rule_6c(self):
        self.assertEqual(self.codes({"enabled": True, "stages": []}), set())
        self.assertEqual(self.codes({"enabled": True, "stages": ["live", "published"]}), set())
        self.assertEqual(self.codes(1), {"CYCLE-TYPE"})
        self.assertEqual(self.codes({"enabled": "true"}), {"CYCLE-TYPE"})
        self.assertEqual(self.codes({"stages": "live"}), {"CYCLE-STAGES"})
        self.assertEqual(self.codes({"stages": [1]}), {"CYCLE-STAGES"})
        self.assertEqual(self.codes({"stages": ["staging"]}), {"CYCLE-STAGES"})
        self.assertEqual(self.codes({"stages": ["live", "live"]}), {"CYCLE-STAGES"})
        self.assertEqual(self.codes({"enabled": True, "skip": True}), {"CYCLE-KEY"})

    def test_one_stage_set_and_one_validator(self):
        import fde_lib
        self.assertIs(cycle.STAGES, fde_lib.CYCLE_STAGES)
        self.assertEqual([v.code for v in cycle_config_violations({"stages": ["x"]})],
                         ["CYCLE-STAGES"])
        for rel in ("runtime/verify.py", "runtime/cycle.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn('("live", "published")', src, rel)

    def test_this_repository_opts_in_with_no_stages(self):
        import tomllib
        raw = tomllib.loads((ROOT / "fde.config.toml").read_text(encoding="utf-8"))
        self.assertEqual(raw["cycle"], {"enabled": True, "stages": []})
        tpl = (ROOT / "templates/fde.config.template.toml").read_text(encoding="utf-8")
        self.assertIn("# [cycle]\n", tpl)
        self.assertNotIn("\n[cycle]", tpl)


# ---------------------------------------------------------------------------
# graph (ADR-0017 Decision 9)
# ---------------------------------------------------------------------------
class TestGraphCycleNode(unittest.TestCase):
    def test_cycle_node_executes_and_carries(self):
        d = Path(tempfile.mkdtemp(dir=_TMP))
        write(d, "cycles/C-1.md", closed_cyc(1, nxt=("a",), demands="fwd-030 (XS)"))
        write(d, "cycles/C-2.md", cyc(2, demands="FWD-031 (XS)", intake=("C-1#1 dropped — x",)))
        g = graph.build_graph(d)
        self.assertEqual(g.nodes["cycle:C-1"]["label"], "the thing works")
        edges = {(s, e, t) for s, e, t, _w in g.edges}
        self.assertIn(("cycle:C-1", "executes", "demand:FWD-030"), edges)
        self.assertIn(("cycle:C-2", "executes", "demand:FWD-031"), edges)
        self.assertIn(("cycle:C-1", "carries", "cycle:C-2"), edges)
        self.assertIn("cycle", graph.Graph.TERMINAL)
        self.assertEqual(graph.forbidden_orphans(d, g), [])

    def test_spec_size_prefers_the_header_and_the_gate_reads_only_the_header(self):
        self.assertEqual(graph.spec_size("# x\n\nsize: s\n\nTriage: **M**\n"), "S")
        self.assertEqual(graph.spec_size("# x **L**\nTriage: score 4 → **M**\n"), "M")
        self.assertIsNone(graph.spec_size("Triage: surfaces 2\n→ **M**\n"))
        self.assertIsNone(graph.spec_header_size("Triage: **M**\n"))
        self.assertIsNone(graph.spec_header_size("## Problem\n\nsize: M\n"))
        self.assertEqual(graph.spec_header_size(
            (ROOT / "specs/FWD-021-cycle-scope/spec.md").read_text(encoding="utf-8")), "M")


# ---------------------------------------------------------------------------
# R13 — the instruction layer states the same four-part rule
# ---------------------------------------------------------------------------
class TestInstructionLayer(unittest.TestCase):
    PARTS = {
        "a": ("commit it before the first behavior change",),
        "b": ("is not acted on in this cycle", "RULE-sized", "MNT-9"),
        "c": ("resolve every done item",
              "present the next-cycle list in the closing report"),
        "d": ("evidence label", "## Intake"),
    }

    def flat(self, rel):
        return " ".join((ROOT / rel).read_text(encoding="utf-8").split())

    def test_four_surfaces_state_all_four_parts(self):
        for rel in ("templates/AGENTS.md.template", "AGENTS.md",
                    "skills/fde-triage/SKILL.md", "skills/fde-scrum/SKILL.md"):
            text = self.flat(rel)
            for part, needles in self.PARTS.items():
                for n in needles:
                    self.assertIn(n, text, f"{rel} part ({part}): {n}")

    def test_agents_md_opens_the_cycle_in_step_1_and_voice_exempts_the_list(self):
        for rel in ("templates/AGENTS.md.template", "AGENTS.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            loop = text.split("## Demand loop", 1)[1].split("\n## ", 1)[0]
            self.assertIn("open\n   the cycle before the first behavior change", loop)
            self.assertIn("`specs/<demand-id>/spec.md` with a `size:`\n   header line", loop)
            self.assertIn("## Cycle scope — when `[cycle]` is enabled", text)
            self.assertLess(text.index("## Scrum mode"), text.index("## Cycle scope"))
            voice = " ".join(text.split("## Voice", 1)[1].split("\n## ", 1)[0].split())
            self.assertIn("next-cycle list is domain content", voice)
            self.assertIn("one-status-line rule does not suppress it", voice)
            section = text.split("## Cycle scope", 1)[1].split("\n## ", 1)[0]
            for bad in ("{{", "DEM-042", "FWD-002"):
                self.assertNotIn(bad, section)

    def test_triage_skill_carries_size_rule_claim_and_ways_out(self):
        t = self.flat("skills/fde-triage/SKILL.md")
        for n in ("`size: M`", "declares `FORWARD: RULE — <reason>`",
                  "a behavior commit may not add a cycle file",
                  "only while the opening commit is still HEAD", "**Ways out.**",
                  "split the commit before push"):
            self.assertIn(n, t)

    def test_scrum_skill_captures_in_the_closing_commit(self):
        t = self.flat("skills/fde-scrum/SKILL.md")
        for n in ("in the closing commit itself", "groomed freely", "`C-<n>#<k> taken`"):
            self.assertIn(n, t)

    def test_sync_review_and_roles(self):
        self.assertIn("no exemption by path", self.flat("skills/fde-sync/SKILL.md"))
        review = self.flat("skills/fde-review/SKILL.md")
        for n in ("open cycle file", "MNT-9", "never excuses a finding"):
            self.assertIn(n, review)
        import tomllib
        roles = {r["id"]: r for r in tomllib.loads(
            (ROOT / "spec/roles.toml").read_text(encoding="utf-8"))["role"]}
        for rid, agent in (("adversarial", "agents/fde-adversarial.md"),
                           ("promotion", "agents/fde-promotion.md")):
            self.assertIn("cycles/**:read", roles[rid]["inputs"])
            self.assertIn("- `cycles/**:read`", (ROOT / agent).read_text(encoding="utf-8"))
            self.assertNotIn("cycles/**", str(roles[rid].get("write_scope", "")))


if __name__ == "__main__":
    unittest.main()
