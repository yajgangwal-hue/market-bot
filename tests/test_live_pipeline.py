import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.daily_report import build_day_report, render
from event_aware_trader.live_model import (
    LIVE_FEATURES,
    append_example,
    load_training,
    train_live_model,
)


def audit_rows(day):
    return [
        {"at": day + "T13:30:00+00:00", "event": "run_complete",
         "detail": {"equity": 100000.0, "entries": 1, "exits": 0, "held": 0}},
        {"at": day + "T13:35:00+00:00", "event": "entry",
         "detail": {"symbol": "AAPL", "score": 78.0, "live_score": 0.61}},
        {"at": day + "T19:45:00+00:00", "event": "exit",
         "detail": {"symbol": "AAPL", "realized_pnl": 412.5,
                    "return_fraction": 0.0044, "r_multiple": 1.3, "armed": True}},
        {"at": day + "T19:50:00+00:00", "event": "run_complete",
         "detail": {"equity": 100412.5, "entries": 0, "exits": 1, "held": 0}},
    ]


class DailyReportTests(unittest.TestCase):
    def _log(self, tmp, rows):
        path = Path(tmp) / "audit.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return path

    def test_a_profitable_session_is_reported_as_such(self):
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            payload = render(self._log(tmp, audit_rows(day)))
            self.assertTrue(payload["profitable_today"])
            self.assertEqual(payload["closed_profitable"], 1)
            self.assertAlmostEqual(payload["realized_today"], 412.5)
            self.assertAlmostEqual(payload["day_pnl"], 412.5)

    def test_other_days_are_excluded(self):
        with TemporaryDirectory() as tmp:
            today = date.today().isoformat()
            other = (date.today() - timedelta(days=3)).isoformat()
            report = build_day_report(self._log(tmp, audit_rows(today) + audit_rows(other)), date.today())
            self.assertEqual(len(report.exits), 1)

    def test_a_quiet_session_reports_nothing_rather_than_failing(self):
        with TemporaryDirectory() as tmp:
            payload = render(Path(tmp) / "missing.jsonl")
            self.assertEqual(payload["closed_today"], 0)
            self.assertFalse(payload["profitable_today"])

    def test_a_good_day_still_carries_the_cumulative_verdict(self):
        """A profitable session must not read as a working system."""
        with TemporaryDirectory() as tmp:
            payload = render(self._log(tmp, audit_rows(date.today().isoformat())))
            self.assertEqual(payload["since_inception"]["status"], "INSUFFICIENT_EVIDENCE")
            self.assertIn("not evidence", payload["reminder"].lower())


class ContinuousLearningTests(unittest.TestCase):
    def test_a_closed_trade_becomes_a_training_row(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            append_example({k: 0.5 for k in LIVE_FEATURES}, 1.4, "AAPL", path)
            rows = load_training(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], 1)
            self.assertEqual(rows[0]["symbol"], "AAPL")

    def test_a_losing_trade_is_labelled_zero(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            append_example({k: 0.5 for k in LIVE_FEATURES}, -0.8, "GLD", path)
            self.assertEqual(load_training(path)[0]["label"], 0)

    def test_examples_accumulate_across_calls(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            for i in range(5):
                append_example({k: float(i) for k in LIVE_FEATURES}, float(i) - 2, "S%d" % i, path)
            self.assertEqual(len(load_training(path)), 5)

    def test_too_few_examples_refuses_to_train(self):
        with TemporaryDirectory() as tmp:
            rows = [{"at": "2026-01-%02d" % (i + 1), "f": {k: 0.5 for k in LIVE_FEATURES},
                     "r": 1.0, "label": i % 2} for i in range(20)]
            self.assertIsNone(train_live_model(rows, Path(tmp) / "m.json"))

    def test_a_corrupt_training_line_is_skipped(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.jsonl"
            path.write_text("not json\n" + json.dumps(
                {"at": "2026-01-01", "symbol": "X", "f": {}, "r": 1.0, "label": 1}) + "\n",
                encoding="utf-8")
            self.assertEqual(len(load_training(path)), 1)


if __name__ == "__main__":
    unittest.main()


class QuietDayExplainsItselfTests(unittest.TestCase):
    """Zero trades must be self-explaining, not just a zero.

    Most sessions open nothing. On 2026-08-31 a full session of zeros turned
    out to be a dead scheduler, and the report could not tell the difference.
    """

    def _log(self, tmp, rows):
        path = Path(tmp) / "audit.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def _rows(self, day):
        return [
            {"at": day + "T13:30:00+00:00", "event": "run_complete",
             "detail": {"equity": 100000.0, "entries": 0, "exits": 0, "held": 0}},
            {"at": day + "T13:31:00+00:00", "event": "no_entries_closest_candidates",
             "detail": {"gate": 70.0, "cleared_all_hard_blockers": 2,
                        "closest": [{"symbol": "PFE", "score": 60.8, "short_by": 9.2},
                                    {"symbol": "PG", "score": 56.5, "short_by": 13.5}]}},
            {"at": day + "T13:32:00+00:00", "event": "universe_incomplete",
             "detail": {"missing": 7, "of": 120, "degraded": True}},
        ]

    def test_a_no_trade_day_names_what_came_closest(self):
        with TemporaryDirectory() as tmp:
            today = date.today().isoformat()
            payload = render(self._log(tmp, self._rows(today)))
            self.assertEqual(payload["opened_today"], 0)
            self.assertEqual(payload["score_gate"], 70.0)
            closest = payload["closest_candidates"]
            self.assertEqual(closest[0]["symbol"], "PFE")
            self.assertEqual(closest[0]["short_by"], 9.2)

    def test_missing_market_data_is_surfaced_not_buried(self):
        """A cycle that scored a partial universe made a less trustworthy
        decision, and the report must say so."""
        with TemporaryDirectory() as tmp:
            today = date.today().isoformat()
            payload = render(self._log(tmp, self._rows(today)))
            self.assertEqual(payload["cycles_with_missing_data"], 1)
            self.assertEqual(payload["worst_symbols_missing"], 7)

    def test_a_clean_day_reports_no_missing_data(self):
        with TemporaryDirectory() as tmp:
            today = date.today().isoformat()
            rows = [r for r in self._rows(today) if r["event"] != "universe_incomplete"]
            payload = render(self._log(tmp, rows))
            self.assertEqual(payload["cycles_with_missing_data"], 0)
