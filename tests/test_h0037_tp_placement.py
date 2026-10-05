"""H-0037: replaying one trade under four take-profit placements, on hand-checkable bars."""

import random
import sys
import unittest
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import h0037_tp_placement as tp                                       # noqa: E402
from event_aware_trader.indicators import rsi                         # noqa: E402

Bar = namedtuple("Bar", "open high low close")


def history(n=60, seed=1, start=100.0):
    rng = random.Random(seed)
    out = [start]
    for _ in range(n - 1):
        out.append(out[-1] * (1 + rng.gauss(0, 0.012)))
    return out


def setup(closes_before, after):
    """Arrays the replay needs: Wilder averages and close of the session before each bar."""
    closes = list(closes_before) + [b.close for b in after]
    ag, al = tp.wilder_averages(closes)
    base = len(closes_before) - 1
    return ([ag[base + i] for i in range(len(after))], [al[base + i] for i in range(len(after))],
            [closes[base + i] for i in range(len(after))])


class Wilder(unittest.TestCase):
    def test_averages_match_the_bots_rsi(self):
        closes = history()
        ag, al = tp.wilder_averages(closes)
        for i in (20, 35, 59):
            expected = rsi(closes[:i + 1])
            got = 100 - 100 / (1 + ag[i] / al[i])
            self.assertAlmostEqual(got, expected, places=9)

    def test_bounce_price_puts_rsi_exactly_at_60(self):
        for seed in range(8):
            closes = history(seed=seed)
            ag, al = tp.wilder_averages(closes)
            price = tp.bounce_price(closes[-1], ag[-1], al[-1])
            self.assertAlmostEqual(rsi(closes + [price]), 60.0, places=7)


class Replay(unittest.TestCase):
    def trade(self, after, policy, haircut=0.0, closes_before=None):
        closes_before = closes_before or [100.0 - 0.3 * i for i in range(30)]   # a steady fall: RSI low
        ag, al, prev = setup(closes_before, after)
        entry = closes_before[-1]
        return tp.replay(after, ag, al, prev, entry, stop=entry - 5.0, take=entry + 5.0,
                         policy=policy, haircut=haircut)

    def test_stop_gap_fills_at_the_open(self):
        out = self.trade([Bar(85.0, 86.0, 84.0, 85.5)], "A")
        self.assertEqual(out, (85.0, "stop", 1))

    def test_take_profit_fills_at_its_level_in_b(self):
        entry = 100.0 - 0.3 * 29
        out = self.trade([Bar(entry + 1, entry + 6, entry + 0.5, entry + 2)], "B")
        self.assertEqual(out, (entry + 5.0, "limit", 1))

    def test_c_sells_at_the_bounce_level_not_the_close(self):
        closes_before = [100.0 - 0.3 * i for i in range(30)]
        ag, al = tp.wilder_averages(closes_before)
        level = tp.bounce_price(closes_before[-1], ag[-1], al[-1])
        bar = Bar(closes_before[-1], level + 0.5, closes_before[-1] - 0.1, level + 0.4)
        out = self.trade([bar], "C", closes_before=closes_before)
        self.assertAlmostEqual(out[0], level)
        self.assertEqual(out[1:], ("limit", 1))
        # the same bar under A exits at the close, by rule, with the haircut
        a = self.trade([bar], "A", haircut=0.01, closes_before=closes_before)
        self.assertEqual(a[1], "reverted")
        self.assertAlmostEqual(a[0], bar.close * 0.99)

    def test_d_uses_the_lower_of_the_two_limits(self):
        closes_before = [100.0 - 0.3 * i for i in range(30)]
        ag, al = tp.wilder_averages(closes_before)
        level = tp.bounce_price(closes_before[-1], ag[-1], al[-1])
        entry = closes_before[-1]
        take = entry + 5.0
        low_limit = min(level, take)
        bar = Bar(entry, max(level, take) + 1.0, entry - 0.1, entry)
        out = self.trade([bar], "D", closes_before=closes_before)
        self.assertAlmostEqual(out[0], low_limit)

    def test_a_bar_reaching_both_goes_to_the_stop(self):
        entry = 100.0 - 0.3 * 29
        out = self.trade([Bar(entry, entry + 6, entry - 6, entry)], "B")
        self.assertEqual(out[1], "stop")

    def test_time_exit_after_twenty_sessions_pays_the_haircut(self):
        entry = 100.0 - 0.3 * 29
        flat = [Bar(entry, entry + 0.1, entry - 0.1, entry)] * 25
        out = self.trade(flat, "A", haircut=0.005)
        self.assertEqual(out[1:], ("time", 20))
        self.assertAlmostEqual(out[0], entry * 0.995)

    def test_not_enough_data_returns_none(self):
        entry = 100.0 - 0.3 * 29
        self.assertIsNone(self.trade([Bar(entry, entry, entry, entry)] * 3, "A"))

    def test_net_r(self):
        self.assertAlmostEqual(tp.net_r(110.0, 100.0, 5.0), (110.0 * 0.9994 - 100.0) / 5.0)


if __name__ == "__main__":
    unittest.main()
