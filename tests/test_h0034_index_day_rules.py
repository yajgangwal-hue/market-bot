"""H-0034 / H-0035: the published opening range breakout and VWAP trend rules,
on hand-checkable sessions."""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import h0034_index_day_rules as dr                                   # noqa: E402

UTC = timezone.utc


def bars_for(d, rows, edt=True):
    """rows: list of (o, h, l, c, v) for consecutive 5-minute bars from 09:30."""
    start = datetime(d.year, d.month, d.day, 13 if edt else 14, 30, tzinfo=UTC)
    return [{"t": (start + timedelta(minutes=5 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "o": o, "h": h, "l": l, "c": c, "v": v} for i, (o, h, l, c, v) in enumerate(rows)]


def flat_rest(level, n, v=1000.0):
    return [(level, level, level, level, v)] * n


D = date(2024, 6, 3)


def session(rows):
    return dr.sessions_from(bars_for(D, rows))[D]


class Sessions(unittest.TestCase):
    def test_complete_needs_all_78_bars(self):
        rows = [(100.0, 100.0, 100.0, 100.0, 1.0)] * 78
        self.assertTrue(dr.complete(session(rows)))
        self.assertFalse(dr.complete(session(rows[:77])))

    def test_early_close_drops_after_hours_bars(self):
        d = date(2024, 7, 3)
        s = dr.sessions_from(bars_for(d, [(100.0, 100.0, 100.0, 100.0, 1.0)] * 78))[d]
        self.assertEqual(len(s), 42)                     # 09:30 .. 12:55
        self.assertFalse(dr.complete(s))


class OpeningRangeBreakout(unittest.TestCase):
    FIRST_UP = (100.00, 100.12, 99.95, 100.10, 1000.0)     # up candle, low 99.95

    def test_long_reaches_ten_r(self):
        rows = [self.FIRST_UP, (100.10, 100.20, 100.05, 100.15, 1000.0),
                (100.15, 101.70, 100.10, 101.65, 1000.0)] + flat_rest(101.65, 75)
        pnl, traded, outcome = dr.orb_day(session(rows), 100_000.0, 0.0)
        risk = 100.10 - 99.95
        shares = int(min(100_000 * 0.01 / risk, 4 * 100_000 / 100.10))
        self.assertTrue(traded)
        self.assertEqual(outcome, "target")
        self.assertAlmostEqual(pnl, shares * 10 * risk, places=6)

    def test_stop_at_the_first_candles_low_fills_a_cent_beyond(self):
        rows = [self.FIRST_UP, (100.10, 100.11, 99.90, 99.92, 1000.0)] + flat_rest(99.92, 76)
        pnl, _, outcome = dr.orb_day(session(rows), 100_000.0, 0.0)
        shares = int(min(100_000 * 0.01 / 0.15, 4 * 100_000 / 100.10))
        self.assertEqual(outcome, "stop")
        self.assertAlmostEqual(pnl, -shares * (100.10 - (99.95 - 0.01)), places=6)
        level, _, _ = dr.orb_day(session(rows), 100_000.0, 0.0, stop_slippage=0.0)
        self.assertAlmostEqual(level, -shares * (100.10 - 99.95), places=6)

    def test_a_gap_through_the_stop_fills_at_the_open(self):
        rows = [self.FIRST_UP, (100.10, 100.11, 100.00, 100.02, 1000.0),
                (99.80, 99.85, 99.70, 99.75, 1000.0)] + flat_rest(99.75, 75)
        pnl, _, outcome = dr.orb_day(session(rows), 100_000.0, 0.0)
        shares = int(min(100_000 * 0.01 / 0.15, 4 * 100_000 / 100.10))
        self.assertEqual(outcome, "stop")
        self.assertAlmostEqual(pnl, -shares * (100.10 - 99.80), places=6)

    def test_stop_assumed_first_when_one_candle_reaches_both(self):
        rows = [self.FIRST_UP, (100.10, 101.70, 99.90, 101.0, 1000.0)] + flat_rest(101.0, 76)
        _, _, outcome = dr.orb_day(session(rows), 100_000.0, 0.0)
        self.assertEqual(outcome, "stop")

    def test_held_to_the_close_without_stop_or_target(self):
        rows = [self.FIRST_UP] + flat_rest(100.30, 76) + [(100.30, 100.45, 100.25, 100.40, 1000.0)]
        rows[1] = (100.10, 100.30, 100.05, 100.30, 1000.0)
        pnl, _, outcome = dr.orb_day(session(rows), 100_000.0, 0.0045)
        shares = int(min(100_000 * 0.01 / 0.15, 4 * 100_000 / 100.10))
        self.assertEqual(outcome, "close")
        self.assertAlmostEqual(pnl, shares * (100.40 - 100.10) - 2 * shares * 0.0045, places=6)

    def test_short_side_mirrors(self):
        first_down = (100.00, 100.05, 99.88, 99.90, 1000.0)
        rows = [first_down, (99.90, 99.95, 99.80, 99.85, 1000.0)] + flat_rest(99.85, 76)
        pnl, _, outcome = dr.orb_day(session(rows), 100_000.0, 0.0)
        shares = int(min(100_000 * 0.01 / 0.15, 4 * 100_000 / 99.90))
        self.assertEqual(outcome, "close")
        self.assertAlmostEqual(pnl, shares * (99.90 - 99.85), places=6)

    def test_doji_does_not_trade(self):
        rows = [(100.0, 100.2, 99.8, 100.0, 1000.0)] + flat_rest(101.0, 77)
        self.assertEqual(dr.orb_day(session(rows), 100_000.0, 0.0), (0.0, False, "doji"))


class VwapTrend(unittest.TestCase):
    def test_a_steady_climb_is_long_from_the_second_open_to_the_close(self):
        rows = [(100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 1000.0)
                for i in range(78)]
        pnl, trades = dr.vwap_day(session(rows), 100_000.0, 0.0)
        entry = rows[1][0]
        shares = int(100_000 / entry)
        self.assertEqual(trades, 1)
        self.assertAlmostEqual(pnl, shares * (rows[-1][3] - entry), places=6)

    def test_a_close_below_vwap_reverses_to_short_at_the_next_open(self):
        up = [(100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 1000.0)
              for i in range(10)]                                       # closes 100.1 .. 101.0
        crash = [(101.0, 101.0, 98.0, 98.0, 1000.0)]                    # bar 10 closes far below VWAP
        rest = flat_rest(97.0, 67)
        rows = up + crash + rest
        pnl, trades = dr.vwap_day(session(rows), 100_000.0, 0.0)
        long_entry, reverse_fill = rows[1][0], rows[11][0]
        shares_long = int(100_000 / long_entry)
        realised = shares_long * (reverse_fill - long_entry)
        shares_short = int((100_000 + realised) / reverse_fill)
        self.assertEqual(trades, 2)
        self.assertAlmostEqual(pnl, realised + shares_short * (reverse_fill - rows[-1][3]), places=6)

    def test_costs_are_per_share_per_side(self):
        rows = [(100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 100.0 + 0.1 * i, 100.0 + 0.1 * i + 0.1, 1000.0)
                for i in range(78)]
        free, _ = dr.vwap_day(session(rows), 100_000.0, 0.0)
        paid, _ = dr.vwap_day(session(rows), 100_000.0, 0.0045)
        self.assertAlmostEqual(free - paid, 2 * int(100_000 / rows[1][0]) * 0.0045, places=6)


class Run(unittest.TestCase):
    def test_a_no_trade_session_counts_as_zero(self):
        rows = [(100.0, 100.2, 99.8, 100.0, 1000.0)] + flat_rest(100.0, 77)
        out = dr.run({D: session(rows)}, D, D, "orb", 0.0045)
        self.assertEqual(out["daily_returns"], [0.0])
        self.assertEqual(out["outcomes"], {"doji": 1})


if __name__ == "__main__":
    unittest.main()
