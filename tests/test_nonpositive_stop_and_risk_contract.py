"""Two defects the audits found, pinned so they cannot come back.

ONE: a non-positive stop crashed the trend rule.
`strategy.generate_candidate` computed `stop = entry - multiple * ATR`,
recorded the blocker "Calculated stop is non-positive", and then
CONTINUED into `costs.round_trip_cost_per_share(entry, stop)`, which
refuses a non-positive price. The blocker was recorded and never
reached, so `run_portfolio(entry_rule="trend")` could not complete a
run on the 230-name research universe. It fired once in ~617,000
symbol-sessions, so it is rare rather than pervasive. Production uses
entry_rule="mean_reversion" and is unaffected.

TWO: `risk_per_trade` reads as a ceiling and is a BASE. The conviction
multiplier is applied AFTER the budget, and the only post-conviction
clamp is on notional, so the effective per-trade risk ceiling is
`risk_per_trade * CONVICTION_MAX`. Measured on the frozen decade:
93.84% of trades exceed the declared 0.5%, the mean is 0.684%, and
nothing exceeds 0.75%. Nothing here changes that behaviour - these
tests state the contract so the next reader is not surprised by it.
"""

import unittest
from datetime import datetime, timedelta, timezone
from math import floor

from event_aware_trader.data import Bar
from event_aware_trader.mean_reversion import (
    CONVICTION_MAX, CONVICTION_MIN, MeanReversionConfig, evaluate)
from event_aware_trader.risk import CostModel, RiskPolicy, position_size
from event_aware_trader.strategy import (
    DEFAULT_UNIVERSE, StrategyConfig, generate_candidate)
from event_aware_trader.types import Action


def bars(closes, high_mult=1.0, low_mult=1.0, volume=4_000_000):
    out, day = [], datetime(2024, 1, 1, tzinfo=timezone.utc)
    for c in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(Bar(timestamp=day, open=c, high=c * high_mult,
                       low=c * low_mult, close=c, volume=volume))
        day += timedelta(days=1)
    return out


class ANonPositiveStopIsRejectedNotRaised(unittest.TestCase):
    """The trend rule must return the REJECT it was already building."""

    #: Must be IN the default universe, or generate_candidate rejects
    #: earlier with "Symbol is outside the liquid... universe" and the
    #: defect is never reached - which is exactly how the first draft of
    #: this test passed while exercising nothing.
    SYMBOL = "AAPL"

    def series(self):
        # Violent range so ATR is enormous relative to price: a
        # 2.0 x ATR stop then lands at or below zero.
        closes, px = [], 40.0
        for i in range(260):
            px = 40.0 if i % 2 else 8.0
            closes.append(px)
        return bars(closes, high_mult=3.0, low_mult=0.05)

    def test_generate_candidate_does_not_raise(self):
        try:
            got = generate_candidate(self.SYMBOL, self.series(), [], 100_000.0,
                                     RiskPolicy(), CostModel(),
                                     StrategyConfig())
        except ValueError as error:
            self.fail("generate_candidate raised instead of rejecting: "
                      "{0}".format(error))
        self.assertNotEqual(got.action, Action.PAPER_LONG)

    def test_the_symbol_is_in_the_universe(self):
        """Guards the two tests below: an out-of-universe symbol is
        rejected before the stop is ever computed."""
        self.assertIn(self.SYMBOL, DEFAULT_UNIVERSE)

    def test_the_blocker_is_actually_reachable(self):
        """Before the fix this string was appended and then orphaned by
        the raise on the next line."""
        got = generate_candidate(self.SYMBOL, self.series(), [], 100_000.0,
                                 RiskPolicy(), CostModel(), StrategyConfig())
        self.assertIn("Calculated stop is non-positive", got.blockers)

    def test_the_cost_model_still_refuses_a_negative_price(self):
        """The guard belongs in the caller; the cost model must stay
        strict, or the next caller inherits the same bug silently."""
        with self.assertRaises(ValueError):
            CostModel().round_trip_cost_per_share(100.0, -5.0)

    def test_mean_reversion_guards_the_same_case(self):
        """Production's rule has always handled it: stop is nulled and
        the signal stands aside."""
        sig = evaluate(self.SYMBOL, self.series(), MeanReversionConfig())
        self.assertEqual(sig.action, "STAND_ASIDE")


class TheRiskBudgetIsABaseNotACeiling(unittest.TestCase):
    """States the contract measured on the frozen decade."""

    def setUp(self):
        self.policy = RiskPolicy(allow_fractional_shares=False)
        self.costs = CostModel()

    def test_position_size_alone_respects_the_declared_budget(self):
        """Before conviction, planned risk never exceeds risk_per_trade."""
        equity = 100_000.0
        for entry, stop in ((100.0, 94.5), (250.0, 236.0), (37.0, 35.1)):
            qty, planned = position_size(equity, entry, stop, self.policy,
                                         self.costs)
            self.assertGreater(qty, 0)
            self.assertLessEqual(planned,
                                 equity * self.policy.risk_per_trade + 1e-9)

    def test_conviction_raises_the_effective_ceiling_to_1_5x(self):
        """The documented contract: conviction multiplies AFTER the
        budget, and the post-conviction clamp bounds NOTIONAL only. So
        the effective risk ceiling is risk_per_trade x CONVICTION_MAX."""
        equity, entry, stop = 100_000.0, 100.0, 94.5
        qty, planned = position_size(equity, entry, stop, self.policy,
                                     self.costs)
        scaled_risk = planned * CONVICTION_MAX
        ceiling = equity * self.policy.risk_per_trade * CONVICTION_MAX
        self.assertLessEqual(scaled_risk, ceiling + 1e-9)
        self.assertGreater(scaled_risk,
                           equity * self.policy.risk_per_trade,
                           "conviction is expected to exceed the base budget; "
                           "if this fails the contract has changed")

    def test_the_effective_ceiling_is_0_75_percent(self):
        """0.5% base x 1.5 max conviction. Pinned as a number because
        the audit measured a realised maximum of exactly 0.7500%."""
        self.assertAlmostEqual(
            self.policy.risk_per_trade * CONVICTION_MAX, 0.0075, places=9)

    def test_conviction_bounds_are_what_the_contract_assumes(self):
        self.assertEqual(CONVICTION_MIN, 0.5)
        self.assertEqual(CONVICTION_MAX, 1.5)

    def test_rounding_can_only_reduce_risk_never_raise_it(self):
        """floor() is what makes the bound hold: realised risk is at or
        below budget x conviction, never above."""
        equity, entry, stop = 100_000.0, 137.0, 129.9
        qty, planned = position_size(equity, entry, stop, self.policy,
                                     self.costs)
        self.assertEqual(qty, float(floor(qty)))
        lps = (entry - stop) + self.costs.round_trip_cost_per_share(entry, stop)
        self.assertLessEqual(qty * lps,
                             equity * self.policy.risk_per_trade + 1e-9)


if __name__ == "__main__":
    unittest.main()
