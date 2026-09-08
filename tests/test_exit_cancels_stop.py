"""A position cannot be closed while its own protective stop reserves the shares.

Found live on 2026-09-08. The bot wanted to exit EWY on an RSI recovery and
Alpaca refused every attempt:

    HTTP 403 DELETE /v2/positions/EWY
    {"available":"0","existing_qty":"106","held_for_orders":"106",
     "message":"insufficient qty available for order (requested: 106,
     available: 0)","symbol":"EWY"}

All 106 shares were reserved by the GTC stop this loop had placed to protect
them. `_reconcile_protective_stops` has always cancelled before submitting for
precisely this reason; the exit path never did.

The consequence was not a nuisance. A protected position could not be closed
by the RULE at all - only by the stop itself - so every RSI-recovery exit and
every holding-cap exit was silently disabled from the moment the protective
stop went on. The strategy's measured edge depends on those exits: the decade
backtest exits on RSI recovery far more often than on the stop.
"""

import unittest
from datetime import datetime, timedelta, timezone

from fake_broker import FakeBroker


class CloseWhileProtectedTests(unittest.TestCase):
    def _broker(self):
        broker = FakeBroker(
            equity=100_000.0,
            positions=[{"symbol": "EWY", "quantity": 106.0,
                        "average_entry_price": 187.35,
                        "market_value": 20_020.0, "unrealized_pnl": 161.0}],
        )
        broker._init_stops()
        broker.open_sells["EWY"] = [{
            "id": "stop-1", "type": "stop", "time_in_force": "gtc",
            "stop_price": 186.0, "quantity": 106.0, "status": "held",
        }]
        return broker

    def test_the_double_reproduces_the_live_refusal(self):
        """Closing while the stop rests must fail, or the test proves nothing."""
        from event_aware_trader.broker import BrokerError
        broker = self._broker()
        with self.assertRaises(BrokerError) as caught:
            broker.close_position("EWY", dry_run=False)
        self.assertIn("insufficient qty", str(caught.exception))

    def test_cancelling_the_stop_first_lets_the_close_succeed(self):
        broker = self._broker()
        for order in broker.open_sell_orders().get("EWY", []):
            broker.cancel_order(order["id"], dry_run=False)
        result = broker.close_position("EWY", dry_run=False)
        self.assertEqual(result["status"], "CLOSE_SUBMITTED")
        self.assertEqual(broker.closed, [("EWY", False)])

    def test_the_cancel_must_come_before_the_close(self):
        """Order of operations is the correctness property, not a preference."""
        broker = self._broker()
        for order in broker.open_sell_orders().get("EWY", []):
            broker.cancel_order(order["id"], dry_run=False)
        broker.close_position("EWY", dry_run=False)
        kinds = [event[0] for event in broker.events]
        self.assertIn("cancel", kinds)
        self.assertIn("close", kinds)
        self.assertLess(kinds.index("cancel"), kinds.index("close"))

    def test_an_unprotected_position_still_closes_directly(self):
        """No resting order means nothing to cancel; the close is unaffected."""
        broker = FakeBroker(
            equity=100_000.0,
            positions=[{"symbol": "RTX", "quantity": 10.0,
                        "average_entry_price": 198.0,
                        "market_value": 1_980.0, "unrealized_pnl": 0.0}],
        )
        broker._init_stops()
        result = broker.close_position("RTX", dry_run=False)
        self.assertEqual(result["status"], "CLOSE_SUBMITTED")
        self.assertEqual(broker.canceled, [])

    def test_a_dry_run_never_cancels_a_real_order(self):
        """The live path guards the cancel behind `not dry_run`.

        A dry run that cancelled the protective stop would strip a real
        position of its protection to simulate an exit it is not going to
        make.
        """
        broker = self._broker()
        broker.close_position("EWY", dry_run=True)
        self.assertEqual(broker.canceled, [])
        self.assertEqual(len(broker.open_sell_orders().get("EWY", [])), 1)


if __name__ == "__main__":
    unittest.main()
