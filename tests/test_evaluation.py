"""The evaluation module is what every exit rule will be judged by.

If its arithmetic is wrong, every comparison built on it is wrong in the same
direction and nothing downstream can catch it. So the numbers are pinned
against hand-computed cases, and the one metric this project never had -
exit efficiency - is pinned in each of its three failure directions.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.evaluation import (
    _exit_quality, evaluate, ruin_probability, table)
from event_aware_trader.portfolio import ClosedTrade, PortfolioReport

START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _trade(entry, exit_price, high, low, pnl, reason="reverted", held=5,
           day=0):
    return ClosedTrade(
        symbol="AAA", entry_time=START + timedelta(days=day),
        exit_time=START + timedelta(days=day + held), quantity=10.0,
        entry_price=entry, exit_price=exit_price, net_pnl=pnl,
        r_multiple=pnl / 100.0, exit_reason=reason, bars_held=held,
        initial_stop=entry * 0.95, exit_stop=entry * 0.95,
        highest_high=high, lowest_low=low)


def _report(trades, curve_values):
    report = PortfolioReport(starting_cash=curve_values[0], cash=0.0,
                             invested=0.0, equity=curve_values[-1])
    report.trades = list(trades)
    report.equity_curve = [(START + timedelta(days=i), v)
                           for i, v in enumerate(curve_values)]
    return report


class ExitQualityTests(unittest.TestCase):
    def test_a_perfect_exit_captures_everything(self):
        captured, gave_back, heat = _exit_quality(_trade(100, 110, 110, 99, 100))
        self.assertAlmostEqual(captured, 1.0)
        self.assertAlmostEqual(gave_back, 0.0)
        self.assertAlmostEqual(heat, 0.01)

    def test_leaving_early_captures_a_fraction(self):
        # Sold at 105 when the trade later reached 120: kept a quarter.
        captured, gave_back, _ = _exit_quality(_trade(100, 105, 120, 99, 50))
        self.assertAlmostEqual(captured, 0.25)
        self.assertAlmostEqual(gave_back, 0.15)

    def test_a_winner_that_became_a_loser_is_negative(self):
        # Was up 20%, closed at 95: the failure the owner named.
        captured, gave_back, _ = _exit_quality(_trade(100, 95, 120, 94, -50))
        self.assertLess(captured, 0.0)
        self.assertAlmostEqual(gave_back, 0.25)

    def test_a_trade_that_never_went_in_profit_is_not_penalised(self):
        # highest_high == entry: no profit was ever available, so captured
        # is 1.0 by convention rather than a division by zero.
        captured, gave_back, heat = _exit_quality(_trade(100, 97, 100, 96, -30))
        self.assertAlmostEqual(captured, 1.0)
        self.assertAlmostEqual(gave_back, 0.03)
        self.assertAlmostEqual(heat, 0.04)


class AggregateTests(unittest.TestCase):
    def test_profit_factor_expectancy_and_losing_run(self):
        trades = [_trade(100, 110, 110, 99, 100, day=0),
                  _trade(100, 95, 101, 94, -50, day=10),
                  _trade(100, 96, 100, 95, -40, day=20),
                  _trade(100, 112, 113, 99, 120, day=30)]
        e = evaluate(_report(trades, [100_000.0] * 60), "t")
        self.assertAlmostEqual(e.profit_factor, 220.0 / 90.0)
        self.assertAlmostEqual(e.expectancy, 130.0 / 4)
        self.assertAlmostEqual(e.win_rate, 0.5)
        self.assertEqual(e.longest_losing_run, 2)
        self.assertAlmostEqual(e.average_win, 110.0)
        self.assertAlmostEqual(e.average_loss, -45.0)

    def test_cagr_and_drawdown_from_the_curve(self):
        values = [100.0] * 100 + [90.0] * 100 + [121.0] * 52
        e = evaluate(_report([], values), "c")
        self.assertAlmostEqual(e.max_drawdown, -0.10)
        self.assertAlmostEqual(e.total_return, 0.21)
        self.assertAlmostEqual(e.cagr, 0.21, places=6)   # exactly one year

    def test_by_exit_reason_splits_correctly(self):
        trades = [_trade(100, 110, 110, 99, 100, reason="reverted"),
                  _trade(100, 95, 101, 94, -50, reason="stop")]
        e = evaluate(_report(trades, [100_000.0] * 30), "r")
        self.assertEqual(set(e.by_exit_reason), {"reverted", "stop"})
        self.assertEqual(e.by_exit_reason["stop"]["trades"], 1)
        self.assertAlmostEqual(e.by_exit_reason["reverted"]["captured"], 1.0)


class RuinTests(unittest.TestCase):
    def test_a_flat_curve_cannot_be_ruined(self):
        self.assertEqual(ruin_probability([0.0] * 300), 0.0)

    def test_a_curve_with_a_crash_in_it_can_be(self):
        # 200 quiet days, then a 40% crash spread over 20 days. Resampling
        # blocks of 20 will land on that block often enough to breach 25%.
        returns = [0.0005] * 200 + [-0.025] * 20 + [0.0005] * 80
        self.assertGreater(ruin_probability(returns), 0.2)

    def test_it_is_deterministic(self):
        returns = [0.001 if i % 3 else -0.002 for i in range(400)]
        self.assertEqual(ruin_probability(returns), ruin_probability(returns))


class TableTests(unittest.TestCase):
    def test_it_renders_one_line_per_configuration(self):
        e = evaluate(_report([], [100.0] * 300), "only")
        rendered = table([e, e])
        self.assertEqual(len(rendered.splitlines()), 4)   # head, rule, 2 rows
        self.assertIn("only", rendered)


if __name__ == "__main__":
    unittest.main()


class OnARealSimulatedRun(unittest.TestCase):
    """evaluate() must read what run_portfolio actually records.

    The tests above build reports by hand. If ClosedTrade's field names ever
    drift from what _exit_quality reads, the synthetic tests keep passing and
    every real evaluation silently scores exit quality on zeros.
    """

    def test_exit_quality_comes_from_real_closed_trades(self):
        from event_aware_trader.portfolio import run_portfolio
        from event_aware_trader.risk import CostModel, RiskPolicy
        from event_aware_trader.types import Bar

        closes = [50.0 + 0.25 * i for i in range(226)]
        last = closes[-1]
        closes += [last * (1 - 0.022 * (i + 1)) for i in range(3)]
        closes += [closes[-1] * (1 + 0.02 * (i + 1)) for i in range(12)]
        bars = [Bar(timestamp=START + timedelta(days=i), open=c, high=c * 1.01,
                    low=c * 0.99, close=c, volume=5_000_000)
                for i, c in enumerate(closes)]
        report = run_portfolio({"AAA": bars}, starting_cash=100_000.0,
                               costs=CostModel(), policy=RiskPolicy(),
                               entry_rule="mean_reversion",
                               entry_fill="signal_close")
        self.assertTrue(report.trades, "the fixture produced no closed trade")
        trade = report.trades[0]
        self.assertGreater(trade.highest_high, 0.0)
        self.assertGreater(trade.lowest_low, 0.0)
        e = evaluate(report, "real")
        self.assertEqual(e.trades, len(report.trades))
        # A rally exit keeps most of what was available.
        self.assertGreater(e.captured, 0.5)
        self.assertIn(trade.exit_reason, e.by_exit_reason)
