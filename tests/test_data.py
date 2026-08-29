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
