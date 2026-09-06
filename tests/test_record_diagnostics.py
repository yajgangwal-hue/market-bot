"""The three things the record could not previously say.

Every configuration measured in this project lost to buy-and-hold until the
last one, and the record had no way to show that: `benchmark_return` existed
as a field and nothing ever populated it, so the assessment could only report
"positive". These cover the comparison, the cost accounting that shows whether
an edge is being eaten, and the holding-period check - plus the small-sample
guards, because a diagnostic that reads a pattern into three trades is worse
than not having one.
"""

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.record import (
    MINIMUM_INFORMATIVE_TRADES,
    MINIMUM_PER_GROUP,
    RecordReport,
    TradeRecord,
    buy_and_hold_return,
    from_audit_log,
    window_of,
)


class FakeBar(object):
    """Only what buy_and_hold_return duck-types on."""

    def __init__(self, stamp, close):
        self.timestamp = datetime.fromisoformat(stamp)
        self.close = close


class FrictionTests(unittest.TestCase):
    def test_gross_pnl_adds_the_fee_back(self):
        """`realized_pnl` in the log is net, so gross is the only view of edge.

        Taken from the real XOP exit of 2026-09-02: proceeds 19983.60 minus
        basis 19992.96 is -9.36 gross, recorded as -9.86 after a 0.4959 fee.
        """
        t = TradeRecord("XOP", "2026-09-01", "2026-09-02", -9.86, -0.000493, fees=0.4959)
        self.assertAlmostEqual(t.gross_pnl, -9.3641, places=4)

    def test_friction_reports_the_share_of_gross_edge_costs_take(self):
        report = RecordReport()
        for _ in range(4):
            report.trades.append(
                TradeRecord("SPY", "2026-01-01", "2026-01-02", 7.5, 0.01, fees=2.5))
        friction = report.friction()
        self.assertEqual(friction["gross_pnl"], 40.0)      # 4 x (7.5 + 2.5)
        self.assertEqual(friction["fees_paid"], 10.0)
        self.assertEqual(friction["net_pnl"], 30.0)
        self.assertEqual(friction["fees_as_share_of_gross_edge"], 0.25)

    def test_costs_exceeding_the_gross_edge_are_called_out(self):
        """The intraday rule's actual shape: +$6.19 edge, -$14.99 friction."""
        report = RecordReport()
        for _ in range(4):
            report.trades.append(
                TradeRecord("SPY", "2026-01-01", "2026-01-02", -6.0, -0.01, fees=10.0))
        self.assertIn("Costs exceed the gross edge", report.friction()["reading"])

    def test_a_negative_gross_edge_is_not_blamed_on_costs(self):
        report = RecordReport()
        for _ in range(4):
            report.trades.append(
                TradeRecord("SPY", "2026-01-01", "2026-01-02", -12.0, -0.02, fees=1.0))
        self.assertIn("the rule is", report.friction()["reading"])

    def test_missing_fee_data_is_declared_rather_than_reported_as_zero(self):
        report = RecordReport()
        report.trades.append(TradeRecord("SPY", "2026-01-01", "2026-01-02", 5.0, 0.01))
        report.trades.append(
            TradeRecord("QQQ", "2026-01-01", "2026-01-02", 5.0, 0.01, fees=0.5))
        self.assertIn("carry no fee data", report.friction()["warning"])
        self.assertEqual(report.friction()["trades_with_fee_data"], 1)

    def test_an_empty_record_has_no_friction_to_report(self):
        self.assertIsNone(RecordReport().friction())

    def test_fees_are_read_from_the_audit_log(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            rows = [
                {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY"}},
                {"at": "2026-01-05", "event": "exit", "detail": {
                    "symbol": "SPY", "realized_pnl": -9.86,
                    "return_fraction": -0.0005, "fees": 0.4959}},
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            self.assertAlmostEqual(from_audit_log(path).trades[0].fees, 0.4959)


class DispositionTests(unittest.TestCase):
    def _report(self, winner_days, loser_days):
        report = RecordReport()
        for days in winner_days:
            report.trades.append(TradeRecord(
                "SPY", "2026-01-01T00:00:00",
                "2026-01-{0:02d}T00:00:00".format(1 + days), 10.0, 0.01))
        for days in loser_days:
            report.trades.append(TradeRecord(
                "QQQ", "2026-01-01T00:00:00",
                "2026-01-{0:02d}T00:00:00".format(1 + days), -10.0, -0.01))
        return report

    def test_a_tiny_sample_refuses_to_call_a_pattern(self):
        """Live on three trades this claimed an effect from one winner."""
        verdict = self._report([1], [3, 4]).disposition()
        self.assertIn("Needs {0} winners".format(MINIMUM_PER_GROUP), verdict["note"])
        self.assertNotIn("disposition_effect_present", verdict)

    def test_losers_held_longer_is_detected_once_the_sample_supports_it(self):
        verdict = self._report([1] * 6, [8] * 6).disposition()
        self.assertTrue(verdict["disposition_effect_present"])
        self.assertEqual(verdict["mean_holding_days_winners"], 1.0)
        self.assertEqual(verdict["mean_holding_days_losers"], 8.0)
        self.assertEqual(verdict["losers_held_longer_by_days"], 7.0)

    def test_symmetric_holding_is_not_flagged(self):
        verdict = self._report([4] * 6, [4] * 6).disposition()
        self.assertFalse(verdict["disposition_effect_present"])
        self.assertIn("not being held longer", verdict["reading"])

    def test_holding_days_tolerates_every_timestamp_shape_in_the_log(self):
        """The log carries "Z", "+00:00" and bare dates, all in one file."""
        for opened, closed in [
            ("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"),
            ("2026-01-01T00:00:00+00:00", "2026-01-03T00:00:00+00:00"),
            ("2026-01-01", "2026-01-03"),
        ]:
            trade = TradeRecord("SPY", opened, closed, 1.0, 0.01)
            self.assertEqual(
                trade.holding_days, 2.0, "{0} -> {1}".format(opened, closed))

    def test_an_unparseable_timestamp_yields_none_rather_than_raising(self):
        self.assertIsNone(
            TradeRecord("SPY", "junk", "also junk", 1.0, 0.01).holding_days)


class BenchmarkTests(unittest.TestCase):
    BARS = [
        FakeBar("2026-01-01T16:00:00", 100.0),
        FakeBar("2026-01-02T16:00:00", 105.0),
        FakeBar("2026-01-03T16:00:00", 110.0),
        FakeBar("2026-01-04T16:00:00", 90.0),
    ]

    def test_return_is_measured_over_the_records_own_window(self):
        got = buy_and_hold_return(self.BARS, "2026-01-01", "2026-01-03")
        self.assertAlmostEqual(got, 0.10)     # 100 -> 110, ignoring the later drop

    def test_an_intraday_exit_still_includes_that_days_close(self):
        """A 14:04 exit used to exclude the 16:00 bar, leaving one price."""
        got = buy_and_hold_return(
            self.BARS, "2026-01-01T13:30:00", "2026-01-02T14:04:45")
        self.assertAlmostEqual(got, 0.05)

    def test_an_uncovered_window_returns_none_rather_than_a_guess(self):
        self.assertIsNone(buy_and_hold_return(self.BARS, "2027-05-01", "2027-05-09"))

    def test_a_reversed_window_is_refused(self):
        self.assertIsNone(buy_and_hold_return(self.BARS, "2026-01-04", "2026-01-01"))

    def test_window_of_spans_first_entry_to_last_exit(self):
        report = RecordReport()
        report.trades.append(TradeRecord("SPY", "2026-03-04", "2026-03-06", 1.0, 0.01))
        report.trades.append(TradeRecord("QQQ", "2026-01-02", "2026-05-09", 1.0, 0.01))
        self.assertEqual(window_of(report), ("2026-01-02", "2026-05-09"))

    def test_no_trades_means_no_window(self):
        self.assertIsNone(window_of(RecordReport()))


class BuyAndHoldVerdictTests(unittest.TestCase):
    """The comparison the module used to recommend and not perform."""

    def _winning_record(self, benchmark):
        report = RecordReport(starting_equity=1000.0, ending_equity=1100.0,
                              benchmark_return=benchmark, sessions_observed=252)
        for i in range(MINIMUM_INFORMATIVE_TRADES + 10):
            report.trades.append(TradeRecord(
                "SPY", "2026-01-{0:02d}".format(i % 28 + 1), "2026-02-01",
                25.0, 0.025))
        return report

    def test_a_real_edge_that_trails_the_index_is_not_called_a_success(self):
        verdict = self._winning_record(0.40).verdict()
        self.assertEqual(verdict["status"], "POSITIVE_BUT_BEATEN_BY_BUY_AND_HOLD")
        self.assertFalse(verdict["vs_buy_and_hold"]["beat_buy_and_hold"])
        self.assertIn("worse outcome than one trade", verdict["explanation"])

    def test_beating_the_index_reports_the_excess(self):
        verdict = self._winning_record(0.02).verdict()
        self.assertEqual(verdict["status"], "POSITIVE_AND_MEASURABLE")
        self.assertAlmostEqual(verdict["vs_buy_and_hold"]["excess_return_pct"], 8.0)

    def test_without_a_benchmark_the_verdict_is_unchanged(self):
        verdict = self._winning_record(None).verdict()
        self.assertEqual(verdict["status"], "POSITIVE_AND_MEASURABLE")
        self.assertIsNone(verdict["vs_buy_and_hold"])

    def test_a_losing_record_is_still_called_negative_not_merely_beaten(self):
        report = RecordReport(starting_equity=1000.0, ending_equity=800.0,
                              benchmark_return=0.10, sessions_observed=252)
        for i in range(MINIMUM_INFORMATIVE_TRADES + 10):
            report.trades.append(TradeRecord(
                "SPY", "2026-01-{0:02d}".format(i % 28 + 1), "2026-02-01",
                -5.0, -0.02 - 0.001 * i))
        self.assertEqual(report.verdict()["status"], "NEGATIVE_AND_MEASURABLE")


if __name__ == "__main__":
    unittest.main()
