"""H-0026's two research-only switches on the emulator. Both default OFF.

`mr_take_profit_atr_by_year`: a take profit in ATRs of the position's own
entry ATR, chosen by the calendar year it was ENTERED. `mr_take_profit_trade_
through`: a limit that is only touched may not fill - daily bars cannot see
the queue - so a touch fill needs the high to clear the level by a margin. A
gap through the level still fills at the open, which is better.
"""

import unittest

from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy

from tests.test_take_profit import oversold_in_an_uptrend


def run(series, **kw):
    return run_portfolio({"AAA": series}, starting_cash=100_000.0, policy=RiskPolicy(),
                         costs=CostModel(), entry_rule="mean_reversion",
                         entry_fill="signal_close", **kw)


def taken(report):
    return [t for t in report.trades if t.exit_reason == "take_profit"]


def level_at(series, trade, atrs):
    """raw_entry + atrs x entry_atr, rebuilt from the trade (stop = 2.5 ATR)."""
    raw_entry = [b for b in series if b.timestamp == trade.entry_time][0].close
    entry_atr = (raw_entry - trade.initial_stop) / 2.5
    return raw_entry + atrs * entry_atr


class TakeProfitByEntryYear(unittest.TestCase):
    def test_off_by_default_and_identical_when_passed_as_off(self):
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        plain = run(series)
        explicit = run(series, mr_take_profit_atr_by_year=None,
                       mr_take_profit_trade_through=0.0)
        self.assertEqual([(t.exit_reason, t.exit_price, t.quantity) for t in plain.trades],
                         [(t.exit_reason, t.exit_price, t.quantity) for t in explicit.trades])
        self.assertFalse(taken(plain))

    def test_the_entry_years_target_is_in_entry_atrs(self):
        # 2.5 ATR is exactly 1R, because the stop sits 2.5 ATR below entry.
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        by_year = run(series, mr_take_profit_atr_by_year={2024: 2.5})
        by_r = run(series, mr_take_profit_r=1.0)
        self.assertTrue(taken(by_year))
        self.assertEqual([(t.exit_price, t.exit_time) for t in taken(by_year)],
                         [(t.exit_price, t.exit_time) for t in taken(by_r)])

    def test_a_year_missing_from_the_table_carries_no_target(self):
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        self.assertFalse(taken(run(series, mr_take_profit_atr_by_year={2023: 2.5})))

    def test_the_table_replaces_the_r_multiple_targets(self):
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0)
        with self.assertRaises(ValueError):
            run(series, mr_take_profit_atr_by_year={2024: 2.5}, mr_take_profit_r=1.0)
        with self.assertRaises(ValueError):
            run(series, mr_take_profit_trade_through=-0.001)


class TradeThrough(unittest.TestCase):
    def _touching(self, margin):
        """A rally bar whose high clears the 2.5-ATR level by `margin` only."""
        probe = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        trade = taken(run(probe, mr_take_profit_atr_by_year={2024: 2.5}))[0]
        level = level_at(probe, trade, 2.5)
        return oversold_in_an_uptrend(rally_to=level * 0.999, peak=level * (1 + margin),
                                      gap_open=150.0), level

    def test_a_bare_touch_fills_without_trade_through(self):
        series, level = self._touching(0.0002)
        fills = taken(run(series, mr_take_profit_atr_by_year={2024: 2.5}))
        self.assertTrue(fills)

    def test_a_bare_touch_does_not_fill_with_five_basis_points_of_trade_through(self):
        series, level = self._touching(0.0002)
        report = run(series, mr_take_profit_atr_by_year={2024: 2.5},
                     mr_take_profit_trade_through=0.0005)
        self.assertFalse(taken(report))

    def test_a_clear_trade_through_fills_at_the_level(self):
        series, level = self._touching(0.002)
        with_margin = taken(run(series, mr_take_profit_atr_by_year={2024: 2.5},
                                mr_take_profit_trade_through=0.0005))
        touch = taken(run(series, mr_take_profit_atr_by_year={2024: 2.5}))
        self.assertTrue(with_margin)
        self.assertEqual(with_margin[0].exit_price, touch[0].exit_price)

    def test_a_gap_through_still_fills_at_the_open(self):
        probe = oversold_in_an_uptrend(rally_to=260.0, peak=260.0, gap_open=150.0)
        trade = taken(run(probe, mr_take_profit_atr_by_year={2024: 2.5}))[0]
        level = level_at(probe, trade, 2.5)
        gapped = oversold_in_an_uptrend(rally_to=level * 1.05, peak=level * 1.05,
                                        gap_open=level * 1.03)
        fill = taken(run(gapped, mr_take_profit_atr_by_year={2024: 2.5},
                         mr_take_profit_trade_through=0.0005))
        self.assertTrue(fill)
        self.assertGreater(fill[0].exit_price, level)


if __name__ == "__main__":
    unittest.main()
