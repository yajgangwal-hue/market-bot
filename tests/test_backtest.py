import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.backtest import run_backtest
from event_aware_trader.types import Bar


def bars_with_periodic_volume_confirmation(count=100):
    start = datetime(2025, 1, 2, 16, tzinfo=timezone.utc)
    result = []
    for index in range(count):
        close = 100.0 + 2.0 * index
        result.append(
            Bar(
                timestamp=start + timedelta(days=index),
                open=close - 0.5,
                high=close + 2.0,
                low=close - 2.0,
                close=close,
                volume=3_000_000 if index % 7 == 0 else 1_000_000,
            )
        )
    return result


class BacktestTests(unittest.TestCase):
    def test_backtest_enters_after_signal_and_records_costs(self):
        bars = bars_with_periodic_volume_confirmation()
        report = run_backtest("SPY", bars, [], 50, len(bars) - 1)
        self.assertGreater(len(report.trades), 0)
        self.assertGreater(report.total_costs, 0)
        for trade in report.trades:
            self.assertGreater(trade.entry_time, trade.signal_time)
            self.assertGreaterEqual(trade.exit_time, trade.entry_time)


if __name__ == "__main__":
    unittest.main()
