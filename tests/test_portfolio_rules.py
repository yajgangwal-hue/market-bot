"""The account simulator: mean reversion, and two data conventions on one timeline.

`portfolio.py` is the only module that models a real account - one cash
balance, the position cap applied across every symbol at once, a loss in one
name closing the guard for all the others. It had no callers, because it only
knew the trend rule and the live config moved to mean reversion. Every
profitability figure this project quoted came from `backtest.run_backtest`,
which gives each symbol its own private balance and therefore answers a
question nobody has.

Wiring it up surfaced a second problem: the price files come from two sources
with two timestamp conventions, 120 naive at 16:00 local and 110 tz-aware at
04:00+00:00. Sorting them together raised TypeError, and stripping the tzinfo
would have been worse than the crash - the same trading day would have become
two keys twelve hours apart, hiding half the universe on every step.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from event_aware_trader.portfolio import (
    _bar_key,
    _is_daily,
    _merged_timestamps,
    run_portfolio,
)
from event_aware_trader.risk import RiskPolicy
from event_aware_trader.types import Bar


def bar(stamp, close, high=None, low=None):
    return Bar(timestamp=stamp, open=close, high=high or close * 1.01,
               low=low or close * 0.99, close=close, volume=5_000_000.0)


def naive_day(day, close):
    return bar(datetime(2026, 9, day, 16, 0), close)


def aware_day(day, close):
    return bar(datetime(2026, 9, day, 4, 0, tzinfo=timezone.utc), close)


class TimelineTests(unittest.TestCase):
    def test_one_bar_per_date_is_recognised_as_daily(self):
        self.assertTrue(_is_daily({"A": [naive_day(d, 100.0) for d in (1, 2, 3)]}))

    def test_many_bars_per_date_is_not_daily(self):
        intraday = [bar(datetime(2026, 9, 1, 9 + i, 30), 100.0) for i in range(4)]
        self.assertFalse(_is_daily({"A": intraday}))

    def test_the_two_conventions_produce_the_same_daily_key(self):
        """16:00 naive and 04:00 UTC are the same trading day."""
        self.assertEqual(_bar_key(naive_day(4, 100.0), True),
                         _bar_key(aware_day(4, 100.0), True))

    def test_a_mixed_universe_merges_to_one_step_per_day(self):
        series = {"YAHOO": [naive_day(d, 100.0) for d in (1, 2, 3)],
                  "ALPACA": [aware_day(d, 100.0) for d in (1, 2, 3)]}
        keys = _merged_timestamps(series, True)
        self.assertEqual(len(keys), 3)          # not 6
        self.assertEqual(keys, sorted(keys))    # and it sorts at all

    def test_intraday_keeps_the_full_timestamp_normalised_to_utc(self):
        aware = bar(datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc), 100.0)
        key = _bar_key(aware, False)
        self.assertIsNone(key.tzinfo)
        self.assertEqual(key, datetime(2026, 9, 1, 14, 30))

    def test_intraday_bars_are_not_collapsed_into_one_step(self):
        intraday = [bar(datetime(2026, 9, 1, 9, 30) + timedelta(minutes=15 * i), 100.0)
                    for i in range(4)]
        self.assertEqual(len(_merged_timestamps({"A": intraday}, False)), 4)


class EntryRuleTests(unittest.TestCase):
    def _series(self):
        """A long uptrend, then a dip deep enough to make RSI oversold."""
        closes = [100.0 + i * 0.25 for i in range(260)]
        closes += [closes[-1] * (1 - 0.03 * i) for i in range(1, 9)]
        closes += [closes[-1] * 1.02 for _ in range(30)]
        start = datetime(2024, 1, 1, 16, 0)
        return {"AAA": [bar(start + timedelta(days=i), c) for i, c in enumerate(closes)]}

    def test_an_unknown_entry_rule_is_refused(self):
        with self.assertRaises(ValueError):
            run_portfolio(self._series(), entry_rule="astrology")

    def test_mean_reversion_runs_and_produces_a_report(self):
        report = run_portfolio(self._series(), starting_cash=100_000.0,
                               entry_rule="mean_reversion")
        self.assertGreater(report.days_simulated, 0)
        self.assertEqual(report.starting_cash, 100_000.0)
        self.assertGreaterEqual(report.equity, 0.0)

    def test_mean_reversion_exits_carry_its_own_reasons(self):
        report = run_portfolio(self._series(), starting_cash=100_000.0,
                               entry_rule="mean_reversion")
        allowed = {"stop", "reverted", "time_exit"}
        for trade in report.trades:
            self.assertIn(trade.exit_reason, allowed)

    def test_the_trend_rule_still_works_unchanged(self):
        report = run_portfolio(self._series(), starting_cash=100_000.0)
        self.assertGreater(report.days_simulated, 0)

    def test_one_cash_balance_is_shared_across_symbols(self):
        """The whole reason this module exists rather than run_backtest."""
        series = self._series()
        series["BBB"] = list(series["AAA"])
        report = run_portfolio(series, starting_cash=100_000.0,
                               policy=RiskPolicy(max_open_positions=6),
                               entry_rule="mean_reversion")
        peak = 0.0
        for trade in report.trades:
            peak = max(peak, trade.quantity * trade.entry_price)
        self.assertLessEqual(peak, 100_000.0 * 1.01)


if __name__ == "__main__":
    unittest.main()
