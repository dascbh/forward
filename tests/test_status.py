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
        self.assertIn("1/3 done", r.stdout)
        self.assertIn("[ ] DEM-036 — reindex guaranteed", r.stdout)

    def test_body_mention_of_closed_does_not_close(self):
        # FM-1: only header lines decide open/closed
        r = run(self.root)
        self.assertIn("OPEN CYCLE C-2", r.stdout)
        self.assertNotIn("C-2  closed", r.stdout)

    def test_closed_cycle_is_one_line(self):
        r = run(self.root)
        self.assertIn("C-1  closed 2026-09-28  2/2  security debts", r.stdout)

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
        self.assertIn("C-1 has every done item met but no closed:",
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
        self.assertIn("1/1 done", r.stdout)

    def test_not_called_by_the_gate(self):
        gate = (ROOT / "runtime" / "verify.py").read_text()
        self.assertNotIn("import status", gate)
        self.assertNotIn("status.py", gate)


if __name__ == "__main__":
    unittest.main()
