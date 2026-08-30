import unittest
from datetime import datetime, timedelta, timezone

from event_aware_trader.cross_sectional import (
    CROSS_SECTIONAL_FEATURES,
    MIN_PEERS_FOR_A_RANK,
    build_snapshot,
    cross_sectional_features,
)
from event_aware_trader.types import Bar

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def ramp(drift, count=300, start=100.0, vol_scale=0.01):
    bars = []
    price = start
    for i in range(count):
        price *= 1.0 + drift
        span = price * vol_scale
        bars.append(Bar(START + timedelta(days=i), price, price + span,
                        price - span, price, 1_000_000))
    return bars


def universe(n=20):
    """n symbols with monotonically increasing drift, so the ordering is known.

    Drift starts at i=1, not i=0: a zero-drift symbol is exactly flat, so its
    close equals its own moving average and it is correctly NOT counted as
    "above" it. That made a full-breadth fixture read 0.95 rather than 1.0.
    """
    return {"S%02d" % i: ramp(0.0002 * (i + 1)) for i in range(n)}


class SnapshotTests(unittest.TestCase):
    def test_a_snapshot_summarises_the_whole_universe(self):
        snap = build_snapshot(universe())
        self.assertIsNotNone(snap)
        self.assertEqual(snap.peer_count, 20)

    def test_too_few_peers_yields_no_snapshot(self):
        """A rank over five names is noise wearing a percentile."""
        self.assertIsNone(build_snapshot(universe(MIN_PEERS_FOR_A_RANK - 1)))

    def test_symbols_with_too_little_history_are_omitted_not_defaulted(self):
        series = universe(12)
        series["SHORT"] = ramp(0.001, count=20)
        snap = build_snapshot(series)
        self.assertNotIn("SHORT", snap.momentum_63)

    def test_breadth_is_the_fraction_above_the_long_average(self):
        rising = {"U%02d" % i: ramp(0.001) for i in range(10)}
        falling = {"D%02d" % i: ramp(-0.001) for i in range(10)}
        merged = dict(rising); merged.update(falling)
        self.assertAlmostEqual(build_snapshot(merged).breadth, 0.5, places=2)

    def test_breadth_is_one_when_everything_is_rising(self):
        self.assertAlmostEqual(build_snapshot(universe()).breadth, 1.0, places=6)

    def test_a_perfectly_flat_symbol_does_not_count_as_above_its_average(self):
        series = {"S%02d" % i: ramp(0.0002 * (i + 1)) for i in range(19)}
        series["FLAT"] = ramp(0.0)
        self.assertAlmostEqual(build_snapshot(series).breadth, 19 / 20, places=6)


class RankTests(unittest.TestCase):
    def setUp(self):
        self.snap = build_snapshot(universe())

    def test_the_strongest_symbol_ranks_near_the_top(self):
        self.assertGreater(cross_sectional_features("S19", self.snap)["rank_mom63"], 0.9)

    def test_the_weakest_symbol_ranks_near_the_bottom(self):
        self.assertLess(cross_sectional_features("S00", self.snap)["rank_mom63"], 0.1)

    def test_ranks_are_bounded(self):
        for symbol in ("S00", "S10", "S19"):
            for name, value in cross_sectional_features(symbol, self.snap).items():
                if name.startswith("rank_"):
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 1.0)

    def test_an_unknown_symbol_gets_neutral_ranks_not_invented_ones(self):
        features = cross_sectional_features("NOT_IN_UNIVERSE", self.snap)
        self.assertEqual(features["rank_mom63"], 0.5)

    def test_no_snapshot_gives_neutral_features(self):
        features = cross_sectional_features("SPY", None)
        self.assertEqual(features["rank_mom63"], 0.5)
        self.assertEqual(set(features), set(CROSS_SECTIONAL_FEATURES))

    def test_relative_strength_has_the_right_sign(self):
        strong = cross_sectional_features("S19", self.snap)["rel_to_mkt"]
        weak = cross_sectional_features("S00", self.snap)["rel_to_mkt"]
        self.assertGreater(strong, 0.0)
        self.assertLess(weak, 0.0)

    def test_every_declared_feature_is_produced(self):
        features = cross_sectional_features("S05", self.snap)
        self.assertEqual(set(features), set(CROSS_SECTIONAL_FEATURES))
        for value in features.values():
            self.assertEqual(value, value)          # not NaN


class NoLookaheadTests(unittest.TestCase):
    def test_a_snapshot_only_sees_bars_it_was_given(self):
        series = universe()
        early = {s: b[:200] for s, b in series.items()}
        late = {s: b[:250] for s, b in series.items()}
        self.assertLess(build_snapshot(early).as_of, build_snapshot(late).as_of)

    def test_future_bars_cannot_change_an_earlier_snapshot(self):
        series = universe()
        cut = {s: b[:200] for s, b in series.items()}
        baseline = cross_sectional_features("S10", build_snapshot(cut))
        tampered = {s: list(b) for s, b in series.items()}
        for s in tampered:
            tampered[s][250] = Bar(tampered[s][250].timestamp, 1e6, 1e6, 1e6, 1e6, 1e9)
        after = cross_sectional_features("S10", build_snapshot({s: b[:200] for s, b in tampered.items()}))
        self.assertEqual(baseline, after)


if __name__ == "__main__":
    unittest.main()
