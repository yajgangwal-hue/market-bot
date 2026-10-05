"""H-0033's replication of the published noise-area rule, on hand-checkable days."""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import h0033_noise_area as na                                         # noqa: E402

UTC = timezone.utc


def day_bars(d, open_, path, volume=1000.0, edt=True):
    """5-minute regular-session bars for one day. `path(i)` gives the close of
    bar i (i = 0 is the 09:30 bar); vw is the close."""
    offset = 4 if edt else 5
    start = datetime(d.year, d.month, d.day, 9 + offset, 30, tzinfo=UTC)
    bars = []
    for i in range(78):                                   # 09:30 .. 15:55
        c = path(i)
        o = open_ if i == 0 else path(i - 1)
        bars.append({"t": (start + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": volume, "vw": c})
    return bars


def quiet(i, base=100.0):
    return base * (1 + (0.001 if i % 2 else -0.001))       # +-0.1% chop, sigma ~0.1%


def trading_days(n, first=date(2024, 6, 3)):
    out, d = [], first
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


class BuildSessions(unittest.TestCase):
    def test_open_checks_vwap_and_close(self):
        d = date(2024, 6, 3)
        s = na.build_sessions(day_bars(d, 100.0, lambda i: 100.0 + i * 0.01))[d]
        self.assertTrue(s.complete)
        self.assertEqual(s.open, 100.0)
        self.assertAlmostEqual(s.price[(10, 0)], 100.0 + 5 * 0.01)       # the 09:55 bar
        self.assertAlmostEqual(s.close_1600, 100.0 + 77 * 0.01)
        self.assertAlmostEqual(s.vwap[(10, 0)], sum(100.0 + i * 0.01 for i in range(6)) / 6)

    def test_an_early_close_ends_at_one_and_is_not_tradeable(self):
        d = date(2024, 7, 3)                                  # NYSE closes 13:00
        s = na.build_sessions(day_bars(d, 100.0, lambda i: 100.0 + i))[d]
        self.assertFalse(s.complete)
        self.assertEqual(s.close, 100.0 + 41)                 # the 12:55 bar, not after-hours
        self.assertNotIn((13, 30), s.price)

    def test_winter_time(self):
        d = date(2024, 1, 3)
        s = na.build_sessions(day_bars(d, 50.0, lambda i: 50.0, edt=False))[d]
        self.assertTrue(s.complete)


class Rule(unittest.TestCase):
    def sessions(self, last_path):
        days = trading_days(17)
        bars = []
        for d in days[:-1]:
            bars += day_bars(d, 100.0, quiet)
        bars += day_bars(days[-1], 100.0, last_path)
        return days, na.build_sessions(bars)

    def test_a_trend_above_band_and_vwap_is_held_long_to_the_close(self):
        days, sessions = self.sessions(lambda i: 100.0 + 0.1 * (i + 1))    # steady climb
        out = na.run(sessions, days[-1], days[-1], cost_per_share=0.0)
        [(_, equity)] = out["curve"]
        shares = 100_000 // 100
        entry = sessions[days[-1]].price[(10, 0)]
        self.assertAlmostEqual(equity - 100_000, shares * (sessions[days[-1]].close_1600 - entry), places=6)
        self.assertEqual(out["trades"], 1)

    def test_quiet_days_never_trade(self):
        days, sessions = self.sessions(quiet)
        out = na.run(sessions, days[-1], days[-1], cost_per_share=0.0045)
        self.assertEqual(out["trades"], 0)
        self.assertAlmostEqual(out["curve"][0][1], 100_000.0)

    def test_costs_are_charged_per_share_each_side(self):
        days, sessions = self.sessions(lambda i: 100.0 + 0.1 * (i + 1))
        free = na.run(sessions, days[-1], days[-1], cost_per_share=0.0)["curve"][0][1]
        paid = na.run(sessions, days[-1], days[-1], cost_per_share=0.0045)["curve"][0][1]
        self.assertAlmostEqual(free - paid, 2 * 1000 * 0.0045)

    def test_dynamic_sizing_is_capped_at_four(self):
        days, sessions = self.sessions(lambda i: 100.0 + 0.1 * (i + 1))
        out = na.run(sessions, days[-1], days[-1], sizing="dynamic", cost_per_share=0.0)
        flat = na.run(sessions, days[-1], days[-1], cost_per_share=0.0)
        gain_dyn = out["curve"][0][1] - 100_000
        gain_flat = flat["curve"][0][1] - 100_000
        self.assertAlmostEqual(gain_dyn / gain_flat, 4.0, places=2)   # quiet history -> tiny vol -> cap

    def test_dynamic_sizing_targets_two_percent_of_daily_volatility(self):
        # quiet intraday moves, but daily closes alternate +-1.5%: sigma_SPY is the
        # sample stdev of the previous 14 close-to-close returns, so exposure < 4
        days = trading_days(17)
        bars, closes = [], []
        for n, d in enumerate(days[:-1]):
            base = 100.0 * (1.015 if n % 2 else 1.0)
            closes.append(base * 1.001)
            bars += day_bars(d, base, lambda i, b=base: quiet(i, b))
        bars += day_bars(days[-1], 100.0, lambda i: 100.0 + 0.1 * (i + 1))
        sessions = na.build_sessions(bars)
        rets = [closes[k] / closes[k - 1] - 1 for k in range(len(closes) - 14, len(closes))]
        exposure = min(4.0, 0.02 / __import__("statistics").stdev(rets))
        self.assertLess(exposure, 4.0)
        dyn = na.run(sessions, days[-1], days[-1], sizing="dynamic", cost_per_share=0.0)
        flat = na.run(sessions, days[-1], days[-1], cost_per_share=0.0)
        gain_flat = flat["curve"][0][1] - 100_000
        self.assertGreater(gain_flat, 0)
        shares = int(100_000 * exposure / sessions[days[-1]].open)
        self.assertAlmostEqual(dyn["curve"][0][1] - 100_000, gain_flat * shares / 1000, places=4)


class SpyHold(unittest.TestCase):
    def test_same_days_as_the_strategy(self):
        days = trading_days(3)
        bars = []
        for d, level in zip(days, (100.0, 110.0, 99.0)):
            bars += day_bars(d, level, lambda i, x=level: x)
        sessions = na.build_sessions(bars)
        curve, rets = na.spy_hold(sessions, days[1], days[2])
        self.assertEqual([d for d, _ in curve], days[1:])
        self.assertAlmostEqual(rets[0], 0.10)                 # day 2 over day 1's close
        self.assertAlmostEqual(na.metrics(curve, rets)["total_return"], -0.01)


if __name__ == "__main__":
    unittest.main()
