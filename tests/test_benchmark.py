"""The benchmark comparison: identical window, total return, and no verdict
from a record too short to carry one."""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.benchmark import (
    MINIMUM_SESSIONS, ForwardRecord, annualised, closes_by_day, equity_by_day,
    forward_record, total_return)
from event_aware_trader.data import Bar

D0 = date(2026, 9, 11)


def days(n, start=D0):
    return [start + timedelta(days=i) for i in range(n)]


class AlignedOnTheSameDays(unittest.TestCase):
    def test_base_is_the_first_day_both_series_have(self):
        account = {D0: 100.0, D0 + timedelta(1): 101.0, D0 + timedelta(2): 102.0}
        bench = {D0 + timedelta(1): 50.0, D0 + timedelta(2): 51.0}   # no D0 bar
        r = forward_record(account, bench, D0)
        self.assertEqual(r.start, D0 + timedelta(1))
        self.assertAlmostEqual(r.account_return, 102.0 / 101.0 - 1.0)
        self.assertAlmostEqual(r.benchmark_return, 0.02)
        self.assertEqual(r.sessions, 2)

    def test_a_day_only_one_side_has_is_dropped_not_paired(self):
        ds = days(4)
        account = {ds[0]: 100.0, ds[1]: 110.0, ds[3]: 120.0}   # no ds[2]
        bench = {ds[0]: 10.0, ds[2]: 12.0, ds[3]: 11.0}        # no ds[1]
        r = forward_record(account, bench, D0)
        self.assertEqual((r.start, r.end, r.sessions), (ds[0], ds[3], 2))
        self.assertAlmostEqual(r.benchmark_return, 0.10)

    def test_days_before_start_are_ignored(self):
        early = D0 - timedelta(days=3)
        account = {early: 50.0, D0: 100.0, D0 + timedelta(1): 105.0}
        bench = {early: 1.0, D0: 10.0, D0 + timedelta(1): 10.5}
        r = forward_record(account, bench, D0)
        self.assertEqual(r.start, D0)
        self.assertAlmostEqual(r.excess, 0.0)

    def test_fewer_than_two_common_days_is_no_record(self):
        self.assertIsNone(forward_record({D0: 1.0}, {D0: 1.0}, D0))
        self.assertIsNone(forward_record({D0: 1.0}, {}, D0))


class NotAFindingUntilLongEnough(unittest.TestCase):
    def _record(self, n):
        ds = days(n)
        return forward_record({d: 100.0 + i for i, d in enumerate(ds)},
                              {d: 10.0 for d in ds}, D0)

    def test_short_records_are_flagged_and_say_so(self):
        r = self._record(5)
        self.assertFalse(r.judgeable)
        self.assertIn("NOT A FINDING", str(r))
        self.assertFalse(r.as_dict()["judgeable"])

    def test_the_floor_is_the_boundary(self):
        self.assertFalse(self._record(MINIMUM_SESSIONS - 1).judgeable)
        self.assertTrue(self._record(MINIMUM_SESSIONS).judgeable)
        self.assertNotIn("NOT A FINDING", str(self._record(MINIMUM_SESSIONS)))


class TheAccountSideIsWhatTheBotRecorded(unittest.TestCase):
    def _audit(self, tmp, rows):
        p = Path(tmp) / "audit.jsonl"
        with p.open("w", encoding="utf-8") as h:
            for at, event, detail in rows:
                h.write(json.dumps({"at": at, "event": event, "detail": detail}) + "\n")
        return p

    def test_last_reading_of_each_day_wins_and_earlier_days_are_excluded(self):
        with TemporaryDirectory() as tmp:
            p = self._audit(tmp, [
                ("2026-09-10T20:00:00+00:00", "cycle", {"broker_equity": 99000.0}),
                ("2026-09-11T14:00:00+00:00", "cycle", {"broker_equity": 100100.0}),
                ("2026-09-11T20:00:00+00:00", "cycle", {"broker_equity": 100233.0}),
                ("2026-09-11T20:05:00+00:00", "hold", {"symbol": "X", "unrealized": 5.0}),
                ("2026-09-14T20:00:00+00:00", "cycle", {"equity": 99913.0}),
            ])
            by = equity_by_day(p, D0)
            self.assertEqual(by, {date(2026, 9, 11): 100233.0,
                                  date(2026, 9, 14): 99913.0})

    def test_broker_equity_is_preferred_over_allocated_equity(self):
        with TemporaryDirectory() as tmp:
            p = self._audit(tmp, [("2026-09-11T20:00:00+00:00", "cycle",
                                   {"broker_equity": 100000.0, "equity": 50000.0})])
            self.assertEqual(equity_by_day(p, D0)[D0], 100000.0)

    def test_missing_log_is_empty_not_an_error(self):
        self.assertEqual(equity_by_day(Path("does/not/exist.jsonl"), D0), {})


class Arithmetic(unittest.TestCase):
    def test_closes_by_day_and_total_return(self):
        bars = [Bar(timestamp=datetime(2026, 9, 11 + i, 20, tzinfo=timezone.utc),
                    open=1, high=1, low=1, close=100.0 + i, volume=1) for i in range(3)]
        by = closes_by_day(bars)
        self.assertEqual(by[date(2026, 9, 13)], 102.0)
        self.assertAlmostEqual(total_return([100.0, 102.0]), 0.02)
        self.assertIsNone(total_return([100.0]))

    def test_annualised(self):
        self.assertAlmostEqual(annualised(0.10, 365), 0.10, places=3)
        self.assertAlmostEqual(annualised(0.21, 730), 0.10, places=2)
        self.assertIsNone(annualised(0.1, 0))
        self.assertIsNone(annualised(-1.0, 100))


if __name__ == "__main__":
    unittest.main()
