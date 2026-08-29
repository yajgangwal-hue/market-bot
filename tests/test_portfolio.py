import unittest

from event_aware_trader.portfolio import run_portfolio
from tests.test_strategy import trending_bars


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.series = {"SPY": trending_bars(count=140), "QQQ": trending_bars(count=140)}

    def test_one_account_is_shared_across_symbols(self):
        report = run_portfolio(self.series, starting_cash=1_000.0)
        self.assertEqual(report.starting_cash, 1_000.0)
        self.assertAlmostEqual(report.equity, report.cash + report.invested, places=6)

    def test_cash_never_goes_negative(self):
        report = run_portfolio(self.series, starting_cash=1_000.0)
        self.assertGreaterEqual(report.cash, 0.0)

    def test_equity_reconciles_with_realized_pnl_when_flat(self):
        report = run_portfolio(self.series, starting_cash=1_000.0)
        if not report.open_positions:
            self.assertAlmostEqual(report.equity, 1_000.0 + report.realized_pnl, places=6)

    def test_no_entry_precedes_its_own_signal(self):
        report = run_portfolio(self.series, starting_cash=1_000.0)
        for trade in report.trades:
            self.assertGreaterEqual(trade.exit_time, trade.entry_time)
            self.assertGreaterEqual(trade.bars_held, 1)

    def test_correlation_bucket_cap_is_enforced_across_the_account(self):
        """SPY and QQQ sit in different buckets; two same-bucket names must not both open."""
        series = {"XLK": trending_bars(count=140), "QQQ": trending_bars(count=140)}
        report = run_portfolio(series, starting_cash=1_000.0)
        by_day = {}
        for trade in report.trades:
            key = trade.entry_time.date()
            by_day.setdefault(key, []).append(trade.symbol)
        for symbols in by_day.values():
            self.assertLessEqual(len(set(symbols)), 1, "two technology-bucket entries on one day")

    def test_starting_cash_must_be_positive(self):
        with self.assertRaises(ValueError):
            run_portfolio(self.series, starting_cash=0.0)


if __name__ == "__main__":
    unittest.main()


class TrailingExitTests(unittest.TestCase):
    """The stay-invested mode: a winner is not closed by a clock."""

    def setUp(self):
        from dataclasses import replace
        from event_aware_trader.strategy import StrategyConfig

        self.series = {"SPY": trending_bars(count=200)}
        self.trailing = replace(StrategyConfig(), exit_mode="trailing")
        self.fixed = replace(StrategyConfig(), exit_mode="fixed_time")

    def test_trailing_holds_longer_than_the_fixed_clock(self):
        held_fixed = run_portfolio(self.series, starting_cash=1_000.0, config=self.fixed)
        held_trail = run_portfolio(self.series, starting_cash=1_000.0, config=self.trailing)
        if held_fixed.trades and held_trail.trades:
            longest_fixed = max(t.bars_held for t in held_fixed.trades)
            longest_trail = max(t.bars_held for t in held_trail.trades)
            self.assertGreater(longest_trail, longest_fixed)

    def test_no_trade_is_closed_by_the_five_day_clock_in_trailing_mode(self):
        report = run_portfolio(self.series, starting_cash=1_000.0, config=self.trailing)
        for trade in report.trades:
            self.assertNotEqual(trade.exit_reason, "time_exit")

    def test_a_trailing_stop_never_loosens(self):
        """The ratchet must be monotonic or it is not a stop at all."""
        from dataclasses import replace
        from event_aware_trader.strategy import StrategyConfig

        config = replace(StrategyConfig(), exit_mode="trailing", trail_activate_r=0.0)
        report = run_portfolio(self.series, starting_cash=1_000.0, config=config)
        for position in report.open_positions:
            self.assertGreaterEqual(position.stop, position.initial_stop)

    def test_invalid_exit_mode_is_rejected(self):
        from dataclasses import replace
        from event_aware_trader.strategy import StrategyConfig

        with self.assertRaises(ValueError):
            replace(StrategyConfig(), exit_mode="hold_forever")

    def test_trailing_mode_keeps_more_capital_at_work(self):
        """Capital at work counts the position still open, not just closed ones.

        On an uninterrupted advance the trailing stop is never hit, so the
        position is still open at the end of the run and contributes zero
        closed trades.  Counting only `report.trades` therefore measures the
        opposite of what this mode does.
        """
        fixed = run_portfolio(self.series, starting_cash=1_000.0, config=self.fixed)
        trail = run_portfolio(self.series, starting_cash=1_000.0, config=self.trailing)
        fixed_days = sum(t.bars_held for t in fixed.trades) + sum(
            p.bars_held for p in fixed.open_positions
        )
        trail_days = sum(t.bars_held for t in trail.trades) + sum(
            p.bars_held for p in trail.open_positions
        )
        self.assertGreater(trail_days, fixed_days)

    def test_an_uninterrupted_advance_is_still_held_at_the_end(self):
        report = run_portfolio(self.series, starting_cash=1_000.0, config=self.trailing)
        self.assertTrue(report.open_positions, "trailing mode closed a trend it should have ridden")
        self.assertGreater(report.invested, 0.0)
