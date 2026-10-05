"""Closes the rule did not make must show up in the reports - beside the rule's
record, never inside it.

On 2026-09-21 five positions were closed outside the bot at 10:05 ET for
-$1,145.64. The daily report said nothing closed and listed all five as held
overnight; the cumulative record showed +$3.76 realized. These tests pin the
corrected behaviour. Reporting only: no order, stop, sizing or fingerprinted
value is involved.
"""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.daily_report import build_day_report, render
from event_aware_trader.record import from_audit_log


def _write(tmp, rows):
    path = Path(tmp) / "audit.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _outside(day, hhmm, symbol, pnl, exit_price, initial_stop):
    return {"at": "{0}T{1}:00+00:00".format(day, hhmm),
            "event": "learned_from_external_exit",
            "detail": {"symbol": symbol, "realized_pnl": pnl,
                       "return_fraction": pnl / 10000.0,
                       "exit_price": exit_price, "initial_stop": initial_stop,
                       "closed_at": "{0}T{1}:00Z".format(day, hhmm),
                       "closed_by": "stop, tool or owner - not the rule"}}


def _day(day):
    return [
        {"at": day + "T13:33:00+00:00", "event": "hold",
         "detail": {"symbol": "AAA", "last": 57.6, "stop": 56.0, "unrealized": -240.0}},
        {"at": day + "T13:33:00+00:00", "event": "hold",
         "detail": {"symbol": "BBB", "last": 889.0, "stop": 861.0, "unrealized": -220.0}},
        {"at": day + "T13:33:01+00:00", "event": "run_complete",
         "detail": {"equity": 98800.0}},
        _outside(day, "14:17", "AAA", -236.0, exit_price=57.64, initial_stop=56.05),
        {"at": day + "T19:48:00+00:00", "event": "entry",
         "detail": {"symbol": "CCC", "entry_reference": 87.46, "stop": 81.71,
                    "quantity": 124.0}},
        {"at": day + "T19:50:00+00:00", "event": "exit",
         "detail": {"symbol": "BBB", "realized_pnl": 50.0, "return_fraction": 0.004}},
        {"at": day + "T19:50:01+00:00", "event": "run_complete",
         "detail": {"equity": 98540.0}},
    ]


class DailyReportOutsideCloses(unittest.TestCase):
    def test_outside_closes_are_counted_and_realized(self):
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            payload = render(_write(tmp, _day(day)))
            self.assertEqual(payload["closed_today"], 2)
            self.assertEqual(payload["closed_by_rule_today"], 1)
            self.assertEqual(payload["closed_outside_the_rule_today"], 1)
            self.assertAlmostEqual(payload["realized_today"], -186.0)
            self.assertAlmostEqual(payload["realized_by_rule_today"], 50.0)
            self.assertAlmostEqual(payload["realized_outside_the_rule_today"], -236.0)

    def test_only_what_is_still_held_is_reported_open(self):
        """AAA closed outside, BBB closed by the rule, CCC opened today."""
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            payload = render(_write(tmp, _day(day)))
            self.assertEqual([p["symbol"] for p in payload["still_open"]], ["CCC"])
            self.assertEqual(payload["positions_held_overnight"], 1)
            self.assertEqual(payload["still_open"][0]["last"], 87.46)
            self.assertEqual(payload["still_open"][0]["stop"], 81.71)

    def test_a_symbol_bought_back_after_an_outside_close_is_open(self):
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            rows = [
                {"at": day + "T13:33:00+00:00", "event": "hold",
                 "detail": {"symbol": "BAC", "last": 57.6, "stop": 56.0, "unrealized": -1.0}},
                _outside(day, "14:17", "BAC", -236.0, 57.64, 56.05),
                {"at": day + "T19:48:00+00:00", "event": "entry",
                 "detail": {"symbol": "BAC", "entry_reference": 58.095, "stop": 54.93}},
            ]
            report = build_day_report(_write(tmp, rows), date.today())
            self.assertEqual([p["symbol"] for p in report.open_positions], ["BAC"])
            self.assertEqual(report.open_positions[0]["last"], 58.095)

    def test_reasons_say_what_the_price_shows_and_no_more(self):
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            rows = _day(day) + [_outside(day, "19:55", "DDD", -90.0, 49.0, 50.0)]
            reasons = {t["symbol"]: t["reason"] for t in render(_write(tmp, rows))["trades"]}
            self.assertEqual(reasons["BBB"], "rule exit")
            self.assertIn("above its protective stop", reasons["AAA"])
            self.assertIn("at or below its protective stop", reasons["DDD"])
            self.assertNotIn("trailing", " ".join(reasons.values()))

    def test_since_inception_shows_outside_closes_beside_the_rule(self):
        with TemporaryDirectory() as tmp:
            day = date.today().isoformat()
            rows = [{"at": day + "T13:30:00+00:00", "event": "entry",
                     "detail": {"symbol": "AAA"}},
                    {"at": day + "T13:30:00+00:00", "event": "entry",
                     "detail": {"symbol": "BBB"}}] + _day(day)
            block = render(_write(tmp, rows))["since_inception"]
            self.assertEqual(block["closed_trades"], 1)
            self.assertEqual(block["closed_outside_the_rule"]["count"], 1)
            self.assertAlmostEqual(block["closed_outside_the_rule"]["realized_pnl"], -236.0)
            self.assertAlmostEqual(block["account_realized_pnl"], -186.0)


class RecordOutsideCloses(unittest.TestCase):
    def _rows(self):
        return [
            {"at": "2026-09-14T19:48:00+00:00", "event": "entry", "detail": {"symbol": "AAA"}},
            {"at": "2026-09-14T19:48:00+00:00", "event": "entry", "detail": {"symbol": "BBB"}},
            {"at": "2026-09-15T19:50:00+00:00", "event": "exit",
             "detail": {"symbol": "AAA", "realized_pnl": 10.0, "return_fraction": 0.001}},
            _outside("2026-09-21", "14:17", "BBB", -20.0, 57.64, 56.05),
        ]

    def test_outside_closes_stay_out_of_the_rules_statistics(self):
        with TemporaryDirectory() as tmp:
            report = from_audit_log(_write(tmp, self._rows()), 100000.0)
            self.assertEqual([t.symbol for t in report.trades], ["AAA"])
            self.assertEqual(report.verdict()["trades"], 1)
            self.assertAlmostEqual(report.ending_equity, 100010.0)

    def test_outside_closes_are_reported_beside_the_record(self):
        with TemporaryDirectory() as tmp:
            report = from_audit_log(_write(tmp, self._rows()), 100000.0)
            self.assertEqual([t.symbol for t in report.outside_closes], ["BBB"])
            self.assertEqual(report.outside_closes[0].opened, "2026-09-14T19:48:00+00:00")
            self.assertAlmostEqual(report.account_realized_pnl(), -10.0)
            payload = report.as_dict()
            self.assertEqual(payload["closed_outside_the_rule"]["count"], 1)
            self.assertAlmostEqual(payload["closed_outside_the_rule"]["realized_pnl"], -20.0)
            self.assertAlmostEqual(payload["account_realized_pnl"], -10.0)

    def test_an_outside_close_without_a_logged_entry_is_still_recorded(self):
        with TemporaryDirectory() as tmp:
            rows = [_outside("2026-09-21", "14:17", "ZZZ", -5.0, 10.0, 9.0)]
            report = from_audit_log(_write(tmp, rows), 100000.0)
            self.assertEqual(report.outside_closes[0].opened, "")
            self.assertAlmostEqual(report.account_realized_pnl(), -5.0)


if __name__ == "__main__":
    unittest.main()
