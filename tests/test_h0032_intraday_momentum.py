"""H-0032's price construction: the right bars, in New York time, across DST."""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import h0032_intraday_momentum as im                                  # noqa: E402


def bar(utc, close):
    return {"t": utc, "c": close, "o": close, "h": close, "l": close, "v": 1}


class SessionPrices(unittest.TestCase):
    def test_winter_and_summer_stamps_map_to_the_same_new_york_times(self):
        bars = [bar("2016-01-04T14:55:00Z", 100.0),   # 09:55 EST
                bar("2016-01-04T20:25:00Z", 101.0),   # 15:25 EST
                bar("2016-01-04T20:55:00Z", 102.0),   # 15:55 EST
                bar("2016-07-05T13:55:00Z", 200.0),   # 09:55 EDT
                bar("2016-07-05T19:25:00Z", 201.0),   # 15:25 EDT
                bar("2016-07-05T19:55:00Z", 202.0)]   # 15:55 EDT
        p = im.session_prices(bars)
        self.assertEqual(p[date(2016, 1, 4)], {"p1000": 100.0, "p1530": 101.0, "p1600": 102.0})
        self.assertEqual(p[date(2016, 7, 5)], {"p1000": 200.0, "p1530": 201.0, "p1600": 202.0})

    def test_an_early_close_is_skipped(self):
        bars = [bar("2016-11-25T14:55:00Z", 100.0), bar("2016-11-25T17:55:00Z", 101.0)]
        self.assertEqual(im.session_prices(bars), {})


class Returns(unittest.TestCase):
    PRICES = {date(2024, 1, 2): {"p1000": 99.0, "p1530": 100.0, "p1600": 100.0},
              date(2024, 1, 3): {"p1000": 101.0, "p1530": 102.0, "p1600": 102.51},
              date(2024, 1, 4): {"p1000": 101.0, "p1530": 101.0, "p1600": 100.0}}

    def test_first_and_last_half_hour_returns(self):
        rows = im.daily_rows(self.PRICES)
        day, first, last, cc = rows[0]
        self.assertEqual(day, date(2024, 1, 3))
        self.assertAlmostEqual(first, 0.01)            # 100 -> 101
        self.assertAlmostEqual(last, 0.005)            # 102 -> 102.51
        self.assertAlmostEqual(cc, 0.0251)

    def test_long_only_trades_only_after_a_rising_first_half_hour(self):
        trades = im.strategy_returns(im.daily_rows(self.PRICES), 0.0002)
        self.assertAlmostEqual(trades[0][1], 0.005 - 0.0002)
        self.assertIsNone(trades[1][1])                # 102.51 -> 101 fell: flat

    def test_a_long_gap_has_no_previous_close(self):
        prices = {date(2024, 1, 2): self.PRICES[date(2024, 1, 2)],
                  date(2024, 1, 12): self.PRICES[date(2024, 1, 3)]}
        self.assertEqual(im.daily_rows(prices), [])


if __name__ == "__main__":
    unittest.main()
