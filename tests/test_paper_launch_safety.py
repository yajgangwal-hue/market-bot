"""Pre-launch safety. One failing close must not leave another position naked.

THE BUG THIS PINS. `close_out` raises BrokerError once its retries are
exhausted, and the exit loop sits above `_reconcile_protective_stops`. An
uncaught raise skipped stop reconciliation for every OTHER open position,
skipped the external-exit reconciler, skipped entries, and discarded the
state write at the end of the cycle. It is worse on the failing symbol
itself: close_out cancels the resting sells before submitting the close,
so a failure left that position with no stop at all.

The tests below drive the real `run_once` against a broker double that
fails exactly one close, and assert that the other position still gets its
stop in the same cycle.

The remaining classes pin the launch-critical invariants that must not
drift overnight: paper-only endpoint resolution, and the learned model
staying inert.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import AutoTradeConfig, run_once
from event_aware_trader.broker import BrokerError
from event_aware_trader.data import Bar
from event_aware_trader.risk import CostModel, RiskPolicy

START = datetime(2026, 1, 2, tzinfo=timezone.utc)


def bars(closes, symbol_high=None):
    out = []
    for i, close in enumerate(closes):
        high = close * 1.01 if symbol_high is None else symbol_high
        out.append(Bar(timestamp=START + timedelta(days=i), open=close,
                       high=high, low=close * 0.99, close=close,
                       volume=5_000_000))
    return out


class OneFailingCloseBroker:
    """Paper-broker double. `fails_close_for` raises on close_position."""

    def __init__(self, positions, fails_close_for=None, equity=100_000.0):
        self._positions = positions
        self.fails_close_for = fails_close_for
        self._equity = equity
        self.closed = []
        self.stops_submitted = []
        self.cancelled = []
        self.parked = []
        self.entries = []
        self._sells = {}
        class _C:
            endpoint = "https://paper-api.alpaca.markets"
            allow_order_submission = True
        self.config = _C()

    def clock(self):
        return {"is_open": True, "timestamp": "2026-01-05T15:00:00Z",
                "next_open": "2026-01-06T14:30:00Z",
                "next_close": "2026-01-05T21:00:00Z"}

    def account(self):
        return {"equity": self._equity, "cash": 50_000.0,
                "buying_power": self._equity, "trading_blocked": False,
                "status": "ACTIVE", "account_number": "PA_TEST"}

    def positions(self):
        return [dict(p) for p in self._positions]

    def open_sell_orders(self):
        return {k: list(v) for k, v in self._sells.items()}

    def open_orders(self):
        return [o for orders in self._sells.values() for o in orders]

    def recent_orders(self, limit=50):
        return []

    def fill_activities(self, page_size=100):
        return []

    def cancel_order(self, order_id, dry_run=True):
        self.cancelled.append(order_id)
        for symbol, orders in list(self._sells.items()):
            self._sells[symbol] = [o for o in orders if o["id"] != order_id]
            if not self._sells[symbol]:
                self._sells.pop(symbol)
        return {"status": "CANCELED", "order_id": order_id}

    def close_position(self, symbol, dry_run=True):
        if symbol == self.fails_close_for:
            raise BrokerError("simulated: insufficient qty available for order")
        self.closed.append(symbol)
        self._positions = [p for p in self._positions
                           if p["symbol"] != symbol]
        return {"status": "CLOSE_SUBMITTED", "order_id": "c-" + symbol}

    def submit_protective_stop(self, symbol, quantity, stop_price,
                               dry_run=True):
        self.stops_submitted.append((symbol, quantity, round(stop_price, 4)))
        self._sells.setdefault(symbol, []).append({
            "id": "s-" + symbol, "symbol": symbol, "side": "sell",
            "type": "stop", "quantity": quantity, "stop_price": stop_price,
            "time_in_force": "gtc", "client_order_id": "t"})
        return {"id": "s-" + symbol, "status": "accepted"}

    def submit_notional_buy(self, symbol, notional, *a, **k):
        # Cash parking. Real production behaviour, so the double accepts it
        # and records it rather than asserting - the tests below are about
        # stop protection, and a double that refuses a legitimate call would
        # fail for the wrong reason.
        self.parked.append((symbol, round(float(notional), 2)))
        return {"status": "SUBMITTED_TO_PAPER_ACCOUNT", "order_id": "p1"}

    def submit_reviewed_candidate(self, *a, **k):
        self.entries.append(a[0] if a else None)
        return {"status": "SUBMITTED_TO_PAPER_ACCOUNT", "order_id": "e1"}


def position(symbol, quantity, entry, last):
    return {"symbol": symbol, "quantity": quantity,
            "average_entry_price": entry, "market_value": quantity * last,
            "unrealized_pnl": (last - entry) * quantity}


class AFailingCloseCannotStripAnotherPositionsStop(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        # Universe of two. BAD exits and its close fails; GOOD is held and
        # must still be protected in the same cycle.
        self.config = AutoTradeConfig(
            universe=("BAD", "GOOD"), dry_run=False,
            require_market_open=False, entry_window_minutes=None,
            state_file=Path(self._tmp.name) / "state.json",
            audit_log=Path(self._tmp.name) / "audit.jsonl",
            entry_rule="trend", broker_retries=1)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, fails_for):
        # BAD is far below its stop so the trend rule closes it; GOOD sits
        # comfortably above its own.
        series = {"BAD": bars([100.0] * 40 + [60.0]),
                  "GOOD": bars([100.0] * 40 + [105.0])}
        broker = OneFailingCloseBroker(
            [position("BAD", 10, 100.0, 60.0),
             position("GOOD", 10, 100.0, 105.0)],
            fails_close_for=fails_for)
        # Both positions already carry a resting stop, as they would live.
        for symbol in ("BAD", "GOOD"):
            broker._sells[symbol] = [{
                "id": "old-" + symbol, "symbol": symbol, "side": "sell",
                "type": "stop", "quantity": 10, "stop_price": 1.0,
                "time_in_force": "gtc", "client_order_id": "old"}]
        result = run_once(self.config, policy=RiskPolicy(), costs=CostModel(),
                          broker=broker, bars_by_symbol=series)
        return broker, result

    def events(self, broker):
        import json
        path = self.config.audit_log
        if not path.exists():
            return []
        return [json.loads(l) for l in
                path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_the_cycle_completes_instead_of_raising(self):
        broker, result = self._run(fails_for="BAD")
        self.assertIsInstance(result, dict)
        self.assertNotEqual(result.get("status"), "halted")

    def test_the_failure_is_logged_as_exit_failed(self):
        broker, _ = self._run(fails_for="BAD")
        names = [e["event"] for e in self.events(broker)]
        self.assertIn("exit_FAILED", names)
        self.assertNotIn("exit", [e["event"] for e in self.events(broker)
                                  if e["detail"].get("symbol") == "BAD"])

    def test_the_other_position_still_gets_its_stop_this_cycle(self):
        """The regression. GOOD must be protected despite BAD failing."""
        broker, _ = self._run(fails_for="BAD")
        protected = {s for s, _q, _p in broker.stops_submitted}
        self.assertIn("GOOD", protected)

    def test_the_failing_position_is_reprotected_in_the_same_cycle(self):
        """close_out cancels the resting sells before it fails."""
        broker, _ = self._run(fails_for="BAD")
        protected = {s for s, _q, _p in broker.stops_submitted}
        self.assertIn("BAD", protected)

    def test_the_stop_level_is_still_known_after_the_failure(self):
        """The stop memory must not be popped on the failure path."""
        import json
        broker, _ = self._run(fails_for="BAD")
        state = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertIn("BAD", state.get("stops", {}))

    def test_state_is_still_written_when_a_close_fails(self):
        broker, _ = self._run(fails_for="BAD")
        self.assertTrue(self.config.state_file.exists())

    def test_a_clean_cycle_still_exits_normally(self):
        """The guard must not swallow a working close."""
        broker, _ = self._run(fails_for=None)
        self.assertIn("BAD", broker.closed)
        names = [e["event"] for e in self.events(broker)]
        self.assertIn("exit", names)
        self.assertNotIn("exit_FAILED", names)


class TheExitRecordSaysWhereItsNumberCameFrom(unittest.TestCase):
    """The recorded P&L is the pre-fill mark, and must say so."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.config = AutoTradeConfig(
            universe=("BAD",), dry_run=False, require_market_open=False,
            entry_window_minutes=None,
            state_file=Path(self._tmp.name) / "state.json",
            audit_log=Path(self._tmp.name) / "audit.jsonl",
            entry_rule="trend", broker_retries=1)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_exit_event_labels_its_pnl_basis(self):
        import json
        broker = OneFailingCloseBroker([position("BAD", 10, 100.0, 60.0)])
        run_once(self.config, policy=RiskPolicy(), costs=CostModel(),
                 broker=broker,
                 bars_by_symbol={"BAD": bars([100.0] * 40 + [60.0])})
        rows = [json.loads(l) for l in
                self.config.audit_log.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        exits = [r for r in rows if r["event"] == "exit"]
        self.assertEqual(len(exits), 1)
        self.assertIn("realized_pnl_basis", exits[0]["detail"])
        self.assertIn("before the fill",
                      exits[0]["detail"]["realized_pnl_basis"])


class PaperOnly(unittest.TestCase):
    def test_the_default_endpoint_is_paper(self):
        from event_aware_trader.broker import PAPER_ENDPOINT, BrokerConfig
        self.assertEqual(BrokerConfig("k", "s").endpoint, PAPER_ENDPOINT)

    def test_the_live_endpoint_is_refused_at_construction(self):
        from event_aware_trader.broker import (AlpacaPaperBroker, BrokerConfig,
                                               LIVE_ENDPOINT)
        with self.assertRaises(BrokerError):
            AlpacaPaperBroker(BrokerConfig("k", "s", endpoint=LIVE_ENDPOINT))

    def test_an_unknown_endpoint_fails_closed(self):
        from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig
        for endpoint in ("https://api.example.com", "",
                         "https://paper-api.alpaca.markets.evil.com"):
            with self.assertRaises(BrokerError):
                AlpacaPaperBroker(BrokerConfig("k", "s", endpoint=endpoint))

    def test_a_trailing_slash_and_case_do_not_defeat_the_check(self):
        from event_aware_trader.broker import AlpacaPaperBroker, BrokerConfig
        with self.assertRaises(BrokerError):
            AlpacaPaperBroker(BrokerConfig(
                "k", "s", endpoint="https://API.Alpaca.Markets/"))


class TheLearnedModelIsInert(unittest.TestCase):
    """Launch requirement: the model must not gate any trade tomorrow."""

    def test_the_live_model_floor_is_zero(self):
        self.assertEqual(AutoTradeConfig().live_model_floor, 0.0)

    def test_the_shipped_model_file_is_unproven_and_cannot_veto(self):
        """The real file the live loop loads, not a stand-in."""
        from event_aware_trader.trade_learning import load_model, model_vetoes
        path = AutoTradeConfig().model_file
        if not Path(path).exists():
            self.skipTest("no model file on disk; nothing can veto")
        model = load_model(Path(path))
        self.assertFalse(model.is_usable, model.status)
        vetoed, _p = model_vetoes(model, {"score": 50.0}, 50.0)
        self.assertFalse(vetoed)


if __name__ == "__main__":
    unittest.main()
