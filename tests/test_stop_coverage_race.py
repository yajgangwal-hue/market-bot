"""The 219/229 protective-stop coverage defect, and its fix.

THE HISTORICAL FAILURE, 2026-09-21. An entry for BAC filled 229 shares
at 19:48:20. Four seconds later `/v2/positions` still reported 219, the
reconciler sized a GTC stop from that 219, and ten shares sat with no
protection for seventeen hours and forty-two minutes - across an
overnight gap. The bot's own telemetry logged

    quantity 219.0  position_quantity 219.0  unprotected_remainder 0.0

a false all-clear, because both sides of that subtraction came from the
same stale snapshot.

These tests pin the behaviour that prevents it. They use a fake broker
whose position endpoint deliberately lags its own fills.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from event_aware_trader import autotrade as AT                    # noqa: E402
from event_aware_trader.autotrade import AutoTradeConfig          # noqa: E402
from event_aware_trader.broker import BrokerError                 # noqa: E402


class LaggingBroker:
    """A broker whose /v2/positions view trails its own fills."""

    def __init__(self, reads, fills=None, sells=None, raise_on_positions=False):
        # `reads` is the sequence of quantities /v2/positions will report.
        self.reads = list(reads)
        self.fills = fills or {}
        self.sells = sells or {}
        self.raise_on_positions = raise_on_positions
        self.position_calls = 0

    def positions(self):
        self.position_calls += 1
        if self.raise_on_positions:
            raise BrokerError("positions unavailable")
        index = min(self.position_calls - 1, len(self.reads) - 1)
        quantity = self.reads[index]
        if quantity <= 0:
            return []
        return [{"symbol": "BAC", "quantity": float(quantity),
                 "asset_class": "us_equity"}]

    def order(self, order_id):
        if order_id not in self.fills:
            raise BrokerError("no such order")
        return {"id": order_id, "symbol": "BAC", "side": "buy",
                "status": "filled", "quantity": self.fills[order_id],
                "filled_quantity": self.fills[order_id]}

    def open_sell_orders(self):
        return self.sells


# ISOLATED. _log() always appends to config.audit_log, so a test left on
# the default path writes synthetic safety events into the live
# data/autotrade-audit.jsonl - which I did once, on 2026-09-22, and had to
# annotate afterwards. A test must never be able to write to the
# operational log.
_SCRATCH = Path(tempfile.mkdtemp(prefix="stop-coverage-tests-"))


def config():
    return AutoTradeConfig(dry_run=False, asset_class="equity",
                           broker_retries=1, retry_backoff_seconds=0.0,
                           audit_log=_SCRATCH / "audit.jsonl",
                           state_file=_SCRATCH / "state.json")


def entry_action(order_id="abc", symbol="BAC"):
    return {"event": "entry",
            "detail": {"symbol": symbol, "result": {"order_id": order_id}}}


class TheAuthoritativeFillQuantity(unittest.TestCase):
    """The ORDER is the authority for what filled, not the position view."""

    def test_the_entry_order_supplies_the_filled_quantity(self):
        broker = LaggingBroker(reads=[219], fills={"abc": 229.0})
        actions = [entry_action()]
        fills = AT._entry_fills_this_cycle(config(), broker, actions)
        self.assertEqual(fills, {"BAC": 229.0})

    def test_a_dry_run_asks_the_broker_nothing(self):
        broker = LaggingBroker(reads=[219], fills={"abc": 229.0})
        cfg = AutoTradeConfig(dry_run=True, asset_class="equity")
        self.assertEqual(
            AT._entry_fills_this_cycle(cfg, broker, [entry_action()]), {})

    def test_an_unreadable_order_is_recorded_not_guessed(self):
        broker = LaggingBroker(reads=[219], fills={})     # lookup raises
        actions = [entry_action("missing")]
        fills = AT._entry_fills_this_cycle(config(), broker, actions)
        self.assertEqual(fills, {})
        self.assertTrue(any(a["event"] == "entry_fill_unreadable"
                            for a in actions))


class TheStalePositionRead(unittest.TestCase):
    """A read BELOW a known fill is the broker being behind, not truth."""

    def setUp(self):
        self._sleep = AT.time.sleep
        AT.time.sleep = lambda _s: None          # keep the suite fast

    def tearDown(self):
        AT.time.sleep = self._sleep

    def test_THE_HISTORICAL_FAILURE_does_not_settle_for_219(self):
        """fill 229, first read 219, later read 229 -> protect 229."""
        broker = LaggingBroker(reads=[219, 219, 229], fills={"abc": 229.0})
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=219.0, expected=229.0)
        self.assertEqual(quantity, 229.0)
        self.assertTrue(settled)

    def test_a_matching_read_is_believed_immediately(self):
        broker = LaggingBroker(reads=[229], fills={"abc": 229.0})
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=229.0, expected=229.0)
        self.assertEqual(quantity, 229.0)
        self.assertTrue(settled)
        self.assertEqual(broker.position_calls, 0)   # no needless re-read

    def test_a_position_that_never_catches_up_is_flagged_unresolved(self):
        broker = LaggingBroker(reads=[219], fills={"abc": 229.0})
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=219.0, expected=229.0)
        self.assertEqual(quantity, 219.0)
        self.assertFalse(settled)

    def test_it_never_returns_more_than_the_broker_has_shown(self):
        """A stop for uncredited shares is rejected, leaving NO stop."""
        broker = LaggingBroker(reads=[219], fills={"abc": 229.0})
        quantity, _ = AT._settled_position_quantity(
            config(), broker, "BAC", observed=219.0, expected=229.0)
        self.assertLessEqual(quantity, 219.0)

    def test_a_partial_fill_is_protected_at_what_is_held(self):
        broker = LaggingBroker(reads=[100], fills={"abc": 100.0})
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=100.0, expected=100.0)
        self.assertEqual((quantity, settled), (100.0, True))

    def test_the_largest_observation_wins_if_the_view_flickers(self):
        broker = LaggingBroker(reads=[229, 219], fills={"abc": 229.0})
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=219.0, expected=229.0)
        self.assertEqual(quantity, 229.0)
        self.assertTrue(settled)

    def test_a_broker_failure_mid_settlement_does_not_raise(self):
        broker = LaggingBroker(reads=[219], fills={}, raise_on_positions=True)
        quantity, settled = AT._settled_position_quantity(
            config(), broker, "BAC", observed=219.0, expected=229.0)
        self.assertEqual(quantity, 219.0)
        self.assertFalse(settled)


def stop(quantity, status="new", stop_price=54.93):
    return {"id": "s1", "symbol": "BAC", "side": "sell", "type": "stop",
            "quantity": float(quantity), "stop_price": stop_price,
            "time_in_force": "gtc", "status": status}


class CoverageIsVerifiedNotAssumed(unittest.TestCase):
    """Submitting is not protecting, and a snapshot may not certify itself."""

    def classify(self, reads, sells, authoritative=None):
        broker = LaggingBroker(reads=reads, sells=sells)
        actions = []
        AT._verify_stop_coverage(config(), broker, actions,
                                 authoritative or {})
        rows = [a for a in actions
                if a["event"].startswith("stop_coverage")]
        return rows[0] if rows else None

    def test_a_matching_resting_stop_is_fully_protected(self):
        row = self.classify([229], {"BAC": [stop(229)]})
        self.assertEqual(row["detail"]["coverage"], "fully_protected")
        self.assertEqual(row["detail"]["unprotected_shares"], 0.0)
        self.assertEqual(row["event"], "stop_coverage")

    def test_THE_HISTORICAL_FAILURE_is_now_a_loud_shortfall(self):
        """229 held, 219 covered -> partially protected, 10 uncovered."""
        row = self.classify([229], {"BAC": [stop(219)]})
        self.assertEqual(row["detail"]["coverage"], "partially_protected")
        self.assertEqual(row["detail"]["unprotected_shares"], 10.0)
        self.assertEqual(row["event"], "stop_coverage_SHORTFALL")

    def test_the_authoritative_fill_beats_a_stale_position_read(self):
        """Position still says 219; the fill says 229. Shortfall shown."""
        row = self.classify([219], {"BAC": [stop(219)]},
                            authoritative={"BAC": 229.0})
        self.assertEqual(row["detail"]["coverage"], "partially_protected")
        self.assertEqual(row["detail"]["unprotected_shares"], 10.0)
        self.assertEqual(row["detail"]["authoritative_quantity"], 229.0)

    def test_a_submitted_but_not_working_stop_is_not_coverage(self):
        row = self.classify([229], {"BAC": [stop(229, status="pending_new")]})
        self.assertEqual(row["detail"]["coverage"],
                         "stop_pending_verification")
        self.assertEqual(row["detail"]["resting_stop_quantity"], 0.0)

    def test_a_cancelled_stop_is_not_coverage(self):
        row = self.classify([229], {"BAC": [stop(229, status="pending_cancel")]})
        self.assertNotEqual(row["detail"]["coverage"], "fully_protected")

    def test_no_stop_at_all_is_unprotected(self):
        row = self.classify([229], {"BAC": []})
        self.assertEqual(row["detail"]["coverage"], "unprotected")
        self.assertEqual(row["detail"]["unprotected_shares"], 229.0)

    def test_a_take_profit_leg_does_not_count_as_protection(self):
        leg = {"id": "t1", "symbol": "BAC", "side": "sell", "type": "limit",
               "quantity": 229.0, "stop_price": None,
               "time_in_force": "day", "status": "new"}
        row = self.classify([229], {"BAC": [leg]})
        self.assertEqual(row["detail"]["coverage"], "unprotected")

    def test_a_position_that_grew_after_the_stop_shows_a_shortfall(self):
        row = self.classify([300], {"BAC": [stop(229)]})
        self.assertEqual(row["detail"]["coverage"], "partially_protected")
        self.assertEqual(row["detail"]["unprotected_shares"], 71.0)

    def test_duplicate_stops_are_summed_not_double_counted_as_failure(self):
        sells = {"BAC": [stop(100), dict(stop(129), id="s2")]}
        row = self.classify([229], sells)
        self.assertEqual(row["detail"]["coverage"], "fully_protected")

    def test_an_unreadable_broker_never_reports_protected(self):
        broker = LaggingBroker(reads=[229], sells={}, raise_on_positions=True)
        actions = []
        AT._verify_stop_coverage(config(), broker, actions, {})
        self.assertTrue(any(a["event"] == "stop_coverage_UNVERIFIED"
                            for a in actions))
        self.assertFalse(any(a["event"] == "stop_coverage" for a in actions))

    def test_verification_is_idempotent(self):
        """Running it twice says the same thing and changes nothing."""
        first = self.classify([229], {"BAC": [stop(229)]})
        second = self.classify([229], {"BAC": [stop(229)]})
        self.assertEqual(first["detail"]["coverage"],
                         second["detail"]["coverage"])


if __name__ == "__main__":
    unittest.main()
