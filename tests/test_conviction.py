"""Conviction weighting, and the control that made it believable.

Six candidate signals were tested on 1,872 entries across 2016-2026. Only the
drawdown from the 20-day high was monotonic on the holdout. RSI depth - the
obvious candidate and the one predicted to work - was noise.

Then it was controlled, which is the part that mattered. Weighting improved
the decade from +84.9% to +127.6%, and that alone proves nothing: bigger
positions crowd others out of the cash, so the result was confounded with
"fewer, bigger positions", a variable that produced 85, 112, 90, 110, 90 with
no ordering when swept directly. Random multipliers from the identical
distribution landed at +73, +73, +77 and +66 - every one BELOW flat - while
keeping more trades. The signal is doing the work, not the position count.
"""

import unittest
from datetime import datetime, timedelta

from event_aware_trader.mean_reversion import (
    CONVICTION_FULL_DRAWDOWN,
    CONVICTION_MAX,
    CONVICTION_MIN,
    conviction,
)
from event_aware_trader.types import Bar


def bar(close, high):
    return Bar(timestamp=datetime(2026, 1, 1), open=close, high=high,
               low=close * 0.97, close=close, volume=5_000_000.0)


def series(depth_from_high, length=21):
    """A window whose last close sits `depth_from_high` under the 20-day high."""
    out = [bar(100.0, 100.0) for _ in range(length - 1)]
    out.append(bar(100.0 * (1 - depth_from_high), 100.0 * (1 - depth_from_high)))
    return out


class ConvictionTests(unittest.TestCase):
    def test_a_flat_setup_gets_the_minimum(self):
        self.assertAlmostEqual(conviction(series(0.0)), CONVICTION_MIN)

    def test_a_full_depth_pullback_gets_the_maximum(self):
        self.assertAlmostEqual(
            conviction(series(CONVICTION_FULL_DRAWDOWN)), CONVICTION_MAX)

    def test_it_scales_linearly_between(self):
        half = conviction(series(CONVICTION_FULL_DRAWDOWN / 2.0))
        self.assertAlmostEqual(half, (CONVICTION_MIN + CONVICTION_MAX) / 2.0, places=6)

    def test_deeper_than_full_depth_does_not_keep_growing(self):
        """Unbounded weighting on the deepest fall is how a knife gets caught."""
        self.assertAlmostEqual(conviction(series(0.40)), CONVICTION_MAX)

    def test_it_is_monotonic_in_depth(self):
        values = [conviction(series(d)) for d in (0.0, 0.02, 0.04, 0.06, 0.08)]
        for earlier, later in zip(values, values[1:]):
            self.assertLessEqual(earlier, later)

    def test_short_history_is_neutral_rather_than_extreme(self):
        """Too few bars must not silently become a maximum-size bet."""
        self.assertEqual(conviction([bar(100.0, 100.0)] * 5), 1.0)

    def test_a_degenerate_high_is_neutral(self):
        broken = [bar(0.0, 0.0) for _ in range(21)]
        self.assertEqual(conviction(broken), 1.0)

    def test_the_multiplier_never_leaves_its_stated_range(self):
        for depth in (0.0, 0.001, 0.03, 0.08, 0.5, 0.99):
            value = conviction(series(depth))
            self.assertGreaterEqual(value, CONVICTION_MIN)
            self.assertLessEqual(value, CONVICTION_MAX)

    def test_average_appetite_is_preserved_not_raised(self):
        """The point is concentration, not a bigger flat bet.

        A uniform spread of setups across the range averages to about 1.0, so
        this reallocates the existing risk budget rather than adding to it -
        which matters, because raising risk uniformly was measured to buy
        drawdown and no return.
        """
        depths = [i * CONVICTION_FULL_DRAWDOWN / 20.0 for i in range(21)]
        average = sum(conviction(series(d)) for d in depths) / len(depths)
        self.assertAlmostEqual(average, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
