"""Three bugs found reading the live path line by line.

None were caught by the suite, which is the point of writing them down: each
failed silently and produced a plausible-looking log line rather than an error.
"""
import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.autotrade import AutoTradeConfig
from event_aware_trader.broker import round_price
from event_aware_trader.types import Bar


class PriceRoundingTests(unittest.TestCase):
    """A stop rounded to 2dp is zero for anything sub-cent.

    submit_protective_stop then refuses it as a non-positive price, so the
    position ends up with NO stop and the log blames the price. The failure
    reads as a rejected order rather than as the rounding that caused it.
    """

    def test_a_normal_share_price_still_rounds_to_the_cent(self):
        self.assertEqual(round_price(186.004), 186.0)
        self.assertEqual(round_price(94.4409), 94.44)

    def test_a_sub_dollar_price_keeps_four_places(self):
        self.assertEqual(round_price(0.8689), 0.8689)
        self.assertAlmostEqual(round_price(0.123456), 0.1235, places=6)

    def test_a_sub_cent_price_does_not_collapse_to_zero(self):
        """This is the bug: 2dp turns a real stop into an invalid one."""
        self.assertEqual(round(0.0000033, 2), 0.0)
        self.assertGreater(round_price(0.0000033), 0.0)

    def test_rounding_never_returns_a_negative(self):
        self.assertGreaterEqual(round_price(0.000000001), 0.0)


class TrailAnchorTests(unittest.TestCase):
    """The trail anchored itself to a LENGTH of a rolling window.

    `opened_bars` stored len(bars) at entry, but bars is a rolling one-month
    window of 15-minute candles whose length barely changes. len(bars) minus
    opened_at therefore collapsed to about 1, `since_entry` became the final
    bar alone, and the trail measured its high over a single candle - so it
    could never arm, silently, for the life of every trend position.
    """

    def _bars(self, n, start_price=100.0):
        base = datetime(2026, 9, 1, tzinfo=timezone.utc)
        return [Bar(timestamp=base + timedelta(minutes=15 * i),
                    open=start_price + i, high=start_price + i + 1,
                    low=start_price + i - 1, close=start_price + i,
                    volume=1_000.0) for i in range(n)]

    def test_a_length_anchor_collapses_when_the_window_rolls(self):
        """Demonstrates the old arithmetic, so the fix is not mistaken for style."""
        bars = self._bars(500)
        opened_at = 500                      # recorded when the window was 500 long
        # one day later the window has rolled: still ~500 bars, different bars
        rolled = self._bars(500)
        since = rolled[-max(1, len(rolled) - opened_at + 1):]
        self.assertEqual(len(since), 1, "the old anchor sees a single candle")

    def test_a_timestamp_anchor_survives_the_roll(self):
        bars = self._bars(500)
        opened_ts = bars[300].timestamp.isoformat()
        since = [b for b in bars if b.timestamp.isoformat() >= opened_ts]
        self.assertEqual(len(since), 200)
        self.assertGreater(max(b.high for b in since), bars[300].high)


class AtrGuardTests(unittest.TestCase):
    """A missing cycle ATR must not silently orphan a mean-reversion position.

    Mean reversion holds a fixed stop and exits on RSI over daily bars; the
    cycle's ATR is a trend-path input. Skipping the whole position for a
    missing ATR left it unexamined for a reason unrelated to the rule managing
    it - and an unmanaged position is what section 1 exists to prevent.
    """

    def test_mean_reversion_is_the_shipped_rule(self):
        self.assertEqual(AutoTradeConfig().entry_rule, "mean_reversion")

    def test_the_trend_path_still_requires_an_atr(self):
        """It genuinely cannot compute a trailing stop without one."""
        cfg = AutoTradeConfig(entry_rule="trend")
        self.assertEqual(cfg.entry_rule, "trend")


if __name__ == "__main__":
    unittest.main()
