import unittest

from event_aware_trader.backtest import run_backtest
from tests.test_strategy import trending_bars


class BacktestTests(unittest.TestCase):
    def test_backtest_enters_after_signal_and_records_costs(self):
        bars = trending_bars(count=120)
        report = run_backtest("SPY", bars, [], 50, len(bars) - 1)
        self.assertGreater(len(report.trades), 0)
        self.assertGreater(report.total_costs, 0)
        for trade in report.trades:
            self.assertGreater(trade.entry_time, trade.signal_time)
            self.assertGreaterEqual(trade.exit_time, trade.entry_time)

    def test_every_trade_has_finite_accounting(self):
        """A NaN bar once produced NaN P&L that silently poisoned the curve."""
        bars = trending_bars(count=120)
        report = run_backtest("SPY", bars, [], 50, len(bars) - 1, starting_equity=1_000.0)
        for trade in report.trades:
            for value in (trade.net_pnl, trade.gross_pnl, trade.r_multiple, trade.exit_price):
                self.assertFalse(value != value, "non-finite value in trade accounting")

    def test_holding_period_is_configurable_and_bounds_the_hold(self):
        from dataclasses import replace
        from event_aware_trader.strategy import StrategyConfig

        bars = trending_bars(count=120)
        config = replace(StrategyConfig(), max_holding_bars=3)
        report = run_backtest("SPY", bars, [], 50, len(bars) - 1, config=config)
        for trade in report.trades:
            self.assertLessEqual(trade.bars_held, 3)


if __name__ == "__main__":
    unittest.main()
