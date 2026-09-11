"""The two fill-timing options in the portfolio simulator.

Both exist because of one measured fact: the return in this strategy lives in
the close-to-open gap, and the shipped order timing sits on the wrong side of
it at entry.

`entry_fill="signal_close"` fills at the close of the bar that produced the
signal instead of at the following open. `rescue_exit` sells a position that
was under water at last night's close and opens above its entry.

Every published figure in this project was produced with both off, so the
first thing pinned here is that they stay off unless asked for. After that,
the mechanics - because a fill-price option that quietly changes WHICH trades
happen, or an exit that fires on the wrong side of a stop, would corrupt every
measurement taken with it rather than merely be wrong.

The fixture is built to produce exactly ONE signal, on its final bar. An
earlier version ramped into a twelve-day slide and produced five round trips,
which made every "did the fill move?" assertion unreadable - and produced no
position at all on the `next_open` side, because a queued entry needs a bar
after the signal to fill into and the series ended on the signal.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.mean_reversion import MeanReversionConfig, evaluate
from event_aware_trader.portfolio import run_portfolio
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.types import Bar

START = datetime(2020, 1, 1, tzinfo=timezone.utc)

# 226 days of steady uptrend, then three days down 2.2% each. The rule needs a
# 200-day average to sit above and 14 days of RSI; on the third down day RSI
# first crosses under 35 and the signal fires, with a stop at 97.37.
RAMP = 226


def _bar(index, opening, high, low, close):
    return Bar(timestamp=START + timedelta(days=index), open=opening,
               high=high, low=low, close=close, volume=5_000_000)


def _setup():
    """Bars ending on the one bar that produces a buy signal."""
    closes = [50.0 + 0.25 * i for i in range(RAMP)]
    last = closes[-1]
    closes += [last * (1 - 0.022 * (i + 1)) for i in range(3)]
    return [_bar(i, c, c * 1.001, c * 0.999, c) for i, c in enumerate(closes)]


# Derived from the fixture rather than written down. Hard-coded 99.24 and
# 97.37 were the rule's real figures rounded to two places, and the tests that
# compared against them failed on the rounding rather than on behaviour.
SIGNAL_CLOSE = _setup()[-1].close
SIGNAL_STOP = evaluate("AAA", _setup(), MeanReversionConfig()).stop


def _after(*bars):
    """The setup plus explicitly-shaped following sessions."""
    series = _setup()
    for offset, (opening, high, low, close) in enumerate(bars):
        series.append(_bar(len(_setup()) + offset, opening, high, low, close))
    return {"AAA": series}


def _run(series, **kwargs):
    return run_portfolio(series, starting_cash=100_000.0, costs=CostModel(),
                         policy=RiskPolicy(), entry_rule="mean_reversion",
                         **kwargs)


def _positions(report):
    return list(report.open_positions)


def _rescued(report):
    return [t for t in report.trades if t.exit_reason == "rescued"]


class FixtureTests(unittest.TestCase):
    """If the fixture stops producing a signal, every test below is vacuous."""

    def test_the_setup_produces_exactly_one_entry(self):
        series = _after((SIGNAL_CLOSE, SIGNAL_CLOSE * 1.01,
                         SIGNAL_CLOSE * 0.995, SIGNAL_CLOSE))
        report = _run(series)
        self.assertEqual(len(report.trades) + len(_positions(report)), 1)


class DefaultsTests(unittest.TestCase):
    def test_both_options_are_off_by_default(self):
        series = _after((SIGNAL_CLOSE, SIGNAL_CLOSE * 1.01,
                         SIGNAL_CLOSE * 0.995, SIGNAL_CLOSE))
        plain = _run(series)
        explicit = _run(series, entry_fill="next_open", rescue_exit=False)
        self.assertEqual(plain.equity, explicit.equity)
        self.assertEqual(len(plain.trades), len(explicit.trades))

    def test_an_unknown_fill_is_refused_rather_than_ignored(self):
        # A typo silently falling back to the default would produce a run
        # labelled as one thing and measured as another.
        with self.assertRaises(ValueError):
            run_portfolio({}, entry_fill="at_the_close")


class SignalCloseFillTests(unittest.TestCase):
    # The morning after the signal opens 3% higher. Under the shipped timing
    # the account pays that gap; under the close fill it owns it.
    GAP_UP = (SIGNAL_CLOSE * 1.03, SIGNAL_CLOSE * 1.05,
              SIGNAL_CLOSE * 1.02, SIGNAL_CLOSE * 1.04)

    def test_it_fills_at_the_signal_bars_close_not_the_next_open(self):
        series = _after(self.GAP_UP)
        shipped = _positions(_run(series, entry_fill="next_open"))
        early = _positions(_run(series, entry_fill="signal_close"))
        self.assertTrue(shipped and early,
                        "the fixture produced no position to compare")
        self.assertAlmostEqual(early[0].raw_entry, SIGNAL_CLOSE, places=6)
        self.assertAlmostEqual(shipped[0].raw_entry, self.GAP_UP[0], places=6)
        self.assertGreater(shipped[0].entry_price, early[0].entry_price,
                           "the close fill did not get the better price")

    def test_it_does_not_invent_or_suppress_signals(self):
        # The option may change the PRICE a decision fills at. If it changed
        # which decisions happen, no run using it could be compared with one
        # that does not.
        series = _after(self.GAP_UP)
        shipped = _run(series, entry_fill="next_open")
        early = _run(series, entry_fill="signal_close")
        self.assertEqual(len(shipped.trades) + len(_positions(shipped)),
                         len(early.trades) + len(_positions(early)))

    def test_no_position_is_ever_opened_at_or_below_its_own_stop(self):
        # Risk per share is the sizing denominator. A fill at or under the
        # stop makes it zero or negative, which silently produces an enormous
        # position on a setup whose premise has already broken.
        report = _run(_after(self.GAP_UP), entry_fill="signal_close")
        for position in _positions(report):
            self.assertGreater(position.entry_price, position.stop)

    def test_the_stop_it_carries_is_the_rules_stop(self):
        report = _run(_after(self.GAP_UP), entry_fill="signal_close")
        self.assertAlmostEqual(_positions(report)[0].stop, SIGNAL_STOP,
                               places=6)


class RescueExitTests(unittest.TestCase):
    # Day 1 after the signal opens flat and closes under water; day 2 opens
    # 1.8% above the entry. That is the account owner's case exactly: losing
    # at last night's close, profitable by the morning.
    FLAT_THEN_RED = (SIGNAL_CLOSE, SIGNAL_CLOSE * 1.002,
                     SIGNAL_CLOSE * 0.983, SIGNAL_CLOSE * 0.988)
    GREEN_OPEN = (SIGNAL_CLOSE * 1.018, SIGNAL_CLOSE * 1.025,
                  SIGNAL_CLOSE * 1.012, SIGNAL_CLOSE * 1.020)

    def test_a_green_open_after_a_red_close_is_taken(self):
        series = _after(self.FLAT_THEN_RED, self.GREEN_OPEN)
        rescued = _rescued(_run(series, rescue_exit=True))
        self.assertEqual(len(rescued), 1, "the rescue did not fire")
        self.assertGreater(rescued[0].net_pnl, 0.0,
                           "a rescue that books a loss is not a rescue")
        self.assertAlmostEqual(rescued[0].exit_price,
                               self.GREEN_OPEN[0] * (1 - 0.0006), places=4)

    def test_it_does_not_fire_on_a_position_that_was_already_winning(self):
        # The request is specifically about a position that WAS losing. One
        # already in profit is an ordinary hold, and selling it here would
        # truncate every winner at the first green open.
        green = (SIGNAL_CLOSE, SIGNAL_CLOSE * 1.022, SIGNAL_CLOSE * 0.999,
                 SIGNAL_CLOSE * 1.020)
        higher = (SIGNAL_CLOSE * 1.030, SIGNAL_CLOSE * 1.035,
                  SIGNAL_CLOSE * 1.025, SIGNAL_CLOSE * 1.032)
        report = _run(_after(green, higher), rescue_exit=True)
        self.assertEqual(_rescued(report), [])

    def test_off_by_default_changes_nothing(self):
        series = _after(self.FLAT_THEN_RED, self.GREEN_OPEN)
        self.assertEqual(_rescued(_run(series)), [])

    def test_it_is_checked_before_the_stop_not_after(self):
        # A session that opens above the entry cannot have hit its stop yet -
        # the open is the first print. Running the stop first would book a
        # loss on a bar that started green, purely because the daily bar's LOW
        # says nothing about when in the session it happened.
        green_then_crash = (SIGNAL_CLOSE * 1.018, SIGNAL_CLOSE * 1.025,
                            SIGNAL_STOP * 0.95, SIGNAL_STOP * 0.96)
        series = _after(self.FLAT_THEN_RED, green_then_crash)
        report = _run(series, rescue_exit=True)
        self.assertEqual([t.exit_reason for t in report.trades], ["rescued"])

    def test_the_first_night_can_be_exempted(self):
        # With a close-filled entry, last night's close IS the purchase price,
        # so entry costs alone make every position "losing" on its first
        # morning and the rule degenerates from a rescue into a one-night
        # scalp. rescue_min_bars=2 is what separates the two.
        series = _after(self.GREEN_OPEN)
        eager = _run(series, entry_fill="signal_close", rescue_exit=True,
                     rescue_min_bars=1)
        patient = _run(series, entry_fill="signal_close", rescue_exit=True,
                       rescue_min_bars=2)
        self.assertEqual(len(_rescued(eager)), 1)
        self.assertEqual(_rescued(patient), [])


if __name__ == "__main__":
    unittest.main()
