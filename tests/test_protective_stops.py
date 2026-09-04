"""The overnight-stop repair.

Bracket legs are time_in_force=day, so protection dies at the bell and a
position held overnight has nothing behind it. These pin the behaviour that
replaces it with a resting GTC stop.
"""
import unittest

from event_aware_trader.autotrade import AutoTradeConfig, _reconcile_protective_stops
from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from tests.fake_broker import FakeBroker


def leg(order_id, symbol, kind, qty, price, tif="day"):
    return {"id": order_id, "symbol": symbol, "side": "sell", "type": kind,
            "quantity": qty, "stop_price": price if kind == "stop" else None,
            "time_in_force": tif, "client_order_id": order_id}


def broker_with(positions, sells=None):
    b = FakeBroker(positions=positions)
    b._init_stops()
    b.open_sells = dict(sells or {})
    return b


def run(broker, stops, dry_run=False):
    config = AutoTradeConfig(dry_run=dry_run)
    state = {"stops": stops}
    actions = []
    _reconcile_protective_stops(config, broker, state, actions)
    return actions


POS = [{"symbol": "SPY", "quantity": 100.0, "average_entry_price": 100.0,
        "market_value": 10_000.0, "unrealized_pnl": 0.0}]


class ReplacingTheBracketTests(unittest.TestCase):
    def test_a_day_bracket_is_replaced_with_a_resting_gtc_stop(self):
        broker = broker_with(POS, {"SPY": [leg("stop-leg", "SPY", "stop", 100.0, 95.0)]})
        run(broker, {"SPY": {"current": 95.0}})
        self.assertIn("stop-leg", broker.canceled)
        self.assertEqual(broker.protective, [("SPY", 100.0, 95.0, False)])

    def test_the_take_profit_leg_is_cancelled_too(self):
        """It reserves the shares just as firmly as the stop does.

        Cancel only the stop and the submit is rejected with "insufficient qty
        available" while the position reads as unprotected - a failure whose
        cause is entirely off-screen.
        """
        broker = broker_with(POS, {"SPY": [
            leg("stop-leg", "SPY", "stop", 100.0, 95.0),
            leg("limit-leg", "SPY", "limit", 100.0, None),
        ]})
        run(broker, {"SPY": {"current": 95.0}})
        self.assertIn("limit-leg", broker.canceled)
        self.assertIn("stop-leg", broker.canceled)
        self.assertEqual(len(broker.protective), 1, "the GTC stop must actually land")

    def test_every_cancel_precedes_the_submit(self):
        """Ordering is correctness, not neatness.

        The shares stay reserved until the cancel lands, so a submit that runs
        first is rejected outright. It also prevents two live stops selling the
        same position twice and opening an accidental short.
        """
        broker = broker_with(POS, {"SPY": [
            leg("stop-leg", "SPY", "stop", 100.0, 95.0),
            leg("limit-leg", "SPY", "limit", 100.0, None),
        ]})
        run(broker, {"SPY": {"current": 95.0}})
        kinds = [kind for kind, _ in broker.events]
        self.assertEqual(kinds.count("submit"), 1)
        self.assertTrue(all(k == "cancel" for k in kinds[:kinds.index("submit")]),
                        "a submit ran before the shares were freed: {0}".format(broker.events))


class LeavingWellAloneTests(unittest.TestCase):
    def test_a_correct_gtc_stop_is_left_untouched(self):
        broker = broker_with(POS, {"SPY": [
            leg("gtc-SPY", "SPY", "stop", 100.0, 95.0, tif="gtc")]})
        run(broker, {"SPY": {"current": 95.0}})
        self.assertEqual(broker.canceled, [])
        self.assertEqual(broker.protective, [], "no churn when it is already right")

    def test_a_ratcheted_stop_is_replaced_at_the_new_price(self):
        broker = broker_with(POS, {"SPY": [
            leg("gtc-SPY", "SPY", "stop", 100.0, 95.0, tif="gtc")]})
        run(broker, {"SPY": {"current": 97.5}})
        self.assertIn("gtc-SPY", broker.canceled)
        self.assertEqual(broker.protective[0][2], 97.5)

    def test_a_quantity_mismatch_is_replaced(self):
        """A partial fill or a manual trim leaves a stop covering the wrong size."""
        broker = broker_with(POS, {"SPY": [
            leg("gtc-SPY", "SPY", "stop", 60.0, 95.0, tif="gtc")]})
        run(broker, {"SPY": {"current": 95.0}})
        self.assertIn("gtc-SPY", broker.canceled)
        self.assertEqual(broker.protective[0][1], 100.0)


class NothingBehindItTests(unittest.TestCase):
    def test_a_sell_order_with_no_position_is_cancelled(self):
        """Closed by hand elsewhere. A resting sell can then only go short."""
        broker = broker_with([], {"SPY": [
            leg("gtc-SPY", "SPY", "stop", 100.0, 95.0, tif="gtc")]})
        run(broker, {"SPY": {"current": 95.0}})
        self.assertEqual(broker.canceled, ["gtc-SPY"])
        self.assertEqual(broker.protective, [])

    def test_a_position_exited_this_cycle_does_not_warn(self):
        """Alpaca's position delete is asynchronous.

        A position sold seconds earlier can still be listed, and its remembered
        stop was popped on exit - so it looks like an unprotected position with
        no planned stop. Warning on the ordinary happy path of an exit teaches
        the user to ignore the warning, which blunts the real one.
        """
        broker = broker_with(POS, {})
        config = AutoTradeConfig(dry_run=False)
        already = [{"at": "now", "event": "exit", "dry_run": False,
                    "detail": {"symbol": "SPY", "quantity": 100.0}}]
        _reconcile_protective_stops(config, broker, {"stops": {}}, already)
        self.assertFalse([a for a in already if a.get("event") == "stop_unknown"],
                         "warned about a position it had just deliberately closed")
        self.assertEqual(broker.protective, [], "and must not re-protect it either")

    def test_a_position_with_no_planned_stop_is_reported_not_guessed(self):
        broker = broker_with(POS, {})
        actions = run(broker, {})
        self.assertEqual(broker.protective, [], "never invent a stop price")
        self.assertTrue(any(a.get("event") == "stop_unknown" for a in actions), actions)


class FailureIsLoudTests(unittest.TestCase):
    def test_a_rejected_submit_is_surfaced_not_swallowed(self):
        broker = broker_with(POS, {"SPY": [leg("stop-leg", "SPY", "stop", 100.0, 95.0)]})
        broker.protect_error = "insufficient qty available for order"
        actions = run(broker, {"SPY": {"current": 95.0}})
        failed = [a for a in actions if a.get("event") == "protective_stop_FAILED"]
        self.assertEqual(len(failed), 1, actions)
        self.assertIn("NO resting stop", failed[0]["detail"]["note"])

    def test_a_broker_read_failure_does_not_abort_the_cycle(self):
        class Blind(FakeBroker):
            def positions(self):
                raise BrokerError("upstream 500")
        broker = Blind()
        actions = run(broker, {"SPY": {"current": 95.0}})
        self.assertTrue(any(a.get("event") == "stop_reconcile_failed" for a in actions))


class SubmissionShapeTests(unittest.TestCase):
    def setUp(self):
        self.broker = AlpacaPaperBroker(
            BrokerConfig(key_id="k", secret_key="s", allow_order_submission=False))

    def test_the_stop_is_gtc_so_it_survives_the_close(self):
        payload = self.broker.submit_protective_stop("SPY", 10, 99.5, dry_run=True)["would_submit"]
        self.assertEqual(payload["time_in_force"], "gtc")
        self.assertEqual(payload["type"], "stop")
        self.assertEqual(payload["side"], "sell")
        self.assertEqual(payload["stop_price"], 99.5)

    def test_a_fractional_quantity_is_refused_with_the_reason(self):
        """Alpaca allows fractional only on day market orders, so a fractional
        position cannot hold a GTC stop at all. Better to say that here than to
        let the broker reject it and have it read as a network blip."""
        with self.assertRaises(BrokerError) as caught:
            self.broker.submit_protective_stop("SPY", 10.5, 99.5, dry_run=True)
        self.assertIn("fractional", str(caught.exception))

    def test_a_nonsense_stop_price_is_refused(self):
        with self.assertRaises(BrokerError):
            self.broker.submit_protective_stop("SPY", 10, 0.0, dry_run=True)


if __name__ == "__main__":
    unittest.main()
