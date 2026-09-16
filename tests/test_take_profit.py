"""The take profit: where it fills, and which multiple a given day uses.

A take profit is a resting LIMIT, which is what separates it from the stop.
A stop gapped through fills at the open and you take the worse price; a limit
gapped through fills at the open and you take the BETTER one. Getting that
backwards would flatter every take-profit result by the size of the gap.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy

START = datetime(2024, 1, 2, tzinfo=timezone.utc)


def bars(closes, highs=None, opens=None, start=START):
    highs = highs or closes
    opens = opens or closes
    return [Bar(timestamp=start + timedelta(days=i), open=o, high=h,
                low=min(o, c) * 0.995, close=c, volume=5_000_000)
            for i, (c, h, o) in enumerate(zip(closes, highs, opens))]


def oversold_in_an_uptrend(rally_to=None, peak=None, gap_open=None,
                           dip_days=6, dip_pct=0.08):
    """A name the rule will actually buy.

    The rule needs RSI under 35 AND price still above its 200-day average -
    an oversold name in an uptrend, not a falling one. A fixture that simply
    dips from a flat line goes UNDER the average and is rejected by the trend
    filter, which is how the first version of this file managed to test
    nothing at all while looking thorough.
    """
    up = [100.0 + i * 0.25 for i in range(250)]          # 100 -> 162
    top = up[-1]
    closes = up + [top * (1 - dip_pct * (j + 1) / dip_days)
                   for j in range(dip_days)]
    if rally_to is not None:
        closes = closes + [rally_to]
    highs = list(closes)
    opens = list(closes)
    if peak is not None:
        highs[-1] = peak
    if gap_open is not None:
        opens[-1] = gap_open
    return bars(closes, highs, opens)


def flat_market(n):
    return bars([200.0] * n)


class WhereATakeProfitFills(unittest.TestCase):
    def _run(self, series, **kw):
        return run_portfolio({"AAA": series}, starting_cash=100_000.0,
                             policy=RiskPolicy(), costs=CostModel(),
                             entry_rule="mean_reversion",
                             entry_fill="signal_close", **kw)

    def test_no_take_profit_by_default(self):
        report = self._run(oversold_in_an_uptrend(rally_to=260.0, peak=260.0))
        self.assertNotIn("take_profit",
                         {t.exit_reason for t in report.trades})

    def test_it_fills_at_the_level_when_the_high_reaches_it(self):
        # Intraday high tags the target; the close is far above it. A limit
        # resting at the target fills AT the target, not at the close.
        #
        # The open is held BELOW the target deliberately. Leave it above and
        # the bar has gapped through, which is the other branch entirely -
        # the first version of this test did that by accident and was really
        # exercising the gap path while claiming to test this one.
        series = oversold_in_an_uptrend(rally_to=260.0, peak=260.0,
                                        gap_open=150.0)
        report = self._run(series, mr_take_profit_r=1.0)
        taken = [t for t in report.trades if t.exit_reason == "take_profit"]
        self.assertTrue(taken, "the target was reached and should have filled")
        trade = taken[0]
        risk = trade.entry_price - trade.initial_stop
        self.assertAlmostEqual(trade.exit_price, trade.entry_price + risk,
                               delta=max(0.05, trade.entry_price * 0.002))
        self.assertLess(trade.exit_price, 260.0)      # not the close

    def test_a_gap_through_the_target_fills_at_the_open_which_is_better(self):
        # The opposite of a stop. A limit gapped through is filled at the
        # open, and the open is above the target, so the fill is BETTER.
        series = oversold_in_an_uptrend(rally_to=280.0, peak=280.0, gap_open=265.0)
        report = self._run(series, mr_take_profit_r=1.0)
        taken = [t for t in report.trades if t.exit_reason == "take_profit"]
        self.assertTrue(taken)
        trade = taken[0]
        risk = trade.entry_price - trade.initial_stop
        target = trade.entry_price + risk
        self.assertGreater(trade.exit_price, target,
                           "a limit gapped through must fill better than its level")

    def test_a_rally_short_of_the_target_does_not_fill(self):
        series = oversold_in_an_uptrend(rally_to=150.0, peak=150.5)
        report = self._run(series, mr_take_profit_r=3.0)
        self.assertNotIn("take_profit", {t.exit_reason for t in report.trades})


class WhichMultipleTheDayUses(unittest.TestCase):
    """The regime switch reads the MARKET's own trend, not the position's."""

    def _two_symbol(self, market_closes, **kw):
        # AAA is the tradeable name; SPY is the market reference and is not
        # itself tradeable here (flat, never oversold).
        name = oversold_in_an_uptrend(rally_to=260.0, peak=260.0)
        spy = bars(market_closes)
        return run_portfolio({"AAA": name, "SPY": spy},
                             starting_cash=100_000.0, policy=RiskPolicy(),
                             costs=CostModel(), entry_rule="mean_reversion",
                             entry_fill="signal_close", **kw)

    def test_a_falling_market_uses_the_down_multiple(self):
        falling = [200.0] * 211 + [200.0 - i * 1.5 for i in range(46)]
        report = self._two_symbol(
            falling, mr_take_profit_down_r=1.0, mr_take_profit_up_r=99.0)
        taken = [t for t in report.trades
                 if t.symbol == "AAA" and t.exit_reason == "take_profit"]
        self.assertTrue(taken, "the down-day target of 1R should have filled")

    def test_a_rising_market_uses_the_up_multiple(self):
        rising = [100.0 + i * 0.5 for i in range(257)]
        report = self._two_symbol(
            rising, mr_take_profit_down_r=99.0, mr_take_profit_up_r=1.0)
        taken = [t for t in report.trades
                 if t.symbol == "AAA" and t.exit_reason == "take_profit"]
        self.assertTrue(taken, "the up-day target of 1R should have filled")

    def test_an_unreachable_multiple_on_the_active_side_never_fills(self):
        falling = [200.0] * 211 + [200.0 - i * 1.5 for i in range(46)]
        report = self._two_symbol(
            falling, mr_take_profit_down_r=99.0, mr_take_profit_up_r=1.0)
        taken = [t for t in report.trades
                 if t.symbol == "AAA" and t.exit_reason == "take_profit"]
        self.assertFalse(taken, "the up multiple must not apply on a down day")

    def test_no_market_reference_means_no_regime_and_no_guess(self):
        # Without SPY in the series the regime is unknown; the regime targets
        # must then do nothing rather than defaulting to one of them.
        report = run_portfolio({"AAA": oversold_in_an_uptrend(rally_to=260.0, peak=260.0)},
                               starting_cash=100_000.0, policy=RiskPolicy(),
                               costs=CostModel(), entry_rule="mean_reversion",
                               entry_fill="signal_close",
                               mr_take_profit_down_r=1.0,
                               mr_take_profit_up_r=1.0)
        self.assertNotIn("take_profit", {t.exit_reason for t in report.trades})


if __name__ == "__main__":
    unittest.main()
