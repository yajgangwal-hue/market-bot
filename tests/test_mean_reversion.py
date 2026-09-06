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
        """bars_held of 2 is the first bar that lies wholly after the entry."""
        bars = make([100.0] * 30 + [80.0])
        self.assertEqual(should_exit(bars, 100.0, 95.0, 2), "stop")

    def test_a_bar_that_predates_the_entry_cannot_breach_the_stop(self):
        """Measured live on EWY: the stop check read the morning's low.

        EWY was entered at 15:00 ET behind a stop at 186.00. The most recent
        daily bar was that same day's, whose low of 181.30 came from before
        the position existed, so this returned "stop" and the next cycle would
        have closed a position sitting on +$161 - while the real broker-side
        stop had correctly never fired.
        """
        bars = make([100.0] * 30 + [80.0])
        self.assertIsNone(should_exit(bars, 100.0, 95.0, 0))
        self.assertIsNone(should_exit(bars, 100.0, 95.0, 1))

    def test_an_entry_timestamp_is_used_in_preference_to_the_bar_count(self):
        bars = make([100.0] * 30 + [80.0])
        after = bars[-1].timestamp.isoformat()
        before = bars[-2].timestamp.isoformat()
        # The last bar closed before the entry: not comparable, whatever the count.
        self.assertIsNone(should_exit(bars, 100.0, 95.0, 9, entry_time=after))
        # The entry predates the last bar: the breach is real.
        self.assertEqual(should_exit(bars, 100.0, 95.0, 0, entry_time=before), "stop")

    def test_a_naive_bar_and_a_utc_entry_are_compared_by_date(self):
        """Comparing the ISO strings got this backwards.

        Bar timestamps are naive market-local ("...T16:00:00"); entry
        timestamps are tz-aware UTC ("...T19:00:24+00:00"). Lexically the bar
        sorts before the entry, while 16:00 ET is really 20:00 UTC - after it.
        A bar that closed after the entry was judged to have closed before,
        which suppresses a stop exit that should fire.
        """
        bars = make([100.0] * 30 + [80.0])
        same_day = bars[-1].timestamp.date().isoformat() + "T19:00:24.557774+00:00"
        day_before = (bars[-2].timestamp.date().isoformat()
                      + "T19:00:24.557774+00:00")
        # The raw strings would compare the wrong way round.
        self.assertLess(bars[-1].timestamp.isoformat(), same_day)
        # Same session as the entry: still holds pre-entry hours, so no exit.
        self.assertIsNone(should_exit(bars, 100.0, 95.0, 5, entry_time=same_day))
        # An earlier session: the bar is wholly after the entry, so it fires.
        self.assertEqual(
            should_exit(bars, 100.0, 95.0, 0, entry_time=day_before), "stop")

    def test_an_unparseable_entry_time_falls_back_to_the_bar_count(self):
        bars = make([100.0] * 30 + [80.0])
        self.assertIsNone(should_exit(bars, 100.0, 95.0, 1, entry_time="junk"))
        self.assertEqual(should_exit(bars, 100.0, 95.0, 2, entry_time="junk"), "stop")

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
