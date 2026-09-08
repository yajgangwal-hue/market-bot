"""Every equity order must be a whole number of shares, after ALL adjustments.

Found live on 2026-09-08. Both RTX entries that day were fractional - 76.5 and
79.5 shares - and every cycle afterwards logged:

    protective_stop_FAILED  "Alpaca cannot rest a GTC stop on a fractional
                             quantity (79.5)."

The position sat all session with no stop at the broker, which is the exact
condition `require_broker_side_stop` exists to prevent: a stop that lives only
in this process "is not a stop, it is an intention".

The cause is an ordering bug, not a missing feature. `run_once` already sizes
with allow_fractional_shares=False so the quantity comes back whole - and then
multiplies it by conviction, which returns 0.5-1.5x:

    51 whole shares  x 1.5 conviction  = 76.5
    53 whole shares  x 1.5 conviction  = 79.5

Both live quantities reproduce exactly. The guard was established and then
undone two lines later, so it protected nothing. And because conviction
returns a non-integer for any setup that is not exactly at the top or bottom
of its range, essentially EVERY equity position was affected - not just RTX.

The liquidity cap scales the quantity too, so the property has to be asserted
after every adjustment rather than before them.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import AutoTradeConfig, run_once
from event_aware_trader.mean_reversion import CONVICTION_MAX, conviction
from event_aware_trader.risk import CostModel, RiskPolicy, position_size
from event_aware_trader.types import Bar
from fake_broker import FakeBroker
from test_entry_rule import oversold_in_an_uptrend


def _config(tmp, **overrides):
    settings = dict(
        dry_run=False,
        audit_log=Path(tmp) / "audit.jsonl",
        state_file=Path(tmp) / "state.json",
        universe=("SPY",),
        entry_rule="mean_reversion",
        model_file=None,
        live_model_file=None,
        require_market_open=False,
    )
    settings.update(overrides)
    return AutoTradeConfig(**settings)


class TheLiveArithmeticTests(unittest.TestCase):
    """Reproduce 76.5 and 79.5 from the shipped sizing, so the cause is pinned."""

    def test_conviction_turns_a_whole_size_fractional(self):
        from dataclasses import replace
        policy = replace(RiskPolicy(), allow_fractional_shares=False)
        whole, _ = position_size(100_000.0, 199.2188, 189.73292802240144,
                                 policy, CostModel())
        self.assertEqual(whole, 51.0)
        self.assertEqual(whole * CONVICTION_MAX, 76.5)   # the live RTX order

    def test_a_deep_pullback_really_does_return_the_top_multiplier(self):
        """Not a contrived input: this is what the shipped rule buys."""
        self.assertAlmostEqual(conviction(oversold_in_an_uptrend()), CONVICTION_MAX)


class OrderQuantityTests(unittest.TestCase):
    """Driven through `run_once`, because the defect was in the ORDER of the
    steps there and no unit of sizing alone can see it.

    `daily_bars` reads the repo's own price files, so the rule would be
    evaluated against whatever SPY did this week rather than against the
    setup under test. It is replaced with the fixture for the duration.
    """

    def _run(self, **overrides):
        from event_aware_trader import autotrade
        bars = oversold_in_an_uptrend()
        original = autotrade.daily_bars
        autotrade.daily_bars = lambda symbol, data_dir=None: bars
        try:
            with TemporaryDirectory() as tmp:
                broker = FakeBroker(equity=100_000.0)
                run_once(_config(tmp, **overrides), broker=broker,
                         bars_by_symbol={"SPY": bars})
                return broker
        finally:
            autotrade.daily_bars = original

    def test_the_submitted_quantity_is_a_whole_number_of_shares(self):
        broker = self._run()
        self.assertTrue(broker.submitted, "the fixture must actually trade")
        for symbol, quantity, _stop, _dry in broker.submitted:
            self.assertEqual(quantity, int(quantity),
                             "{0} ordered {1} shares; Alpaca cannot rest a GTC "
                             "stop on that".format(symbol, quantity))

    def test_conviction_still_moves_the_size(self):
        """Flooring must not quietly disable the weighting it protects.

        A fix that returned the unweighted size would pass the test above and
        silently undo a change that was validated against a random control.
        """
        from dataclasses import replace
        bars = oversold_in_an_uptrend()
        broker = self._run()
        _, quantity, _, _ = broker.submitted[0]
        policy = replace(RiskPolicy(), allow_fractional_shares=False)
        unweighted, _ = position_size(
            100_000.0, bars[-1].close,
            broker.submitted[0][2], policy, CostModel())
        self.assertGreater(quantity, unweighted,
                           "a deep pullback should size ABOVE the flat size")

    def test_the_broker_side_stop_can_actually_rest_on_it(self):
        """The point of the whole exercise, asserted end to end."""
        broker = self._run()
        _, quantity, stop, _ = broker.submitted[0]
        broker._init_stops()
        broker.submit_protective_stop("SPY", quantity, stop, dry_run=False)
        self.assertEqual(len(broker.open_sell_orders()["SPY"]), 1)

    def test_crypto_sizing_is_left_fractional(self):
        """One BTC is most of this account, and crypto CAN rest a stop_limit.

        Probed on the live account 2026-09-04: type "stop" is refused for
        crypto, "stop_limit" rests. So the whole-share rule is an equity rule
        and must not follow the asset class it does not apply to.
        """
        from dataclasses import replace
        policy = replace(RiskPolicy(), allow_fractional_shares=True)
        quantity, _ = position_size(100_000.0, 60_000.0, 57_000.0,
                                    policy, CostModel())
        self.assertNotEqual(quantity, int(quantity))


class TheDoubleTests(unittest.TestCase):
    """The double let this ship, so it is corrected alongside the code.

    `close_position` already mirrors Alpaca's share reservation for exactly
    this reason. A double that accepts what the real broker refuses is how a
    defect reaches the account.
    """

    def test_a_fractional_protective_stop_is_refused(self):
        from event_aware_trader.broker import BrokerError
        broker = FakeBroker(equity=100_000.0)
        broker._init_stops()
        with self.assertRaises(BrokerError) as caught:
            broker.submit_protective_stop("RTX", 79.5, 189.73, dry_run=False)
        self.assertIn("fractional", str(caught.exception))

    def test_a_whole_quantity_rests_normally(self):
        broker = FakeBroker(equity=100_000.0)
        broker._init_stops()
        broker.submit_protective_stop("RTX", 79.0, 189.73, dry_run=False)
        self.assertEqual(len(broker.open_sell_orders()["RTX"]), 1)


if __name__ == "__main__":
    unittest.main()


class FractionalPositionProtectionTests(unittest.TestCase):
    """A fractional position must get a stop on its whole-share part.

    Sizing now floors before the order is sent, so this is for what a partial
    fill, a corporate action, or a position opened before the fix leaves
    behind - RTX on 2026-09-08 being the live example. Protecting 76 of 76.5
    shares covers 99.3% of the position; the old behaviour protected none of
    it and logged the same failure every cycle indefinitely.
    """

    def _broker(self, quantity):
        broker = FakeBroker(
            equity=100_000.0,
            positions=[{"symbol": "RTX", "quantity": quantity,
                        "average_entry_price": 199.28,
                        "market_value": quantity * 199.2,
                        "unrealized_pnl": -5.36}],
        )
        broker._init_stops()
        return broker

    def _reconcile(self, broker, state):
        from event_aware_trader.autotrade import _reconcile_protective_stops
        with TemporaryDirectory() as tmp:
            actions = []
            _reconcile_protective_stops(
                _config(tmp, universe=("RTX",)), broker, state, actions)
            return actions

    def _state(self, stop=189.73):
        return {"stops": {"RTX": {"initial": stop, "current": stop}}}

    def test_the_whole_share_part_is_protected(self):
        broker = self._broker(76.5)
        self._reconcile(broker, self._state())
        self.assertEqual(len(broker.protective), 1)
        symbol, quantity, _stop, _dry = broker.protective[0]
        self.assertEqual((symbol, quantity), ("RTX", 76.0))

    def test_the_unprotected_remainder_is_reported_not_hidden(self):
        broker = self._broker(76.5)
        actions = self._reconcile(broker, self._state())
        placed = [a for a in actions if a["event"] == "protective_stop_placed"]
        self.assertEqual(len(placed), 1)
        self.assertAlmostEqual(placed[0]["detail"]["unprotected_remainder"], 0.5)
        self.assertEqual(placed[0]["detail"]["position_quantity"], 76.5)

    def test_the_stop_is_not_churned_on_the_next_cycle(self):
        """The comparison must use the same quantity the submit used.

        Checking a 76-share stop against a 76.5-share position calls it wrong
        every cycle and cancels then resubmits forever - which would leave the
        position briefly naked every fifteen minutes, all day.
        """
        broker = self._broker(76.5)
        state = self._state()
        self._reconcile(broker, state)
        broker.canceled.clear()
        before = len(broker.protective)
        self._reconcile(broker, state)
        self.assertEqual(broker.canceled, [])
        self.assertEqual(len(broker.protective), before)

    def test_a_whole_position_is_unaffected(self):
        broker = self._broker(76.0)
        self._reconcile(broker, self._state())
        self.assertEqual(broker.protective[0][1], 76.0)

    def test_under_one_share_is_reported_rather_than_failing_silently(self):
        broker = self._broker(0.4)
        actions = self._reconcile(broker, self._state())
        self.assertEqual(broker.protective, [])
        self.assertTrue([a for a in actions if a["event"] == "too_small_to_protect"])
