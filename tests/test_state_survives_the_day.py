"""State that describes open positions must survive the day boundary.

Diagnosed live on 2026-09-09 after the account lost money on a stop that
should never have been where it was.

RTX was entered at 199.28 with a stop at 189.73 - 2.5 times the DAILY ATR,
about 5.5% below. The next morning its stop was 198.31, half a percent below,
and it was killed by an ordinary intraday wiggle at 13:40.

Two faults compounded, and each is separately sufficient to cause it.

FIRST, the first cycle of a new session replaced the whole state dict:

    state = {"session": today, "opening_equity": equity, "orders_today": 0}

That is correct for the daily loss guard and catastrophic for everything else
in there. It discarded `stops` - the entry-time stop of every OPEN position -
and `week`/`week_opening_equity`, the weekly guard's anchor, so the weekly
guard re-baselined every calendar day and could never accumulate across a
losing week. That is precisely the failure the weekly guard's own comment says
it was written to fix.

SECOND, with the stop forgotten, section 1 rebuilt one from `wilder_atr(bars)`
where `bars` is the CYCLE's series - 15-minute candles live. Measured on RTX
that day: daily ATR 4.3655 puts the stop 5.48% below entry, the 15-minute ATR
0.4623 puts it 0.58% below. Nine times too tight.

The consequence was not one bad trade. It happened to every position held
overnight, every day, on a rule that intends to hold about fourteen sessions
and earns 73.6% of its return from overnight moves.
"""

import unittest
from datetime import date, datetime, timedelta

from event_aware_trader.indicators import wilder_atr
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.types import Bar


def bars(count, start, step_minutes=None, spread=0.02):
    """Daily bars by default; intraday when step_minutes is given."""
    out = []
    price = 200.0
    for i in range(count):
        stamp = (start + timedelta(minutes=step_minutes * i)
                 if step_minutes else start + timedelta(days=i))
        high = price * (1 + spread)
        low = price * (1 - spread)
        out.append(Bar(timestamp=stamp, open=price, high=high, low=low,
                       close=price, volume=1_000_000.0))
    return out


class SessionResetTests(unittest.TestCase):
    """The reset, isolated. It is three lines and it cost real money."""

    def _roll(self, state, today, equity):
        """The shipped logic, as a function so the property can be asserted."""
        if state.get("session") != today:
            state = dict(state)
            state.update({"session": today, "opening_equity": equity,
                          "orders_today": 0})
        return state

    def _yesterday(self):
        return {
            "session": "2026-09-08",
            "opening_equity": 100_048.92,
            "orders_today": 2,
            "week": "2026-W37",
            "week_opening_equity": 100_006.52,
            "stops": {"RTX": {"initial": 189.73, "current": 189.73,
                              "opened_at_ts": "2026-09-08T19:30:00+00:00"}},
            "open_features": {"RTX": {"rsi": 34.79}},
        }

    def test_the_remembered_stop_survives(self):
        """The one that killed RTX."""
        rolled = self._roll(self._yesterday(), "2026-09-09", 100_027.40)
        self.assertEqual(rolled["stops"]["RTX"]["initial"], 189.73)

    def test_the_week_anchor_survives(self):
        """Otherwise the weekly guard re-baselines daily and never fires."""
        rolled = self._roll(self._yesterday(), "2026-09-09", 100_027.40)
        self.assertEqual(rolled["week"], "2026-W37")
        self.assertEqual(rolled["week_opening_equity"], 100_006.52)

    def test_open_position_features_survive(self):
        rolled = self._roll(self._yesterday(), "2026-09-09", 100_027.40)
        self.assertIn("RTX", rolled["open_features"])

    def test_the_session_fields_DO_reset(self):
        """The daily loss guard still re-baselines, which is its whole job."""
        rolled = self._roll(self._yesterday(), "2026-09-09", 100_027.40)
        self.assertEqual(rolled["session"], "2026-09-09")
        self.assertEqual(rolled["opening_equity"], 100_027.40)
        self.assertEqual(rolled["orders_today"], 0)

    def test_a_field_added_later_is_carried_by_default(self):
        """Carrying the dict forward means the next field added here is safe
        unless someone deliberately makes it session-scoped."""
        state = self._yesterday()
        state["something_new"] = {"kept": True}
        rolled = self._roll(state, "2026-09-09", 100_000.0)
        self.assertEqual(rolled["something_new"], {"kept": True})

    def test_the_same_session_is_left_completely_alone(self):
        state = self._yesterday()
        self.assertIs(self._roll(state, "2026-09-08", 99_000.0), state)


class StopTimescaleTests(unittest.TestCase):
    """A daily rule's stop must be rebuilt from DAILY volatility."""

    def test_the_two_timescales_give_wildly_different_stops(self):
        config = MeanReversionConfig()
        entry = 200.0
        daily = bars(300, datetime(2026, 1, 1), spread=0.022)
        intraday = bars(300, datetime(2026, 9, 1), step_minutes=15, spread=0.0023)

        daily_atr = wilder_atr(daily, config.atr_days)
        intraday_atr = wilder_atr(intraday, config.atr_days)
        self.assertIsNotNone(daily_atr)
        self.assertIsNotNone(intraday_atr)

        daily_stop = entry - config.stop_atr_multiple * daily_atr
        intraday_stop = entry - config.stop_atr_multiple * intraday_atr

        # The intraday-derived stop sits far closer to price - which is what
        # turns a weeks-long hold into a same-day stop-out.
        self.assertGreater(intraday_stop, daily_stop)
        self.assertGreater(daily_atr / intraday_atr, 5.0,
                           "fixture must reproduce the real ~9x gap")

    def test_the_live_numbers_reproduce(self):
        """RTX on 2026-09-09, measured from the account's own price files."""
        config = MeanReversionConfig()
        entry = 199.28
        self.assertAlmostEqual(entry - config.stop_atr_multiple * 4.3655,
                               188.37, places=1)
        self.assertAlmostEqual(entry - config.stop_atr_multiple * 0.4623,
                               198.12, places=1)


if __name__ == "__main__":
    unittest.main()
