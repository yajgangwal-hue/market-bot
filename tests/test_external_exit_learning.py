"""Every closed trade teaches the model, whatever closed it.

Before 2026-09-14 only the rule's own exits produced a training example. The
stop - 35% of trades and every large loss - taught it nothing, so the record
it learned from had its worst outcomes deleted.

The refusals are tested as hard as the happy path. A broker that cannot be
reached must never look like a closed position, and a trade that cannot be
rebuilt honestly must be dropped rather than labelled with a guess.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader import live_model
from event_aware_trader.autotrade import (
    AutoTradeConfig, _learn_from_external_exits)
from event_aware_trader.broker import BrokerError


class FakeBroker:
    def __init__(self, held, fills, fail_positions=False, fail_fills=False):
        self._held = held
        self._fills = fills
        self.fail_positions = fail_positions
        self.fail_fills = fail_fills

    def positions(self):
        if self.fail_positions:
            raise BrokerError("network down")
        return [{"symbol": s} for s in self._held]

    def fill_activities(self, page_size=100):
        if self.fail_fills:
            raise BrokerError("activities unavailable")
        return self._fills


def fill(symbol, side, qty, price, t):
    return {"symbol": symbol, "side": side, "qty": str(qty),
            "price": str(price), "transaction_time": t}


FEATURES = {k: 0.5 for k in live_model.LIVE_FEATURES}

RTX_FILLS = [
    fill("RTX", "buy", 66, 198.93, "2026-09-09T15:30:00"),
    fill("RTX", "sell", 66, 195.20, "2026-09-14T19:40:27"),
]


class LearningFromExitsTheRuleDidNotMake(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "examples.jsonl"
        self._real = live_model.TRAINING_PATH
        live_model.TRAINING_PATH = self.path
        # No __defaults__ patching. append_example now reads
        # TRAINING_PATH at call time, so redirecting the module constant
        # above is enough and adding a parameter cannot silently rebind
        # the wrong one.
        self.config = AutoTradeConfig(
            dry_run=True,
            audit_log=Path(self._tmp.name) / "audit.jsonl",
            state_file=Path(self._tmp.name) / "state.json")

    def tearDown(self):
        live_model.TRAINING_PATH = self._real
        self._tmp.cleanup()

    def _state(self):
        return {"open_features": {"RTX": dict(FEATURES)},
                "stops": {"RTX": {"initial": 187.89629030651562,
                                  "current": 187.89629030651562}}}

    def _rows(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def test_a_stopped_out_trade_becomes_a_training_example(self):
        state = self._state()
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker(["COST"], RTX_FILLS), state, actions)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "RTX")
        expected = (195.20 - 198.93) / (198.93 - 187.89629030651562)
        self.assertAlmostEqual(rows[0]["r"], expected, places=6)
        self.assertEqual(rows[0]["label"], 0)          # a loss
        self.assertNotIn("RTX", state["open_features"])
        self.assertNotIn("RTX", state["stops"])
        events = [a["event"] for a in actions]
        self.assertIn("learned_from_external_exit", events)
        self.assertIn("retrained", events)

    def test_a_position_still_held_is_left_alone(self):
        state = self._state()
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker(["RTX", "COST"], RTX_FILLS), state, actions)
        self.assertEqual(self._rows(), [])
        self.assertIn("RTX", state["open_features"])
        self.assertEqual(actions, [])

    def test_case_differences_do_not_look_like_a_closed_position(self):
        state = self._state()
        _learn_from_external_exits(
            self.config, FakeBroker(["rtx"], RTX_FILLS), state, [])
        self.assertIn("RTX", state["open_features"])
        self.assertEqual(self._rows(), [])

    def test_a_winning_trade_is_labelled_one_at_or_above_1R(self):
        state = self._state()
        fills = [fill("RTX", "buy", 66, 198.93, "T1"),
                 fill("RTX", "sell", 66, 210.0, "T2")]   # +1.0R at 209.96
        _learn_from_external_exits(self.config, FakeBroker([], fills), state, [])
        rows = self._rows()
        self.assertGreater(rows[0]["r"], 1.0)
        self.assertEqual(rows[0]["label"], 1)


class RefusalsThatProtectTheRecord(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "examples.jsonl"
        self._real_default = live_model.append_example.__defaults__
        live_model.append_example.__defaults__ = (self.path,)
        self.config = AutoTradeConfig(
            dry_run=True,
            audit_log=Path(self._tmp.name) / "audit.jsonl",
            state_file=Path(self._tmp.name) / "state.json")

    def tearDown(self):
        live_model.append_example.__defaults__ = self._real_default
        self._tmp.cleanup()

    def _state(self):
        return {"open_features": {"RTX": dict(FEATURES)},
                "stops": {"RTX": {"initial": 187.9}}}

    def test_an_unreachable_broker_never_deletes_a_live_trades_record(self):
        state = self._state()
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker([], RTX_FILLS, fail_positions=True),
            state, actions)
        self.assertIn("RTX", state["open_features"])
        self.assertFalse(self.path.exists())
        self.assertEqual(actions[0]["event"], "external_exit_lookup_failed")

    def test_a_failed_fills_lookup_keeps_the_features_for_next_cycle(self):
        state = self._state()
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker([], RTX_FILLS, fail_fills=True),
            state, actions)
        self.assertIn("RTX", state["open_features"])
        self.assertEqual(actions[0]["event"], "external_exit_fills_failed")

    def test_an_entry_older_than_the_feed_is_dropped_not_invented(self):
        state = self._state()
        actions = []
        only_the_sell = [fill("RTX", "sell", 66, 195.20, "T2")]
        _learn_from_external_exits(
            self.config, FakeBroker([], only_the_sell), state, actions)
        self.assertFalse(self.path.exists())          # no fabricated example
        self.assertNotIn("RTX", state["open_features"])
        self.assertEqual(actions[0]["event"], "external_exit_unrecoverable")
        self.assertIn("older than the feed", actions[0]["detail"]["why"])

    def test_a_stop_above_the_entry_yields_no_label(self):
        state = {"open_features": {"RTX": dict(FEATURES)},
                 "stops": {"RTX": {"initial": 500.0}}}
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker([], RTX_FILLS), state, actions)
        self.assertFalse(self.path.exists())
        self.assertEqual(actions[0]["event"], "external_exit_unrecoverable")
        self.assertIn("not below the entry", actions[0]["detail"]["why"])

    def test_a_missing_stop_record_yields_no_label(self):
        state = {"open_features": {"RTX": dict(FEATURES)}, "stops": {}}
        actions = []
        _learn_from_external_exits(
            self.config, FakeBroker([], RTX_FILLS), state, actions)
        self.assertFalse(self.path.exists())
        self.assertIn("no initial stop", actions[0]["detail"]["why"])

    def test_nothing_tracked_is_a_no_op(self):
        actions = []
        _learn_from_external_exits(self.config, FakeBroker([], []), {}, actions)
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()


class TheCorpusIsOneFile(unittest.TestCase):
    """append_example must write where train_live_model reads.

    The defect this guards against was live for three days: the 1,526-row
    seed was written to data/big-dataset.jsonl while append_example wrote to
    data/live-training.jsonl, which stayed empty. A refit would have thrown
    the seed away and rebuilt the model from a handful of recent trades - and
    nothing failed, because each half worked perfectly on its own file.
    """

    def test_append_then_load_then_train_uses_one_path(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "corpus.jsonl"
            real_path = live_model.TRAINING_PATH
            live_model.TRAINING_PATH = path
            try:
                live_model.append_example(FEATURES, 1.5, "AAA")
                live_model.append_example(FEATURES, -0.5, "BBB")
                rows = live_model.load_training(path)
            finally:
                live_model.TRAINING_PATH = real_path
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["symbol"] for r in rows], ["AAA", "BBB"])
            self.assertEqual([r["label"] for r in rows], [1, 0])
            # The trainer reads f and label off exactly these rows.
            for row in rows:
                self.assertEqual(sorted(row["f"]), sorted(live_model.LIVE_FEATURES))

    def test_append_and_load_agree_on_where_the_corpus_lives(self):
        """Asserted BEHAVIOURALLY, which is what the property really is.

        This used to compare `__defaults__[0]` on both functions. That
        broke the moment a parameter was added - and worse, it would have
        kept passing if the default had been bound to a stale path, since
        it only compared two constants. Writing and then reading proves
        the thing that matters.
        """
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "corpus.jsonl"
            real_path = live_model.TRAINING_PATH
            live_model.TRAINING_PATH = path
            try:
                live_model.append_example(FEATURES, 1.5, "ZZZ")
                rows = live_model.load_training()
            finally:
                live_model.TRAINING_PATH = real_path
            self.assertEqual([r["symbol"] for r in rows], ["ZZZ"])
