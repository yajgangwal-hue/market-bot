"""The owner's +0.5% target / -0.2% stop, tracked beside the bot.

Reporting only: the comparison reads the audit log and places nothing. These
tests pin how each position is judged, what is left out and why, and that the
daily report carries the comparison without ever depending on it.

Every position here is 100 shares at $100, so cost is $10,000, the target is
+$50 and the stop is -$20.
"""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from event_aware_trader.daily_report import render
from event_aware_trader.tight_exit_shadow import compare

D1, D2, D3 = "2026-09-28", "2026-09-29", "2026-09-30"


def _at(day, hhmm):
    return "{0}T{1}:00+00:00".format(day, hhmm)


def _entry(day, hhmm, symbol="AAA", price=100.0, quantity=100.0):
    return {"at": _at(day, hhmm), "event": "entry",
            "detail": {"symbol": symbol, "entry_reference": price, "quantity": quantity}}


def _check(day, hhmm, gain, symbol="AAA"):
    # `last` is the previous session's close in the real log; it must not be read.
    return {"at": _at(day, hhmm), "event": "hold",
            "detail": {"symbol": symbol, "last": 1.0, "unrealized": gain}}


def _outside(day, hhmm, pnl, symbol="AAA", price=100.0, quantity=100.0):
    return {"at": _at(day, hhmm), "event": "learned_from_external_exit",
            "detail": {"symbol": symbol, "realized_pnl": pnl, "entry_price": price,
                       "quantity": quantity, "closed_at": _at(day, hhmm)}}


def _rule_exit(day, hhmm, pnl, symbol="AAA", price=100.0, quantity=100.0):
    return {"at": _at(day, hhmm), "event": "exit",
            "detail": {"symbol": symbol, "realized_pnl": pnl, "entry_price": price,
                       "quantity": quantity}}


def _compare(rows, as_of=D3, since=None):
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return compare(path, as_of=date.fromisoformat(as_of),
                       since=date.fromisoformat(since) if since else None)


def _only(payload):
    rows = payload["positions"]
    assert len(rows) == 1, rows
    return rows[0]


class HowAPositionIsJudged(unittest.TestCase):
    def test_a_target_inside_a_session_is_booked_at_the_level(self):
        row = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", 20.0),
                              _check(D2, "14:00", 70.0), _check(D2, "15:00", 120.0)]))
        rule = row["tight_rule"]
        self.assertEqual(rule["outcome"], "target")
        self.assertEqual(rule["status"], "sold at the +0.5% target")
        self.assertEqual(rule["sold"], _at(D2, "14:00"))
        self.assertAlmostEqual(rule["realized"], 50.0)   # the resting limit, not the +70 check
        self.assertIsNone(rule["unrealized"])
        self.assertEqual(row["bot"]["status"], "open")
        self.assertAlmostEqual(row["bot"]["unrealized"], 120.0)
        self.assertAlmostEqual(row["tight_rule_minus_bot"], -70.0)

    def test_a_stop_inside_a_session_is_booked_at_the_level(self):
        rule = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", -10.0),
                               _check(D2, "13:45", -30.0)]))["tight_rule"]
        self.assertEqual(rule["outcome"], "stop")
        self.assertEqual(rule["status"], "stopped out at -0.2%")
        self.assertAlmostEqual(rule["realized"], -20.0)

    def test_a_gap_through_the_stop_is_booked_at_the_open(self):
        rule = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", -80.0)]))["tight_rule"]
        self.assertEqual(rule["status"], "stopped out at the open, below -0.2%")
        self.assertAlmostEqual(rule["realized"], -80.0)   # a stop cannot fill above the open
        self.assertAlmostEqual(rule["gain_pct"], -0.8)

    def test_a_gap_over_the_target_is_booked_at_the_open(self):
        rule = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", 90.0)]))["tight_rule"]
        self.assertEqual(rule["status"], "sold at the open, above the +0.5% target")
        self.assertAlmostEqual(rule["realized"], 90.0)

    def test_the_first_check_on_the_entry_day_is_not_a_gap(self):
        rule = _only(_compare([_entry(D1, "14:26"), _check(D1, "14:45", -50.0)]))["tight_rule"]
        self.assertEqual(rule["status"], "stopped out at -0.2%")
        self.assertAlmostEqual(rule["realized"], -20.0)

    def test_neither_level_leaves_both_sides_identical(self):
        row = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", 10.0),
                              _check(D2, "13:45", -15.0), _check(D2, "14:00", 45.0)]))
        self.assertEqual(row["tight_rule"]["outcome"], "neither")
        self.assertEqual(row["tight_rule"]["status"], "still open - neither level reached yet")
        self.assertAlmostEqual(row["tight_rule"]["unrealized"], 45.0)
        self.assertAlmostEqual(row["bot"]["unrealized"], 45.0)
        self.assertAlmostEqual(row["tight_rule_minus_bot"], 0.0)

    def test_closed_before_either_level_ends_the_same_way(self):
        row = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", 10.0),
                              _outside(D2, "13:40", -300.0)]))
        self.assertEqual(row["bot"]["status"], "closed outside the bot")
        self.assertEqual(row["tight_rule"]["status"],
                         "closed with the bot - neither level was reached first")
        self.assertAlmostEqual(row["tight_rule"]["realized"], -300.0)
        self.assertAlmostEqual(row["bot"]["realized"], -300.0)

    def test_the_bot_keeps_its_own_result_after_the_rule_sold(self):
        row = _only(_compare([_entry(D1, "19:45"), _check(D2, "13:30", 60.0),
                              _check(D2, "14:00", 200.0), _rule_exit(D3, "15:00", 400.0)]))
        self.assertEqual(row["bot"]["status"], "closed by the rule")
        self.assertAlmostEqual(row["bot"]["realized"], 400.0)
        self.assertAlmostEqual(row["tight_rule"]["realized"], 60.0)
        self.assertAlmostEqual(row["tight_rule_minus_bot"], -340.0)

    def test_an_open_position_not_checked_yet(self):
        rows = [_entry(D1, "13:30", symbol="ZZZ"), _check(D1, "13:45", 5.0, symbol="ZZZ"),
                _entry(D1, "19:45")]
        payload = _compare(rows)
        row = [r for r in payload["positions"] if r["symbol"] == "AAA"][0]
        self.assertEqual(row["tight_rule"]["status"], "still open - not checked yet")
        self.assertAlmostEqual(row["bot"]["unrealized"], 0.0)


class CostBasis(unittest.TestCase):
    def test_closed_positions_are_costed_at_the_brokers_fill(self):
        """Before the freeze the entry reference was stale: 128.92 for a fill
        at 126.42. +$64 is +0.506% of the real cost but +0.496% of the stale
        one - on the stale basis the target would be missed."""
        row = _only(_compare([_entry(D1, "14:00", price=128.92), _check(D1, "14:15", 64.0),
                              _outside(D2, "15:00", -15.0, price=126.42)]))
        self.assertAlmostEqual(row["cost"], 12642.0)
        self.assertEqual(row["tight_rule"]["outcome"], "target")
        self.assertAlmostEqual(row["tight_rule"]["realized"], 63.21)

    def test_the_brokers_share_count_is_used_while_open(self):
        rows = [_entry(D1, "14:00"),
                {"at": _at(D1, "14:15"), "event": "stop_coverage",
                 "detail": {"symbol": "AAA", "held_quantity": 50.0}},
                _check(D1, "14:30", -15.0)]
        row = _only(_compare(rows))
        self.assertEqual(row["shares"], 50.0)
        self.assertEqual(row["tight_rule"]["outcome"], "stop")   # -15 on $5,000 is -0.3%
        self.assertAlmostEqual(row["tight_rule"]["realized"], -10.0)

    def test_rows_a_notice_marks_synthetic_are_ignored(self):
        rows = [_entry(D1, "14:00"),
                {"at": "2026-09-28T14:10:00.5+00:00", "event": "stop_coverage",
                 "detail": {"symbol": "AAA", "held_quantity": 300.0}},
                _check(D1, "14:30", -15.0),
                {"at": _at(D1, "14:40"), "event": "audit_log_contamination_notice",
                 "detail": {"synthetic_events": ["stop_coverage"],
                            "synthetic_timestamps": ["2026-09-28T14:10:00"]}}]
        row = _only(_compare(rows))
        self.assertEqual(row["shares"], 100.0)
        self.assertEqual(row["tight_rule"]["outcome"], "neither")   # -0.15% of $10,000


class WhatIsLeftOut(unittest.TestCase):
    def test_a_second_entry_before_any_close_leaves_the_first_out(self):
        payload = _compare([_entry(D1, "14:00"), _check(D1, "14:15", 10.0),
                            _entry(D1, "15:00"), _check(D1, "15:15", -30.0)])
        row = _only(payload)
        self.assertEqual(row["opened"], _at(D1, "15:00"))
        self.assertAlmostEqual(row["tight_rule"]["realized"], -20.0)
        self.assertEqual(len(payload["not_compared"]), 1)
        self.assertIn("second entry", payload["not_compared"][0]["reason"])

    def test_a_position_that_vanished_is_left_out(self):
        payload = _compare([_entry(D1, "19:45", symbol="YYY"), _check(D2, "13:30", 10.0, symbol="YYY"),
                            _entry(D1, "19:45"), _check(D3, "13:30", 10.0)])
        self.assertEqual([r["symbol"] for r in payload["positions"]], ["AAA"])
        self.assertEqual(payload["not_compared"][0]["symbol"], "YYY")
        self.assertIn("stopped appearing", payload["not_compared"][0]["reason"])

    def test_a_trade_closed_before_any_check_is_left_out(self):
        payload = _compare([_entry(D1, "14:00"), _rule_exit(D1, "14:05", 5.0)])
        self.assertEqual(payload["positions"], [])
        self.assertEqual(payload["not_compared"][0]["reason"],
                         "closed before the bot's first check of it")

    def test_checks_and_closes_without_a_logged_entry_are_listed(self):
        payload = _compare([_check(D1, "14:00", 5.0, symbol="QQQ"),
                            _outside(D1, "15:00", -5.0, symbol="RRR")])
        reasons = {i["symbol"]: i["reason"] for i in payload["not_compared"]}
        self.assertEqual(reasons["QQQ"], "checked while held, but no entry was logged")
        self.assertEqual(reasons["RRR"], "closed with no logged entry")


class Totals(unittest.TestCase):
    def _rows(self):
        return [
            _entry(D1, "19:45", symbol="AAA"), _check(D2, "13:30", 90.0, symbol="AAA"),
            _outside(D2, "14:00", -120.0, symbol="AAA"),                       # closed D2
            _entry(D1, "19:45", symbol="BBB"), _check(D2, "13:30", -5.0, symbol="BBB"),
            _check(D3, "13:30", 30.0, symbol="BBB"),                            # open, in band
            _entry(D1, "19:45", symbol="CCC"), _check(D2, "13:30", -60.0, symbol="CCC"),
            _check(D3, "13:30", 150.0, symbol="CCC"),                           # open, rule stopped
        ]

    def test_totals_are_the_sums_of_the_rows(self):
        payload = _compare(self._rows())
        total = payload["every_position"]
        self.assertEqual(total["positions"], 3)
        self.assertAlmostEqual(total["bot"]["realized"], -120.0)
        self.assertAlmostEqual(total["bot"]["unrealized"], 180.0)
        self.assertAlmostEqual(total["bot"]["total"], 60.0)
        self.assertAlmostEqual(total["tight_rule"]["realized"], 90.0 - 60.0)
        self.assertAlmostEqual(total["tight_rule"]["unrealized"], 30.0)
        self.assertAlmostEqual(total["tight_rule"]["total"], 60.0)
        self.assertEqual((total["tight_rule"]["sold_at_target"], total["tight_rule"]["stopped_out"],
                          total["tight_rule"]["neither_level"]), (1, 1, 1))
        self.assertAlmostEqual(total["tight_rule_minus_bot"], 0.0)
        for side in ("bot", "tight_rule"):
            self.assertAlmostEqual(total[side]["total"], sum(r[side]["gain"] for r in payload["positions"]))

    def test_held_since_counts_what_was_open_on_or_after_the_date(self):
        rows = self._rows() + [_entry(D1, "13:30", symbol="OLD"), _check(D1, "13:45", 1.0, symbol="OLD"),
                               _outside(D1, "14:00", -7.0, symbol="OLD")]
        payload = _compare(rows, since=D2)
        self.assertEqual(payload["every_position"]["positions"], 4)
        self.assertEqual(payload["held_since"]["since"], D2)
        self.assertEqual(payload["held_since"]["positions"], 3)          # OLD closed on D1
        self.assertAlmostEqual(payload["held_since"]["bot"]["total"], 60.0)

    def test_held_since_is_omitted_before_the_date(self):
        self.assertNotIn("held_since", _compare(self._rows(), as_of=D1, since=D2))

    def test_as_of_ignores_later_rows(self):
        payload = _compare(self._rows(), as_of=D2)
        bbb = [r for r in payload["positions"] if r["symbol"] == "BBB"][0]
        self.assertAlmostEqual(bbb["bot"]["unrealized"], -5.0)            # the D3 check is not read


class DailyReportCarriesIt(unittest.TestCase):
    def _write(self, tmp):
        path = Path(tmp) / "audit.jsonl"
        rows = [_entry(D1, "19:45"), _check(D2, "13:30", 20.0), _check(D2, "14:00", 70.0),
                {"at": _at(D2, "19:46"), "event": "run_complete", "detail": {"equity": 100000.0}}]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def test_the_daily_report_carries_the_comparison(self):
        with TemporaryDirectory() as tmp:
            payload = render(self._write(tmp), session=date.fromisoformat(D2))
        block = payload["tight_exit_comparison"]
        self.assertEqual(block["rule"], "+0.5% target / -0.2% stop")
        self.assertEqual(block["every_position"]["positions"], 1)
        self.assertEqual(block["held_since"]["since"], "2026-09-28")
        self.assertAlmostEqual(block["positions"][0]["tight_rule"]["realized"], 50.0)

    def test_a_fault_in_the_comparison_never_takes_the_report_down(self):
        with TemporaryDirectory() as tmp, mock.patch(
                "event_aware_trader.daily_report.compare_tight_exit",
                side_effect=RuntimeError("boom")):
            payload = render(self._write(tmp), session=date.fromisoformat(D2))
        self.assertEqual(payload["tight_exit_comparison"], {"error": "RuntimeError: boom"})
        self.assertEqual(payload["session"], D2)
        self.assertIn("since_inception", payload)


if __name__ == "__main__":
    unittest.main()
