"""Selling into the day's strength, and never silently not selling at all.

The failure that matters most here is the quiet one: a rule that waits for a
peak that never comes, holds the position all day, and reports nothing wrong.
The deadline tests are the ones guarding that.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.peak_exit import (
    DEFAULT_MIN_BARS, SELL, WAIT, decide, session_bars)

TODAY = date(2026, 9, 14)
OPEN = datetime(2026, 9, 14, 13, 30, tzinfo=timezone.utc)   # 09:30 ET


def bar(minutes, close, high=None, low=None):
    high = close if high is None else high
    low = close if low is None else low
    return Bar(timestamp=OPEN + timedelta(minutes=minutes), open=close,
               high=high, low=low, close=close, volume=1000)


def rising(n=10, start=100.0, step=0.5):
    return [bar(i * 5, start + i * step) for i in range(n)]


class AtThePeak(unittest.TestCase):
    def test_it_sells_when_price_is_at_the_session_high(self):
        bars = rising()                      # last bar IS the high
        d = decide(bars, TODAY)
        self.assertEqual(d.action, SELL)
        self.assertIn("at the session high", d.reason)
        self.assertAlmostEqual(d.gap_pct, 0.0)

    def test_it_waits_while_price_is_below_the_high(self):
        bars = rising() + [bar(100, 98.0)]   # dropped well off the top
        d = decide(bars, TODAY)
        self.assertEqual(d.action, WAIT)
        self.assertIn("below the session high", d.reason)
        self.assertGreater(d.gap_pct, 1.0)

    def test_within_the_tolerance_band_counts_as_the_peak(self):
        bars = rising()
        high = max(b.high for b in bars)
        bars.append(bar(100, high * 0.9990))     # 0.10% off, inside 0.15%
        self.assertEqual(decide(bars, TODAY).action, SELL)
        bars[-1] = bar(100, high * 0.9950)       # 0.50% off, outside it
        self.assertEqual(decide(bars, TODAY).action, WAIT)

    def test_the_high_is_the_bar_high_not_just_closes(self):
        # A spike that closed well off its own high still sets the bar to beat.
        bars = rising(6) + [bar(35, 100.0, high=120.0)]
        d = decide(bars, TODAY)
        self.assertEqual(d.session_high, 120.0)
        self.assertEqual(d.action, WAIT)


class TooEarlyToJudge(unittest.TestCase):
    def test_it_will_not_act_on_the_first_half_hour(self):
        bars = rising(3)                     # 3 bars, all-time high is bar 3
        d = decide(bars, TODAY)
        self.assertEqual(d.action, WAIT)
        self.assertIn("not meaningful", d.reason)
        self.assertEqual(d.bars_seen, 3)

    def test_min_bars_is_the_boundary(self):
        self.assertEqual(decide(rising(DEFAULT_MIN_BARS - 1), TODAY).action, WAIT)
        self.assertEqual(decide(rising(DEFAULT_MIN_BARS), TODAY).action, SELL)

    def test_the_deadline_overrides_the_warm_up(self):
        # A half-day, or a late start: few bars, but the close is imminent.
        d = decide(rising(2), TODAY, minutes_to_close=5.0)
        self.assertEqual(d.action, SELL)


class TheDeadline(unittest.TestCase):
    def test_it_sells_near_the_close_even_far_from_the_high(self):
        bars = rising() + [bar(100, 90.0)]
        d = decide(bars, TODAY, minutes_to_close=10.0)
        self.assertEqual(d.action, SELL)
        self.assertIn("did not come back", d.reason)

    def test_it_keeps_waiting_while_there_is_still_time(self):
        bars = rising() + [bar(100, 90.0)]
        self.assertEqual(decide(bars, TODAY, minutes_to_close=90.0).action, WAIT)

    def test_an_unreadable_clock_never_triggers_the_deadline(self):
        # None must not be compared as though it were zero minutes left.
        bars = rising() + [bar(100, 90.0)]
        d = decide(bars, TODAY, minutes_to_close=None)
        self.assertEqual(d.action, WAIT)


class OtherDaysAreNotTodaysRange(unittest.TestCase):
    def test_yesterdays_bars_are_ignored(self):
        yesterday = [Bar(timestamp=OPEN - timedelta(days=1, minutes=-5 * i),
                         open=200.0, high=200.0, low=200.0, close=200.0,
                         volume=1) for i in range(8)]
        bars = yesterday + rising()
        self.assertEqual(len(session_bars(bars, TODAY)), 10)
        d = decide(bars, TODAY)
        self.assertLess(d.session_high, 200.0)   # yesterday's 200 not counted
        self.assertEqual(d.action, SELL)

    def test_no_bars_today_waits(self):
        d = decide(rising(), date(2026, 9, 15))
        self.assertEqual(d.action, WAIT)
        self.assertIn("no bars", d.reason)


if __name__ == "__main__":
    unittest.main()
