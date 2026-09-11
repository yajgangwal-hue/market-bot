"""Entering at the end of the session instead of the start of the next one.

The rule forms its signal from a completed daily bar and then fills at the
NEXT session's open, so the account is out of the market across exactly the
move it has just predicted. Measured across the decade's 710 trades, the gap
handed away that way is worth +0.1292% a trade - positive in both halves, and
larger in the recent one. Re-run end to end at matched friction it is worth
about +1.3 CAGR points with a slightly BETTER drawdown.

Nothing about the order changes: same name, same size, same stop, same
commission. Only the hour changes. That is what makes this the one improvement
found in this project that costs nothing to take - and also what makes it
dangerous, because a window on entries sits directly in the order path.

These tests pin the four things that would turn it into a loss:

  * a window on ENTRIES must never become a window on PROTECTION - exits and
    the stop reconciler have to keep running all day;
  * the window must be measured by the BROKER's clock, which knows half-days
    and holidays, and must refuse to act when it cannot read one;
  * inside the window the signal must include the session in progress. Filling
    at today's close on yesterday's information would pay the gap's price
    without reading the day that set it - worse than either design;
  * the window is not the daily loss guard, and must not report itself as one.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import (
    AutoTradeConfig, _minutes_to_close, _with_today, run_once)
from event_aware_trader.types import Bar
from fake_broker import FakeBroker

# Throwaway audit and state files. Tests that left these at their defaults
# once wrote 49 fabricated entries into the live audit log, which record.py
# reads back as fact.
_TMP = TemporaryDirectory()


def _config(**overrides):
    settings = dict(
        dry_run=True, universe=("SPY",), asset_class="equity",
        entry_rule="mean_reversion", cash_parking_symbol=None,
        reserved_fraction=0.0,
        audit_log=Path(_TMP.name) / "audit.jsonl",
        state_file=Path(_TMP.name) / "state.json")
    settings.update(overrides)
    return AutoTradeConfig(**settings)


def _bar(when, price=100.0):
    return Bar(timestamp=datetime(when.year, when.month, when.day,
                                  tzinfo=timezone.utc),
               open=price, high=price * 1.01, low=price * 0.99,
               close=price, volume=1_000_000)


class ClockBroker(FakeBroker):
    """A broker whose clock sits a chosen number of minutes from the close."""

    def __init__(self, minutes_left, **kwargs):
        super().__init__(**kwargs)
        self._left = minutes_left

    def clock(self):
        now = datetime(2026, 9, 11, 18, 0, tzinfo=timezone.utc)
        if self._left is None:
            return {"is_open": True, "timestamp": now.isoformat(),
                    "next_open": None, "next_close": "not a timestamp"}
        return {
            "is_open": True,
            "timestamp": now.isoformat(),
            "next_open": None,
            "next_close": (now + timedelta(minutes=self._left)).isoformat(),
        }


class MinutesToCloseTests(unittest.TestCase):
    def test_reads_the_brokers_own_clock(self):
        self.assertAlmostEqual(
            _minutes_to_close(ClockBroker(17.5).clock()), 17.5, places=6)

    def test_unparseable_close_is_unknown_not_zero(self):
        # None means "cannot tell". Returning 0.0 would read as "the close is
        # now" and would open the window on every broken clock.
        self.assertIsNone(_minutes_to_close(ClockBroker(None).clock()))

    def test_missing_clock_is_unknown(self):
        self.assertIsNone(_minutes_to_close(None))
        self.assertIsNone(_minutes_to_close({}))


class WithTodayTests(unittest.TestCase):
    def test_appends_the_session_in_progress(self):
        history = [_bar(datetime(2026, 9, 10))]
        today = _bar(datetime(2026, 9, 11), 105.0)
        merged = _with_today(history, today)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[-1].close, 105.0)

    def test_never_duplicates_a_day_the_file_already_has(self):
        # The daily file is refreshed once a cycle. If a refresh has already
        # landed today's bar, appending it again would feed the RSI the same
        # session twice and quietly shift every indicator that reads it.
        today = _bar(datetime(2026, 9, 11))
        history = [_bar(datetime(2026, 9, 10)), today]
        self.assertEqual(len(_with_today(history, today)), 2)

    def test_leaves_history_alone_when_there_is_no_bar_for_today(self):
        history = [_bar(datetime(2026, 9, 10))]
        self.assertEqual(_with_today(history, None), history)


class EntryWindowTests(unittest.TestCase):
    def test_off_by_default(self):
        # Every figure this project has published was produced without a
        # window. It stays off until it is switched on deliberately.
        self.assertIsNone(AutoTradeConfig().entry_window_minutes)

    def test_outside_the_window_no_entries_are_attempted(self):
        broker = ClockBroker(300, equity=100_000.0, cash=100_000.0)
        result = run_once(_config(entry_window_minutes=20), broker=broker,
                          bars_by_symbol={"SPY": []})
        self.assertEqual(broker.submitted, [])
        kinds = {a.get("event") for a in result.get("actions", [])}
        self.assertIn("outside_entry_window", kinds)

    def test_a_clock_it_cannot_read_does_not_enter_blind(self):
        broker = ClockBroker(None, equity=100_000.0, cash=100_000.0)
        result = run_once(_config(entry_window_minutes=20), broker=broker,
                          bars_by_symbol={"SPY": []})
        self.assertEqual(broker.submitted, [])
        kinds = {a.get("event") for a in result.get("actions", [])}
        self.assertIn("entry_window_unknown", kinds)

    def test_exits_still_run_outside_the_window(self):
        # The failure this exists to prevent: a window meant to delay BUYING
        # that also delays selling, so a position needing its stop replaced
        # sits unprotected until 15:45.
        position = {"symbol": "SPY", "quantity": 10.0,
                    "average_entry_price": 100.0, "market_value": 1_000.0,
                    "unrealized_pnl": 0.0, "current_price": 100.0}
        broker = ClockBroker(300, equity=100_000.0, cash=50_000.0,
                             positions=[position])
        result = run_once(_config(entry_window_minutes=20), broker=broker,
                          bars_by_symbol={"SPY": []})
        kinds = [a.get("event") for a in result.get("actions", [])]
        self.assertIn("outside_entry_window", kinds)
        # The held position was still looked at this cycle: it produced its
        # own stop-management record alongside the window record.
        self.assertTrue(
            [k for k in kinds if k != "outside_entry_window"],
            "the held position was not managed outside the entry window: "
            "{0}".format(kinds))

    def test_inside_the_window_without_todays_bars_does_not_enter(self):
        # `_todays_bars` reaches the network and returns {} on any failure.
        # Entering then would fill at today's close on yesterday's signal -
        # paying the gap's price without reading the day that set it.
        import event_aware_trader.autotrade as autotrade
        original = autotrade._todays_bars
        autotrade._todays_bars = lambda config, symbols: {}
        try:
            broker = ClockBroker(10, equity=100_000.0, cash=100_000.0)
            result = run_once(_config(entry_window_minutes=20), broker=broker,
                              bars_by_symbol={"SPY": []})
        finally:
            autotrade._todays_bars = original
        self.assertEqual(broker.submitted, [])
        kinds = {a.get("event") for a in result.get("actions", [])}
        self.assertIn("entry_window_no_data", kinds)

    def test_the_window_does_not_report_the_day_as_halted(self):
        # `halted` means the daily loss guard closed the book, and the cycle's
        # status is built from it. An ordinary 10am cycle reporting
        # halted_for_the_day would look like a fault in every log and in every
        # report built from one.
        broker = ClockBroker(300, equity=100_000.0, cash=100_000.0)
        result = run_once(_config(entry_window_minutes=20), broker=broker,
                          bars_by_symbol={"SPY": []})
        self.assertFalse(result.get("halted"))
        self.assertNotEqual(result.get("status"), "halted_for_the_day")


if __name__ == "__main__":
    unittest.main()
