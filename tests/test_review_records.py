"""FWD-038 (C-14 A4): review records close — the promotion endings status
reads (B-30), `fixed_in` on a blocker fixed inside its demand (B-31), the
board merge line names the review record (B-39), and I2 reads every review
record under reviews/ (B-50)."""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

from support import make_project, verify

ROOT = Path(__file__).resolve().parent.parent


def _status():
    spec = importlib.util.spec_from_file_location(
        "status_fwd038", ROOT / "runtime" / "status.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ENDINGS = ("met", "declined", "limit", "not met")


class TestPromotionEndings(unittest.TestCase):
    """B-30: the template and the promotion agent name the four endings
    status.py reads, and status.py reads every one but `not met` as
    settled."""

    def test_template_names_the_four_endings(self):
        for rel in ("templates/cycle/promotion.md",
                    ".fde/templates/cycle/promotion.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            line = next(l for l in text.splitlines() if l.startswith("- A1 —"))
            self.assertIn("met | declined | limit | not met", line, rel)

    def test_agent_names_the_four_endings(self):
        for rel in ("agents/fde-promotion.md", ".claude/agents/fde-promotion.md"):
            text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
            for e in ENDINGS:
                self.assertIn(f"`— {e}`", text, f"{rel}: {e}")

    def test_status_reads_the_settled_endings(self):
        st = _status()
        self.assertEqual(set(st.PROMOTION_MARKS), {"met", "declined", "limit"})
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "promotion.md"
            p.write_text("- A1 — x — met\n- A2 — y — declined\n"
                         "- A3 — z — limit\n- A4 — w — not met\n")
            self.assertEqual(st._promotion_marks(p),
                             {"A1": "x", "A2": "-", "A3": "-"})


FIXED = """[meta]
demand_id = "D-1"
kind = "code"
context_policy = "artifact_only"

[[finding]]
id = "F1"
severity = "high"
probe = "p"
evidence = "e"
blocking = true
fixed_in = "abc1234"

[[finding]]
id = "F2"
severity = "high"
probe = "p"
evidence = "e"
blocking = true
"""


class TestFixedIn(unittest.TestCase):
    """B-31: a blocking finding with `fixed_in` is closed."""

    def test_template_documents_fixed_in(self):
        for rel in ("templates/findings.template.toml",
                    ".fde/templates/findings.template.toml"):
            self.assertIn('fixed_in  = "<sha>"',
                          (ROOT / rel).read_text(encoding="utf-8"), rel)

    def test_review_skill_says_it_in_one_sentence(self):
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
            self.assertIn("`fixed_in = \"<sha>\"`", text, rel)
            # reviews/FWD-038 F2: when, and against which budget
            self.assertIn("in a commit of its own (I3), in the cycle "
                          "review's pass and within its budget, never as an "
                          "extra round.", text, rel)

    def test_the_reviewer_role_is_told(self):
        # reviews/FWD-038 F1: the role that writes fixed_in says so
        for rel in ("agents/fde-adversarial.md",
                    ".claude/agents/fde-adversarial.md"):
            text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
            self.assertIn("On each blocking finding fixed inside its demand, "
                          "record the fixing commit as `fixed_in = \"<sha>\"` "
                          "in `reviews/<demand-id>/findings.toml`, in a "
                          "commit of its own. This is part of the cycle "
                          "review's pass, within its budget; it is never an "
                          "extra round.", text, rel)

    def test_status_counts_a_fixed_blocker_as_closed(self):
        st = _status()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "reviews" / "D-1"
            d.mkdir(parents=True)
            (d / "findings.toml").write_text(FIXED)
            summary, rows = st.load_findings(root, "D-1")
            self.assertEqual(summary["findings"], 2)
            self.assertEqual(summary["blocking"], 1)
            by_id = {r["id"]: r for r in rows}
            self.assertFalse(by_id["F1"]["blocking"])
            self.assertEqual(by_id["F1"]["fixed_in"], "abc1234")
            self.assertTrue(by_id["F2"]["blocking"])

    def test_gates_accept_fixed_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            f = p / "reviews" / "D-1" / "findings.toml"
            f.parent.mkdir(parents=True)
            f.write_text(FIXED)
            for gate in ("adversarial-isolation", "finding-discipline"):
                r = verify(p, "--gate", gate)
                self.assertEqual(r.returncode, 0, r.stdout)


class TestMergeNamesReview(unittest.TestCase):
    """B-39: the merge line names the review record; a demand merges only
    with it."""

    def test_board_template_merge_line_names_the_review(self):
        for rel in ("templates/cycle/board.md", ".fde/templates/cycle/board.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertTrue(re.search(
                r"^- YYYY-MM-DD DEM-<n> decided merged <sha>; review "
                r"`reviews/DEM-<n>/findings\.toml`", text, re.M), rel)

    def test_review_skill_merges_only_with_the_record(self):
        for rel in ("skills/fde-review/SKILL.md",
                    ".claude/skills/fde-review/SKILL.md"):
            text = " ".join((ROOT / rel).read_text(encoding="utf-8").split())
            self.assertIn("A demand merges only with its review record "
                          "(`reviews/<id>/findings.toml`)", text, rel)
            self.assertIn("its merge line on `board.md` names it", text, rel)


class TestI2ReadsEveryRecord(unittest.TestCase):
    """B-50: findings-plan.toml, findings-delta.toml — every findings*.toml
    under reviews/ gets the isolation check."""

    def _run(self, name: str, body: str):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_project(tmp)
            ok = p / "reviews" / "D-1" / "findings.toml"
            ok.parent.mkdir(parents=True)
            ok.write_text('[meta]\ncontext_policy = "artifact_only"\n')
            other = p / "reviews" / "C-1" / name
            other.parent.mkdir(parents=True)
            other.write_text(body)
            return verify(p, "--gate", "adversarial-isolation")

    def test_plan_record_without_isolation_fails(self):
        r = self._run("findings-plan.toml", "[meta]\nkind = 'plan'\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("reviews/C-1/findings-plan.toml", r.stdout)

    def test_delta_record_without_isolation_fails(self):
        r = self._run("findings-delta.toml", "[meta]\nround = 2\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("reviews/C-1/findings-delta.toml", r.stdout)

    def test_isolated_records_pass_and_are_counted(self):
        r = self._run("findings-plan.toml",
                      '[meta]\ncontext_policy = "artifact_only"\n')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 report(s)", r.stdout)

    def test_this_repository_records_pass(self):
        r = verify(ROOT, "--gate", "adversarial-isolation")
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
