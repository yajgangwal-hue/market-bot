"""Does the LIVE LOOP actually close a protected position, or only log that it did?

`test_exit_cancels_stop.py` documents this hazard and pins the correct
sequence. Every one of its five tests drives the broker double directly -
cancel, then close - and none of them calls `run_once`. So it proved the
double behaves correctly and never proved that `autotrade` does.

It does not. Found on 2026-09-11:

    broker.cancel_order(oid)          # exit path
    broker.cancel_order(oid, dry_run=config.dry_run)   # reconciler

`cancel_order` defaults to `dry_run=True`. The bare call cancelled as a DRY
RUN, so the broker returned DRY_RUN_NOT_SUBMITTED and left the stop resting;
the shares stayed reserved; and the close that followed was refused:

    HTTP 403 DELETE /v2/positions/EWY
    {"available":"0","held_for_orders":"106","message":"insufficient qty ..."}

Which is in the live audit log, on 2026-09-08, exactly once - the only time
this path has ever run in production. The cancel-before-close fix made that
day never worked. It logged a cancellation that had not happened.

The reason no test caught it is the same reason the fractional-stop bug
shipped: the double was more permissive than the broker. `FakeBroker.
cancel_order` removed the order from `open_sells` whether or not it was a dry
run, and only varied the status string - so in every test a dry-run cancel
freed the shares and the close succeeded. That is corrected alongside this
file.

The consequence while it was live: a position could only ever be closed by its
own stop. Every RSI-recovery exit and every holding-cap exit was silently
disabled from the moment the protective stop went on - and the decade backtest
exits on RSI recovery far more often than on the stop, so this removes the
exit the measured edge is mostly made of.

These tests go through `run_once`.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import event_aware_trader.autotrade as autotrade
from event_aware_trader.autotrade import AutoTradeConfig, run_once
from event_aware_trader.types import Bar
from fake_broker import FakeBroker

_TMP = TemporaryDirectory()

SYMBOL = "TJX"
ENTRY = 100.0
STOP = 92.0


def _recovered_series():
    """Daily bars that end well above their 200-day average, RSI far over 60.

    The exit rule leaves on RSI recovery, so the fixture has to produce one -
    a series that merely exists would test nothing.
    """
    closes = [80.0 + 0.05 * i for i in range(240)]
    closes += [closes[-1] * (1 + 0.02 * (i + 1)) for i in range(12)]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Bar(timestamp=start + timedelta(days=i), open=c, high=c * 1.005,
                low=c * 0.995, close=c, volume=5_000_000)
            for i, c in enumerate(closes)]


def _protected_broker():
    broker = FakeBroker(
        equity=100_000.0, cash=700.0,
        positions=[{"symbol": SYMBOL, "quantity": 151.0,
                    "average_entry_price": ENTRY,
                    "market_value": 151.0 * 130.0,
                    "current_price": 130.0,
                    "unrealized_pnl": 151.0 * 30.0}],
    )
    broker._init_stops()
    # The position carries its protective stop, which is what reserves the
    # shares. This is the state EVERY live position is in.
    broker.open_sells[SYMBOL] = [{
        "id": "stop-live", "type": "stop", "time_in_force": "gtc",
        "stop_price": STOP, "quantity": 151.0, "status": "held",
    }]
    return broker


def _config(**overrides):
    state = Path(_TMP.name) / "state.json"
    state.write_text(json.dumps({
        "stops": {SYMBOL: {
            "current": STOP, "initial": STOP,
            "opened_at_ts": "2026-08-01T14:00:00+00:00",
            "opened_bars": 100, "opened_days": 100,
        }},
    }), encoding="utf-8")
    settings = dict(
        dry_run=False, universe=(SYMBOL,), asset_class="equity",
        entry_rule="mean_reversion", cash_parking_symbol=None,
        reserved_fraction=0.0, require_market_open=False,
        entry_window_minutes=None, model_file=None, live_model_file=None,
        audit_log=Path(_TMP.name) / "audit.jsonl", state_file=state)
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _run(config, broker):
    series = _recovered_series()
    daily = autotrade.daily_bars
    autotrade.daily_bars = lambda symbol, *a, **k: series
    try:
        return run_once(config, broker=broker, bars_by_symbol={SYMBOL: series})
    finally:
        autotrade.daily_bars = daily


class TheFixtureMustActuallyExit(unittest.TestCase):
    def test_the_rule_wants_out_of_this_position(self):
        # If the fixture does not trigger an exit, every assertion below is
        # vacuously true and the file is worthless.
        from event_aware_trader.mean_reversion import should_exit

        config = _config()
        series = _recovered_series()
        reason = should_exit(series, ENTRY, STOP, 25, autotrade._mr(config),
                             entry_time="2026-08-01T14:00:00+00:00")
        self.assertIsNotNone(reason, "the fixture produces no exit signal")


class ClosingAProtectedPositionTests(unittest.TestCase):
    def test_the_position_is_actually_closed(self):
        broker = _protected_broker()
        _run(_config(), broker)
        self.assertEqual([s for s, dry in broker.closed], [SYMBOL],
                         "the loop did not close the position")
        self.assertEqual([dry for _s, dry in broker.closed], [False],
                         "the close was submitted as a dry run")

    def test_the_stop_is_cancelled_for_real_first(self):
        # The whole bug in one assertion. A dry-run cancel returns
        # DRY_RUN_NOT_SUBMITTED and leaves the shares reserved, so the close
        # that follows is refused - and the loop reports a cancellation that
        # never happened.
        broker = _protected_broker()
        _run(_config(), broker)
        self.assertEqual(broker.open_sell_orders().get(SYMBOL, []), [],
                         "the protective stop was not really cancelled, so "
                         "the shares stayed reserved and the close would be "
                         "refused with HTTP 403")

    def test_cancel_happens_before_close(self):
        broker = _protected_broker()
        _run(_config(), broker)
        kinds = [event[0] for event in broker.events]
        self.assertIn("cancel", kinds)
        self.assertIn("close", kinds)
        self.assertLess(kinds.index("cancel"), kinds.index("close"))

    def test_an_exit_is_recorded_only_when_one_happened(self):
        broker = _protected_broker()
        result = _run(_config(), broker)
        self.assertEqual(result.get("exits"), 1)

    def test_a_dry_run_neither_cancels_nor_closes(self):
        # A dry run that stripped the protective stop would leave a real
        # position unprotected to simulate an exit it is not going to make.
        broker = _protected_broker()
        _run(_config(dry_run=True), broker)
        self.assertEqual(broker.canceled, [])
        self.assertEqual(len(broker.open_sell_orders().get(SYMBOL, [])), 1)


class CloseOutIsTheProductionFunctionTests(unittest.TestCase):
    """`close_out` is what both run_once and the live verification drive.

    It was extracted so that the live check in scripts/verify_sell_path.py
    exercises the SAME code the bot runs, rather than a hand-written copy of
    the sequence. A copy is what test_exit_cancels_stop.py had, and a copy
    cannot notice when the original stops matching it.
    """

    def test_run_once_routes_its_close_through_close_out(self):
        calls = []
        original = autotrade.close_out

        def spy(config, broker, symbol, actions):
            calls.append(symbol)
            return original(config, broker, symbol, actions)

        autotrade.close_out = spy
        try:
            _run(_config(), _protected_broker())
        finally:
            autotrade.close_out = original
        self.assertEqual(calls, [SYMBOL],
                         "run_once no longer closes through close_out, so the "
                         "live verification would be testing a different path")

    def test_close_out_alone_cancels_then_closes(self):
        broker = _protected_broker()
        actions = []
        result = autotrade.close_out(_config(), broker, SYMBOL, actions)
        self.assertEqual(result["status"], "CLOSE_SUBMITTED")
        self.assertEqual(broker.open_sell_orders().get(SYMBOL, []), [])
        kinds = [event[0] for event in broker.events]
        self.assertLess(kinds.index("cancel"), kinds.index("close"))


class ALiveExitRecordsItsOwnQuality(unittest.TestCase):
    """The exit event carries what a simulated ClosedTrade carries.

    `captured` and `gave_back` are how the simulator scores exits. Without the
    same numbers on live exits, record.py can report a win rate and nothing
    about whether the winners were left too early or the losers held too
    long - and the learning loop has outcomes but no exit errors.
    """

    def test_the_exit_event_carries_captured_and_gave_back(self):
        broker = _protected_broker()
        result = _run(_config(), broker)
        exits = [a for a in result.get("actions", []) if a.get("event") == "exit"]
        self.assertEqual(len(exits), 1)
        detail = exits[0]["detail"]
        for key in ("highest_high", "lowest_low", "captured", "gave_back"):
            self.assertIn(key, detail, key + " missing from the live exit record")
        # The fixture rallied from 100 to ~130 and exits at the last close, so
        # the exit kept most of what was available and gave back little.
        self.assertGreater(detail["highest_high"], detail["entry_price"])
        self.assertGreaterEqual(detail["captured"], 0.0)
        self.assertGreaterEqual(detail["gave_back"], 0.0)
        self.assertLessEqual(detail["lowest_low"], detail["highest_high"])



# ---------------------------------------------------------------------------
# SPEC-0001 C-19 made run_once section 1 fetch today's bar for HELD symbols.
# Without this stub these tests would reach the live vendor and append a REAL
# current-session bar to a synthetic fixture, so the outcome would depend on
# what the market did today. Returning {} reproduces exactly the series these
# tests were written against. A test that needs a specific bar still patches
# `_todays_bars` itself and restores to this stub.
# ---------------------------------------------------------------------------
import event_aware_trader.autotrade as _spec0001_autotrade

_spec0001_real_todays = None


def setUpModule():
    global _spec0001_real_todays
    _spec0001_real_todays = _spec0001_autotrade._todays_bars
    _spec0001_autotrade._todays_bars = lambda _config, _symbols: {}


def tearDownModule():
    if _spec0001_real_todays is not None:
        _spec0001_autotrade._todays_bars = _spec0001_real_todays

if __name__ == "__main__":
    unittest.main()


class PositionsOpenedInTheClosingWindowGetADurableStop(unittest.TestCase):
    """The bracket's stop leg is time_in_force=day and dies at the close.

    _reconcile_protective_stops runs BEFORE entries, so a position opened in
    the 15:45 window had no cycle left to replace its expiring day-stop and
    sat naked overnight - across the gap that carries 73.6% of this
    strategy's return. Found live on 2026-09-15 (MDY, $19,425, no stop).
    """

    def test_reconcile_runs_again_after_an_entry(self):
        import inspect
        from event_aware_trader import autotrade
        source = inspect.getsource(autotrade.run_once)
        calls = source.count("_reconcile_protective_stops(config, broker, state, actions)")
        self.assertGreaterEqual(
            calls, 2,
            "run_once must reconcile stops AFTER entries as well as before, or a "
            "position opened in the closing window keeps only its day-stop")
        before = source.index("_reconcile_protective_stops(config, broker, state, actions)")
        entries = source.index("if entries_open:")
        after = source.rindex("_reconcile_protective_stops(config, broker, state, actions)")
        self.assertLess(before, entries, "the first pass must precede entries")
        self.assertGreater(after, entries, "the second pass must follow entries")

    def test_the_second_pass_is_skipped_on_a_dry_run(self):
        import inspect
        from event_aware_trader import autotrade
        source = inspect.getsource(autotrade.run_once)
        tail = source[source.index("2b. protect anything just opened"):]
        self.assertIn("if submitted and not config.dry_run:", tail)
