"""EXP-0056: the take profit rests at the broker, beside the stop, as one OCO.

What the owner saw: a chart connected to the account showed each position's
stop order but no take profit, because the take profit existed only inside
this program. Now both halves are real orders. The properties pinned here:

- an open position (including one opened before EXP-0055) is moved from its
  standalone stop to an OCO carrying its own remembered take profit, and the
  stop is CANCELLED BEFORE the OCO is submitted (the stop reserves the shares);
- a correct OCO is left alone, so nothing churns;
- a refused OCO never leaves a position naked: the plain GTC stop goes in the
  same cycle, and the OCO is not retried again that session;
- switched off, or with adaptive exits off, nothing changes from before;
- an exit cancels both halves before it closes;
- the coverage check counts the OCO's held stop leg as protection, and
  reports the take profit beside it;
- the request sent to Alpaca has exactly the documented OCO shape.

Driven through run_once wherever the money path is involved: tests that drive
the broker double by hand cannot catch run_once going wrong.
"""

import json
import unittest
from dataclasses import replace

import event_aware_trader.autotrade as autotrade
from event_aware_trader.adaptive_exits import AdaptiveExitConfig
from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig, BrokerError
from event_aware_trader.daily_report import _outside_reason
from fake_broker import FakeBroker
from tests.test_adaptive_exits_live import ENTRY, STOP, SYMBOL, Harness, _quiet, _recovered

LEVEL = 108.0          # entry 100 behind a stop at 92: ATR 3.2, 2.5-ATR target


def _position(mark=101.0, orders=None):
    broker = FakeBroker(equity=100_000.0, cash=700.0, positions=[{
        "symbol": SYMBOL, "quantity": 151.0, "average_entry_price": ENTRY,
        "market_value": 151.0 * mark, "current_price": mark,
        "unrealized_pnl": 151.0 * (mark - ENTRY)}])
    broker._init_stops()
    broker.open_sells[SYMBOL] = orders if orders is not None else [
        {"id": "stop-live", "symbol": SYMBOL, "side": "sell", "type": "stop",
         "time_in_force": "gtc", "stop_price": STOP, "quantity": 151.0, "status": "new"}]
    return broker


def _oco_pair(take=LEVEL, stop=STOP, quantity=151.0):
    return [
        {"id": "tp-1", "symbol": SYMBOL, "side": "sell", "type": "limit",
         "time_in_force": "gtc", "stop_price": None, "limit_price": take,
         "quantity": quantity, "status": "new", "order_class": "oco",
         "parent_id": None, "oco_group": "g1"},
        {"id": "sl-1", "symbol": SYMBOL, "side": "sell", "type": "stop",
         "time_in_force": "gtc", "stop_price": stop, "limit_price": None,
         "quantity": quantity, "status": "held", "order_class": "oco",
         "parent_id": "tp-1", "oco_group": "g1"},
    ]


class TakeProfitAtTheBroker(Harness, unittest.TestCase):
    def cycle(self, broker, series=None, **overrides):
        overrides.setdefault("retry_backoff_seconds", 0.0)
        return self.run_cycle(self.config(**overrides), broker, series or _quiet())

    def test_an_existing_position_is_moved_to_an_oco_with_its_own_levels(self):
        broker = _position()
        self.cycle(broker)
        kinds = [e[0] for e in broker.events]
        self.assertLess(kinds.index("cancel"), kinds.index("submit_oco"))
        self.assertIn("stop-live", broker.canceled)
        [(symbol, quantity, stop, take, dry)] = broker.protective_oco
        self.assertEqual((symbol, quantity, dry), (SYMBOL, 151.0, False))
        self.assertAlmostEqual(stop, STOP)
        self.assertAlmostEqual(take, LEVEL)
        types = sorted(o["type"] for o in broker.open_sells[SYMBOL])
        self.assertEqual(types, ["limit", "stop"])
        [placed] = self.audit("protective_stop_placed")
        self.assertEqual(placed["order_class"], "oco")
        self.assertAlmostEqual(placed["take_profit"], LEVEL)

    def test_a_correct_oco_is_left_alone(self):
        broker = _position(orders=_oco_pair())
        self.cycle(broker)
        self.assertEqual(broker.canceled, [])
        self.assertFalse(getattr(broker, "protective_oco", []))
        self.assertEqual(broker.protective, [])

    def test_a_wrong_take_profit_is_replaced_whole(self):
        broker = _position(orders=_oco_pair(take=111.0))
        self.cycle(broker)
        self.assertIn("tp-1", broker.canceled)
        [(_, _, _, take, _)] = broker.protective_oco
        self.assertAlmostEqual(take, LEVEL)

    def test_a_refused_oco_falls_back_to_the_plain_stop_in_the_same_cycle(self):
        broker = _position()
        broker.oco_error = "Alpaca returned HTTP 422: invalid order class"
        self.cycle(broker)
        self.assertEqual(len(broker.protective), 1)          # the standalone stop
        [stop_order] = broker.open_sells[SYMBOL]
        self.assertEqual((stop_order["type"], stop_order["stop_price"]), ("stop", STOP))
        self.assertTrue(self.audit("protective_oco_FAILED"))
        [placed] = self.audit("protective_stop_placed")
        self.assertTrue(placed["fallback_from_oco"])
        self.assertIn("broker_take_profit_paused", self.state())

    def test_after_a_refusal_the_session_does_not_churn(self):
        broker = _position()
        broker.oco_error = "Alpaca returned HTTP 422: invalid order class"
        config = self.config(retry_backoff_seconds=0.0)
        self.run_cycle(config, broker, _quiet())
        submits_before = [e for e in broker.events if e[0].startswith("submit")]
        cancels_before = list(broker.canceled)
        self.run_cycle(config, broker, _quiet())
        self.assertEqual([e for e in broker.events if e[0].startswith("submit")], submits_before)
        self.assertEqual(broker.canceled, cancels_before)

    def test_switched_off_the_standalone_stop_stays(self):
        broker = _position()
        self.cycle(broker, adaptive_exits=replace(AdaptiveExitConfig(take_profit_mode="atr"),
                                                  take_profit_at_broker=False))
        self.assertEqual(broker.canceled, [])
        self.assertFalse(getattr(broker, "protective_oco", []))

    def test_with_adaptive_exits_off_an_oco_goes_back_to_a_plain_stop(self):
        broker = _position(orders=_oco_pair())
        self.cycle(broker, adaptive_exits=None)
        self.assertIn("tp-1", broker.canceled)
        [stop_order] = broker.open_sells[SYMBOL]
        self.assertEqual((stop_order["type"], stop_order["stop_price"]), ("stop", STOP))

    def test_an_exit_cancels_both_halves_then_closes(self):
        broker = _position(mark=130.0, orders=_oco_pair())
        self.cycle(broker, series=_recovered())
        self.assertEqual(broker.closed, [(SYMBOL, False)])
        kinds = [e[0] for e in broker.events]
        self.assertLess(kinds.index("cancel"), kinds.index("close"))
        self.assertEqual(broker.events[kinds.index("cancel")][1], "tp-1")

    def test_coverage_counts_the_held_stop_leg_and_reports_the_take_profit(self):
        broker = _position()
        self.cycle(broker)
        [coverage] = [c for c in self.audit("stop_coverage") if c["symbol"] == SYMBOL]
        self.assertEqual(coverage["coverage"], "fully_protected")
        self.assertEqual(coverage["resting_take_profit_quantity"], 151.0)


class Labels(unittest.TestCase):
    def test_a_fill_at_the_take_profit_is_called_that(self):
        self.assertIn("take profit", _outside_reason(
            {"exit_price": 108.2, "initial_stop": 92.0, "take_profit": 108.0}))

    def test_a_fill_below_it_keeps_the_old_wording(self):
        self.assertEqual(
            _outside_reason({"exit_price": 91.5, "initial_stop": 92.0, "take_profit": 108.0}),
            "closed outside the rule, at or below its protective stop")


class TheRequestAlpacaReceives(unittest.TestCase):
    def broker(self):
        return AlpacaPaperBroker(BrokerConfig(key_id="test", secret_key="test",
                                              allow_order_submission=False))

    def test_the_documented_oco_shape(self):
        sent = self.broker().submit_protective_oco("tjx", 151.0, 92.004, 108.0049,
                                                   dry_run=True)["would_submit"]
        self.assertEqual(sent["order_class"], "oco")
        self.assertEqual((sent["side"], sent["type"], sent["time_in_force"]),
                         ("sell", "limit", "gtc"))
        self.assertEqual(sent["qty"], "151")
        self.assertEqual(sent["take_profit"], {"limit_price": 108.0})
        self.assertEqual(sent["stop_loss"], {"stop_price": 92.0})
        self.assertNotIn("limit_price", sent)          # as Alpaca's own example
        self.assertEqual(sent["symbol"], "TJX")

    def test_refusals(self):
        broker = self.broker()
        for args in (("TJX", 150.5, 92.0, 108.0), ("BTC/USD", 1.0, 92.0, 108.0),
                     ("TJX", 151.0, 108.0, 92.0), ("TJX", 0.0, 92.0, 108.0)):
            with self.assertRaises(BrokerError):
                broker.submit_protective_oco(*args, dry_run=True)

    def test_the_order_list_reads_a_held_leg_under_its_open_parent(self):
        broker = self.broker()
        parent = {"id": "p", "symbol": "TJX", "side": "sell", "type": "limit", "qty": "151",
                  "limit_price": "108", "status": "new", "time_in_force": "gtc",
                  "order_class": "oco",
                  "legs": [{"id": "c", "symbol": "TJX", "side": "sell", "type": "stop",
                            "qty": "151", "stop_price": "92", "status": "held",
                            "time_in_force": "gtc", "order_class": "oco"}]}
        flat_parent = dict(parent, legs=None)

        def request(method, path, payload=None):
            return [parent] if "nested=true" in path else [flat_parent]   # the leg aged out
        broker._request = request
        rows = {o["id"]: o for o in broker.open_orders()}
        self.assertEqual(set(rows), {"p", "c"})
        self.assertEqual(rows["c"]["parent_id"], "p")
        self.assertEqual(rows["c"]["stop_price"], 92.0)
        self.assertEqual(rows["p"]["limit_price"], 108.0)


if __name__ == "__main__":
    unittest.main()
