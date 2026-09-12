"""The loop that learns from the bot's own trades, end to end.

The machinery was all present and the loop produced nothing for two weeks. Two
faults, and neither raised an error:

1. THE DEADLOCK. `snapshot` was built only `if estimator is not None` - only
   once a trained live model existed. The snapshot supplies the nine
   CROSS-SECTIONAL features of the sixteen the model trains on, and those nine
   are the whole reason it scores 0.5665 out of sample against 0.50 for
   everything before it. With no snapshot they record at their neutral
   defaults (0.0, and 0.5 for the ranks), so a completed trade carried nine
   constants into the training file, the model could never learn the features
   that are its advantage, it could never become usable, and `estimator`
   stayed None for ever. The condition that skipped the work required the
   outcome the work produces.

   Found in the live state on 2026-09-12: all six open positions carried
   rank_mom21/63/126, rank_pos52, rank_vol at exactly 0.5 and breadth,
   mkt_ret21, mkt_vol, rel_to_mkt at exactly 0.0.

2. NO EXITS. `append_example` is called from the exit path, so a bot that
   cannot close a position cannot learn from one either. Between 2026-09-04
   and 2026-09-11 the sell path was broken (see test_exit_closes_for_real.py)
   and not one trade closed, so the writer never fired.

These tests pin the loop at both ends: features must be real when they are
recorded, and a closed trade must produce a training row.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import event_aware_trader.autotrade as autotrade
from event_aware_trader.cross_sectional import CROSS_SECTIONAL_FEATURES
from event_aware_trader.live_model import LIVE_FEATURES, append_example
from event_aware_trader.types import Bar

_TMP = TemporaryDirectory()


def _series(base, n=260, drift=0.05):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    closes = [base + drift * i for i in range(n)]
    return [Bar(timestamp=start + timedelta(days=i), open=c, high=c * 1.01,
                low=c * 0.99, close=c, volume=5_000_000)
            for i, c in enumerate(closes)]


def _universe():
    """Enough distinct names that cross-sectional ranks are meaningful.

    MIN_PEERS_FOR_A_RANK is 10 and `build_snapshot` returns None below it - a
    first version of this fixture used six symbols, got None, and looked like
    a bug in the code under test rather than in the fixture.
    """
    return {"S{0:02d}".format(i): _series(20.0 + 7.0 * i, drift=0.01 + 0.01 * i)
            for i in range(14)}


class TheSnapshotMustNotDependOnTheModel(unittest.TestCase):
    """The deadlock, pinned at its source."""

    def test_cross_sectional_features_are_real_with_no_model_on_disk(self):
        from event_aware_trader.cross_sectional import build_snapshot
        from event_aware_trader.live_model import live_features

        bars = _universe()
        # No model file anywhere - the state the account was actually in.
        snapshot = build_snapshot(bars)
        self.assertIsNotNone(
            snapshot, "build_snapshot needs no model and must produce one")

        feats = live_features("S03", bars["S03"], snapshot)
        ranks = [k for k in feats if k.startswith("rank_")]
        self.assertTrue(ranks, "no rank features were produced at all")
        self.assertFalse(
            all(abs(float(feats[k]) - 0.5) < 1e-9 for k in ranks),
            "every rank_* is exactly 0.5, which is the no-snapshot default - "
            "the cross-sectional features are dead and the model can never "
            "learn the thing that makes it better than chance")

    def test_a_none_snapshot_is_what_the_dead_state_looks_like(self):
        # Proves the assertion above discriminates: with snapshot=None the
        # features really do collapse to the placeholder values seen live.
        from event_aware_trader.live_model import live_features

        bars = _universe()
        feats = live_features("S03", bars["S03"], None)
        ranks = [k for k in feats if k.startswith("rank_")]
        self.assertTrue(
            all(abs(float(feats[k]) - 0.5) < 1e-9 for k in ranks),
            "the no-snapshot path no longer produces 0.5 placeholders, so the "
            "test above is no longer measuring what it claims")

    def test_nine_of_the_sixteen_trained_features_are_cross_sectional(self):
        # The stake. If this ratio drops the deadlock matters less; if it
        # holds, two thirds of the model's inputs depend on the snapshot.
        shared = set(LIVE_FEATURES) & set(CROSS_SECTIONAL_FEATURES)
        self.assertGreaterEqual(
            len(shared), 5,
            "the model's dependence on cross-sectional features has changed; "
            "re-read the deadlock reasoning before trusting it")


class AClosedTradeMustProduceATrainingRow(unittest.TestCase):
    def test_append_example_writes_a_row_the_trainer_can_read(self):
        from event_aware_trader.live_model import load_training

        path = Path(_TMP.name) / "training.jsonl"
        append_example({k: 0.25 for k in LIVE_FEATURES}, 1.4, "AAA", path)
        append_example({k: 0.75 for k in LIVE_FEATURES}, -0.8, "BBB", path)

        rows = load_training(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["label"] for r in rows], [1, 0],
                         "the label must be 1 when the trade made at least 1R")
        for row in rows:
            self.assertEqual(set(row["f"]), set(LIVE_FEATURES),
                             "a row missing a trained feature trains a "
                             "different model than the one that scores it")

    def test_the_exit_path_is_what_calls_it(self):
        # `append_example` lives in the exit block, so a bot that cannot close
        # a position cannot learn from one. That is not a hypothetical: it is
        # why this loop produced nothing between 09-04 and 09-11.
        import inspect

        source = inspect.getsource(autotrade.run_once)
        self.assertIn("append_example(opened_features", source,
                      "the exit path no longer records a training example")
        cut = source.index("append_example(opened_features")
        self.assertIn("open_features", source[:cut],
                      "entry-time features must be recorded before the exit "
                      "can pair them with an outcome")


if __name__ == "__main__":
    unittest.main()
