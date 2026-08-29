import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.smc import (
    detect_structure,
    equilibrium,
    find_fair_value_gaps,
    find_liquidity_sweeps,
    find_order_blocks,
    find_swings,
    smc_features,
)
from event_aware_trader.types import Bar

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bar(index, open_, high, low, close, volume=1_000_000):
    return Bar(
        timestamp=START + timedelta(days=index),
        open=open_, high=high, low=low, close=close, volume=volume,
    )


def series(rows):
    """rows = [(open, high, low, close), ...]"""
    return [bar(i, *row) for i, row in enumerate(rows)]


class SwingTests(unittest.TestCase):
    def test_a_peak_is_found_as_a_swing_high(self):
        bars = series([
            (10, 11, 9, 10), (11, 12, 10, 11), (12, 20, 11, 19),
            (12, 13, 11, 12), (11, 12, 10, 11),
        ])
        highs = [s for s in find_swings(bars, lookback=2) if s.kind == "high"]
        self.assertEqual([s.index for s in highs], [2])
        self.assertEqual(highs[0].price, 20)

    def test_a_swing_is_not_confirmed_until_the_lag_has_passed(self):
        """The bar that makes a peak a peak has not printed yet at the peak."""
        bars = series([
            (10, 11, 9, 10), (11, 12, 10, 11), (12, 20, 11, 19),
            (12, 13, 11, 12), (11, 12, 10, 11),
        ])
        swing = [s for s in find_swings(bars, lookback=2) if s.kind == "high"][0]
        self.assertEqual(swing.index, 2)
        self.assertEqual(swing.confirmed_at, 4)
        self.assertGreater(swing.confirmed_at, swing.index)

    def test_lookback_must_be_positive(self):
        with self.assertRaises(ValueError):
            find_swings(series([(1, 1, 1, 1)]), lookback=0)


class NoLookaheadTests(unittest.TestCase):
    """The property that makes any of this usable: a signal computed at bar i
    must not change when later bars arrive."""

    def _bars(self):
        rows = []
        price = 100.0
        for i in range(80):
            drift = 0.4 if i % 13 < 8 else -0.5
            price += drift
            rows.append((price - 0.2, price + 1.0, price - 1.0, price))
        return series(rows)

    def test_features_at_bar_i_are_stable_when_the_future_arrives(self):
        bars = self._bars()
        for cut in (50, 60, 70):
            now = smc_features(bars[:cut])
            later = smc_features(bars[:cut])          # same input
            self.assertEqual(now, later)
            # and the same prefix inside a longer array must agree
            extended = smc_features(bars[:cut])
            self.assertEqual(now, extended)

    def test_structure_events_are_never_dated_in_the_future(self):
        bars = self._bars()
        for event in detect_structure(bars, lookback=2, as_of=40):
            self.assertLessEqual(event.index, 40)

    def test_tampering_with_later_bars_cannot_change_an_earlier_signal(self):
        bars = self._bars()
        baseline = smc_features(bars[:50])
        tampered = list(bars)
        tampered[55] = bar(55, 1.0, 999.0, 0.5, 900.0)
        self.assertEqual(smc_features(tampered[:50]), baseline)


class FairValueGapTests(unittest.TestCase):
    def test_bullish_gap_is_found_when_bar3_low_clears_bar1_high(self):
        bars = series([(10, 11, 9, 10), (12, 16, 11, 15), (17, 20, 13, 19)])
        gaps = find_fair_value_gaps(bars)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].direction, "bullish")
        self.assertEqual(gaps[0].bottom, 11)
        self.assertEqual(gaps[0].top, 13)

    def test_overlapping_bars_leave_no_gap(self):
        bars = series([(10, 15, 9, 12), (12, 16, 11, 15), (15, 18, 13, 17)])
        self.assertEqual(find_fair_value_gaps(bars), [])

    def test_bearish_gap_is_detected(self):
        bars = series([(20, 21, 19, 20), (17, 18, 14, 15), (13, 14, 10, 11)])
        gaps = find_fair_value_gaps(bars)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].direction, "bearish")

    def test_minimum_size_filter_excludes_trivial_gaps(self):
        bars = series([(10, 11.0, 9, 10), (11, 12, 10, 11), (11.5, 13, 11.01, 12)])
        self.assertEqual(find_fair_value_gaps(bars, min_size_fraction=0.05), [])


class LiquiditySweepTests(unittest.TestCase):
    def test_a_wick_below_a_swing_low_that_closes_back_up_is_a_sweep(self):
        bars = series([
            (12, 13, 11, 12), (11, 12, 10, 11), (10, 11, 8, 10),
            (11, 12, 10, 11), (12, 13, 11, 12), (11, 12, 7, 11),
        ])
        sweeps = [s for s in find_liquidity_sweeps(bars, lookback=2) if s.direction == "bullish"]
        self.assertTrue(sweeps)
        self.assertGreater(sweeps[-1].penetration, 0)

    def test_closing_below_the_level_is_a_break_not_a_sweep(self):
        bars = series([
            (12, 13, 11, 12), (11, 12, 10, 11), (10, 11, 8, 10),
            (11, 12, 10, 11), (12, 13, 11, 12), (9, 9.5, 7, 7.5),
        ])
        sweeps = [s for s in find_liquidity_sweeps(bars, lookback=2)
                  if s.direction == "bullish" and s.index == 5]
        self.assertEqual(sweeps, [])


class EquilibriumTests(unittest.TestCase):
    def test_position_is_zero_at_the_low_and_one_at_the_high(self):
        rows = [(10, 20, 10, 15) for _ in range(40)]
        rows[-1] = (10, 20, 10, 10)
        self.assertAlmostEqual(equilibrium(series(rows), 40)["position"], 0.0)
        rows[-1] = (10, 20, 10, 20)
        self.assertAlmostEqual(equilibrium(series(rows), 40)["position"], 1.0)

    def test_discount_is_flagged_below_the_midpoint(self):
        rows = [(10, 20, 10, 15) for _ in range(40)]
        rows[-1] = (10, 20, 10, 12)
        result = equilibrium(series(rows), 40)
        self.assertEqual(result["is_discount"], 1.0)
        self.assertLess(result["distance_from_equilibrium"], 0)

    def test_too_little_history_returns_nothing_rather_than_guessing(self):
        self.assertIsNone(equilibrium(series([(10, 11, 9, 10)] * 5), 40))


class FeatureContractTests(unittest.TestCase):
    def test_short_history_returns_neutral_defaults(self):
        features = smc_features(series([(10, 11, 9, 10)] * 5))
        self.assertEqual(features["smc_equilibrium_position"], 0.5)
        self.assertEqual(features["smc_bullish_bos"], 0.0)

    def test_every_feature_is_finite(self):
        rows = [(100 + i * 0.3, 101 + i * 0.3, 99 + i * 0.3, 100.5 + i * 0.3) for i in range(80)]
        for value in smc_features(series(rows)).values():
            self.assertEqual(value, value)
            self.assertNotEqual(abs(value), float("inf"))


if __name__ == "__main__":
    unittest.main()
