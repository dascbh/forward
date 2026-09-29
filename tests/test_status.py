"""FWD-024: the cycle and backlog view — a read-only report, never a gate
(ADR-0018). Every case runs the real script as a subprocess against a
temporary tree, the way the owner runs it."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "runtime" / "status.py"

OPEN = """cycle: C-2
objective: erase a KB source
opened: 2026-09-28
demands: DEM-035 (M), DEM-036 (M)

## Tasks
- DEM-035 erase
- DEM-036 reindex

## Done when
- [x] DEM-035 — in production
- [ ] DEM-036 — reindex guaranteed
- [-] something not met

closed: this word in the body does not close the cycle
"""

CLOSED = """# C-1 — first round

objective: security debts
closed: 2026-09-28
opened: 2026-09-28

## Done when
- [x] a
- [x] b
"""

BACKLOG = """---
goal: g
date: 2026-08-09
---

# Product backlog

| # | item | hypothesis | evidence | size |
|---|---|---|---|---|
| 1 | Role isolation | shared role crosses tenants | usage-data | M |

## Captured from cycle C-2

- FC-3 listing failure writes existed=False

## Other

- (C-10) unrelated idea from a later cycle
- (C-2) timeout without a total bound
"""


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True)


class StatusCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "cycles").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text, raw=False):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if raw:
            p.write_bytes(text)
        else:
            p.write_text(text)


class TestView(StatusCase):
    """R1: open cycle with progress, its backlog lines, closed cycles one line
    each, the backlog grouped by section."""

    def setUp(self):
        super().setUp()
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)

    def test_open_cycle_with_progress(self):
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OPEN CYCLE C-2", r.stdout)
        self.assertIn("erase a KB source", r.stdout)
        self.assertIn("1/3 met, 1 declined, 1 pending", r.stdout)
        self.assertIn("[ ] DEM-036 — reindex guaranteed", r.stdout)

    def test_body_mention_of_closed_does_not_close(self):
        # FM-1: only header lines decide open/closed
        r = run(self.root)
        self.assertIn("OPEN CYCLE C-2", r.stdout)
        self.assertNotIn("C-2  closed", r.stdout)

    def test_closed_cycle_is_one_line(self):
        r = run(self.root)
        self.assertIn("C-1  closed 2026-09-28  2/2 met  security debts", r.stdout)

    def test_backlog_lines_of_the_open_cycle_by_token_or_section(self):
        # FM-3: C-10 must not be claimed by C-2
        part = run(self.root).stdout.split("BACKLOG")[0]
        self.assertIn("FC-3 listing failure", part)
        self.assertIn("(C-2) timeout", part)
        self.assertNotIn("C-10", part)

    def test_backlog_grouped_by_section(self):
        out = run(self.root).stdout
        backlog = out[out.index("BACKLOG"):]
        self.assertIn("#1 Role isolation", backlog)
        self.assertNotIn("# item", backlog)
        self.assertLess(backlog.index("Captured from cycle C-2"),
                        backlog.index("Other"))


class TestWarnings(StatusCase):
    """R2: warnings first; exit 0 on any content (FM-5)."""

    def test_two_open_cycles_are_reported(self):
        # FM-2
        self.write("cycles/C-1.md", OPEN.replace("C-2", "C-1"))
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)
        r = run(self.root)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("WARNING"), r.stdout)
        self.assertIn("2 cycles open: C-1, C-2", r.stdout)

    def test_missing_objective_and_backlog_warn(self):
        self.write("cycles/C-1.md", "opened: 2026-09-28\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 0)
        self.assertIn("C-1 has no objective", r.stdout)
        self.assertIn("no backlog.md", r.stdout)

    def test_open_cycle_with_every_item_met_is_ready_to_close(self):
        self.write("cycles/C-1.md", "objective: o\n\n## Done when\n- [x] a\n")
        self.assertIn("C-1 has no pending done item but no closed: line",
                      run(self.root).stdout)


class TestSelectors(StatusCase):
    """R3: --cycle, --backlog, --cycles."""

    def setUp(self):
        super().setUp()
        self.write("cycles/C-1.md", CLOSED)
        self.write("cycles/C-2.md", OPEN)
        self.write("backlog.md", BACKLOG)

    def test_cycle_in_full(self):
        out = run(self.root, "--cycle", "C-1").stdout
        self.assertIn("CYCLE C-1 (closed 2026-09-28)", out)
        self.assertIn("[x] a", out)
        self.assertNotIn("BACKLOG", out)

    def test_unknown_cycle_is_a_bad_argument(self):
        self.assertEqual(run(self.root, "--cycle", "C-9").returncode, 2)

    def test_backlog_only_and_cycles_only(self):
        b = run(self.root, "--backlog").stdout
        self.assertIn("BACKLOG", b)
        self.assertNotIn("OPEN CYCLE", b)
        c = run(self.root, "--cycles").stdout
        self.assertIn("OPEN CYCLE C-2", c)
        self.assertNotIn("#1 Role isolation", c)


class TestTolerance(StatusCase):
    """R4 / FM-4: malformed input never tracebacks."""

    def test_no_cycles_directory(self):
        (self.root / "cycles").rmdir()
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no open cycle", r.stdout)

    def test_empty_non_utf8_and_sectionless_files(self):
        self.write("cycles/C-1.md", "")
        self.write("cycles/C-2.md", b"objective: caf\xe9\n## DONE WHEN\n- [X] ok\n",
                   raw=True)
        self.write("backlog.md", b"\xff\xfe junk\n| broken |\n", raw=True)
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("1/1 met", r.stdout)

    def test_not_called_by_the_gate(self):
        gate = (ROOT / "runtime" / "verify.py").read_text()
        self.assertNotIn("import status", gate)
        self.assertNotIn("status.py", gate)


class TestRoundOneFindings(StatusCase):
    """reviews/FWD-024 round 1: each finding's probe, red before the fix."""

    def test_f1_closed_line_below_the_header_is_named(self):
        self.write("cycles/C-1.md", "objective: o\n\n## Done when\n- [x] a\n\nclosed: 2026-09-28\n")
        out = run(self.root).stdout
        self.assertIn("C-1 has a closed: line below its header", out)
        self.assertNotIn("no pending done item but no closed:", out)

    def test_f2_cycle_named_in_a_later_table_cell(self):
        self.write("cycles/C-3.md", "objective: o\n")
        self.write("backlog.md", "| # | item | evidence |\n|---|---|---|\n"
                   "| 4 | Idea | usage-data (C-3 review) |\n")
        part = run(self.root).stdout.split("BACKLOG")[0]
        self.assertIn("#4 Idea", part)

    def test_f3_numbered_spaced_and_unknown_marks_are_counted(self):
        self.write("cycles/C-1.md", "objective: o\n## Done when\n1. [x] a\n- [ x ] b\n"
                   "- [~] c\n- [] d\n")
        out = run(self.root).stdout
        self.assertIn("2/4 met, 2 pending", out)
        self.assertIn("[~] c", out)
        self.assertNotIn("no pending done item", out)

    def test_f4_narrow_stdout_encoding_never_tracebacks(self):
        self.write("cycles/C-1.md", "objective: seta → e caf\u00e9\n")
        r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)],
                           capture_output=True, text=True, encoding="ascii",
                           errors="replace", env={"PYTHONIOENCODING": "ascii",
                                                  "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_f5_misnamed_and_duplicate_cycle_files_warn(self):
        self.write("cycles/C-3-status.md", "objective: o\n")
        self.write("cycles/C-01.md", "objective: o\n")
        self.write("cycles/C-1.md", "objective: o\n")
        self.write("cycles/.DS_Store", "x")
        out = run(self.root).stdout
        self.assertIn("cycles/C-3-status.md is not named C-<n>.md", out)
        self.assertIn("2 files in cycles/ read as C-1", out)
        self.assertNotIn(".DS_Store", out)

    def test_notes_bad_root_fences_and_legacy_next_cycle(self):
        self.assertEqual(run(self.root / "nope").returncode, 2)
        self.write("cycles/C-1.md", "objective: o\n## Done when\n- [x] a\n```\n- [ ] fake\n```\n"
                   "## Next cycle\n- old idea\n")
        out = run(self.root).stdout
        self.assertIn("1/1 met", out)
        self.assertIn("C-1 keeps a ## Next cycle list (1 lines)", out)
        self.assertIn("old idea", run(self.root, "--cycle", "C-1").stdout)


if __name__ == "__main__":
    unittest.main()
