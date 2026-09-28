"""FWD-021 (ADR-0017): declared cycle scope — the `cycle` gate, its pure
core (runtime/cycle.py), validate() rule 6c, the graph's cycle node, and
the instruction layer. Contract: specs/FWD-021-cycle-scope/architecture.md.

Every red case asserts the check label (C1..C6) and the reason. Fixtures
are temp git repos from support.make_project(cycle=True); a fixture's
root commit is never examined (no parent tree), so each scenario commits
its starting state first and then the commits under test."""
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
from fde_lib import Config, Spec, validate  # noqa: E402

XS_DONE = ("declared-before", "regression-proven", "review-rounds", "residuals",
           "the thing works")
S_DONE = ("declared-before", "regression-proven", "review-rounds", "residuals",
          "specs/FWD-040-x/acceptance.md")
BIG = "".join(f"line {i}\n" for i in range(20))   # never RULE-eligible (>= 10)


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


class Fixture(unittest.TestCase):
    def project(self, **kw) -> Path:
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        kw.setdefault("cycle", True)
        p = make_project(d, **kw)
        write(p, "src/a.py", "x = 1\n")
        return p

    def gate(self, p, since=None, *extra, env=None):
        args = ["--gate", "cycle"] + (["--since", since] if since else []) + list(extra)
        return verify(p, *args, env=env)

    def assertRed(self, r, *needles):
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for n in needles:
            self.assertIn(n, r.stdout, r.stdout)

    def assertGreen(self, r, *needles):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for n in needles:
            self.assertIn(n, r.stdout, r.stdout)


# ---------------------------------------------------------------------------
# C1 — declared before
# ---------------------------------------------------------------------------
class TestC1DeclaredBefore(Fixture):
    def test_no_cycle_in_parent_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}", "no open cycle in the parent tree")

    def test_only_a_closed_cycle_in_parent_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        commit_all(p, "close C-1")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {sha[:7]}", "no open cycle in the parent tree")
        self.assertNotIn("C4", r.stdout)

    def test_acceptance_in_the_same_commit_as_code_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-040 (S)", done=S_DONE))
        root = commit_all(p, "init")
        write(p, "specs/FWD-040-x/spec.md", "Triage: **S**\n")
        write(p, "specs/FWD-040-x/acceptance.md", "date: 2026-10-01\n")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "spec and code together")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}",
                       "specs/FWD-040-x/acceptance.md is absent from the parent tree")

    def test_acceptance_in_an_earlier_commit_is_green(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-040 (S)", done=S_DONE))
        root = commit_all(p, "init")
        write(p, "specs/FWD-040-x/spec.md", "Triage: **S**\n")
        write(p, "specs/FWD-040-x/acceptance.md", "date: 2026-10-01\n")
        commit_all(p, "spec first")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        self.assertGreen(self.gate(p, root), "1 behavior commit(s) examined")

    def test_rule_eligible_commit_with_no_cycle_is_green(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", "x = 2\n")
        commit_all(p, "FORWARD: RULE — typo")
        self.assertGreen(self.gate(p, root), "(1 RULE-exempt")

    def test_rule_claiming_ineligible_commit_with_no_cycle_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "FORWARD: RULE — says it is small")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}", "no open cycle")

    def test_child_of_the_enabling_commit_needs_a_cycle(self):
        p = self.project(cycle=False)
        root = commit_all(p, "init")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg + "\n[cycle]\nenabled = true\n")
        write(p, "src/a.py", BIG)
        enabling = commit_all(p, "enable the mode, with code")   # not examined
        write(p, "src/a.py", BIG + BIG)
        child = commit_all(p, "code after enabling")
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {child[:7]}", "no open cycle")
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
        write(p, "cycles/C-1.md", cyc(1))   # the working tree is fine now; history is not
        r = self.gate(p, root)
        self.assertRed(r, f"C1 {sha[:7]}: the parent's open C-1 fails its form: C2 "
                          f"cycles/C-1.md: profile key")
        self.assertNotIn("CYCLE    C2", r.stdout)

    def test_declared_xs_while_spec_triages_m_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1, demands="FWD-050 (XS)"))
        write(p, "specs/FWD-050-y/spec.md", "# y\n\nTriage: surfaces 3 → **M**\n")
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        sha = commit_all(p, "code")
        r = self.gate(p, root)
        self.assertRed(r, "C2 cycles/C-1.md: FWD-050 is declared XS but "
                          "specs/FWD-050-y/spec.md triages it M", f"C1 {sha[:7]}")

    def test_non_behavior_commit_needs_no_cycle(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "docs/notes.md", BIG)
        commit_all(p, "docs")
        self.assertGreen(self.gate(p, root), "0 behavior commit(s) examined")


# ---------------------------------------------------------------------------
# C2 — form
# ---------------------------------------------------------------------------
class TestC2Form(unittest.TestCase):
    def form(self, text, stages=(), specs=None, name="cycles/C-1.md"):
        return cycle.check_form(cycle.parse(name, text.encode()), list(stages), specs or {})

    def test_valid_xs_cycle_has_no_breach(self):
        self.assertEqual(self.form(cyc(1)), [])

    def test_the_skill_schema_is_red_on_every_field(self):
        schema = skill_blocks()[0]
        out = self.form(schema)
        for key in ("cycle", "objective", "opened", "demands"):
            self.assertTrue(any(f"header '{key}:' is an unfilled placeholder" in b
                                for b in out), (key, out))
        items = [l for l in schema.splitlines() if l.startswith("- ")]
        self.assertEqual(len(items), 6)
        flagged = [b for b in out if "item" in b and "unfilled placeholder" in b]
        self.assertEqual(len(flagged), len(items), out)
        self.assertTrue(all(b.startswith("C2 cycles/C-1.md: ") for b in out))

    def test_missing_header_and_section_are_red(self):
        text = cyc(1).replace("objective: the thing works\n", "").replace("## Tasks\n- do the thing\n", "")
        out = self.form(text)
        self.assertIn("C2 cycles/C-1.md: header 'objective:' missing or empty", out)
        self.assertIn("C2 cycles/C-1.md: section '## Tasks' missing", out)

    def test_empty_section_is_red(self):
        out = self.form(cyc(1, tasks=()))
        self.assertIn("C2 cycles/C-1.md: '## Tasks' has no item", out)

    def test_cycle_header_must_equal_the_stem(self):
        out = self.form(cyc(1), name="cycles/C-2.md")
        self.assertTrue(any("does not equal the file's stem C-2" in b for b in out), out)

    def test_bad_dates_and_demands_are_red(self):
        out = self.form(cyc(1, opened="20261001", demands="FWD-030 (XL), FWD-030 (XS), FWD-030 (S)"))
        self.assertTrue(any("'opened: 20261001' is not a YYYY-MM-DD date" in b for b in out))
        self.assertTrue(any("demand 'FWD-030 (XL)' is not" in b for b in out))
        self.assertTrue(any("demand FWD-030 is listed twice" in b for b in out))
        out = self.form(closed_cyc(1).replace("closed: 2026-10-02", "closed: 2026-09-01"))
        self.assertTrue(any("is earlier than opened" in b for b in out), out)

    def test_missing_and_duplicate_profile_keys_are_red(self):
        out = self.form(cyc(1, done=("declared-before", "declared-before", "review-rounds",
                                     "residuals", "the thing works")))
        self.assertIn("C2 cycles/C-1.md: profile key 'regression-proven' missing from "
                      "'## Done when'", out)
        self.assertIn("C2 cycles/C-1.md: profile key 'declared-before' appears 2 times", out)

    def test_promotion_is_required_at_m(self):
        out = self.form(cyc(1, demands="FWD-040 (M)", done=S_DONE))
        self.assertIn("C2 cycles/C-1.md: profile key 'promotion' missing from "
                      "'## Done when'", out)

    def test_undeclared_stage_key_is_red_and_declared_one_is_required(self):
        out = self.form(cyc(1, done=XS_DONE + ("live checks pass",)))
        self.assertIn("C2 cycles/C-1.md: 'live' is present but [cycle].stages does "
                      "not declare it", out)
        out = self.form(cyc(1), stages=("published",))
        self.assertIn("C2 cycles/C-1.md: profile key 'published' missing from "
                      "'## Done when'", out)
        self.assertEqual(self.form(cyc(1, done=XS_DONE + ("published on PyPI",)),
                                   stages=("published",)), [])

    def test_s_demand_needs_its_acceptance_path(self):
        out = self.form(cyc(1, demands="FWD-040 (S)"))
        self.assertTrue(any("S demand FWD-040 has no specs/FWD-040…/acceptance.md" in b
                            for b in out), out)
        # the id boundary: FWD-4 is not FWD-40-x's demand
        out = self.form(cyc(1, demands="FWD-4 (S)", done=S_DONE))
        self.assertTrue(any("S demand FWD-4 has no" in b for b in out), out)

    def test_xs_demand_needs_an_inline_item(self):
        out = self.form(cyc(1, done=XS_DONE[:4]))
        self.assertIn("C2 cycles/C-1.md: XS demand(s) FWD-030 have no inline done item", out)
        out = self.form(cyc(1, demands="FWD-030 (XS), FWD-031 (XS)",
                            done=XS_DONE[:4] + ("FWD-030 passes",)))
        self.assertIn("C2 cycles/C-1.md: XS demand FWD-031 is named by no inline done item", out)

    def test_malformed_done_line_is_red(self):
        text = cyc(1).replace("- [ ] the thing works", "- the thing works")
        out = self.form(text)
        self.assertTrue(any("'## Done when' line '- the thing works' is not" in b for b in out))

    def test_resolved_item_without_evidence_is_red(self):
        text = cyc(1).replace("- [ ] the thing works", "- [x] the thing works")
        self.assertTrue(any("marked [x] with no ' — <evidence>'" in b for b in self.form(text)))

    def test_bad_intake_line_is_red(self):
        out = self.form(cyc(1, intake=("C-0#1 maybe later",)))
        self.assertTrue(any("'## Intake' item 1 is not" in b for b in out), out)

    def test_undecodable_file_is_red(self):
        c = cycle.parse("cycles/C-1.md", b"cycle: C-1\n\xff\xfe\n")
        out = cycle.check_form(c, [], {})
        self.assertTrue(out and out[0].startswith("C2 cycles/C-1.md: not UTF-8"), out)


class TestC2InTheGate(Fixture):
    def test_stray_entry_under_cycles_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        write(p, "cycles/notes.md", "hello\n")
        r = self.gate(p)
        self.assertRed(r, "C2 cycles/notes.md: stray entry")

    def test_undecodable_cycle_file_is_red(self):
        p = self.project()
        (p / "cycles").mkdir()
        (p / "cycles/C-1.md").write_bytes(b"cycle: C-1\n\xff\n")
        self.assertRed(self.gate(p), "C2 cycles/C-1.md: not UTF-8")


# ---------------------------------------------------------------------------
# C3 — closure
# ---------------------------------------------------------------------------
class TestC3Closure(unittest.TestCase):
    def closure(self, text):
        return cycle.check_closure(cycle.parse("cycles/C-1.md", text.encode()))

    def test_well_closed_cycle_is_green(self):
        self.assertEqual(self.closure(closed_cyc(1)), [])

    def test_unresolved_item_at_close_is_red(self):
        text = closed_cyc(1).replace("- [x] residuals — evidence", "- [ ] residuals")
        self.assertIn("C3 cycles/C-1.md: closed with '## Done when' item 4 unresolved",
                      self.closure(text))

    def test_not_met_item_missing_from_next_cycle_is_red(self):
        text = cyc(1, closed="2026-10-02", nxt=("something else",),
                   marks={0: ("x", "e"), 1: ("x", "e"), 2: ("x", "e"), 3: ("x", "e"),
                          4: ("-", "ran out of time")})
        self.assertIn("C3 cycles/C-1.md: not-met item 'the thing works' is not carried "
                      "into '## Next cycle'", self.closure(text))
        carried = text.replace("- something else", "- the thing works, again")
        self.assertEqual(self.closure(carried), [])

    def test_none_alongside_other_items_is_red(self):
        self.assertIn("C3 cycles/C-1.md: '- none' alongside other '## Next cycle' items",
                      self.closure(closed_cyc(1, nxt=("none", "a thing"))))

    def test_empty_next_cycle_at_close_is_red(self):
        self.assertTrue(any("empty '## Next cycle'" in b
                            for b in self.closure(closed_cyc(1, nxt=()))))


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
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md '## Tasks' changed")

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
        text = closed_cyc(1).replace("- [x] the thing works — evidence",
                                     "- [x] something easier — evidence")
        write(p, "cycles/C-1.md", text)
        sha = commit_all(p, "close dishonestly")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md closing rewrote "
                                           f"done item 5")

    def test_cycle_added_closed_is_red(self):
        p = self.project()
        root = commit_all(p, "init")
        write(p, "cycles/C-1.md", closed_cyc(1))
        sha = commit_all(p, "add closed")
        self.assertRed(self.gate(p, root), f"C4 {sha[:7]}: cycles/C-1.md is added already closed")

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
        self.assertRed(r, f"C5 {sha[:7]}: cycles/C-3.md is numbered at or below the existing C-5")
        self.assertIn("C5 cycles/: open cycle C-3 is not the highest-numbered cycle", r.stdout)

    def test_serial_pure(self):
        a = cycle.parse("cycles/C-1.md", closed_cyc(1).encode())
        b = cycle.parse("cycles/C-2.md", cyc(2).encode())
        self.assertEqual(cycle.check_serial([a, b], "x"), [])


# ---------------------------------------------------------------------------
# C6 — dispositions
# ---------------------------------------------------------------------------
class TestC6Dispositions(Fixture):
    BACKLOG = "---\ngoal: g\ndate: 2026-10-01\n---\n\n# Backlog\n\n"

    def test_no_disposition_with_scrum_on_is_red(self):
        p = self.project(scrum=True)
        write(p, "backlog.md", self.BACKLOG)
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        self.assertRed(self.gate(p), "C6 cycles/C-1.md: C-1#1 has no disposition — "
                                     "capture it in backlog.md")

    def test_backlog_line_without_evidence_label_is_red(self):
        p = self.project(scrum=True)
        write(p, "backlog.md", self.BACKLOG + "- fix the bug in x (C-1#1)\n")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        self.assertRed(self.gate(p), "C-1#1 has no disposition",
                       "backlog.md cites it without an evidence label")

    def test_backlog_line_with_label_is_green(self):
        p = self.project(scrum=True)
        write(p, "backlog.md", self.BACKLOG + "- fix the bug in x (C-1#1) · opinion\n")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        self.assertGreen(self.gate(p), "backlog 1")

    def test_no_disposition_with_scrum_off_is_red_once_a_next_cycle_opens(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        write(p, "cycles/C-2.md", cyc(2))
        self.assertRed(self.gate(p), "C6 cycles/C-1.md: C-1#1 has no disposition in "
                                     "C-2's '## Intake'")

    def test_pending_with_scrum_off_is_green_and_reported(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a bug in x",)))
        r = self.gate(p)
        self.assertGreen(r, "C-1 closed: 1 next-cycle item(s)", "pending 1",
                         "C-1#1 a bug in x", "no open cycle — 0 behavior commit(s)")

    def test_intake_taken_deferred_dropped_are_green(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a", "b", "c")))
        write(p, "cycles/C-2.md", cyc(2, tasks=("fix a (C-1#1)",), nxt=("b still (C-1#2)",),
                                      intake=("C-1#1 taken", "C-1#2 deferred",
                                              "C-1#3 dropped — not worth it")))
        self.assertGreen(self.gate(p), "taken 1, deferred 1, dropped 1")

    def test_taken_without_a_citing_task_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 taken",)))
        self.assertRed(self.gate(p), "C6 cycles/C-2.md: C-1#1 taken, but no '## Tasks' "
                                     "item cites it")

    def test_double_disposition_is_red(self):
        p = self.project(scrum=True)
        write(p, "backlog.md", self.BACKLOG + "- a (C-1#1) · usage-data\n")
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        write(p, "cycles/C-2.md", cyc(2, intake=("C-1#1 dropped — duplicate",)))
        self.assertRed(self.gate(p), "C6 cycles/C-1.md: C-1#1 has 2 dispositions")

    def test_intake_citing_a_missing_or_foreign_token_is_red(self):
        p = self.project()
        write(p, "cycles/C-1.md", closed_cyc(1, nxt=("a",)))
        write(p, "cycles/C-2.md", closed_cyc(2, nxt=("b",), intake=("C-1#1 dropped — x",)))
        write(p, "cycles/C-3.md", cyc(3, intake=("C-2#1 dropped — y", "C-2#4 dropped — z",
                                                 "C-1#1 dropped — w")))
        r = self.gate(p)
        self.assertRed(r, "C6 cycles/C-3.md: intake cites C-2#4, which does not exist")
        out = cycle.check_dispositions(
            [cycle.parse(f"cycles/C-{n}.md", (p / f"cycles/C-{n}.md").read_bytes())
             for n in (1, 2, 3)], False)
        self.assertTrue(any("intake cites C-1#1, which is not an item of the immediately "
                            "previous cycle" in b for b in out[-1].breaches))

    def test_token_boundary(self):
        self.assertTrue(cycle.cites("see C-3#1.", "C-3#1"))
        self.assertFalse(cycle.cites("see C-3#12", "C-3#1"))
        self.assertFalse(cycle.cites("see C-13#1", "C-3#1"))


# ---------------------------------------------------------------------------
# R10 — merges and fail-closed
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

    def test_non_table_cycle_in_parent_config_is_red(self):
        p = self.project(cycle=False)
        good = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", "cycle = 1\n" + good)
        root = commit_all(p, "init")
        write(p, "fde.config.toml", good + "\n[cycle]\nenabled = true\n")
        sha = commit_all(p, "fix it")
        self.assertRed(self.gate(p, root), f"C1 {sha[:7]}: parent config [cycle] is not a table")

    def test_git_failure_is_red_through_run_gate(self):
        p = self.project()
        write(p, "cycles/C-1.md", cyc(1))
        commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code")
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, True)
        real = shutil.which("git")
        shim = bindir / "git"
        shim.write_text("#!/bin/sh\ncase \" $* \" in\n  *' ls-tree '*)\n"
                        "    echo 'fake git: simulated ls-tree failure' >&2\n    exit 128\n"
                        "    ;;\nesac\n" f"exec \"{real}\" \"$@\"\n")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
        r = self.gate(p, env=env)
        self.assertRed(r, "CYCLE could not run: a git operation failed", "ls-tree")
        self.assertNotIn("Traceback", r.stderr)


# ---------------------------------------------------------------------------
# R9 — silence and compatibility
# ---------------------------------------------------------------------------
class TestR9Silence(Fixture):
    def test_pre_opt_in_history_is_not_examined(self):
        p = self.project(cycle=False)
        root = commit_all(p, "init")
        write(p, "src/a.py", BIG)
        commit_all(p, "code, no cycle, mode off")
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg + "\n[cycle]\nenabled = true\n")
        commit_all(p, "enable")
        self.assertGreen(self.gate(p, root), "0 behavior commit(s) examined")

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
        r = self.gate(p)
        self.assertGreen(r)
        rows = [l for l in r.stdout.splitlines() if "CYCLE" in l]
        self.assertEqual(len(rows), 1, r.stdout)
        self.assertIn("cycle mode off — declared-scope gate not in force", rows[0])

    def test_enabled_must_be_strictly_true(self):
        p = self.project(cycle=False)
        cfg = (p / "fde.config.toml").read_text(encoding="utf-8")
        write(p, "fde.config.toml", cfg + '\n[cycle]\nenabled = "true"\n')
        commit_all(p, "init")
        self.assertIn("not in force", self.gate(p).stdout)

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
        self.assertEqual(cycle.check_form(c, [], {}), [])


# ---------------------------------------------------------------------------
# validate() rule 6c
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
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
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

    def test_spec_size_reads_the_triage_line_only(self):
        self.assertEqual(graph.spec_size("# x **L**\nTriage: score 4 → **M**\n"), "M")
        self.assertIsNone(graph.spec_size("Triage: surfaces 2\n→ **M**\n"))
        self.assertIsNone(graph.spec_size("no triage here? **S**"[:0]))


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
            self.assertIn("## Cycle scope — when `[cycle]` is enabled", text)
            self.assertLess(text.index("## Scrum mode"), text.index("## Cycle scope"))
            voice = " ".join(text.split("## Voice", 1)[1].split("\n## ", 1)[0].split())
            self.assertIn("next-cycle list is domain content", voice)
            self.assertIn("one-status-line rule does not suppress it", voice)
            for bad in ("{{", "DEM-042", "FWD-002"):
                section = text.split("## Cycle scope", 1)[1].split("\n## ", 1)[0]
                self.assertNotIn(bad, section)

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
