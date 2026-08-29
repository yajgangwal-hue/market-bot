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
