"""H-0036: the 7,846-rule technical-analysis universe on 5-minute bars, and the
data-snooping tests, on hand-checkable inputs."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import h0036_ta_universe as ta                                        # noqa: E402


def sessions_from_closes(closes, volume=1000.0):
    """Synthetic sessions of 78 bars from a flat list of closes (length a multiple of 78)."""
    out, d = {}, date(2024, 1, 2)
    for s in range(len(closes) // ta.BARS):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out[d] = [{"c": float(c), "v": volume} for c in closes[s * ta.BARS:(s + 1) * ta.BARS]]
        d += timedelta(days=1)
    return out


class Universe(unittest.TestCase):
    def test_counts_match_appendix_a(self):
        rules = ta.universe()
        self.assertEqual(len(rules), 7846)
        self.assertEqual(len(set(rules)), 7846)


class BuildingBlocks(unittest.TestCase):
    def test_ffill_state(self):
        sig = np.array([0, 0, 1, 0, 0, -1, 0], dtype=np.int8)
        self.assertEqual(ta._ffill_state(sig).tolist(), [0, 0, 1, 1, 1, -1, -1])

    def test_hold_ignores_signals_inside_the_hold_then_goes_neutral(self):
        ev = np.array([0, 1, 0, -1, 0, 0, 0, -1, 0, 0], dtype=np.int8)
        self.assertEqual(ta._hold(ev, 3).tolist(), [0, 1, 1, 1, 0, 0, 0, -1, -1, -1])

    def test_delay_waits_for_d_bars(self):
        st = np.array([1, 1, -1, 1, 1, 1, -1, -1], dtype=np.int8)
        self.assertEqual(ta._delay(st, 2).tolist(), [0, 1, 1, 1, 1, 1, 1, -1])

    def test_crossings(self):
        st = np.array([0, 1, 1, -1, -1, 1], dtype=np.int8)
        self.assertEqual(ta._crossings(st).tolist(), [0, 1, 0, -1, 0, 1])


class Rules(unittest.TestCase):
    def series(self, closes, cost=0.0):
        return ta.Series(sessions_from_closes(closes), cost)

    def test_filter_rule_switches_on_x_percent_moves_from_extremes(self):
        head = [100, 105, 111, 115, 103, 110, 114]
        s = self.series(head + [114] * (ta.BARS - len(head)))
        pos = s._filter_states(0.10)
        # 111 >= 100*1.1 -> long; high 115; 103 <= 115*0.9 -> short; low 103; 114 >= 113.3 -> long
        self.assertEqual(pos[:7].tolist(), [0, 0, 1, 1, -1, -1, 1])

    def test_filter_with_neutral_band_y(self):
        head = [100, 111, 120, 113, 100]
        s = self.series(head + [100] * (ta.BARS - len(head)))
        pos = s._filter_states(0.10, 0.05)
        # long at 111; high 120; 113 <= 120*0.95=114 -> neutral (high and low reset to 113);
        # 100 <= 113*0.9=101.7 -> short
        self.assertEqual(pos[:5].tolist(), [0, 1, 1, 0, -1])

    def test_support_resistance_breaks_previous_n_extremes(self):
        head = [10, 11, 12, 13, 12, 11, 9]
        s = self.series(head + [9] * (ta.BARS - len(head)))
        pos = s.position(("sr", "plain", ("n", 3), 0.0, None), {})
        # 13 > max(10, 11, 12) -> long; 11 < min(12, 13, 12) -> short
        self.assertEqual(pos[:7].tolist(), [0, 0, 0, 1, 1, -1, -1])

    def test_channel_breakout_needs_a_narrow_channel(self):
        head = [100, 100.2, 100.1, 100.15, 101.5]
        s = self.series(head + [101.5] * (ta.BARS - len(head)))
        pos = s.position(("channel", "plain", 3, 0.005, 0.0, 5), {})
        # 100.15 stays inside 100.0..100.2; then the previous 3 closes span 100.1..100.2,
        # within 0.5%, and 101.5 breaks above -> long for 5 bars
        self.assertEqual(pos[:10].tolist(), [0, 0, 0, 0, 1, 1, 1, 1, 1, 0])

    def test_moving_average_band_is_neutral_inside(self):
        s = self.series([100.0] * ta.BARS)
        pos = s.position(("ma", "band", ("single", 2), 0.01), {})
        self.assertTrue((pos == 0).all())

    def test_every_rule_runs_on_three_sessions(self):
        rng = np.random.default_rng(1)
        closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.001, 3 * ta.BARS)))
        s = self.series(closes.tolist(), cost=0.0045)
        gross, net = ta.run_universe(s, ta.universe())
        self.assertEqual(gross.shape, (7846, 3))
        self.assertTrue(np.isfinite(net).all())
        self.assertTrue((net <= gross + 1e-15).all())


class DailyPnL(unittest.TestCase):
    def test_flat_at_the_close_and_costs_on_entry_changes_and_exit(self):
        closes = [100.0 + i for i in range(ta.BARS)] + [200.0] * ta.BARS
        s = ta.Series(sessions_from_closes(closes), 0.01)
        pos = np.ones(2 * ta.BARS, dtype=np.int8)
        gross, net = s.daily(pos)
        expected = sum((100.0 + j) / (99.0 + j) - 1 for j in range(1, ta.BARS))
        self.assertAlmostEqual(gross[0], expected)
        self.assertAlmostEqual(gross[1], 0.0)            # the overnight jump to 200 is never earned
        self.assertAlmostEqual(gross[0] - net[0], 0.01 / 100.0 + 0.01 / (100.0 + ta.BARS - 1))
        self.assertAlmostEqual(gross[1] - net[1], 0.01 / 200.0 + 0.01 / 200.0)


class DataSnooping(unittest.TestCase):
    def test_pure_noise_is_not_significant(self):
        rng = np.random.default_rng(7)
        d = rng.normal(0, 0.01, (60, 600))
        out = ta.reality_check_and_spa(d, n_boot=300)
        self.assertGreater(out["reality_check_p"], 0.05)
        self.assertGreater(out["spa_p"], 0.05)

    def test_a_real_edge_is_found_among_noise(self):
        rng = np.random.default_rng(8)
        d = rng.normal(0, 0.01, (60, 600))
        d[17] += 0.004                                    # t about 10
        out = ta.reality_check_and_spa(d, n_boot=300)
        self.assertEqual(out["best_index_among_tested"], 17)
        self.assertLess(out["reality_check_p"], 0.01)
        self.assertLess(out["spa_p"], 0.01)

    def test_stationary_indices_are_in_range_and_blocky(self):
        rng = np.random.default_rng(3)
        idx = ta.stationary_indices(1000, 0.1, rng)
        self.assertTrue(((idx >= 0) & (idx < 1000)).all())
        steps = np.diff(idx)
        self.assertGreater(((steps == 1) | (steps == -999)).mean(), 0.8)   # mostly block continuations


if __name__ == "__main__":
    unittest.main()
