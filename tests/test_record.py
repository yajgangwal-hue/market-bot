import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.record import (
    MINIMUM_INFORMATIVE_TRADES,
    RecordReport,
    TradeRecord,
    from_audit_log,
)


def record_of(returns, sessions=252):
    report = RecordReport(sessions_observed=sessions)
    for i, r in enumerate(returns):
        report.trades.append(
            TradeRecord("SPY", "2026-01-%02d" % (i % 28 + 1), "2026-02-01", r * 1000, r)
        )
    return report


class VerdictTests(unittest.TestCase):
    def test_no_trades_is_reported_as_expected_not_broken(self):
        verdict = RecordReport().verdict()
        self.assertEqual(verdict["status"], "NO_TRADES_YET")
        self.assertIn("not a malfunction", verdict["explanation"])

    def test_a_handful_of_trades_proves_nothing(self):
        verdict = record_of([0.05, 0.04, 0.06]).verdict()
        self.assertEqual(verdict["status"], "INSUFFICIENT_EVIDENCE")
        self.assertGreater(verdict["trades_still_needed_for_a_first_read"], 0)

    def test_a_small_winning_streak_still_spans_a_coin_flip(self):
        """Three wins from three is a 100% win rate and means nothing."""
        verdict = record_of([0.02, 0.03, 0.01]).verdict()
        self.assertEqual(verdict["win_rate"], 1.0)
        self.assertTrue(verdict["win_rate_interval_includes_a_coin_flip"])

    def test_a_large_ambiguous_sample_is_called_luck_not_edge(self):
        returns = [0.01 if i % 2 else -0.01 for i in range(MINIMUM_INFORMATIVE_TRADES + 10)]
        verdict = record_of(returns).verdict()
        self.assertEqual(verdict["status"], "NOT_DISTINGUISHABLE_FROM_LUCK")

    def test_a_large_clearly_negative_sample_is_called_negative(self):
        returns = [-0.02 - 0.001 * i for i in range(MINIMUM_INFORMATIVE_TRADES + 10)]
        verdict = record_of(returns).verdict()
        self.assertEqual(verdict["status"], "NEGATIVE_AND_MEASURABLE")


class TimeToEvidenceTests(unittest.TestCase):
    def test_a_rare_rule_reports_a_long_horizon(self):
        """Three trades a year cannot answer the question this decade."""
        verdict = record_of([0.01, -0.01, 0.02], sessions=252).verdict()
        horizon = verdict["time_to_evidence"]
        self.assertLess(horizon["trades_per_year_at_this_rate"], 10)
        self.assertGreater(horizon["years_to_a_first_read"], 2)

    def test_a_frequent_rule_reports_a_short_horizon(self):
        verdict = record_of([0.001] * 250, sessions=252).verdict()
        horizon = verdict["time_to_evidence"]
        self.assertGreater(horizon["trades_per_year_at_this_rate"], 100)
        self.assertEqual(horizon["years_to_a_first_read"], 0.0)

    def test_no_observation_window_reports_a_note_not_a_number(self):
        verdict = record_of([0.01], sessions=0).verdict()
        self.assertIn("note", verdict["time_to_evidence"])


class AuditLogTests(unittest.TestCase):
    def test_a_missing_log_is_an_empty_record(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(from_audit_log(Path(tmp) / "none.jsonl").trades, [])

    def test_entries_and_exits_are_paired(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            rows = [
                {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY", "quantity": 1}},
                {"at": "2026-01-02", "event": "hold", "detail": {"symbol": "SPY"}},
                {"at": "2026-01-05", "event": "exit",
                 "detail": {"symbol": "SPY", "realized_pnl": 5.0, "return_fraction": 0.01}},
                {"at": "2026-01-06", "event": "run_complete", "detail": {}},
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            report = from_audit_log(path)
            self.assertEqual(len(report.trades), 1)
            self.assertEqual(report.trades[0].net_pnl, 5.0)

    def test_an_unclosed_entry_is_not_counted_as_a_trade(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text(json.dumps(
                {"at": "2026-01-01", "event": "entry", "detail": {"symbol": "SPY"}}
            ), encoding="utf-8")
            self.assertEqual(from_audit_log(path).trades, [])

    def test_corrupt_lines_are_skipped_rather_than_crashing(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text("not json\n{broken\n", encoding="utf-8")
            self.assertEqual(from_audit_log(path).trades, [])


if __name__ == "__main__":
    unittest.main()
