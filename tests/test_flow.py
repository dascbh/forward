"""Cycle time and lead time from git (runtime/flow.py, owner request
2026-09-30): nothing to fill in, minutes from the commits."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import flow  # noqa: E402
import status  # noqa: E402

T0 = 1_790_000_000  # a fixed epoch; hours below are offsets from it


def commit(p: Path, hours: float, msg: str):
    env = {**os.environ, "GIT_COMMITTER_DATE": f"@{int(T0 + hours * 3600)} +0000",
           "GIT_AUTHOR_DATE": f"@{int(T0 + hours * 3600)} +0000"}
    subprocess.run(["git", "add", "-A"], cwd=p, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=p, check=True,
                   capture_output=True, env=env)


def plan(state: str, items: str = "- B-1 export the report", extra: str = "") -> str:
    return (f"cycle: C-1\nstate: {state}\ndate: 2026-09-30\nsize: S\n{extra}"
            f"objective: export\n\n## Items\n\n{items}\n\n## Acceptance criteria\n\n- **AC-1** ok\n")


class Flow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = p = Path(self.tmp.name)
        for args in (["init", "-q"], ["config", "user.email", "f@t"], ["config", "user.name", "f"]):
            subprocess.run(["git", *args], cwd=p, check=True, capture_output=True)
        (p / "cycles" / "C-1").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel: str, text: str):
        (self.p / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.p / rel).write_text(text)

    def closed_cycle(self):
        self.write("backlog.md", "# Backlog\n\n- B-1 export the report\n")
        commit(self.p, 0, "request")
        self.write("cycles/C-1/plan.md", plan("draft"))
        commit(self.p, 2, "draft")
        self.write("cycles/C-1/plan.md", plan("planned"))
        commit(self.p, 3, "planned")
        self.write("cycles/C-1/plan.md", plan("running", extra="signed-off: 2026-09-30 owner\n"))
        commit(self.p, 5, "signed")
        self.write("cycles/C-1/plan.md", plan("running", extra="signed-off: x\nclosed: 2026-09-30\n"))
        commit(self.p, 9, "closed")

    def test_a_closed_cycle_has_its_wait_cycle_time_and_lead_time(self):
        self.closed_cycle()
        [r] = flow.measure(self.p)["cycles"]
        self.assertEqual(r["state"], "closed")
        self.assertEqual(r["wait_signoff_h"], 3.0)   # first plan commit → running
        self.assertEqual(r["cycle_time_h"], 4.0)     # running → closed
        self.assertEqual(r["lead_time_h"], 9.0)      # request → closed

    def test_items_in_running_prose_count_as_the_request(self):
        self.write("backlog.md", "# Backlog\n\n- B-7 older\n- B-8 newer\n")
        commit(self.p, 0, "request")
        self.write("cycles/C-1/plan.md", plan("running", items="B-8 (part) · B-7 trail."))
        commit(self.p, 1, "plan")
        self.write("cycles/C-1/plan.md", plan("closed", items="B-8 (part) · B-7 trail."))
        commit(self.p, 2, "close")
        [r] = flow.measure(self.p)["cycles"]
        self.assertEqual(r["items"], 2)
        self.assertEqual(r["lead_time_h"], 2.0)

    def test_no_item_starts_the_lead_at_the_first_plan_commit(self):
        self.write("cycles/C-1/plan.md", plan("running", items="none"))
        commit(self.p, 1, "plan")
        self.write("cycles/C-1/plan.md", plan("closed", items="none"))
        commit(self.p, 4, "close")
        [r] = flow.measure(self.p)["cycles"]
        self.assertEqual(r["lead_time_h"], 3.0)

    def test_abandoned_and_running_have_no_cycle_or_lead_time(self):
        self.closed_cycle()
        self.write("cycles/C-2/plan.md", plan("running").replace("C-1", "C-2"))
        commit(self.p, 10, "second")
        self.write("cycles/C-3/plan.md", plan("abandoned").replace("C-1", "C-3"))
        commit(self.p, 11, "third")
        rows = {r["cycle"]: r for r in flow.measure(self.p)["cycles"]}
        self.assertIsNone(rows["C-2"]["cycle_time_h"])
        self.assertIsNotNone(rows["C-2"]["running_for_h"])
        self.assertIsNone(rows["C-3"]["lead_time_h"])

    def test_cycles_joined_by_depends_are_one_objective(self):
        self.closed_cycle()
        self.write("cycles/C-2/plan.md",
                   plan("running", extra="depends: C-1\n").replace("C-1\nstate", "C-2\nstate"))
        commit(self.p, 12, "slice")
        d = flow.measure(self.p)
        [o] = d["objectives"]
        self.assertEqual(o["cycles"], ["C-1", "C-2"])
        self.assertEqual(o["closed"], 1)
        self.assertIsNone(o["lead_time_h"])
        self.write("cycles/C-2/plan.md",
                   plan("closed", extra="depends: C-1\n").replace("C-1\nstate", "C-2\nstate"))
        commit(self.p, 20, "slice closed")
        [o] = flow.measure(self.p)["objectives"]
        self.assertEqual(o["lead_time_h"], 20.0)  # first request → last cycle closed

    def test_state_reads_like_the_status_view(self):
        self.assertEqual(flow.state_of("state: planned (signed off later)\n"), "planned")
        self.assertEqual(flow.state_of("state: running\nclosed: 2026-09-30\n"), "closed")
        self.assertEqual(flow.state_of("state: running\nclosed:\n"), "running")
        self.assertEqual(flow.state_of("x: y\n\n## Items\nstate: closed\n"), "")

    def test_status_flow_prints_and_emits_json(self):
        self.closed_cycle()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(status.main(["--root", str(self.p), "--flow"]), 0)
        self.assertIn("cycle time 4.0h", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            status.main(["--root", str(self.p), "--flow", "--format", "json"])
        self.assertEqual(json.loads(out.getvalue())["median"]["lead_time_h"], 9.0)


if __name__ == "__main__":
    unittest.main()
