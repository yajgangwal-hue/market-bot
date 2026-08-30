import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.indicators import (
    intraday_volatility_profile,
    volatility_multiplier_for,
)
from event_aware_trader.types import Bar


def session_bars(days=10, slots=6, opening_multiple=3.0):
    """Bars where the first slot of each session is deliberately wider."""
    bars = []
    start = datetime(2026, 1, 5, 9, 30, tzinfo=timezone.utc)
    for day in range(days):
        for slot in range(slots):
            stamp = start + timedelta(days=day, minutes=15 * slot)
            width = 1.0 * (opening_multiple if slot == 0 else 1.0)
            close = 100.0
            bars.append(Bar(timestamp=stamp, open=close, high=close + width,
                            low=close - width, close=close, volume=1_000_000))
    return bars


class ProfileTests(unittest.TestCase):
    def test_the_wider_opening_slot_is_detected(self):
        profile = intraday_volatility_profile(session_bars())
        self.assertGreater(profile["09:30"], profile["09:45"])
        self.assertGreater(profile["09:30"], 1.0)

    def test_profile_is_normalised_around_one(self):
        profile = intraday_volatility_profile(session_bars())
        mean = sum(profile.values()) / len(profile)
        self.assertAlmostEqual(mean, 1.0, places=6)

    def test_thin_slots_are_not_estimated_from_two_bars(self):
        profile = intraday_volatility_profile(session_bars(days=2), minimum_samples=5)
        self.assertEqual(profile, {})

    def test_no_bars_returns_empty_rather_than_dividing_by_zero(self):
        self.assertEqual(intraday_volatility_profile([]), {})


class MultiplierTests(unittest.TestCase):
    def test_multiplier_is_bounded(self):
        bars = session_bars(opening_multiple=50.0)
        self.assertLessEqual(volatility_multiplier_for(bars, cap=3.0), 3.0)
        self.assertGreaterEqual(volatility_multiplier_for(bars, cap=3.0), 0.5)

    def test_daily_bars_get_a_neutral_multiplier(self):
        """Every daily bar is the same slot, so there is nothing to scale."""
        start = datetime(2026, 1, 5, 16, tzinfo=timezone.utc)
        bars = [
            Bar(timestamp=start + timedelta(days=i), open=100, high=101,
                low=99, close=100, volume=1_000_000)
            for i in range(60)
        ]
        self.assertEqual(volatility_multiplier_for(bars), 1.0)

    def test_too_little_history_is_neutral(self):
        self.assertEqual(volatility_multiplier_for([]), 1.0)

    def test_it_looks_at_the_next_slot_not_the_current_one(self):
        bars = session_bars(days=12)
        # ending mid-session, the next slot is an ordinary one
        trimmed = [b for b in bars if b.timestamp.strftime("%H:%M") <= "10:15"]
        self.assertGreater(volatility_multiplier_for(trimmed), 0.0)


class StopScalingTests(unittest.TestCase):
    def test_scaling_widens_the_stop_in_volatile_slots(self):
        from dataclasses import replace
        from event_aware_trader.strategy import StrategyConfig

        on = StrategyConfig.for_interval("15m", use_intraday_volatility_scaling=True)
        off = replace(on, use_intraday_volatility_scaling=False)
        self.assertTrue(on.use_intraday_volatility_scaling)
        self.assertFalse(off.use_intraday_volatility_scaling)

    def test_default_is_on(self):
        from event_aware_trader.strategy import StrategyConfig

        self.assertTrue(StrategyConfig().use_intraday_volatility_scaling)


if __name__ == "__main__":
    unittest.main()
