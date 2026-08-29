import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.strategy import generate_candidate
from event_aware_trader.types import Action, Bar


def trending_bars(count=70):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(count):
        close = 100.0 + index * 2.0
        bars.append(
            Bar(
                timestamp=start + timedelta(days=index),
                open=close - 0.2,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000 if index < count - 1 else 2_500_000,
            )
        )
    return bars


class StrategyTests(unittest.TestCase):
    def test_future_bars_do_not_change_a_completed_signal(self):
        bars = trending_bars()
        original = generate_candidate("SPY", bars[:60], [], 10_000)
        changed_future = list(bars[:60]) + [bars[60]]
        changed_future[-1] = Bar(
            timestamp=changed_future[-1].timestamp,
            open=1,
            high=500,
            low=0.5,
            close=2,
            volume=99_999_999,
        )
        repeated = generate_candidate("SPY", changed_future[:60], [], 10_000)
        self.assertEqual(original.as_dict(), repeated.as_dict())

    def test_low_relative_volume_is_rejected(self):
        bars = trending_bars()
        candidate = generate_candidate("SPY", bars[:-1], [], 10_000)
        self.assertEqual(candidate.action, Action.REJECT)
        self.assertTrue(any("Relative volume" in blocker for blocker in candidate.blockers))

    def test_strong_liquid_trend_can_clear_a_paper_only_gate(self):
        candidate = generate_candidate("SPY", trending_bars(), [], 10_000)
        self.assertEqual(candidate.action, Action.PAPER_LONG)
        self.assertGreater(candidate.quantity, 0)
        self.assertGreater(candidate.planned_risk, 0)

    def test_outside_universe_is_rejected(self):
        candidate = generate_candidate("MEME", trending_bars(), [], 10_000)
        self.assertEqual(candidate.action, Action.REJECT)
        self.assertTrue(any("outside" in blocker for blocker in candidate.blockers))


if __name__ == "__main__":
    unittest.main()
