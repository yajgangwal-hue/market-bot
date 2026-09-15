"""Selling into the day's strength, and never silently not selling at all.

The failure that matters most here is the quiet one: a rule that waits for a
peak that never comes, holds the position all day, and reports nothing wrong.
The deadline tests are the ones guarding that.
"""

import unittest
from datetime import date, datetime, timedelta, timezone

from event_aware_trader.data import Bar
from event_aware_trader.peak_exit import (
    DEFAULT_MIN_BARS, DEFAULT_PULLBACK, SELL, WAIT, decide, session_bars)

TODAY = date(2026, 9, 14)
OPEN = datetime(2026, 9, 14, 13, 30, tzinfo=timezone.utc)   # 09:30 ET


def bar(minutes, close, high=None, low=None):
    high = close if high is None else high
    low = close if low is None else low
    return Bar(timestamp=OPEN + timedelta(minutes=minutes), open=close,
               high=high, low=low, close=close, volume=1000)


def rising(n=10, start=100.0, step=0.5):
    return [bar(i * 5, start + i * step) for i in range(n)]


class SellingOnThePullbackNotTheTouch(unittest.TestCase):
    """The defect this class exists for: the first version sold at the OPEN.

    With a touch-the-high rule the first bar of the day is trivially the
    session high, so the test passed immediately and every new high re-armed
    it. On a day that rose all day it captured 90.9% of the best price
    available; waiting for a pullback captures 100%.
    """

    def test_a_day_that_only_rises_is_held_not_sold_at_the_open(self):
        d = decide(rising(10), TODAY)        # every bar a new high
        self.assertEqual(d.action, WAIT)
        self.assertAlmostEqual(d.gap_pct, 0.0)
        self.assertIn("waiting for a", d.reason)

    def test_it_sells_once_price_comes_off_the_high(self):
        bars = rising(10)
        high = max(x.high for x in bars)
        bars.append(bar(100, high * (1 - DEFAULT_PULLBACK - 0.0005)))
        d = decide(bars, TODAY)
        self.assertEqual(d.action, SELL)
        self.assertIn("pulled back", d.reason)

    def test_a_pullback_smaller_than_the_threshold_does_not_fire(self):
        bars = rising(10)
        high = max(x.high for x in bars)
        bars.append(bar(100, high * (1 - DEFAULT_PULLBACK / 2)))
        self.assertEqual(decide(bars, TODAY).action, WAIT)

    def test_the_threshold_is_the_boundary(self):
        bars = rising(10)
        high = max(x.high for x in bars)
        bars.append(bar(100, high * (1 - DEFAULT_PULLBACK)))
        self.assertEqual(decide(bars, TODAY).action, SELL)

    def test_the_high_is_the_bar_high_not_just_closes(self):
        # A spike that closed well off its own high sets the bar to beat, and
        # that same bar is already a pullback from it.
        bars = rising(6) + [bar(35, 100.0, high=120.0)]
        d = decide(bars, TODAY)
        self.assertEqual(d.session_high, 120.0)
        self.assertEqual(d.action, SELL)


class TooEarlyToJudge(unittest.TestCase):
    def test_it_will_not_act_on_the_first_half_hour(self):
        bars = [bar(0, 100.0), bar(5, 99.0), bar(10, 90.0)]   # would fire
        d = decide(bars, TODAY)
        self.assertEqual(d.action, WAIT)
        self.assertIn("not meaningful", d.reason)
        self.assertEqual(d.bars_seen, 3)

    def test_min_bars_is_the_boundary(self):
        # A falling shape WOULD fire, so this isolates the warm-up guard.
        falling = [bar(i * 5, 100.0 - i) for i in range(DEFAULT_MIN_BARS)]
        self.assertEqual(decide(falling[:-1], TODAY).action, WAIT)
        self.assertEqual(decide(falling, TODAY).action, SELL)

    def test_the_deadline_overrides_the_warm_up(self):
        # A half-day, or a late start: few bars, but the close is imminent.
        d = decide(rising(2), TODAY, minutes_to_close=5.0)
        self.assertEqual(d.action, SELL)


class TheDeadline(unittest.TestCase):
    def test_it_sells_near_the_close_even_when_the_high_never_returned(self):
        # A day that only rose never pulls back, so only the deadline can end
        # it - the case that would otherwise hold a position forever.
        d = decide(rising(10), TODAY, minutes_to_close=10.0)
        self.assertEqual(d.action, SELL)
        self.assertIn("did not come back", d.reason)

    def test_it_keeps_waiting_while_there_is_still_time(self):
        self.assertEqual(decide(rising(10), TODAY, minutes_to_close=90.0).action, WAIT)

    def test_an_unreadable_clock_never_triggers_the_deadline(self):
        # None must not be compared as though it were zero minutes left.
        self.assertEqual(decide(rising(10), TODAY, minutes_to_close=None).action, WAIT)


class OtherDaysAreNotTodaysRange(unittest.TestCase):
    def test_yesterdays_bars_are_ignored(self):
        yesterday = [Bar(timestamp=OPEN - timedelta(days=1, minutes=-5 * i),
                         open=200.0, high=200.0, low=200.0, close=200.0,
                         volume=1) for i in range(8)]
        bars = yesterday + rising(10) + [bar(100, 100.0)]   # then a pullback
        self.assertEqual(len(session_bars(bars, TODAY)), 11)
        d = decide(bars, TODAY)
        self.assertLess(d.session_high, 200.0)   # yesterday's 200 not counted
        self.assertEqual(d.action, SELL)

    def test_no_bars_today_waits(self):
        d = decide(rising(10), date(2026, 9, 15))
        self.assertEqual(d.action, WAIT)
        self.assertIn("no bars", d.reason)


if __name__ == "__main__":
    unittest.main()
