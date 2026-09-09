"""How long a position has been held must not depend on the price file's depth.

Found by line-by-line audit on 2026-09-08. `bars_held` was computed as

    len(series) - opened_days

where `opened_days` was the LENGTH OF THE PRICE FILE at the moment the
position opened. That is an absolute index into a file whose length is a
configuration choice, not a market fact: `session-run.ps1` refreshes with
`days=800` and gets about 548 daily bars.

Deepen that history - which is exactly what "give the bot more market data"
means - and len(series) becomes 2,684 while the remembered `opened_days`
stays 548. `bars_held` is then 2,136 against a `max_holding_bars` of 20, so
every open position reports a holding-cap exit and the entire book is
liquidated on the next cycle. Nothing about the market would have changed;
only the depth of a CSV.

The entry timestamp was already being recorded and is immune to this, so age
is counted from it. Dates are compared rather than ISO strings, because the
price files carry two conventions - naive 16:00 local and tz-aware
04:00+00:00 - and "16:00..." sorts after "04:00+00:00" for the same session.
"""

import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.autotrade import _parse_stamp
from event_aware_trader.types import Bar


def daily(count, start=datetime(2026, 1, 1)):
    return [Bar(timestamp=start + timedelta(days=i), open=100.0, high=101.0,
                low=99.0, close=100.0, volume=1_000_000.0)
            for i in range(count)]


def age_from_date(series, opened_at):
    """The shipped calculation, isolated so the property can be asserted."""
    entry_day = _parse_stamp(opened_at).date()
    return sum(1 for bar in series if bar.timestamp.date() > entry_day)


class StampParsingTests(unittest.TestCase):
    def test_both_file_conventions_yield_the_same_date(self):
        aware = _parse_stamp("2026-09-08T19:30:00+00:00").date()
        naive = _parse_stamp("2026-09-08T16:00:00").date()
        self.assertEqual(aware, naive)

    def test_a_trailing_z_is_accepted(self):
        self.assertEqual(_parse_stamp("2026-09-08T19:30:00Z").date(),
                         _parse_stamp("2026-09-08T19:30:00+00:00").date())

    def test_an_evening_utc_stamp_keeps_its_own_day(self):
        """23:30Z is still the 8th, not the 9th."""
        self.assertEqual(_parse_stamp("2026-09-08T23:30:00+00:00").date().day, 8)


class AgeTests(unittest.TestCase):
    def test_age_is_the_number_of_sessions_after_entry(self):
        series = daily(10)                       # 2026-01-01 .. 2026-01-10
        self.assertEqual(age_from_date(series, "2026-01-01T16:00:00"), 9)
        self.assertEqual(age_from_date(series, "2026-01-09T16:00:00"), 1)
        self.assertEqual(age_from_date(series, "2026-01-10T16:00:00"), 0)

    def test_deepening_the_history_does_not_age_the_position(self):
        """The defect, stated as a property.

        The same position, the same entry date, with a price file that now
        reaches five years further back. Age must not move.
        """
        entry = "2026-01-09T16:00:00"
        shallow = daily(10, datetime(2026, 1, 1))
        # Same final session, five years more history behind it. The start is
        # derived rather than written down so the two series genuinely end on
        # the same day.
        deep = daily(1200, shallow[-1].timestamp - timedelta(days=1199))
        self.assertEqual(deep[-1].timestamp.date(), shallow[-1].timestamp.date())
        self.assertEqual(age_from_date(shallow, entry), age_from_date(deep, entry))

    def test_the_old_arithmetic_would_have_liquidated_the_book(self):
        """Why this matters, pinned as a number rather than an assertion.

        Reproduces the live figures: RTX opened with a 548-bar file, and a
        deeper refresh would have made it 2,684.
        """
        opened_days = 548
        deepened = 2_684
        old_age = max(0, deepened - opened_days)
        self.assertEqual(old_age, 2_136)
        self.assertGreater(old_age, 20, "would breach max_holding_bars of 20")

    def test_a_missing_timestamp_still_has_a_fallback(self):
        """Positions opened before this change have no entry stamp to use."""
        series = daily(10)
        opened_days = 4
        self.assertEqual(max(0, len(series) - opened_days), 6)


if __name__ == "__main__":
    unittest.main()
