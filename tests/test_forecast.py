"""When a running cycle will likely end, from the project's own history
(runtime/forecast.py, owner 2026-10-01: "I have no idea how long a cycle
will take")."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "runtime"))

import forecast  # noqa: E402

H = 3600
NOW = 1_800_000_000


class Cycle:
    def __init__(self, cid):
        self.id, self.state, self.layout = cid, "running", "directory"


def demand(did, merged=False, begun=False, started=None, last=None, waits=()):
    return {"id": did, "merged": merged, "begun": begun, "started": started,
            "last": last, "waits": list(waits)}


def run(progress: dict, demands_h, closings_h):
    hist = {"demands": [x * H for x in demands_h], "closings": [x * H for x in closings_h]}
    cycles = [Cycle(c) for c in progress]
    with mock.patch.object(forecast, "history", return_value=hist), \
         mock.patch.object(forecast.status, "load_cycles", return_value=cycles), \
         mock.patch.object(forecast.status, "cycle_progress",
                           side_effect=lambda root, c: progress[c.id]):
        return forecast.forecast(Path("."), now=NOW)


class Forecast(unittest.TestCase):
    def test_percentiles(self):
        self.assertEqual(forecast._pct([1, 2, 3, 4, 5], 0.5), 3)
        self.assertAlmostEqual(forecast._pct([1, 2, 3, 4, 5], 0.85), 4.4)

    def test_not_started_demands_in_parallel_then_the_closing(self):
        p = {"C-1": {"title": "x", "waits": [],
                     "demands": [demand("A"), demand("B")]}}
        f = run(p, [2, 2, 2], [1, 1, 1])
        [r] = f["cycles"]
        self.assertEqual(r["p50"], NOW + 2 * H + 1 * H)   # parallel 2h, then 1h closing
        self.assertEqual(r["remaining"], 2)

    def test_a_dependent_demand_waits_and_a_begun_one_counts_what_is_left(self):
        p = {"C-1": {"title": "x", "waits": [],
                     "demands": [demand("A", begun=True, started=NOW - 1 * H),
                                 demand("B", waits=["A"])]}}
        f = run(p, [2, 2, 2], [1, 1, 1])
        self.assertEqual(f["cycles"][0]["p50"], NOW + 1 * H + 2 * H + 1 * H)

    def test_a_cycle_waiting_for_another_starts_when_that_build_ends(self):
        p = {"C-1": {"title": "x", "waits": [], "demands": [demand("A")]},
             "C-2": {"title": "y", "waits": ["C-1"], "demands": [demand("B")]}}
        f = run(p, [2, 2, 2], [1, 1, 1])
        by = {r["cycle"]: r for r in f["cycles"]}
        self.assertEqual(by["C-2"]["p50"], NOW + 2 * H + 2 * H + 1 * H)

    def test_the_pessimistic_answer_is_never_earlier(self):
        p = {"C-1": {"title": "x", "waits": [], "demands": [demand("A")]}}
        f = run(p, [1, 2, 8], [1, 2, 6])
        r = f["cycles"][0]
        self.assertGreater(r["p85"], r["p50"])

    def test_the_worst_case_is_of_the_total_never_a_sum_of_worst_pieces(self):
        # a first version summed each piece's p85 and read a day for a
        # half-day's work (owner, 2026-10-01: "C-8 ready tomorrow?")
        p = {"C-1": {"title": "x", "waits": [],
                     "demands": [demand("A"), demand("B", waits=["A"]), demand("C", waits=["B"])]}}
        hist = [1] * 17 + [10] * 3            # p85 of one demand is 10h
        f = run(p, hist, [1, 1, 1])
        self.assertLess(f["cycles"][0]["p85"] - NOW, (3 * 10 + 1) * H)

    def test_a_demand_in_review_draws_from_review_to_merge_times(self):
        late = {"at": NOW - 1 * H, "verb": "decided", "text": "triage of the review round 1"}
        d = demand("A", begun=True, started=NOW - 9 * H)
        d["events"] = [late]
        p = {"C-1": {"title": "x", "waits": [], "demands": [d]}}
        hist = {"demands": [10 * H] * 5, "tails": [2 * H] * 5, "closings": [0] * 0}
        with mock.patch.object(forecast, "history", return_value=hist), \
             mock.patch.object(forecast.status, "load_cycles", return_value=[Cycle("C-1")]), \
             mock.patch.object(forecast.status, "cycle_progress", side_effect=lambda r, c: p[c.id]):
            f = forecast.forecast(Path("."), now=NOW)
        self.assertEqual(f["cycles"][0]["p50"], NOW + 1 * H)  # 2h review→merge, 1h in

    def test_too_little_history_says_so(self):
        p = {"C-1": {"title": "x", "waits": [], "demands": [demand("A")]}}
        f = run(p, [2, 2], [1, 1, 1])
        self.assertFalse(f["enough"])
        self.assertIn("not enough history", forecast.render(f)[0])

    def test_few_closings_stop_at_the_last_merge_and_say_so(self):
        p = {"C-1": {"title": "x", "waits": [], "demands": [demand("A")]}}
        f = run(p, [2, 2, 2], [1])
        self.assertEqual(f["cycles"][0]["p50"], NOW + 2 * H)
        self.assertIn("the closing comes on top", forecast.render(f)[0])


if __name__ == "__main__":
    unittest.main()
