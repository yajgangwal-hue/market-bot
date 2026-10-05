"""Adaptive exits in the live loop (EXP-0055), driven through run_once.

The take profit is an extra exit: when the BROKER's mark reaches the level,
the position leaves through close_out - the same cancel-then-close path as
every other exit. The stop, the bounce exit and the holding cap keep
precedence. New entries carry the level from the start; positions opened
earlier get one, once, from the stop they were opened with.

Entry 100 behind a stop at 92: ATR (100 - 92) / 2.5 = 3.2, so the shipped
2.5-ATR take profit sits at 108.0.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import event_aware_trader.autotrade as autotrade
from event_aware_trader.adaptive_exits import AdaptiveExitConfig
from event_aware_trader.autotrade import AutoTradeConfig, run_once
from event_aware_trader.mean_reversion import should_exit
from event_aware_trader.types import Bar
from fake_broker import FakeBroker
from tests.test_take_profit import oversold_in_an_uptrend

SYMBOL = "TJX"
ENTRY, STOP, LEVEL = 100.0, 92.0, 108.0
OPENED = "2026-09-01T19:45:00+00:00"


def _bars(closes, start=datetime(2026, 1, 1, tzinfo=timezone.utc)):
    return [Bar(timestamp=start + timedelta(days=i), open=c, high=c * 1.005,
                low=c * 0.995, close=c, volume=5_000_000) for i, c in enumerate(closes)]


def _quiet():
    """Above its 200-day average after a pullback: RSI well under 60, no stop."""
    return _bars([80.0 + 0.1 * i for i in range(240)] + [104.0 - 0.5 * i for i in range(6)])


def _recovered():
    """RSI far over 60 - the frozen rule wants out on its own."""
    closes = [80.0 + 0.05 * i for i in range(240)]
    return _bars(closes + [closes[-1] * (1 + 0.02 * (i + 1)) for i in range(12)])


def _broker(mark):
    broker = FakeBroker(equity=100_000.0, cash=700.0, positions=[{
        "symbol": SYMBOL, "quantity": 151.0, "average_entry_price": ENTRY,
        "market_value": 151.0 * mark, "current_price": mark,
        "unrealized_pnl": 151.0 * (mark - ENTRY)}])
    broker._init_stops()
    broker.open_sells[SYMBOL] = [{"id": "stop-live", "type": "stop", "time_in_force": "gtc",
                                  "stop_price": STOP, "quantity": 151.0, "status": "held"}]
    return broker


class Harness:
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._todays = autotrade._todays_bars
        autotrade._todays_bars = lambda config, symbols: {}     # no network, ever
        self._daily = autotrade.daily_bars

    def tearDown(self):
        autotrade._todays_bars = self._todays
        autotrade.daily_bars = self._daily
        self.tmp.cleanup()

    def config(self, stop_state=None, **overrides):
        state = self.dir / "state.json"
        remembered = {"current": STOP, "initial": STOP, "opened_at_ts": OPENED,
                      "opened_bars": 100, "opened_days": 100}
        remembered.update(stop_state or {})
        state.write_text(json.dumps({"stops": {SYMBOL: remembered}}), encoding="utf-8")
        # These tests pin EXP-0055/56's fixed 2.5-ATR target, which
        # take_profit_mode="atr" keeps. The bounce price (EXP-0057, the
        # default) is pinned in test_bounce_take_profit.py.
        settings = dict(dry_run=False, universe=(SYMBOL,), asset_class="equity",
                        adaptive_exits=AdaptiveExitConfig(take_profit_mode="atr"),
                        entry_rule="mean_reversion", cash_parking_symbol=None,
                        reserved_fraction=0.0, require_market_open=False,
                        entry_window_minutes=None, model_file=None, live_model_file=None,
                        audit_log=self.dir / "audit.jsonl", state_file=state)
        settings.update(overrides)
        return AutoTradeConfig(**settings)

    def run_cycle(self, config, broker, series):
        autotrade.daily_bars = lambda symbol, *a, **k: series
        return run_once(config, broker=broker, bars_by_symbol={SYMBOL: series})

    def audit(self, event):
        path = self.dir / "audit.jsonl"
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return [r["detail"] for r in rows if r["event"] == event]

    def state(self):
        return json.loads((self.dir / "state.json").read_text(encoding="utf-8"))


class TakeProfitInTheLiveLoop(Harness, unittest.TestCase):
    def test_the_fixture_does_not_exit_on_its_own(self):
        config = self.config()
        self.assertIsNone(should_exit(_quiet(), ENTRY, STOP, 2, autotrade._mr(config),
                                      entry_time=OPENED))

    def test_a_mark_at_the_level_sells_through_close_out(self):
        broker = _broker(108.5)
        self.run_cycle(self.config(), broker, _quiet())
        self.assertEqual(broker.closed, [(SYMBOL, False)])
        kinds = [event[0] for event in broker.events]
        self.assertLess(kinds.index("cancel"), kinds.index("close"))
        self.assertEqual([e["exit_reason"] for e in self.audit("exit")], ["take_profit"])

    def test_a_mark_below_the_level_holds_and_reports_it(self):
        broker = _broker(107.5)
        self.run_cycle(self.config(), broker, _quiet())
        self.assertEqual(broker.closed, [])
        [hold] = self.audit("hold")
        self.assertAlmostEqual(hold["take_profit"], LEVEL)
        remembered = self.state()["stops"][SYMBOL]
        self.assertAlmostEqual(remembered["take_profit"], LEVEL)
        self.assertEqual(remembered["take_profit_atr"], 2.5)

    def test_a_remembered_level_is_kept_as_it_is(self):
        broker = _broker(106.0)
        self.run_cycle(self.config({"take_profit": 105.0}), broker, _quiet())
        self.assertEqual([e["exit_reason"] for e in self.audit("exit")], ["take_profit"])

    def test_a_learned_multiple_sets_the_level_of_a_position_without_one(self):
        (self.dir / "adaptive-exits.json").write_text(
            json.dumps({"take_profit_atr": 3.0, "stop_atr": 2.5}), encoding="utf-8")
        broker = _broker(109.0)
        self.run_cycle(self.config(), broker, _quiet())
        self.assertEqual(broker.closed, [])
        [hold] = self.audit("hold")
        self.assertAlmostEqual(hold["take_profit"], 100.0 + 3.0 * 3.2)

    def test_switched_off_there_is_no_take_profit(self):
        broker = _broker(150.0)
        self.run_cycle(self.config(adaptive_exits=None), broker, _quiet())
        self.assertEqual(broker.closed, [])
        [hold] = self.audit("hold")
        self.assertIsNone(hold["take_profit"])

    def test_the_frozen_rule_keeps_precedence(self):
        broker = _broker(130.0)
        self.run_cycle(self.config(), broker, _recovered())
        self.assertEqual([e["exit_reason"] for e in self.audit("exit")], ["reverted"])


class ANewEntryCarriesItsLevels(Harness, unittest.TestCase):
    def enter(self, learned=None):
        if learned:
            (self.dir / "adaptive-exits.json").write_text(json.dumps(learned), encoding="utf-8")
        state = self.dir / "state.json"
        state.write_text("{}", encoding="utf-8")
        config = AutoTradeConfig(dry_run=True, universe=(SYMBOL,), asset_class="equity",
                                 adaptive_exits=AdaptiveExitConfig(take_profit_mode="atr"),
                                 entry_rule="mean_reversion", cash_parking_symbol=None,
                                 reserved_fraction=0.0, require_market_open=False,
                                 entry_window_minutes=None, model_file=None,
                                 live_model_file=None, audit_log=self.dir / "audit.jsonl",
                                 state_file=state)
        broker = FakeBroker(equity=100_000.0)
        self.run_cycle(config, broker, oversold_in_an_uptrend())
        [entry] = self.audit("entry")
        return entry, self.state()["stops"][SYMBOL], broker

    def test_the_entry_records_its_take_profit_from_its_own_atr(self):
        entry, remembered, broker = self.enter()
        self.assertTrue(broker.submitted)
        atr = (entry["entry_reference"] - entry["stop"]) / 2.5
        self.assertAlmostEqual(entry["take_profit"], entry["entry_reference"] + 2.5 * atr)
        self.assertEqual((entry["take_profit_atr"], entry["stop_atr"]), (2.5, 2.5))
        self.assertAlmostEqual(remembered["take_profit"], entry["take_profit"])

    def test_a_learned_stop_multiple_places_the_stop(self):
        frozen, _, _ = self.enter()
        self.tearDown(); self.setUp()
        learned, remembered, _ = self.enter({"take_profit_atr": 2.5, "stop_atr": 3.0})
        self.assertAlmostEqual(learned["entry_reference"], frozen["entry_reference"])
        self.assertAlmostEqual((learned["entry_reference"] - learned["stop"])
                               / (frozen["entry_reference"] - frozen["stop"]), 3.0 / 2.5)
        self.assertEqual(learned["stop_atr"], 3.0)
        self.assertEqual(remembered["stop_atr"], 3.0)


if __name__ == "__main__":
    unittest.main()
