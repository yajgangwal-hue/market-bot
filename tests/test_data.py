import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.data import load_bars

HEADER = "timestamp,open,high,low,close,volume\n"
GOOD = "2026-01-02T16:00:00+00:00,100,101,99,100.5,1000000\n"


class DataTests(unittest.TestCase):
    def _load(self, body):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.csv"
            path.write_text(HEADER + body, encoding="utf-8")
            return load_bars(path)

    def test_nan_close_row_is_skipped(self):
        """Yahoo reports the still-open session with a NaN close, not a null."""
        bars = self._load(GOOD + "2026-01-03T16:00:00+00:00,101,102,100,nan,900000\n")
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].close, 100.5)

    def test_infinite_and_non_positive_prices_are_skipped(self):
        bars = self._load(
            GOOD
            + "2026-01-03T16:00:00+00:00,101,inf,100,101.5,900000\n"
            + "2026-01-04T16:00:00+00:00,101,102,100,0,900000\n"
            + "2026-01-05T16:00:00+00:00,101,102,100,-5,900000\n"
        )
        self.assertEqual(len(bars), 1)

    def test_a_file_of_only_bad_rows_raises(self):
        with self.assertRaises(ValueError):
            self._load("2026-01-03T16:00:00+00:00,101,102,100,nan,900000\n")


if __name__ == "__main__":
    unittest.main()


class BatchHistoryParsingTests(unittest.TestCase):
    """The batched path must screen exactly what the per-symbol path screens.

    Batching was added because 120 requests a cycle got rate-limited and lost
    6-18 symbols silently. It would be a poor trade to fix that by letting a
    NaN or a still-open bar through on the new path.
    """

    def _frame(self):
        import pandas as pd
        index = pd.to_datetime(["2026-08-27", "2026-08-28", "2026-08-31"])
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [101.0, 102.0, 103.0],
                "Low": [99.0, 100.0, 101.0],
                # The last row is the session still in progress.
                "Close": [100.5, 101.5, float("nan")],
                "Volume": [1000.0, 1100.0, 1200.0],
            },
            index=index,
        )

    def test_a_still_open_bar_with_a_nan_close_is_dropped(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "1d", "TEST")
        self.assertEqual(len(bars), 2)
        for bar in bars:
            self.assertFalse(math.isnan(bar.close))

    def test_a_daily_bar_is_stamped_at_the_close_not_midnight(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "1d", "TEST")
        # Midnight would make a same-day signal look knowable before it was.
        for bar in bars:
            self.assertEqual(bar.timestamp.hour, 16)

    def test_an_intraday_bar_keeps_its_own_timestamp(self):
        from event_aware_trader.data import _bars_from_history
        bars = _bars_from_history(self._frame(), "15m", "TEST")
        self.assertEqual(bars[0].timestamp.hour, 0)

    def test_a_frame_with_nothing_usable_raises_rather_than_returning_empty(self):
        from event_aware_trader.data import _bars_from_history
        frame = self._frame()
        frame["Close"] = [float("nan")] * 3
        # Silently returning [] would read downstream as "no signal".
        with self.assertRaises(ValueError):
            _bars_from_history(frame, "1d", "TEST")
