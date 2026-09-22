"""SPEC-0001 v1.0.0 C-19: live rule exits must see the session in progress.

THE DEFECT THIS PINS. `run_once` section 1 read `daily_bars(symbol)`
alone. The daily price files deliberately exclude the session in
progress, so the exit rule evaluated RSI on closes through D-1 and
could only act on a condition one session after it became true. The
entry path already appended today's forming bar; the exit path did not.

C-1 (normative): on session D the strategy may use information through
the current moment of D, with the in-progress price standing in for
today's close, acting on the cycle the condition first becomes true.

C-19: feeding the exit path a series that includes D corrects
`bars_held` in the same stroke, because the expression counts bars
after the entry date and today becomes one of them. A second,
independent `bars_held` adjustment would double-count - these tests
pin that it is NOT needed.

Nothing here changes a threshold. rsi_exit stays 60, max_holding_bars
stays 20, the stop stays where it was placed.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import event_aware_trader.autotrade as autotrade
from event_aware_trader.autotrade import AutoTradeConfig, _with_today, run_once
from event_aware_trader.mean_reversion import MeanReversionConfig, should_exit
from event_aware_trader.types import Bar
from fake_broker import FakeBroker

_TMP = TemporaryDirectory()
SYMBOL = "TJX"
ENTRY = 100.0
STOP = 50.0                      # far below; the stop must never be what fires
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
MR = MeanReversionConfig()


def _bar(day_index, close):
    return Bar(timestamp=START + timedelta(days=day_index), open=close,
               high=close * 1.005, low=close * 0.995, close=close,
               volume=5_000_000)


def _flat_series(n=260):
    """A gently declining series: RSI stays well under rsi_exit."""
    return [_bar(i, 120.0 - 0.05 * i) for i in range(n)]


def _recovery_bar(series, jump=0.25):
    """One forming bar big enough to carry RSI over rsi_exit."""
    last = series[-1]
    close = last.close * (1.0 + jump)
    return Bar(timestamp=last.timestamp + timedelta(days=1), open=last.close,
               high=close * 1.01, low=last.close * 0.999, close=close,
               volume=5_000_000)


class A_CurrentSessionRsiVisibility(unittest.TestCase):
    """D-1 does not satisfy the exit; D does; the decision must use D."""

    def setUp(self):
        self.through_d_minus_1 = _flat_series()
        self.today = _recovery_bar(self.through_d_minus_1)
        self.with_d = self.through_d_minus_1 + [self.today]

    def test_the_prior_session_alone_does_NOT_trigger_the_exit(self):
        self.assertIsNone(should_exit(self.through_d_minus_1, ENTRY, STOP,
                                      bars_held=3, config=MR))

    def test_the_current_session_DOES_trigger_the_exit(self):
        self.assertEqual(should_exit(self.with_d, ENTRY, STOP,
                                     bars_held=3, config=MR), "reverted")

    def test_the_difference_is_the_in_progress_bar_alone(self):
        """Same rule, same thresholds - only the visible session differs."""
        self.assertNotEqual(
            should_exit(self.through_d_minus_1, ENTRY, STOP, 3, MR),
            should_exit(self.with_d, ENTRY, STOP, 3, MR))


class A2_TheLiveExitPathUsesTodaysBar(unittest.TestCase):
    """The wiring, not just the rule: run_once must append today's bar."""

    def _run(self, todays_bar):
        series = _flat_series()
        broker = FakeBroker(
            equity=100_000.0, cash=700.0,
            positions=[{"symbol": SYMBOL, "quantity": 151.0,
                        "average_entry_price": ENTRY,
                        "market_value": 151.0 * 120.0,
                        "current_price": 120.0,
                        "unrealized_pnl": 0.0}])
        broker._init_stops()
        broker.open_sells[SYMBOL] = [{
            "id": "stop-live", "type": "stop", "time_in_force": "gtc",
            "stop_price": STOP, "quantity": 151.0, "status": "held"}]
        # Entered TEN sessions ago, so bars_held stays under
        # max_holding_bars and the only rule that can fire is the RSI exit.
        # An older entry would trip the 20-session cap and the control would
        # pass for the wrong reason - which is exactly what the first draft
        # of this test did.
        opened = series[-10].timestamp.isoformat()
        state = Path(_TMP.name) / "state-a2.json"
        state.write_text(json.dumps({"stops": {SYMBOL: {
            "current": STOP, "initial": STOP,
            "opened_at_ts": opened}}}), encoding="utf-8")
        config = AutoTradeConfig(
            dry_run=True, universe=(SYMBOL,), asset_class="equity",
            entry_rule="mean_reversion", cash_parking_symbol=None,
            reserved_fraction=0.0, require_market_open=False,
            entry_window_minutes=None, model_file=None, live_model_file=None,
            audit_log=Path(_TMP.name) / "audit-a2.jsonl", state_file=state)
        real_daily, real_todays = autotrade.daily_bars, autotrade._todays_bars
        autotrade.daily_bars = lambda s, *a, **k: series
        autotrade._todays_bars = lambda c, syms: (
            {SYMBOL: todays_bar} if todays_bar is not None else {})
        try:
            result = run_once(config, broker=broker,
                              bars_by_symbol={SYMBOL: series})
        finally:
            autotrade.daily_bars, autotrade._todays_bars = (real_daily,
                                                            real_todays)
        return [a for a in result["actions"] if a["event"] == "exit"]

    def test_without_todays_bar_the_rule_does_not_fire(self):
        """The old behaviour, kept as the control."""
        self.assertEqual(self._run(None), [])

    def test_with_todays_bar_the_rule_fires_on_this_cycle(self):
        exits = self._run(_recovery_bar(_flat_series()))
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["detail"]["symbol"], SYMBOL)

    def test_the_exit_path_asks_only_about_held_symbols(self):
        """Scoped to holdings, so the universe fetch is untouched."""
        seen = {}
        series = _flat_series()
        real_daily, real_todays = autotrade.daily_bars, autotrade._todays_bars
        autotrade.daily_bars = lambda s, *a, **k: series
        def _record(_config, syms):
            seen["syms"] = list(syms)
            return {}
        autotrade._todays_bars = _record
        broker = FakeBroker(
            equity=100_000.0, cash=700.0,
            positions=[{"symbol": SYMBOL, "quantity": 151.0,
                        "average_entry_price": ENTRY,
                        "market_value": 151.0 * 120.0,
                        "current_price": 120.0, "unrealized_pnl": 0.0}])
        broker._init_stops()
        state = Path(_TMP.name) / "state-a3.json"
        state.write_text(json.dumps({"stops": {}}), encoding="utf-8")
        config = AutoTradeConfig(
            dry_run=True, universe=(SYMBOL, "AAPL", "MSFT"),
            asset_class="equity", entry_rule="mean_reversion",
            cash_parking_symbol=None, reserved_fraction=0.0,
            require_market_open=False, entry_window_minutes=None,
            model_file=None, live_model_file=None,
            audit_log=Path(_TMP.name) / "audit-a3.jsonl", state_file=state)
        try:
            run_once(config, broker=broker, bars_by_symbol={SYMBOL: series})
        finally:
            autotrade.daily_bars, autotrade._todays_bars = (real_daily,
                                                            real_todays)
        self.assertEqual(seen.get("syms"), [SYMBOL])


class B_BarsHeldSemantics(unittest.TestCase):
    """SPEC-0001 §5 / C-15: bars_held counts sessions strictly after entry."""

    def _bars_held(self, series, entry_day):
        """The expression run_once uses, applied to the given series."""
        return sum(1 for bar in series if bar.timestamp.date() > entry_day)

    def test_the_series_correction_alone_produces_the_canonical_count(self):
        """C-19: no second adjustment is needed - or permitted."""
        series = _flat_series(260)
        entry_day = series[-21].timestamp.date()       # entry on E
        through_d_minus_1 = series[:-1]                # file ends E+19
        todays = series[-1]                            # forming bar = E+20

        stale = self._bars_held(through_d_minus_1, entry_day)
        corrected = self._bars_held(_with_today(through_d_minus_1, todays),
                                    entry_day)
        self.assertEqual(stale, 19)                    # the defect
        self.assertEqual(corrected, 20)                # SPEC-0001 §5

    def test_the_cap_fires_on_E_plus_20_not_E_plus_21(self):
        series = _flat_series(260)
        entry_day = series[-21].timestamp.date()
        corrected = _with_today(series[:-1], series[-1])
        held = self._bars_held(corrected, entry_day)
        self.assertEqual(held, MR.max_holding_bars)
        self.assertEqual(should_exit(corrected, ENTRY, STOP, held, MR),
                         "time")

    def test_one_session_earlier_the_cap_does_not_fire(self):
        series = _flat_series(259)
        entry_day = series[-21].timestamp.date()
        corrected = _with_today(series[:-1], series[-1])
        held = self._bars_held(corrected, entry_day)
        self.assertEqual(held, 20)
        # and at E+19 it must not fire
        earlier = series[:-1]
        held_earlier = self._bars_held(earlier, entry_day)
        self.assertEqual(held_earlier, 19)
        self.assertIsNone(should_exit(earlier, ENTRY, STOP, held_earlier, MR))

    def test_the_entry_session_itself_is_never_counted(self):
        series = _flat_series(260)
        entry_day = series[-1].timestamp.date()        # entry today
        self.assertEqual(self._bars_held(series, entry_day), 0)


class C_NoFutureLeakage(unittest.TestCase):
    """Only the session in progress may be added - never anything later."""

    def test_a_bar_already_present_is_not_appended_twice(self):
        series = _flat_series()
        self.assertEqual(len(_with_today(series, series[-1])), len(series))

    def test_a_stale_bar_cannot_overwrite_a_newer_series(self):
        """A bar dated at or before the series end is refused."""
        series = _flat_series()
        older = series[-5]
        self.assertEqual(_with_today(series, older), series)

    def test_an_absent_bar_leaves_the_series_untouched(self):
        series = _flat_series()
        self.assertIs(_with_today(series, None), series)

    def test_only_one_session_is_ever_added(self):
        series = _flat_series()
        todays = _recovery_bar(series)
        self.assertEqual(len(_with_today(series, todays)), len(series) + 1)

    def test_the_appended_bar_is_the_current_session_not_a_future_one(self):
        """The decision may see D. It may never see D+1."""
        series = _flat_series()
        todays = _recovery_bar(series)
        out = _with_today(series, todays)
        self.assertEqual(out[-1].timestamp, todays.timestamp)
        self.assertTrue(all(b.timestamp <= todays.timestamp for b in out))

    def test_the_in_progress_close_is_a_proxy_not_a_settled_close(self):
        """C-1: the in-progress price stands in for today's close.

        Two different in-progress prices on the same session must be able
        to produce two different decisions - that is what 'acting on the
        cycle the condition first becomes true' means.
        """
        series = _flat_series()
        early = Bar(timestamp=series[-1].timestamp + timedelta(days=1),
                    open=series[-1].close, high=series[-1].close,
                    low=series[-1].close * 0.99,
                    close=series[-1].close * 0.995, volume=1_000_000)
        late = _recovery_bar(series)
        self.assertIsNone(should_exit(_with_today(series, early), ENTRY,
                                      STOP, 3, MR))
        self.assertEqual(should_exit(_with_today(series, late), ENTRY, STOP,
                                     3, MR), "reverted")


class D_ThresholdsUntouched(unittest.TestCase):
    """C-3: this correction governs timing and observability only."""

    def test_no_strategy_parameter_moved(self):
        self.assertEqual(MR.rsi_entry, 35.0)
        self.assertEqual(MR.rsi_exit, 60.0)
        self.assertEqual(MR.max_atr_fraction, 0.035)
        self.assertEqual(MR.stop_atr_multiple, 2.5)
        self.assertEqual(MR.max_holding_bars, 20)

    def test_the_frozen_fingerprint_is_unchanged(self):
        from event_aware_trader.forward import frozen_fingerprint
        self.assertEqual(
            frozen_fingerprint(),
            "da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b")


if __name__ == "__main__":
    unittest.main()
