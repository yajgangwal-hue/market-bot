import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.regime_shorts import (
    ShortPolicy,
    classify_regime,
    short_size,
    shorts_allowed,
)
from event_aware_trader.types import Bar

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def bars(drift, count=260, start=100.0):
    out, price = [], start
    for i in range(count):
        price *= 1.0 + drift
        out.append(Bar(START + timedelta(days=i), price, price * 1.01,
                       price * 0.99, price, 1_000_000))
    return out


class RegimeTests(unittest.TestCase):
    def test_a_rising_market_is_not_bear(self):
        self.assertFalse(classify_regime(bars(0.001)).is_bear)

    def test_a_falling_market_is_bear(self):
        self.assertTrue(classify_regime(bars(-0.002)).is_bear)

    def test_too_little_history_returns_nothing_rather_than_guessing(self):
        self.assertIsNone(classify_regime(bars(0.001, count=50)))

    def test_one_bad_close_does_not_flip_the_book(self):
        """Confirmation exists so a single dip is not a regime change."""
        series = bars(0.001)
        last = series[-1]
        series[-1] = Bar(last.timestamp, last.open, last.high, last.close * 0.5,
                         last.close * 0.5, last.volume)
        regime = classify_regime(series, ShortPolicy(enabled=True, confirmation_days=3))
        self.assertFalse(regime.is_bear)

    def test_distance_from_the_average_has_the_right_sign(self):
        self.assertGreater(classify_regime(bars(0.001)).distance, 0)
        self.assertLess(classify_regime(bars(-0.002)).distance, 0)


class GatingTests(unittest.TestCase):
    def test_shorting_is_off_by_default(self):
        self.assertFalse(ShortPolicy().enabled)
        self.assertFalse(shorts_allowed(classify_regime(bars(-0.002)), ShortPolicy()))

    def test_enabled_plus_bear_allows_a_short(self):
        policy = ShortPolicy(enabled=True)
        self.assertTrue(shorts_allowed(classify_regime(bars(-0.002), policy), policy))

    def test_enabled_but_rising_still_refuses(self):
        """Shorting a rising tape is what turned +58.9% into -0.74%."""
        policy = ShortPolicy(enabled=True)
        self.assertFalse(shorts_allowed(classify_regime(bars(0.001), policy), policy))

    def test_no_regime_information_means_no_short(self):
        self.assertFalse(shorts_allowed(None, ShortPolicy(enabled=True)))


class SizingTests(unittest.TestCase):
    def test_a_short_is_capped_below_a_long(self):
        policy = ShortPolicy(enabled=True, max_short_fraction=0.30)
        shares = short_size(100_000, 100.0, 110.0, policy)
        self.assertLessEqual(shares * 100.0, 100_000 * 0.30)

    def test_whole_shares_only(self):
        shares = short_size(100_000, 380.0, 400.0, ShortPolicy(enabled=True))
        self.assertEqual(shares, round(shares))

    def test_a_stop_below_entry_is_refused(self):
        """For a short the stop sits ABOVE the entry; below is incoherent."""
        self.assertEqual(short_size(100_000, 100.0, 90.0, ShortPolicy(enabled=True)), 0.0)

    def test_an_oversized_fraction_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            ShortPolicy(max_short_fraction=0.9)

    def test_non_positive_equity_sizes_nothing(self):
        self.assertEqual(short_size(0.0, 100.0, 110.0, ShortPolicy(enabled=True)), 0.0)


if __name__ == "__main__":
    unittest.main()
