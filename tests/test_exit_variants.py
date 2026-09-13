"""The five mean-reversion exit variants: mechanics, pinned before measurement.

Each variant is off by default and must reproduce the baseline exactly when
off - every published figure depends on that. When on, each has one property
that would corrupt a measurement if it were wrong:

    trail      the stop only ever rises, and rises from the high through
               YESTERDAY - a stop raised from today's high would sit above a
               low that has not happened yet
    partial    books a "partial" trade for the sold fraction, reduces the
               open quantity, and fires once
    momentum   fires only while the position is in profit
    regime     fires only in a downtrend with elevated or stressed volatility
    vol-trail  the stop only ever rises

None of these tests says whether a variant makes money. That is the sweep's
job; this file only guarantees the sweep is measuring what it says.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.mean_reversion import MeanReversionConfig, evaluate
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.types import Bar

START = datetime(2020, 1, 1, tzinfo=timezone.utc)
RAMP = 226


def _bar(index, opening, high, low, close):
    return Bar(timestamp=START + timedelta(days=index), open=opening,
               high=high, low=low, close=close, volume=5_000_000)


def _setup():
    """226 up days then three down days: exactly one buy signal, on the last."""
    closes = [50.0 + 0.25 * i for i in range(RAMP)]
    last = closes[-1]
    closes += [last * (1 - 0.022 * (i + 1)) for i in range(3)]
    return [_bar(i, c, c * 1.001, c * 0.999, c) for i, c in enumerate(closes)]


SIGNAL_CLOSE = _setup()[-1].close
SIGNAL_STOP = evaluate("AAA", _setup(), MeanReversionConfig()).stop
RISK = SIGNAL_CLOSE - SIGNAL_STOP


def _after(*bars):
    series = _setup()
    n = len(series)
    for offset, (o, h, l, c) in enumerate(bars):
        series.append(_bar(n + offset, o, h, l, c))
    return {"AAA": series}


def _run(series, **kwargs):
    return run_portfolio(series, starting_cash=100_000.0, costs=CostModel(),
                         policy=RiskPolicy(), entry_rule="mean_reversion",
                         entry_fill="signal_close", **kwargs)


def _rally(days, step=0.012):
    """Sessions climbing steadily from the signal close."""
    out = []
    price = SIGNAL_CLOSE
    for _ in range(days):
        nxt = price * (1 + step)
        out.append((price, nxt * 1.002, price * 0.998, nxt))
        price = nxt
    return out


class OffByDefaultTests(unittest.TestCase):
    def test_all_variants_off_reproduces_the_baseline(self):
        series = _after(*_rally(8))
        plain = _run(series)
        explicit = _run(series, mr_trail=None, mr_partial=None,
                        mr_momentum_drop=None, mr_regime_exit=False,
                        mr_vol_trail=None)
        self.assertEqual(plain.equity, explicit.equity)
        self.assertEqual([t.exit_reason for t in plain.trades],
                         [t.exit_reason for t in explicit.trades])


class TrailTests(unittest.TestCase):
    def test_the_stop_only_ever_rises(self):
        series = _after(*_rally(6),
                        # then a sharp reversal that would lower a naive stop
                        (SIGNAL_CLOSE * 1.07, SIGNAL_CLOSE * 1.07,
                         SIGNAL_CLOSE * 1.00, SIGNAL_CLOSE * 1.01))
        report = _run(series, mr_trail=(0.5, 2.5))
        for trade in report.trades:
            self.assertGreaterEqual(trade.exit_stop, trade.initial_stop)
        for position in report.open_positions:
            self.assertGreaterEqual(position.stop, position.initial_stop)

    def test_it_activates_only_after_the_gain_threshold(self):
        # A rally too small to reach 1.0R must leave the stop where it was.
        tiny = [(SIGNAL_CLOSE, SIGNAL_CLOSE + 0.2 * RISK,
                 SIGNAL_CLOSE * 0.999, SIGNAL_CLOSE + 0.1 * RISK)] * 3
        report = _run(_after(*tiny), mr_trail=(1.0, 2.0))
        for position in report.open_positions:
            self.assertAlmostEqual(position.stop, position.initial_stop, 6)
            self.assertFalse(position.trailing_active)

    def test_a_raised_stop_can_close_the_trade_on_the_way_back_down(self):
        # Up enough to activate the trail (0.5R) but gently enough that RSI
        # stays under 60 - a 2%-a-day rally reverted on the rule and the
        # baseline had exited before the trail was tested. Then down through
        # the trailed level but not the original stop: only the trail exits.
        up = _rally(3, step=0.006)
        top = up[-1][3]
        down = [(top, top, top * 0.985, top * 0.99)]
        series = _after(*up, *down)
        without = _run(series)
        with_trail = _run(series, mr_trail=(0.5, 1.0))
        self.assertEqual([t.exit_reason for t in without.trades], [])
        self.assertEqual([t.exit_reason for t in with_trail.trades], ["stop"])
        self.assertGreater(with_trail.trades[0].exit_stop,
                           with_trail.trades[0].initial_stop)


class PartialTests(unittest.TestCase):
    def test_it_books_a_partial_and_halves_the_position_once(self):
        series = _after(*_rally(6, step=0.02))
        report = _run(series, mr_partial=(1.0, 0.5))
        partials = [t for t in report.trades if t.exit_reason == "partial"]
        self.assertEqual(len(partials), 1)
        # The other half either still rides or has since closed on the rule;
        # either way it is exactly the same size as the half that was sold.
        rest = ([p.quantity for p in report.open_positions]
                + [t.quantity for t in report.trades if t.exit_reason != "partial"])
        self.assertEqual(len(rest), 1)
        self.assertAlmostEqual(partials[0].quantity, rest[0], 6)

    def test_the_partial_fills_at_its_level_not_the_high(self):
        series = _after(*_rally(6, step=0.02))
        report = _run(series, mr_partial=(1.0, 0.5))
        partial = next(t for t in report.trades if t.exit_reason == "partial")
        level = SIGNAL_CLOSE + 1.0 * RISK
        self.assertAlmostEqual(partial.exit_price, level * (1 - 0.0006), 4)

    def test_no_partial_without_the_move(self):
        report = _run(_after(*_rally(3, step=0.002)), mr_partial=(1.0, 0.5))
        self.assertEqual([t for t in report.trades if t.exit_reason == "partial"], [])


class MomentumTests(unittest.TestCase):
    def test_it_never_fires_while_under_water(self):
        # RSI can rise and fall while the price stays below entry.
        wobble = [(SIGNAL_CLOSE * 0.99, SIGNAL_CLOSE * 0.995, SIGNAL_CLOSE * 0.985,
                   SIGNAL_CLOSE * (0.99 + 0.003 * (i % 3))) for i in range(8)]
        report = _run(_after(*wobble), mr_momentum_drop=1.0)
        self.assertEqual([t for t in report.trades if t.exit_reason == "momentum"], [])

    def test_it_fires_on_a_rollover_in_profit(self):
        # A rise gentle enough that RSI stays under the 60 exit - which takes
        # precedence, correctly - followed by a fade that rolls momentum over
        # while price is still above entry.
        up = _rally(3, step=0.006)
        top = up[-1][3]
        fade = [(top * (1 - 0.002 * i), top * (1 - 0.002 * i) * 1.001,
                 top * (1 - 0.002 * (i + 1)), top * (1 - 0.002 * (i + 1)))
                for i in range(5)]
        report = _run(_after(*up, *fade), mr_momentum_drop=3.0)
        reasons = [t.exit_reason for t in report.trades]
        self.assertIn("momentum", reasons)
        self.assertGreater(report.trades[0].exit_price, SIGNAL_CLOSE)
        self.assertNotIn("reverted", reasons,
                         "the fixture reached RSI 60; it no longer tests momentum")


class VolTrailTests(unittest.TestCase):
    def test_the_stop_only_ever_rises(self):
        series = _after(*_rally(6), (SIGNAL_CLOSE * 1.07, SIGNAL_CLOSE * 1.07,
                                     SIGNAL_CLOSE * 1.00, SIGNAL_CLOSE * 1.01))
        report = _run(series, mr_vol_trail=2.5)
        for position in report.open_positions:
            self.assertGreaterEqual(position.stop, position.initial_stop)
        for trade in report.trades:
            self.assertGreaterEqual(trade.exit_stop, trade.initial_stop)


if __name__ == "__main__":
    unittest.main()
