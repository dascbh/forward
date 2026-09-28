"""FWD-021 (ADR-0017 and its revisions): declared cycle scope — the
`cycle` gate, its pure core (runtime/cycle.py), validate() rule 6c, the
graph's cycle node, and the instruction layer. Contract:
specs/FWD-021-cycle-scope/architecture.md, "Revision — round 4" governing
over every earlier revision (round 2's merge model withdrawn).

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
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle — open a cycle in an "
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
        self.assertGreen(self.gate(p, root), "1 behavior commit(s), all declared before")

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
        self.assertGreen(self.gate(p, root), "0 behavior commit(s), all declared before")

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
                       f"cycles/C-2.md: close, open, code — three commits")
        q = self.project()
        write(q, "cycles/C-1.md", cyc(1))
        root = commit_all(q, "init")
        write(q, "cycles/C-1.md", closed_cyc(1))
        write(q, "src/b.py", BIG)
        commit_all(q, "last code, and close")
        self.assertGreen(self.gate(q, root), "1 behavior commit(s), all declared before")

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
        self.assertGreen(self.gate(p, root), "0 behavior commit(s), all declared before")


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

    def test_adding_a_stage_after_close_leaves_the_closed_cycle_green(self):
        # a stage change is gate-governing config (R2c): it lands under a
        # new open cycle, which takes the new key as an amended item
        p, root = self.closed_repo()
        write(p, "cycles/C-2.md", cyc(2, intake=()))
        commit_all(p, "open C-2")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("[cycle]\nenabled = true",
                                                '[cycle]\nenabled = true\nstages = ["published"]'))
        write(p, "cycles/C-2.md", cyc(2, intake=(),
                                      done=XS_DONE + ("amended 2026-10-02: published on PyPI",)))
        commit_all(p, "start publishing")
        self.assertGreen(self.gate(p, root))

    def test_removing_a_stage_with_only_closed_cycles_is_red(self):
        # F22: removing a stage is a behavior commit and needs an open cycle
        p, root = self.closed_repo(done=XS_DONE + ("live checks pass",), stages=["live"])
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace('stages = ["live"]', "stages = []"))
        sha = commit_all(p, "stop deploying")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")

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
        self.assertGreen(self.gate(p, root, explicit=True), "captured 1 (C-1#1)")
        write(p, "backlog.md", BACKLOG)
        commit_all(p, "groom: row removed")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix the bug (C-1#1)",), intake=("C-1#1 taken",)))
        commit_all(p, "open C-2, pulling C-1#1")
        self.assertGreen(self.gate(p, root, explicit=True), "captured 1 (C-1#1)")

    def test_scrum_on_intake_must_be_a_pull(self):
        p, root = self.open_one(True)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        write(p, "backlog.md", BACKLOG + "- x (C-1#1) · opinion\n")
        commit_all(p, "close and capture")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 dropped — dup",)))
        sha = commit_all(p, "open C-2")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} C-2: C-1#1 is already captured in "
                                           f"the backlog, so it may appear only as 'taken'")

    def test_scrum_off_next_cycle_must_cover_every_item(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x", "b")))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix a (C-1#1)",), intake=("C-1#1 taken",)))
        sha = commit_all(p, "open C-2, forgetting C-1#2")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} C-2: C-1#2 has no disposition — add "
                                           f"it to ## Intake (taken/deferred/dropped) in this "
                                           f"opening commit")

    def test_scrum_off_taken_deferred_dropped_are_green(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x", "b", "c")))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix a (C-1#1)",), nxt=("b still (C-1#2)",),
                                      intake=("C-1#1 taken", "C-1#2 deferred",
                                              "C-1#3 dropped — not worth it")))
        commit_all(p, "open C-2")
        self.assertGreen(self.gate(p, root, explicit=True), "taken 1 (C-1#1), deferred 1 (C-1#2), dropped 1 (C-1#3)")

    def test_taken_without_a_citing_task_and_missing_token_are_red(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 taken", "C-1#4 dropped — x")))
        sha = commit_all(p, "open C-2")
        r = self.gate(p, root)
        self.assertRed(r, f"C6 {sha[:7]} C-2: C-1#1 taken, but no '## Tasks' item "
                          f"cites it", "intake cites C-1#4, which names no item")

    def test_pending_in_the_working_tree_is_reported_not_red(self):
        p, root = self.open_one(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        commit_all(p, "close")
        self.assertGreen(self.gate(p, root, explicit=True), "C-1 closed: 1 next-cycle item(s)", "pending 1 (C-1#1)", "no open cycle — 0 behavior commit(s)")

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

    def test_a_merge_made_on_main_after_opt_in_is_red(self):
        # F31 (a): linear history once cycles exist
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "side")
        write(p, "src/b.py", BIG)
        side = commit_all(p, "side code")
        run_git(p, "checkout", "-q", main)
        write(p, "src/c.py", BIG)
        mn = commit_all(p, "main code")
        run_git(p, "merge", "-q", "--no-ff", "-m", "merge side", "side")
        m = git_out(p, "rev-parse", "HEAD")
        self.assertRed(self.gate(p, root), f"C1 {m[:7]}: a merge after opt-in (parents "
                       f"{mn[:7]}, {side[:7]}) — history must stay linear once cycles "
                       f"exist; rebase the branch onto the protected line (git rebase "
                       f"<main>) and push the result")

    def test_unparseable_config_in_an_examined_commit_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", good + "\n[[[ not toml\n")
        broke = commit_all(p, "break config")
        write(p, "fde.config.toml", good)
        fixed = commit_all(p, "fix config")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {broke[:7]}: this commit makes fde.config.toml not valid TOML")
        self.assertNotIn(f"C1 {fixed[:7]}", r.stdout)

    def test_invalid_cycle_section_in_an_examined_parent_is_red(self):
        p = self.project(cycle=False)
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", "cycle = 1\n" + good)
        root = commit_all(p, "init")
        write(p, "fde.config.toml", good + "\n[cycle]\nenabled = true\n")
        commit_all(p, "fix it")
        self.assertGreen(self.gate(p, root))    # the parent is pre-opt-in (R2b)
        q = self.project()
        write(q, "cycles/C-1.md", cyc(1))
        root = commit_all(q, "init")
        self.set_config(q, "", (q / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("[cycle]\nenabled = true", '[cycle]\nenabled = true\nstages = ["beta"]'))
        badc = commit_all(q, "bad stage")
        write(q, "docs/x.md", "x\n")
        sha = commit_all(q, "anything, not repairing it")
        self.assertRed(self.gate(q, root), f"C1 {badc[:7]}: this commit makes fde.config.toml "
                       f"invalid ([cycle] stages ['beta'] unknown",
                       f"C1 {sha[:7]}: parent config is invalid ([cycle] stages ['beta'] "
                       f"unknown")

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
            self.assertIn("`specs/<demand-id>/spec.md` (with `[cycle]`\n   on, it also carries a `size:` header line)", loop)
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
                  "split the commit before push", "rebase the branch onto the protected line",
                  "close, open, code: three commits", "git fetch --unshallow",
                  "run the branch through a pull request",
                  "remove the stage in the commit that closes that cycle"):
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


# ---------------------------------------------------------------------------
# Round 2 (architecture.md "Revision — round 2", part 7)
# ---------------------------------------------------------------------------
def _flag(p: Path, on: bool) -> None:
    cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
    a, b = ("enabled = false", "enabled = true") if on else ("enabled = true", "enabled = false")
    write(p, "fde.config.toml", cfg.replace("[cycle]\n" + a, "[cycle]\n" + b))


def _cfg_sub(p: Path, a: str, b: str) -> None:
    cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
    assert a in cfg, a
    write(p, "fde.config.toml", cfg.replace(a, b))


LINEAR = "history must stay linear once cycles exist; rebase the branch onto the protected line"


class TestF31LinearHistory(Fixture):
    """Round 3 part 1: examined = any parent opted; an examined merge is red."""

    def branch(self, p):
        return git_out(p, "rev-parse", "--abbrev-ref", "HEAD")

    def orphan(self, p, name, with_config=False):
        run_git(p, "checkout", "-q", "--orphan", name)
        keep = (p / "fde.config.toml").read_text(encoding="utf-8") if with_config else None
        run_git(p, "rm", "-rq", "--cached", ".")
        for f in list(p.iterdir()):
            if f.name != ".git":
                shutil.rmtree(f) if f.is_dir() else f.unlink()
        if keep is not None:
            write(p, "fde.config.toml", keep)
        write(p, "src/evil.py", BIG)
        return commit_all(p, "orphan root")

    def red_everywhere(self, p, before, *needles):
        for since in (before, "0" * 40, None):
            self.assertRed(self.gate(p, since), *needles)

    def test_b_main_merged_into_an_orphan_root_then_fast_forwarded_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        before = commit_all(p, "close C-1")
        main = self.branch(p)
        self.orphan(p, "evil")
        run_git(p, "merge", "-q", "--allow-unrelated-histories", "-m", "merge main", main)
        m = git_out(p, "rev-parse", "HEAD")
        run_git(p, "checkout", "-q", main)
        run_git(p, "merge", "-q", "--ff-only", "evil")
        self.red_everywhere(p, before, f"C1 {m[:7]}: a merge after opt-in", LINEAR)

    def test_c_main_merged_into_a_pre_opt_in_branch_then_fast_forwarded_is_red(self):
        p = self.project(cycle=False)
        pre = commit_all(p, "pre-opt-in")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "feature")
        write(p, "src/feature.py", BIG)
        commit_all(p, "feature, forked before opt-in")
        run_git(p, "checkout", "-q", main)
        self.set_config(p, "\n[cycle]\nenabled = true\n")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "opt in, open C-1")
        write(p, "cycles/C-1.md", closed_cyc(1))
        before = commit_all(p, "close C-1")
        run_git(p, "checkout", "-q", "feature")
        run_git(p, "merge", "-q", "-m", "merge main into feature", main)
        m = git_out(p, "rev-parse", "HEAD")
        run_git(p, "checkout", "-q", main)
        run_git(p, "merge", "-q", "--ff-only", "feature")
        self.red_everywhere(p, before, f"C1 {m[:7]}: a merge after opt-in")
        self.assertRed(self.gate(p, pre), f"C1 {m[:7]}: a merge after opt-in")

    def test_d_merge_rewording_a_frozen_item_reports_linearity_only(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        before = commit_all(p, "init: C-1 open")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "side")
        write(p, "cycles/C-1.md", cyc(1, done=XS_DONE[:4] + ("it compiles",)))
        side = commit_all(p, "reword on a side branch")
        run_git(p, "checkout", "-q", main)
        write(p, "docs/n.md", "n\n")
        commit_all(p, "main moves")
        run_git(p, "merge", "-q", "--no-ff", "-m", "merge", "side")
        m = git_out(p, "rev-parse", "HEAD")
        r = self.gate(p, before)
        self.assertRed(r, f"C1 {m[:7]}: a merge after opt-in", f"C4 {side[:7]}")
        self.assertNotIn(f"C4 {m[:7]}", r.stdout)

    def test_e_orphan_root_with_the_flag_merging_main_with_ours_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        before = commit_all(p, "init")
        main = self.branch(p)
        self.orphan(p, "evil", with_config=True)
        run_git(p, "merge", "-q", "-s", "ours", "--allow-unrelated-histories", "-m", "ours", main)
        m = git_out(p, "rev-parse", "HEAD")
        run_git(p, "checkout", "-qf", main)
        run_git(p, "merge", "-q", "--ff-only", "evil")
        self.assertFalse((p / "cycles").exists())
        self.red_everywhere(p, before, f"C1 {m[:7]}: a merge after opt-in")

    def test_f_the_same_content_rebased_linearly_under_an_open_cycle_is_green(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        before = commit_all(p, "init")
        write(p, "src/evil.py", BIG)
        commit_all(p, "the same code, linear, under C-1")
        self.assertGreen(self.gate(p, before), "1 behavior commit(s)")

    def test_pre_opt_in_merges_stay_out_of_scope_and_the_row_adds_up(self):
        p = self.project(cycle=False)
        commit_all(p, "root")
        main = self.branch(p)
        run_git(p, "checkout", "-q", "-b", "b")
        write(p, "src/b.py", BIG)
        commit_all(p, "b")
        run_git(p, "checkout", "-q", main)
        write(p, "src/c.py", BIG)
        commit_all(p, "c")
        run_git(p, "merge", "-q", "--no-ff", "-m", "pre-opt-in merge", "b")
        self.set_config(p, "\n[cycle]\nenabled = true\n")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "O: opt in, open C-1")
        write(p, "src/a.py", BIG)
        commit_all(p, "code under C-1")
        r = self.gate(p, "0" * 40)
        self.assertGreen(r, "6 commit(s) in range: 1 examined, 5 pre-opt-in (1 root(s))")
        t, e, u = map(int, re.search(r"(\d+) commit\(s\) in range: (\d+) examined, "
                                     r"(\d+) pre-opt-in", r.stdout).groups())
        self.assertEqual(t, e + u)   # F39


class TestF33CloseAndOpen(Fixture):
    def c1_open(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, nxt=("a",)))
        return p, commit_all(p, "init")

    def test_close_and_open_in_one_commit_is_red_with_or_without_intake(self):
        for intake in ((), ("C-1#1 dropped — no longer needed",)):
            p, root = self.c1_open()
            write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
            write(p, "cycles/C-2.md", cyc(2, intake=intake))
            sha = commit_all(p, "close and open")
            self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: closes C-1 and opens C-2 in "
                           f"one commit — commit the close first, then open C-2 with its "
                           f"## Intake in a separate commit")

    def test_close_then_open_with_intake_is_green_and_without_it_red(self):
        p, root = self.c1_open()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        commit_all(p, "close")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 dropped — no longer needed",)))
        commit_all(p, "open")
        self.assertGreen(self.gate(p, root))
        q, root = self.c1_open()
        write(q, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        commit_all(q, "close")
        write(q, "cycles/C-2.md", cyc(2))
        sha = commit_all(q, "open, no intake")
        self.assertRed(self.gate(q, root), f"C6 {sha[:7]} C-2: C-1#1 has no disposition")


class TestF34Shallow(Fixture):
    def test_a_shallow_clone_is_one_red_row(self):
        p = self.project()
        commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "a C1 breach, behind the boundary")
        for i in range(3):
            write(p, f"docs/{i}.md", f"{i}\n")
            commit_all(p, f"docs {i}")
        c = Path(tempfile.mkdtemp(dir=_TMP)) / "clone"
        run_git(p, "clone", "-q", "--depth", "2", f"file://{p}", str(c))
        for since in (None, "0" * 40):
            r = self.gate(c, since, explicit=True)
            self.assertEqual(r.results, [("CYCLE", False,
                                          "CYCLE: shallow clone — the gate needs full "
                                          "history; fetch it (fetch-depth: 0, or git "
                                          "fetch --unshallow)")])


class TestF35FullHistorySuffix(Fixture):
    def test_a_red_commit_on_main_names_the_way_out_in_full_history_runs(self):
        p = self.project()
        commit_all(p, "init")
        write(p, "src/a.py", BIG)
        red = commit_all(p, "code with no cycle (already on main)")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "open C-1")
        write(p, "src/b.py", BIG)
        commit_all(p, "clean work")
        self.assertRed(self.gate(p, "0" * 40), f"C1 {red[:7]}: no open cycle",
                       "— if this commit is already on the protected line, this push did "
                       "not cause it: run the branch through a pull request (its base "
                       "resolves) or push again once the branch exists remotely "
                       "(ADR-0017 R3e)")
        self.assertGreen(self.gate(p, red))


class TestF36DeepConfig(Fixture):
    DEEP = "deep = " + "[" * 3000 + "]" * 3000 + "\n"

    def test_pre_opt_in_deep_config_is_green_without_traceback(self):
        p = self.project(cycle=False)
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        commit_all(p, "init")
        write(p, "fde.config.toml", self.DEEP + good)
        commit_all(p, "deep, before opt-in")
        write(p, "fde.config.toml", good + "\n[cycle]\nenabled = true\n")
        commit_all(p, "fix, opt in")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "open C-1")
        self.assertGreen(self.gate(p, "0" * 40))
        r = verify(p, "--gate", "cycle", "--since", "0" * 40)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_deep_config_in_an_examined_parent_is_a_red_row_under_all(self):
        p = self.project()
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "fde.config.toml", self.DEEP + good)
        deep = commit_all(p, "deep")
        write(p, "fde.config.toml", good)
        commit_all(p, "fix")
        r = verify(p, "--all", "--since", root)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn(f"C1 {deep[:7]}: this commit makes fde.config.toml not valid TOML",
                      r.stdout)
        for gid in ("CFG ", "I4 ", "I6 "):
            self.assertIn(gid, r.stdout)


class TestF37ComposedMessage(Fixture):
    def test_rule_advice_only_where_rule_could_apply(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close")
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = ["lib/"]')
        narrow = commit_all(p, "FORWARD: RULE — tidy config")
        r = self.gate(p, root)
        row = next(x for x in r.stdout.split("; C") if narrow[:7] in x)
        self.assertIn("a change to [gate]/[triage]/[cycle] always needs an open cycle", row)
        self.assertNotIn("FORWARD: RULE", row)
        q = self.project()
        root = commit_all(q, "init")
        write(q, "src/a.py", BIG)
        sha = commit_all(q, "plain code")
        self.assertRed(self.gate(q, root), f"C1 {sha[:7]}: no open cycle — open a cycle in an "
                       f"earlier commit, or declare \"FORWARD: RULE — <reason>\" if it is "
                       f"RULE-sized")


class TestF38ReportShape(Fixture):
    def test_a_string_behavior_paths_in_the_working_tree_reports_n_a(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = "src/"')
        r = self.gate(p, explicit=True)
        self.assertIn("n/a (working-tree [gate] paths are not a list of strings)", r.stdout)
        self.assertNotIn("could not run", r.stdout)


class TestF19PreOptInIsNeverJudged(Fixture):
    def history(self, breakage: str, after_cycle: bool):
        p = self.project(cycle=False)
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        if after_cycle:
            self.set_config(p, "\n[cycle]\nenabled = true\n", good)
            good = (p / "fde.config.toml").read_text(encoding="utf-8")
            write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "fde.config.toml", good + breakage)
        broke = commit_all(p, "break")
        write(p, "fde.config.toml", good)
        fixed = commit_all(p, "fix")
        if not after_cycle:
            self.set_config(p, "\n[cycle]\nenabled = true\n")
            commit_all(p, "opt in")
            write(p, "cycles/C-1.md", cyc(1))
            commit_all(p, "open C-1")
        return p, root, broke, fixed

    def test_pre_opt_in_breakage_is_green_under_root_and_all_zeros(self):
        for breakage in ("\n[[[ not toml\n", '\n[cycle]\nenabled = "no"\n'):
            p, root, _b, _f = self.history(breakage, after_cycle=False)
            self.assertGreen(self.gate(p, root))
            self.assertGreen(self.gate(p, "0" * 40), "full history (new branch)")

    def test_the_same_breakage_after_the_first_cycle_file_is_red(self):
        # R4e: red at the commit that introduces it; the repair is green
        p, root, broke, fixed = self.history("\n[[[ not toml\n", after_cycle=True)
        r = self.gate(p, "0" * 40)
        self.assertRed(r, f"C1 {broke[:7]}: this commit makes fde.config.toml not valid "
                          f"TOML — fix it before pushing (amend or rebase); once pushed, "
                          f"the next commit repairs it and this one stays reported")
        self.assertNotIn(f"C1 {fixed[:7]}", r.stdout)
        p, root, broke, fixed = self.history('\n[scrum]\nenabled = "no"\n', after_cycle=True)
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {broke[:7]}: this commit makes fde.config.toml invalid "
                          f"([scrum] malformed)")
        self.assertNotIn(f"C1 {fixed[:7]}", r.stdout)


class TestF20NarrowReader(Fixture):
    def test_mistyped_sections_before_opt_in_are_green_without_traceback(self):
        for bad in ("weights = 5\n", 'gate = "x"\n'):
            p = self.project(cycle=False)
            good = (p / "fde.config.toml").read_text(encoding="utf-8")
            write(p, "fde.config.toml", bad + good.replace("[weights]", "[weights_]")
                  if bad.startswith("weights") else bad + good.replace("[gate]", "[gate_]"))
            root = commit_all(p, "pre-opt-in, mistyped")
            write(p, "fde.config.toml", good + "\n[cycle]\nenabled = true\n")
            commit_all(p, "fix and opt in")
            self.assertGreen(self.gate(p, "0" * 40))
            r = verify(p, "--gate", "cycle", "--since", root)
            self.assertNotIn("Traceback", r.stderr, bad)

    def test_bad_behavior_paths_in_an_examined_parent_is_a_red_row_under_all(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = "src/"')
        bad = commit_all(p, "mistype")
        _cfg_sub(p, 'behavior_paths = "src/"', 'behavior_paths = ["src/"]')
        fixed = commit_all(p, "fix")
        r = verify(p, "--all", "--since", root)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn(f"C1 {bad[:7]}: this commit makes fde.config.toml invalid "
                      f"([gate].behavior_paths must be a list of strings)", r.stdout)
        self.assertNotIn(f"C1 {fixed[:7]}", r.stdout)
        self.assertIn("CFG ", r.stdout)
        self.assertIn("I4 ", r.stdout)


class TestF21DispositionsIgnoreTheScrumMode(Fixture):
    def c1_closed(self, scrum):
        p = self.project(scrum=scrum)
        write(p, "backlog.md", BACKLOG)
        write(p, "cycles/C-1.md", cyc(1, nxt=("fix the flaky thing", "p99 latency")))
        return p, commit_all(p, "init")

    def scrum(self, p, on):
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        if "[scrum]" in cfg:
            cfg = cfg.replace("[scrum]\nenabled = " + ("false" if on else "true"),
                              "[scrum]\nenabled = " + ("true" if on else "false"))
        else:
            cfg += "\n[scrum]\nenabled = " + ("true" if on else "false") + "\n"
        write(p, "fde.config.toml", cfg)

    def report_sums(self, p, root):
        r = self.gate(p, root, explicit=True)
        row = next(m for g, _ok, m in r.results if g == "CYCLE-RPT" and "C-1 closed" in m)
        total = int(re.search(r"C-1 closed: (\d+) next-cycle", row).group(1))
        counts = [int(x) for x in re.findall(
            r"(?:captured|taken|deferred|dropped|pending|missing) (\d+)", row)]
        self.assertEqual(len(counts), 6, row)
        self.assertEqual(sum(counts), total, row)

    def test_close_under_scrum_off_then_scrum_on_then_open_without_intake_is_red(self):
        p, root = self.c1_closed(False)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("fix the flaky thing", "p99 latency")))
        commit_all(p, "close, scrum off")
        self.scrum(p, True)
        commit_all(p, "scrum on")
        write(p, "cycles/C-2.md", cyc(2))
        sha = commit_all(p, "open C-2, no intake")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} C-2: C-1#1 has no disposition")
        self.report_sums(p, root)

    def test_scrum_on_off_close_on_with_an_uncaptured_item_is_red(self):
        p, root = self.c1_closed(True)
        self.scrum(p, False)
        commit_all(p, "scrum off")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("fix the flaky thing", "p99 latency")))
        write(p, "backlog.md", BACKLOG + "- flaky (C-1#1) · usage-data\n")
        commit_all(p, "close; only C-1#1 captured")
        self.scrum(p, True)
        commit_all(p, "scrum on")
        write(p, "cycles/C-2.md", cyc(2))
        sha = commit_all(p, "open C-2 without C-1#2")
        r = self.gate(p, root)
        self.assertRed(r, f"C6 {sha[:7]} C-2: C-1#2 has no disposition")
        self.assertNotIn("C-1#1 has no disposition", r.stdout)
        self.report_sums(p, root)

    def test_the_same_with_intake_coverage_is_green(self):
        p, root = self.c1_closed(True)
        self.scrum(p, False)
        commit_all(p, "scrum off")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("fix the flaky thing", "p99 latency")))
        write(p, "backlog.md", BACKLOG + "- flaky (C-1#1) · usage-data\n")
        commit_all(p, "close; only C-1#1 captured")
        self.scrum(p, True)
        commit_all(p, "scrum on")
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#2 dropped — measured, fine",)))
        commit_all(p, "open C-2")
        r = self.gate(p, root, explicit=True)
        self.assertGreen(r, "captured 1 (C-1#1)", "dropped 1 (C-1#2)")
        self.report_sums(p, root)


class TestF22GateConfigIsBehavior(Fixture):
    def closed_only(self, **kw):
        p = self.project(**kw)
        write(p, "cycles/C-1.md", cyc(1, done=kw.get("_done", XS_DONE)))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close")
        return p, root

    def test_narrow_act_restore_is_red_at_the_narrowing(self):
        p, root = self.closed_only()
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = ["lib/"]')
        narrow = commit_all(p, "narrow")
        write(p, "src/a.py", BIG)
        commit_all(p, "code, invisible to the narrowed paths")
        _cfg_sub(p, 'behavior_paths = ["lib/"]', 'behavior_paths = ["src/"]')
        commit_all(p, "restore")
        self.assertRed(self.gate(p, root), f"C1 {narrow[:7]}: no open cycle")

    def test_stages_removed_and_restored_is_red(self):
        p = self.project(stages=["live"])
        done = XS_DONE + ("live checks pass",)
        write(p, "cycles/C-1.md", cyc(1, done=done))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1, done=done))
        commit_all(p, "close")
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        off = commit_all(p, "remove the stage")
        _cfg_sub(p, "stages = []", 'stages = ["live"]')
        commit_all(p, "restore")
        self.assertRed(self.gate(p, root), f"C1 {off[:7]}: no open cycle")

    def test_narrowing_claimed_as_rule_is_red(self):
        p, root = self.closed_only()
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = ["lib/"]')
        sha = commit_all(p, "FORWARD: RULE — tidy config")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")


class TestF23StageRemoval(Fixture):
    """Addendum 2026-09-28 (architecture.md part 7a): a stage is removed in
    the commit that closes the cycle carrying its key."""
    LIVE = "live checks pass"
    DONE2 = XS_DONE + (LIVE,)
    WHY = "we stopped deploying this service"

    def close2(self, nxt=("live checks pass: carried, the service may deploy again",),
               live_mark=("-", WHY)):
        marks = {i: ("x", "evidence") for i in range(len(self.DONE2) - 1)}
        if live_mark:
            marks[len(self.DONE2) - 1] = live_mark
        return cyc(2, done=self.DONE2, closed="2026-10-03", nxt=nxt, marks=marks, intake=())

    def step1(self):
        p = self.project(stages=["live"])
        write(p, "cycles/C-1.md", closed_cyc(1, done=self.DONE2))
        root = commit_all(p, "init: C-1 closed")
        write(p, "cycles/C-2.md", cyc(2, done=self.DONE2, intake=()))
        commit_all(p, "1: open C-2 with a live item")
        return p, root

    def step2(self, p):
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        write(p, "cycles/C-2.md", self.close2())
        return commit_all(p, "2: remove live in the commit that closes C-2")

    def step3(self, p, intake=("C-2#1 dropped — the service no longer deploys",)):
        write(p, "cycles/C-3.md", cyc(3, intake=intake))
        return commit_all(p, "3: open C-3")

    def green_sequence(self):
        p, root = self.step1()
        self.assertGreen(self.gate(p, root))
        self.step2(p)
        self.assertGreen(self.gate(p, root))
        self.step3(p)
        self.assertGreen(self.gate(p, root))
        write(p, "src/a.py", BIG)
        commit_all(p, "4: code under C-3")
        self.assertGreen(self.gate(p, root), "4 commit(s) in range: 4 examined, 0 pre-opt-in (0 root(s)); 2 behavior commit(s)")
        return p, root

    def test_green_sequence(self):
        self.green_sequence()

    def test_a_removal_while_the_carrier_stays_open_is_red(self):
        p, root = self.step1()
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        sha = commit_all(p, "stop deploying mid-cycle")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: removes stage 'live' while C-2 "
                       f"carries it — remove the stage in the commit that closes C-2 "
                       f"(resolve its 'live' item; a [-] item is carried to ## Next cycle)")

    def test_b_close_first_then_remove_is_red(self):
        p, root = self.step1()
        write(p, "cycles/C-2.md", self.close2())
        commit_all(p, "close C-2, stage still declared")
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        sha = commit_all(p, "remove live afterwards")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")

    def test_c_close_with_the_live_item_unresolved_is_red(self):
        p, root = self.step1()
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        write(p, "cycles/C-2.md", self.close2(nxt=("none",), live_mark=None))
        sha = commit_all(p, "remove and close, live left open")
        self.assertRed(self.gate(p, root), f"C3 {sha[:7]} cycles/C-2.md: closed with "
                                           f"'## Done when' item 6 unresolved")

    def test_d_not_met_live_without_a_carried_item_is_red(self):
        p, root = self.step1()
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        write(p, "cycles/C-2.md", self.close2(nxt=("something unrelated",)))
        sha = commit_all(p, "remove and close, nothing carried")
        self.assertRed(self.gate(p, root), f"C3 {sha[:7]} cycles/C-2.md: not-met item "
                                           f"\"{self.LIVE}\" needs its own next-cycle item")

    def test_e_removal_close_and_new_cycle_in_one_commit_is_red(self):
        p, root = self.step1()
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        write(p, "cycles/C-2.md", self.close2())
        write(p, "cycles/C-3.md", cyc(3, intake=("C-2#1 dropped — gone",)))
        sha = commit_all(p, "remove, close and open")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: a behavior commit opens "
                                           f"cycles/C-3.md")

    def test_f_removal_claimed_as_rule_without_closing_is_red(self):
        p, root = self.step1()
        _cfg_sub(p, 'stages = ["live"]', "stages = []")
        sha = commit_all(p, "FORWARD: RULE — drop a stage")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: removes stage 'live' while C-2 "
                                           f"carries it")

    def test_g_restore_under_c3_is_green_and_the_working_tree_asks_for_the_key(self):
        p, root = self.green_sequence()
        _cfg_sub(p, "stages = []", 'stages = ["live"]')
        sha = commit_all(p, "restore live under C-3")
        r = self.gate(p, root)
        self.assertRed(r, "C2 cycles/C-3.md: profile key 'live' missing",
                       "append '- [ ] amended YYYY-MM-DD: live'")
        self.assertNotIn(f"C1 {sha[:7]}", r.stdout)
        write(p, "cycles/C-3.md", cyc(3, intake=("C-2#1 dropped — the service no longer deploys",),
                                      done=XS_DONE + ("amended 2026-10-04: live checks pass",)))
        commit_all(p, "C-3 takes the live key")
        self.assertGreen(self.gate(p, root))

    def test_h_restore_with_no_open_cycle_is_red(self):
        p, root = self.green_sequence()
        write(p, "cycles/C-3.md", closed_cyc(3, intake=("C-2#1 dropped — the service no "
                                                        "longer deploys",)))
        commit_all(p, "close C-3")
        _cfg_sub(p, "stages = []", 'stages = ["live"]')
        sha = commit_all(p, "restore live, no cycle")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: no open cycle")

    def test_i_next_opening_without_disposing_of_the_live_item_is_red(self):
        p, root = self.step1()
        self.step2(p)
        sha = self.step3(p, intake=())
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} C-3: C-2#1 has no disposition")


class TestF24TopLevel(Fixture):
    def test_project_in_a_subdirectory_is_one_red_row(self):
        outer = Path(tempfile.mkdtemp(dir=_TMP))
        p = outer / "sub"
        shutil.copytree(_template(cycle=True), p)
        shutil.move(str(p / ".git"), str(outer / ".git"))
        r = self.gate(p, explicit=True)
        self.assertEqual(r.results, [("CYCLE", False,
                                      "CYCLE: the project must be the git top level (found "
                                      "prefix sub/) — move fde.config.toml to the "
                                      "repository root")])


class TestF25PullOnce(Fixture):
    def test_the_same_captured_token_taken_twice_is_red(self):
        p = self.project(scrum=True)
        write(p, "backlog.md", BACKLOG)
        write(p, "cycles/C-1.md", cyc(1, nxt=("a",)))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        write(p, "backlog.md", BACKLOG + "- a (C-1#1) · opinion\n")
        commit_all(p, "close, captured")
        write(p, "cycles/C-2.md", cyc(2, tasks=("do a (C-1#1)",), intake=("C-1#1 taken",)))
        commit_all(p, "open C-2, pulling it")
        write(p, "cycles/C-2.md", closed_cyc(2, tasks=("do a (C-1#1)",), intake=("C-1#1 taken",)))
        commit_all(p, "close C-2")
        write(p, "cycles/C-3.md", cyc(3, tasks=("do a again (C-1#1)",), intake=("C-1#1 taken",)))
        sha = commit_all(p, "open C-3, pulling it again")
        self.assertRed(self.gate(p, root), f"C6 {sha[:7]} C-3: C-1#1 was already taken by an "
                                           f"earlier cycle")


class TestF26Cost(Fixture):
    def spawns_for(self, n_pre: int) -> int:
        import subprocess
        p = self.project(cycle=False)
        commit_all(p, "init")
        ref = git_out(p, "symbolic-ref", "HEAD")
        stream = []
        for i in range(1, n_pre + 1):
            body = f"x = {i}\n".encode()
            stream.append(f"commit {ref}\nmark :{i}\ncommitter f <f@t> {1700000000 + i} +0000\n"
                          f"data 3\nc{i % 10}\n" + (f"from {ref}^0\n" if i == 1 else "")
                          + f"M 100644 inline src/a.py\ndata {len(body)}\n")
            stream.append(body.decode() + "\n")
        subprocess.run(["git", "fast-import", "--quiet", "--force"], cwd=p, check=True,
                       input="".join(stream).encode())
        run_git(p, "reset", "-q", "--hard")
        self.set_config(p, "\n[cycle]\nenabled = true\n")
        commit_all(p, "opt in")
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "open C-1")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        calls = []
        orig = vmod.Gate._run_git

        def counting(gate, *a, **k):
            calls.append(a[:2])
            return orig(gate, *a, **k)
        vmod.Gate._run_git = counting
        try:
            r = self.gate(p, "0" * 40)
        finally:
            vmod.Gate._run_git = orig
        self.assertGreen(r, "2 examined")
        return len(calls)

    def test_spawns_do_not_grow_with_pre_opt_in_history(self):
        self.assertEqual(self.spawns_for(20), self.spawns_for(200))


class TestF29OneClaimOneVerdict(Fixture):
    def test_a_raised_rule_limit_does_not_exempt_a_big_claimed_commit(self):
        p = self.project()
        root = commit_all(p, "init")
        self.set_config(p, "", (p / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("[triage]\n", "[triage]\nrule_lane_max_loc = 500\n", 1))
        raised = commit_all(p, "raise the RULE limit")
        write(p, "src/a.py", "".join(f"y{i} = {i}\n" for i in range(100)))
        big = commit_all(p, "FORWARD: RULE — says it is small")
        self.set_config(p, "", (p / "fde.config.toml").read_text(encoding="utf-8")
                        .replace("rule_lane_max_loc = 500\n", "", 1))
        commit_all(p, "restore")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {raised[:7]}: no open cycle", f"C1 {big[:7]}: no open cycle")
        cfg = Config.load(p)
        bp, ep = gate_paths(cfg.raw)
        g = vmod.Gate(p, bp, ep)
        g.gate_rule_lane(since=root)
        self.assertFalse(g.results[0][1], g.results)
        self.assertIn(big[:7], g.results[0][2])


class TestThisRepositoryAllZeros(unittest.TestCase):
    def test_this_repository_all_zeros_and_default_range_stay_green(self):
        r = verify(ROOT, "--gate", "cycle", "--since", "0" * 40)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("full history (new branch)", r.stdout)
        r = verify(ROOT, "--gate", "cycle")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("range last commit only", r.stdout)



# ---------------------------------------------------------------------------
# Round 4 (architecture.md "Revision — round 4", part 6)
# ---------------------------------------------------------------------------
NOT_IN_FORCE = ("CYCLE", True, "cycle mode off — declared-scope gate not in force")


class TestF41ArmedByHistory(Fixture):
    """R4a: a push whose parent is opted is examined even when its own
    working tree disarms the mode; each push is run on its own range, as
    CI runs `--since <previous tip>`."""

    def c1_closed(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init: open C-1")
        write(p, "cycles/C-1.md", closed_cyc(1))
        return p, commit_all(p, "close C-1")

    def test_temporary_disarm_is_red_at_its_own_push(self):
        p, before = self.c1_closed()
        _flag(p, False)
        write(p, "src/evil.py", BIG)
        a = commit_all(p, "push A: flag off, code")
        self.assertRed(self.gate(p, before), f"C1 {a[:7]}: no open cycle — open a cycle in "
                       f"an earlier commit; a change to [gate]/[triage]/[cycle] always "
                       f"needs an open cycle")
        r = verify(p, "--all", "--since", before)
        self.assertIn(f"C1 {a[:7]}", r.stdout)
        self.assertEqual(r.returncode, 1)
        write(p, "cycles/C-2.md", cyc(2, intake=()))
        b = commit_all(p, "push B: open C-2, still off")
        rb = self.gate(p, a)
        self.assertNotIn("not in force", rb.stdout)
        self.assertIn("1 commit(s) in range: 1 examined", rb.stdout)
        _flag(p, True)
        commit_all(p, "push C: flag back on")
        self.assertIn("1 examined", self.gate(p, b).stdout)
        self.assertRed(self.gate(p, before), f"C1 {a[:7]}: no open cycle")

    def test_re_root_is_red_at_its_own_push(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, tasks=("the declared task",)))
        before = commit_all(p, "init: C-1 open")
        _flag(p, False)
        run_git(p, "rm", "-rq", "cycles")
        write(p, "src/evil.py", BIG)
        a = commit_all(p, "push A: flag off, cycles/ deleted, code")
        self.assertRed(self.gate(p, before), f"C4 {a[:7]}: cycles/C-1.md was deleted")
        _flag(p, True)
        write(p, "src/more.py", BIG)
        commit_all(p, "push B: flag on, more code")
        self.assertGreen(self.gate(p, a), "1 commit(s) in range: 0 examined, 1 pre-opt-in")
        self.assertRed(self.gate(p, before), f"C4 {a[:7]}: cycles/C-1.md was deleted")

    def test_honest_exit_is_one_red_commit_then_silence(self):
        p, _before = self.c1_closed()
        exit_base = git_out(p, "rev-parse", "HEAD")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg.replace("\n[cycle]\nenabled = true\n", "\n"))
        run_git(p, "rm", "-rq", "cycles")
        ex = commit_all(p, "leave the cycle mode")
        self.assertRed(self.gate(p, exit_base), f"C4 {ex[:7]}: cycles/C-1.md was deleted")
        write(p, "src/a.py", BIG)
        commit_all(p, "ordinary code, later push")
        self.assertEqual(self.gate(p, ex, explicit=True).results, [NOT_IN_FORCE])
        self.assertEqual(self.gate(p, ex).results, [])


class TestNeverOptedClient(Fixture):
    def test_a_depth_1_clone_of_a_never_opted_client_is_silent(self):
        p = self.project(cycle=False)
        commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        c = Path(tempfile.mkdtemp(dir=_TMP)) / "clone"
        run_git(p, "clone", "-q", "--depth", "1", f"file://{p}", str(c))
        self.assertEqual(self.gate(c, explicit=True).results, [NOT_IN_FORCE])
        self.assertEqual(self.gate(c, "0" * 40).results, [])
        r = verify(c, "--all")
        self.assertNotIn("CYCLE", r.stdout)


class TestF42SerialAtEveryCycleCommit(Fixture):
    def c2_open(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1))
        base = commit_all(p, "init: C-1 closed with none")
        write(p, "cycles/C-2.md", cyc(2, intake=()))
        commit_all(p, "open C-2")
        return p, base

    def test_c3_added_while_c2_is_open_is_red_at_that_commit(self):
        p, base = self.c2_open()
        write(p, "cycles/C-3.md", cyc(3, intake=()))
        x = commit_all(p, "X: add C-3 while C-2 is open")
        self.assertRed(self.gate(p, base), f"C5 {x[:7]}: opens C-3 while C-2 is open — close "
                                           f"C-2 first (separate commit), then open C-3")

    def test_c2_and_c3_added_together_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1))
        base = commit_all(p, "init")
        write(p, "cycles/C-2.md", cyc(2, intake=()))
        write(p, "cycles/C-3.md", cyc(3, intake=()))
        x = commit_all(p, "add C-2 and C-3 together")
        self.assertRed(self.gate(p, base), f"C5 {x[:7]}: opens C-3 while C-2 is open")

    def test_the_original_probe_range_is_red(self):
        p, base = self.c2_open()
        write(p, "cycles/C-3.md", cyc(3, intake=()))
        x = commit_all(p, "X: add C-3 while C-2 is open")
        write(p, "cycles/C-2.md", closed_cyc(2, intake=(), nxt=("fix the flaky thing",
                                                                 "p99 latency")))
        commit_all(p, "Y: close C-2 with two items")
        write(p, "src/a.py", BIG)
        commit_all(p, "Z: code under C-3")
        self.assertRed(self.gate(p, base), f"C5 {x[:7]}: opens C-3 while C-2 is open")

    def test_the_legal_order_is_green(self):
        p, base = self.c2_open()
        write(p, "cycles/C-2.md", closed_cyc(2, intake=(), nxt=("fix the flaky thing",
                                                                 "p99 latency")))
        commit_all(p, "close C-2")
        write(p, "cycles/C-3.md", cyc(3, intake=("C-2#1 dropped — fixed upstream",
                                                 "C-2#2 dropped — measured, fine")))
        commit_all(p, "open C-3 with Intake")
        write(p, "src/a.py", BIG)
        commit_all(p, "code under C-3")
        self.assertGreen(self.gate(p, base), "1 behavior commit(s)")


class TestF43RedAtTheIntroducingCommit(Fixture):
    def m(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init: C-1 open")
        _cfg_sub(p, 'behavior_paths = ["src/"]', 'behavior_paths = "src/"')
        return p, root, commit_all(p, "M: behavior_paths becomes a string")

    def test_m_is_red_and_n_repairs_it_green(self):
        p, root, m = self.m()
        self.assertRed(self.gate(p, root), f"C1 {m[:7]}: this commit makes fde.config.toml "
                       f"invalid ([gate].behavior_paths must be a list of strings) — fix it "
                       f"before pushing (amend or rebase); once pushed, the next commit "
                       f"repairs it and this one stays reported")
        _cfg_sub(p, 'behavior_paths = "src/"', 'behavior_paths = ["src/"]')
        commit_all(p, "N: restore the list")
        self.assertGreen(self.gate(p, m), "1 commit(s) in range: 1 examined")

    def test_n_prime_leaving_the_string_is_red(self):
        p, root, m = self.m()
        write(p, "src/a.py", BIG)
        n2 = commit_all(p, "N': code, the string left in place")
        self.assertRed(self.gate(p, m), f"C1 {n2[:7]}: parent config is invalid "
                                        f"([gate].behavior_paths must be a list of strings) "
                                        f"and this commit does not repair it")


class TestF44SymlinkedConfig(Fixture):
    LINK = ("CYCLE", False, "CYCLE: fde.config.toml must be a regular file (found a "
                            "symlink) — replace the link with the file")

    def linked(self, p):
        (p / "config").mkdir(exist_ok=True)
        (p / "fde.config.toml").rename(p / "config" / "fde.toml")
        os.symlink("config/fde.toml", p / "fde.config.toml")

    def test_a_symlinked_working_tree_config_with_a_cycle_is_one_red_row(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        self.linked(p)
        self.assertEqual(self.gate(p, explicit=True).results, [self.LINK])

    def test_a_commit_that_makes_the_config_a_symlink_is_red_at_that_commit(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        self.linked(p)
        link = commit_all(p, "config becomes a symlink")
        (p / "fde.config.toml").unlink()
        write(p, "fde.config.toml", good)
        commit_all(p, "back to a regular file")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {link[:7]}: this commit makes fde.config.toml a symlink")
        self.assertEqual(r.stdout.count("C1 "), 1, r.stdout)

    def test_the_probe_history_is_red_not_green(self):
        p = self.project()
        self.linked(p)
        root = commit_all(p, "opt in through a symlinked config")
        write(p, "src/a.py", BIG)
        commit_all(p, "undeclared 1")
        write(p, "src/b.py", BIG)
        commit_all(p, "undeclared 2")
        for since in (root, "0" * 40):
            self.assertEqual(self.gate(p, since).results, [self.LINK])


class TestF45ReplaceObjects(Fixture):
    def test_git_replace_does_not_change_the_verdict(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        close = commit_all(p, "close C-1")
        write(p, "src/a.py", BIG)
        u = commit_all(p, "U: undeclared code")
        self.assertRed(self.gate(p, close), f"C1 {u[:7]}: no open cycle")
        tree = git_out(p, "rev-parse", f"{close}^{{tree}}")
        fake = git_out(p, "commit-tree", tree, "-p", close, "-m", "looks harmless")
        run_git(p, "replace", u, fake)
        self.assertEqual(git_out(p, "log", "-1", "--format=%s", u), "looks harmless")
        self.assertRed(self.gate(p, close), f"C1 {u[:7]}: no open cycle")
        self.assertRed(self.gate(p, "0" * 40), f"C1 {u[:7]}: no open cycle")



class TestNoRepository(Fixture):
    """A never-opted client whose directory is not a git repository is
    silent; with the flag on, the git failure is a red row."""

    def bare_dir(self, **kw) -> Path:
        p = self.project(**kw)
        shutil.rmtree(p / ".git")
        env_ceiling = str(p.parent)
        return p, {"GIT_CEILING_DIRECTORIES": env_ceiling}

    def test_never_opted_non_git_client_is_silent(self):
        p, env = self.bare_dir(cycle=False)
        old = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = env["GIT_CEILING_DIRECTORIES"]
        try:
            self.assertEqual(self.gate(p, explicit=True).results, [NOT_IN_FORCE])
            self.assertEqual(self.gate(p).results, [])
        finally:
            if old is None:
                os.environ.pop("GIT_CEILING_DIRECTORIES")
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = old
        r = verify(p, "--all", env=env)
        self.assertNotIn("CYCLE", r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        r = verify(p, "--gate", "cycle", env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("CYCLE"), 1, r.stdout)
        self.assertIn("not in force", r.stdout)

    def test_git_failure_while_armed_is_red(self):
        p, env = self.bare_dir(cycle=True)
        r = verify(p, "--gate", "cycle", env=env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CYCLE could not run: a git operation failed", r.stdout)
        self.assertIn("not a git repository", r.stdout)
        self.assertNotIn("Traceback", r.stderr)


class TestReplaceOptionIsTheCycleGatesOnly(Fixture):
    def test_other_gates_do_not_receive_no_replace_objects(self):
        import subprocess as sp
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        cfg = Config.load(p)
        bp, ep = gate_paths(cfg.raw)
        g = vmod.Gate(p, bp, ep)
        seen = []
        real = sp.run

        def spy(argv, *a, **k):
            seen.append((tag[0], list(argv)))
            return real(argv, *a, **k)
        tag = ["cycle"]
        vmod.subprocess.run = spy
        try:
            g.gate_cycle(cfg, since=root)
            tag[0] = "other"
            g.gate_rule_lane(since=root, explicit=True)
            g.changed(False, root)
            g.gate_adversarial()
        finally:
            vmod.subprocess.run = real
        cyc_calls = [a for t, a in seen if t == "cycle" and a[0] == "git"]
        other = [a for t, a in seen if t == "other" and a[0] == "git"]
        self.assertTrue(cyc_calls and all(a[1] == "--no-replace-objects" for a in cyc_calls))
        self.assertTrue(other)
        self.assertFalse(any("--no-replace-objects" in a for a in other), other)
        self.assertEqual(g._git_global, ())

if __name__ == "__main__":
    unittest.main()
