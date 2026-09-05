"""An in-progress daily candle must never reach a daily rule.

Found by the user reviewing the data path. Confirmed live on 2026-09-05: every
one of the ten crypto price files carried a bar dated that day - a 1Day candle
that does not close until UTC midnight, read at 04:00. Its "close" was four
hours of trading, and RSI, the 200-day average and ATR were all computed
through it.

That is lookahead in practice even though the timestamp is honestly today's
date: a live loop acts on a number that did not exist at the previous close,
while a backtest over the same code sees a completed candle. The two stop
measuring the same strategy, which is the failure that makes a backtest lie.

The equity path was not protected either. It skipped in-progress sessions only
because Yahoo happens to report their close as NaN - behaviour, not a contract.
"""
import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.data import _bars_from_history


class FakeFrame:
    """Minimal stand-in for a yfinance frame: iterrows() of timestamp, row."""

    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


def frame(dates):
    return FakeFrame([
        (d, {"Open": 100.0, "High": 101.0, "Low": 99.0,
             "Close": 100.5, "Volume": 1_000_000.0})
        for d in dates
    ])


class DailyCandleTests(unittest.TestCase):
    def setUp(self):
        self.as_of = datetime(2026, 9, 5, 4, 0)

    def test_todays_in_progress_candle_is_excluded(self):
        bars = _bars_from_history(
            frame([datetime(2026, 9, 3), datetime(2026, 9, 4), datetime(2026, 9, 5)]),
            "1d", "SPY", as_of=self.as_of)
        self.assertEqual([b.timestamp.date().isoformat() for b in bars],
                         ["2026-09-03", "2026-09-04"])

    def test_a_completed_candle_is_kept(self):
        bars = _bars_from_history(
            frame([datetime(2026, 9, 4)]), "1d", "SPY", as_of=self.as_of)
        self.assertEqual(len(bars), 1)

    def test_a_future_dated_candle_is_excluded_too(self):
        """A clock skew or a bad feed must not become a tradeable signal.

        Filtering every bar leaves nothing, and _bars_from_history raises
        rather than returning an empty series - which is right: a fetch that
        yields no usable data is a failure to report, not a quiet no-op that
        looks like "no signal today".
        """
        with self.assertRaises(ValueError):
            _bars_from_history(
                frame([datetime(2026, 9, 6)]), "1d", "SPY", as_of=self.as_of)

    def test_yesterday_becomes_eligible_the_next_day(self):
        """The candle is not discarded, only deferred until it has closed."""
        with self.assertRaises(ValueError):
            _bars_from_history(
                frame([datetime(2026, 9, 5)]), "1d", "SPY", as_of=self.as_of)
        later = datetime(2026, 9, 6, 4, 0)
        self.assertEqual(
            len(_bars_from_history(frame([datetime(2026, 9, 5)]), "1d", "SPY", as_of=later)),
            1)

    def test_intraday_intervals_are_untouched(self):
        """A 15-minute bar for today is complete and is the point of intraday."""
        stamps = [datetime(2026, 9, 5, 14, 30), datetime(2026, 9, 5, 14, 45)]
        bars = _bars_from_history(frame(stamps), "15m", "SPY", as_of=self.as_of)
        self.assertEqual(len(bars), 2)

    def test_without_as_of_it_uses_the_current_date(self):
        """as_of exists for tests; production must not depend on passing it."""
        tomorrow = datetime.now() + timedelta(days=1)
        with self.assertRaises(ValueError):
            _bars_from_history(frame([tomorrow]), "1d", "SPY")


if __name__ == "__main__":
    unittest.main()
