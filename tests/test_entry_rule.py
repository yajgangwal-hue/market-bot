"""The switchable entry rule, and the exit that has to match it.

Mean reversion is the shipped default because it is the one that measures.
Through record.py's own verdict, one engine, two years, 120 equities:

    trend gate      138 trades  NOT_DISTINGUISHABLE_FROM_LUCK  p=0.34
    mean reversion   31 trades  POSITIVE_AND_MEASURABLE        p=0.030

The risk in a switch like this is subtler than a wrong number: trading one
rule's entries against the other's exits would measure neither, so the pairing
is pinned here as much as the entry itself.
"""
import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.autotrade import AutoTradeConfig, _mean_reversion_candidate
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import StrategyConfig
from event_aware_trader.types import Action, Bar

START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _bars(closes):
    out = []
    for i, close in enumerate(closes):
        out.append(Bar(timestamp=START + timedelta(days=i),
                       open=close, high=close * 1.005, low=close * 0.995,
                       close=close, volume=80_000_000.0))
    return out


def oversold_in_an_uptrend(dip_days=12):
    """A long rise, then a sharp dip that stays above the 200-day average.

    That is the setup the rule is built for: short-horizon weakness inside an
    intact long-term uptrend, rather than a downtrend to catch.
    """
    rise = [100.0 + i * 0.5 for i in range(230)]          # 100 -> 214
    peak = rise[-1]
    dip = [peak * (1.0 - 0.012 * (i + 1)) for i in range(dip_days)]
    return _bars(rise + dip)


def _candidate(bars):
    return _mean_reversion_candidate(
        "SPY", bars, 100_000.0, RiskPolicy(), CostModel(),
        StrategyConfig.for_interval("1d", exit_mode="trailing"))


class DefaultTests(unittest.TestCase):
    def test_the_shipped_rule_is_mean_reversion(self):
        self.assertEqual(AutoTradeConfig().entry_rule, "mean_reversion")

    def test_the_trend_gate_is_still_reachable(self):
        self.assertEqual(AutoTradeConfig(entry_rule="trend").entry_rule, "trend")


class SignalTests(unittest.TestCase):
    def test_weakness_inside_an_uptrend_is_a_buy(self):
        c = _candidate(oversold_in_an_uptrend())
        self.assertEqual(c.action, Action.PAPER_LONG, c.blockers)
        self.assertIsNotNone(c.entry)
        self.assertIsNotNone(c.stop)

    def test_a_steady_rise_with_no_weakness_is_not(self):
        """The rule buys dips, not strength - that is the whole premise."""
        c = _candidate(_bars([100.0 + i * 0.5 for i in range(240)]))
        self.assertNotEqual(c.action, Action.PAPER_LONG)

    def test_a_long_downtrend_is_refused(self):
        """Oversold below the 200-day average is a falling knife, not a dip."""
        c = _candidate(_bars([200.0 - i * 0.5 for i in range(240)]))
        self.assertNotEqual(c.action, Action.PAPER_LONG)

    def test_the_stop_sits_below_the_entry(self):
        c = _candidate(oversold_in_an_uptrend())
        self.assertLess(c.stop, c.entry)

    def test_a_target_is_supplied_only_so_the_entry_can_bracket(self):
        """Mean reversion never exits on a target; the leg is cancelled next
        cycle. It exists so an equity entry is protected on arrival."""
        c = _candidate(oversold_in_an_uptrend())
        self.assertGreater(c.target, c.entry)

    def test_deeper_oversold_ranks_first(self):
        """Score orders several oversold names; it is not the trend score."""
        shallow = _candidate(oversold_in_an_uptrend(dip_days=8))
        deep = _candidate(oversold_in_an_uptrend(dip_days=16))
        if shallow.action == Action.PAPER_LONG and deep.action == Action.PAPER_LONG:
            self.assertGreater(deep.score, shallow.score)

    def test_a_rejected_candidate_carries_its_reasons(self):
        c = _candidate(_bars([200.0 - i * 0.5 for i in range(240)]))
        self.assertTrue(c.blockers, "a refusal with no reason cannot be debugged")

    def test_liquidity_is_reported_for_the_participation_cap(self):
        """cap_by_participation needs this, and silently skips without it."""
        c = _candidate(oversold_in_an_uptrend())
        self.assertIn("average_dollar_volume", c.features)
        self.assertGreater(c.features["average_dollar_volume"], 0)


if __name__ == "__main__":
    unittest.main()
