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
    def test_the_shipped_window_is_twenty_minutes(self):
        self.assertEqual(AutoTradeConfig().entry_window_minutes, 20)

    def test_it_admits_the_last_cycle_and_excludes_the_one_before(self):
        # This is the whole point of the number and it was got wrong once.
        # Entries fire on the FIRST qualifying cycle, so a window wide enough
        # to admit 15:30 does not add 15:30 as a fallback - it makes 15:30 the
        # default and 15:45 unreachable. Measured on 1,417 oversold sessions,
        # the 15:30 fill reaches the next open at -0.0295% against +0.0257%
        # for 15:45, which gives back a third of what this change is worth.
        window = AutoTradeConfig().entry_window_minutes
        for minutes_left in (18, 15, 12):      # where the 15:45 cycle lands
            self.assertTrue(0 < minutes_left <= window,
                            "the {0}-minute cycle cannot enter".format(
                                minutes_left))
        for minutes_left in (30, 28, 45):      # the 15:30 cycle and earlier
            self.assertFalse(0 < minutes_left <= window,
                             "the {0}-minute cycle should be excluded".format(
                                 minutes_left))

    def test_a_qualifying_setup_inside_the_window_still_produces_an_order(self):
        # The window is a gate on the order path, so the thing that must be
        # proved is not only that it blocks - it is that it lets the shipped
        # configuration trade. Without this, "no orders, ever" would pass
        # every other test in this file.
        import event_aware_trader.autotrade as autotrade

        closes = [50.0 + 0.25 * i for i in range(226)]
        last = closes[-1]
        closes += [last * (1 - 0.022 * (i + 1)) for i in range(3)]
        history = [Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)
                       + timedelta(days=i), open=c, high=c * 1.001,
                       low=c * 0.999, close=c, volume=5_000_000)
                   for i, c in enumerate(closes)]

        daily, todays = autotrade.daily_bars, autotrade._todays_bars
        autotrade.daily_bars = lambda symbol, *a, **k: history[:-1]
        autotrade._todays_bars = lambda config, symbols: {"SPY": history[-1]}
        try:
            broker = ClockBroker(12, equity=100_000.0, cash=100_000.0)
            run_once(_config(dry_run=True), broker=broker,
                     bars_by_symbol={"SPY": history})
        finally:
            autotrade.daily_bars, autotrade._todays_bars = daily, todays

        self.assertTrue(broker.submitted,
                        "the shipped configuration placed no order inside its "
                        "own entry window")
        self.assertEqual(broker.submitted[0][0], "SPY")

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


class TodaysBarsTests(unittest.TestCase):
    """The partial bar: legitimate to decide on, never legitimate to save."""

    def test_the_shared_fetch_still_drops_today_by_default(self):
        # `fetch_alpaca_equity_bars` deliberately discards the session in
        # progress, because a partial daily bar written into the price files
        # is the defect that corrupted 59 of them. The close window needs that
        # bar, but every path that writes to disk must keep the default.
        import inspect

        from event_aware_trader.data import fetch_alpaca_equity_bars

        default = inspect.signature(
            fetch_alpaca_equity_bars).parameters["include_today"].default
        self.assertIs(default, False)

    def test_the_close_window_asks_for_it_explicitly(self):
        # The first version of `_todays_bars` used the default and therefore
        # returned nothing - every symbol, every cycle, silently. The bot
        # would have logged "no same-day bars" forever and never entered.
        import event_aware_trader.autotrade as autotrade

        seen = {}

        def fake(symbols, days=760, batch=100, interval="1d",
                 include_today=False):
            seen["include_today"] = include_today
            return {}

        # `_todays_bars` imports the fetch from `.data` at call time, so the
        # module attribute is the seam.
        import event_aware_trader.data as data

        original = data.fetch_alpaca_equity_bars
        data.fetch_alpaca_equity_bars = fake
        try:
            autotrade._todays_bars(_config(), ["SPY"])
        finally:
            data.fetch_alpaca_equity_bars = original
        self.assertIs(seen.get("include_today"), True)

    def test_crypto_is_never_asked_for_here(self):
        # Equity daily bars only. A crypto pair sent to the stocks endpoint
        # fails the whole batch rather than just itself.
        import event_aware_trader.autotrade as autotrade
        import event_aware_trader.data as data

        seen = {}

        def fake(symbols, days=760, batch=100, interval="1d",
                 include_today=False):
            seen["symbols"] = list(symbols)
            return {}

        original = data.fetch_alpaca_equity_bars
        data.fetch_alpaca_equity_bars = fake
        try:
            autotrade._todays_bars(_config(), ["SPY", "BTC/USD", "ETH/USD"])
        finally:
            data.fetch_alpaca_equity_bars = original
        self.assertEqual(seen.get("symbols"), ["SPY"])


if __name__ == "__main__":
    unittest.main()
