import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.mean_reversion import (
    MeanReversionConfig,
    evaluate,
    should_exit,
)
from event_aware_trader.types import Bar

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make(closes, volume=2_000_000):
    return [
        Bar(timestamp=START + timedelta(days=i), open=c, high=c * 1.01,
            low=c * 0.99, close=c, volume=volume)
        for i, c in enumerate(closes)
    ]


def uptrend_then_dip(length=260, dip=0.95, dip_bars=12):
    """A long advance ending in an uninterrupted decline.

    The decline has to be monotonic to actually drive RSI down: an earlier
    version bounced part-way through and only reached RSI 45.8, which is not
    oversold and so never triggered the rule under test.
    """
    # A steeper advance leaves the 200-day average far enough below that a
    # pullback can be genuinely oversold while the uptrend is still intact -
    # which is precisely the setup the rule is meant to find.
    closes = [100.0 * (1.0 + 0.003 * i) for i in range(length - dip_bars)]
    peak = closes[-1]
    step = (1.0 - dip) / dip_bars
    for i in range(1, dip_bars + 1):
        closes.append(peak * (1.0 - step * i))
    return make(closes)


class EntryTests(unittest.TestCase):
    def test_oversold_inside_an_uptrend_is_a_buy(self):
        signal = evaluate("SPY", uptrend_then_dip())
        self.assertTrue(signal.is_buy, signal.reasons)
        self.assertIsNotNone(signal.stop)
        self.assertLess(signal.stop, signal.close)

    def test_strength_without_weakness_is_not_a_buy(self):
        closes = [100.0 * (1.0 + 0.002 * i) for i in range(260)]
        signal = evaluate("SPY", make(closes))
        self.assertFalse(signal.is_buy)
        self.assertTrue(any("RSI" in r for r in signal.reasons))

    def test_weakness_below_the_long_average_is_refused(self):
        """Buying a dip only makes sense inside an intact uptrend."""
        closes = [100.0 * (1.0 - 0.002 * i) for i in range(260)]
        signal = evaluate("SPY", make(closes))
        self.assertFalse(signal.is_buy)
        self.assertTrue(any("200-day" in r for r in signal.reasons))

    def test_a_falling_knife_is_refused_by_the_volatility_ceiling(self):
        bars = uptrend_then_dip(dip=0.55)     # violent collapse
        config = MeanReversionConfig(max_atr_fraction=0.02)
        signal = evaluate("SPY", bars, config)
        self.assertFalse(signal.is_buy)
        self.assertTrue(any("falling knife" in r for r in signal.reasons))

    def test_illiquid_and_cheap_instruments_are_refused(self):
        bars = uptrend_then_dip()
        thin = [Bar(b.timestamp, b.open, b.high, b.low, b.close, 10.0) for b in bars]
        self.assertFalse(evaluate("SPY", thin).is_buy)

    def test_short_history_stands_aside_rather_than_guessing(self):
        signal = evaluate("SPY", make([100.0] * 20))
        self.assertFalse(signal.is_buy)
        self.assertIn("Not enough history", signal.reasons)


class ExitTests(unittest.TestCase):
    def test_a_breached_stop_exits(self):
        bars = make([100.0] * 30 + [80.0])
        self.assertEqual(should_exit(bars, 100.0, 95.0, 1), "stop")

    def test_recovery_to_the_exit_threshold_closes_the_trade(self):
        closes = [100.0] * 20 + [100.0 + i for i in range(1, 20)]
        self.assertEqual(should_exit(make(closes), 100.0, 90.0, 3), "reverted")

    def test_the_time_limit_applies(self):
        bars = make([100.0] * 40)
        config = MeanReversionConfig(max_holding_bars=5)
        self.assertEqual(should_exit(bars, 100.0, 90.0, 5, config), "time")

    def test_an_ordinary_bar_keeps_the_position(self):
        closes = [100.0] * 20 + [99.0, 99.5, 100.0]
        self.assertIsNone(should_exit(make(closes), 100.0, 90.0, 2))


class ConfigTests(unittest.TestCase):
    def test_thresholds_must_be_ordered(self):
        with self.assertRaises(ValueError):
            MeanReversionConfig(rsi_entry=60.0, rsi_exit=40.0)

    def test_stop_multiple_must_be_positive(self):
        with self.assertRaises(ValueError):
            MeanReversionConfig(stop_atr_multiple=0.0)

    def test_the_stop_is_wider_than_the_trend_rule_uses(self):
        """Entries are into weakness, so the stop has to allow for more noise."""
        from event_aware_trader.strategy import StrategyConfig

        self.assertGreater(
            MeanReversionConfig().stop_atr_multiple, StrategyConfig().stop_atr_multiple
        )


if __name__ == "__main__":
    unittest.main()
