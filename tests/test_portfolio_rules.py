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


class CashCurveTests(unittest.TestCase):
    """Idle capital has to be visible before it can be argued about.

    Measured on the live config: 82.5% of the account sits in cash on average
    and 46% of days are 100% cash. That single figure is the whole of the
    28-point gap against buy-and-hold, and nothing recorded it.
    """

    def _series(self):
        closes = [100.0 + i * 0.25 for i in range(260)]
        closes += [closes[-1] * (1 - 0.03 * i) for i in range(1, 9)]
        closes += [closes[-1] * 1.02 for _ in range(30)]
        start = datetime(2024, 1, 1, 16, 0)
        return {"AAA": [bar(start + timedelta(days=i), c) for i, c in enumerate(closes)]}

    def test_cash_is_recorded_at_every_step(self):
        report = run_portfolio(self._series(), starting_cash=100_000.0,
                               entry_rule="mean_reversion")
        self.assertEqual(len(report.cash_curve), len(report.equity_curve))

    def test_cash_never_exceeds_equity_and_is_never_negative(self):
        report = run_portfolio(self._series(), starting_cash=100_000.0,
                               entry_rule="mean_reversion")
        for (_, cash), (_, equity) in zip(report.cash_curve, report.equity_curve):
            self.assertGreaterEqual(cash, -1e-6)
            self.assertLessEqual(cash, equity + 1e-6)

    def test_an_account_that_never_trades_is_all_cash(self):
        """A flat series produces no oversold signal, so nothing is deployed."""
        flat = {"AAA": [bar(datetime(2024, 1, 1, 16, 0) + timedelta(days=i), 100.0)
                        for i in range(300)]}
        report = run_portfolio(flat, starting_cash=100_000.0,
                               entry_rule="mean_reversion")
        self.assertEqual(report.trades, [])
        for _, cash in report.cash_curve:
            self.assertAlmostEqual(cash, 100_000.0, places=2)


if __name__ == "__main__":
    unittest.main()


class CorrelationBucketCapTests(unittest.TestCase):
    """`max_per_bucket` has to reach the simulator, not just the guard.

    The guard counts occurrences of the candidate's bucket in what it is
    handed. The simulator used to hand it a SET, which collapses two holdings
    in one bucket into a single entry and caps every configuration at one name
    however the policy is set - so raising the dial would have appeared to do
    nothing and the concurrency question would have been answered wrongly.
    """

    def _two_names_in_one_bucket(self):
        """Two symbols the shipped map puts in the same bucket.

        Read from the real map rather than asserted, so this test says
        something true about the shipped configuration rather than about a
        fixture invented to agree with it.
        """
        from event_aware_trader.strategy import CORRELATION_BUCKETS
        by_bucket = {}
        for symbol, bucket in sorted(CORRELATION_BUCKETS.items()):
            by_bucket.setdefault(bucket, []).append(symbol)
        for bucket, symbols in sorted(by_bucket.items()):
            if len(symbols) >= 2:
                return symbols[0], symbols[1]
        self.skipTest("the shipped map has no bucket with two names in it")

    def _series(self, first, second):
        closes = [100.0 + i * 0.25 for i in range(260)]
        closes += [closes[-1] * (1 - 0.03 * i) for i in range(1, 9)]
        closes += [closes[-1] * 1.02 for _ in range(30)]
        start = datetime(2024, 1, 1, 16, 0)
        bars = [bar(start + timedelta(days=i), c) for i, c in enumerate(closes)]
        # Identical series, so both qualify on the same bar and the ONLY thing
        # that can separate them is the bucket rule under test.
        return {first: list(bars), second: list(bars)}

    def _concurrent_peak(self, report):
        events = []
        for trade in report.trades:
            events.append((trade.entry_time, 1))
            events.append((trade.exit_time, -1))
        events.sort()
        live = peak = 0
        for _, delta in events:
            live += delta
            peak = max(peak, live)
        return peak

    def test_one_per_bucket_is_the_shipped_behaviour(self):
        from dataclasses import replace
        first, second = self._two_names_in_one_bucket()
        report = run_portfolio(self._series(first, second),
                               starting_cash=100_000.0,
                               policy=replace(RiskPolicy(), max_per_bucket=1),
                               entry_rule="mean_reversion")
        self.assertEqual(self._concurrent_peak(report), 1)

    def test_raising_the_cap_lets_a_second_name_in(self):
        from dataclasses import replace
        first, second = self._two_names_in_one_bucket()
        report = run_portfolio(self._series(first, second),
                               starting_cash=100_000.0,
                               policy=replace(RiskPolicy(), max_per_bucket=2),
                               entry_rule="mean_reversion")
        self.assertEqual(self._concurrent_peak(report), 2)

    def test_the_default_policy_still_holds_one(self):
        """No shipped behaviour moves until a measurement says it should."""
        self.assertEqual(RiskPolicy().max_per_bucket, 1)
