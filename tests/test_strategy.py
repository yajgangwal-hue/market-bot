import math
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from event_aware_trader.strategy import StrategyConfig, generate_candidate
from event_aware_trader.types import Action, Bar


def trending_bars(count=90, drift=0.0045, amplitude=0.012, period=11.0, final_volume=2_500_000):
    """An uptrend that also pulls back, which a real advance always does.

    The previous fixture was a perfectly straight ramp of +2.00 a day.  That
    is not a mild simplification: with no pullback the close sits about 6.3
    ATRs above its own 20-day average forever, so the extension blocker
    rejected it and the "ideal setup" test could never pass.  Adding an
    oscillation around the drift keeps the trend intact while holding
    extension near 2.4 ATRs, which is what the gate is actually designed for.
    """
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    for index in range(count):
        base = 100.0 * math.exp(drift * index)
        close = base * (1.0 + amplitude * math.sin(2.0 * math.pi * index / period))
        span = close * 0.011
        bars.append(
            Bar(
                timestamp=start + timedelta(days=index),
                open=close - span * 0.15,
                high=close + span,
                low=close - span,
                close=close,
                volume=1_000_000 if index < count - 1 else final_volume,
            )
        )
    return bars


def straight_ramp_bars(count=70):
    """A pathological, pullback-free advance used to prove the extension gate."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=start + timedelta(days=index),
            open=100.0 + index * 2.0 - 0.2,
            high=100.0 + index * 2.0 + 1.0,
            low=100.0 + index * 2.0 - 1.0,
            close=100.0 + index * 2.0,
            volume=1_000_000 if index < count - 1 else 2_500_000,
        )
        for index in range(count)
    ]


class StrategyTests(unittest.TestCase):
    def test_future_bars_do_not_change_a_completed_signal(self):
        bars = trending_bars()
        original = generate_candidate("SPY", bars[:60], [], 10_000)
        tampered = list(bars[:60]) + [bars[60]]
        tampered[-1] = Bar(
            timestamp=tampered[-1].timestamp, open=1, high=500, low=0.5, close=2, volume=99_999_999
        )
        repeated = generate_candidate("SPY", tampered[:60], [], 10_000)
        self.assertEqual(original.as_dict(), repeated.as_dict())

    def test_strong_liquid_trend_can_clear_a_paper_only_gate(self):
        candidate = generate_candidate("SPY", trending_bars(), [], 10_000)
        self.assertEqual(candidate.action, Action.PAPER_LONG)
        self.assertGreater(candidate.quantity, 0)
        self.assertGreater(candidate.planned_risk, 0)

    def test_a_thousand_dollar_account_can_still_size_a_high_priced_etf(self):
        """The $1,000 case that whole-share sizing silently disqualified."""
        candidate = generate_candidate("SPY", trending_bars(), [], 1_000)
        self.assertEqual(candidate.action, Action.PAPER_LONG)
        self.assertGreater(candidate.quantity, 0)
        self.assertLess(candidate.quantity, 1.0)
        self.assertLessEqual(candidate.planned_risk, 1_000 * 0.005 + 1e-9)

    def test_extension_blocks_a_pullback_free_advance(self):
        candidate = generate_candidate("SPY", straight_ramp_bars(), [], 10_000)
        self.assertEqual(candidate.action, Action.REJECT)
        self.assertTrue(any("ATRs above" in blocker for blocker in candidate.blockers))

    def test_low_relative_volume_is_scored_not_blocked_by_default(self):
        bars = trending_bars(final_volume=700_000)
        candidate = generate_candidate("SPY", bars, [], 10_000)
        self.assertFalse(any("Relative volume" in blocker for blocker in candidate.blockers))
        participation = [c for c in candidate.score_breakdown if c.name == "participation"]
        self.assertEqual(len(participation), 1)
        self.assertLess(participation[0].contribution, participation[0].maximum)

    def test_strict_participation_gate_restores_the_hard_block(self):
        bars = trending_bars(final_volume=700_000)
        config = replace(StrategyConfig(), strict_participation_gate=True)
        candidate = generate_candidate("SPY", bars, [], 10_000, config=config)
        self.assertEqual(candidate.action, Action.REJECT)
        self.assertTrue(any("Relative volume" in blocker for blocker in candidate.blockers))

    def test_outside_universe_is_rejected(self):
        candidate = generate_candidate("MEME", trending_bars(), [], 10_000)
        self.assertEqual(candidate.action, Action.REJECT)
        self.assertTrue(any("outside" in blocker for blocker in candidate.blockers))


if __name__ == "__main__":
    unittest.main()
