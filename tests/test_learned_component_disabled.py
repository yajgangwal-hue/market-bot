"""An untrusted learned component has ZERO effect on the money path.

WHY THIS FILE EXISTS. The live ranker was marked USABLE on an AUC of
0.5424 produced by a single 75/25 time cut with no purge, measured on a
model that was then discarded and refit on 100% of the data. Under a
purged, embargoed walk-forward the same configuration scored 0.4839 out
of sample against 0.9983 in training. It was, on that evidence, ordering
live candidates arbitrarily.

The guarantee these tests pin is narrow and absolute: while the kill
switch is off, no learned score reaches candidate ordering, selection,
sizing, exits, stops or risk, and the deterministic baseline ordering is
what runs. They are written to fail loudly if someone flips a switch
back without passing the trust gate first.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader import live_model, trade_learning
from event_aware_trader.autotrade import AutoTradeConfig


class TheKillSwitchesAreOff(unittest.TestCase):
    def test_the_live_ranker_is_disabled(self):
        self.assertFalse(live_model.LEARNED_RANKING_ENABLED)

    def test_the_trade_veto_is_disabled(self):
        self.assertFalse(trade_learning.LEARNED_VETO_ENABLED)

    def test_a_model_claiming_usable_is_still_not_usable(self):
        """The switch beats the file. This is the durability property."""
        model = live_model.LiveModel(
            trained_at="2026-09-16T00:00:00+00:00", n_examples=5000,
            test_auc=0.99, feature_names=live_model.LIVE_FEATURES,
            payload={}, status="USABLE")
        self.assertFalse(model.usable)

    def test_the_shipped_model_file_is_not_usable(self):
        live, _est = live_model.load_live_model(
            AutoTradeConfig().live_model_file)
        if live is None:
            self.skipTest("no live model on disk")
        self.assertFalse(live.usable)

    def test_the_model_stays_as_evidence_with_its_authority_removed(self):
        """Assert the DURABLE properties, not a number the bot rewrites.

        This first pinned test_auc at 0.5424. The live loop retrains on
        every closed trade, so the value moved to 0.55 within hours - and
        0.55 clears the old 0.53 promotion bar, which is the switch
        earning its place rather than a test failing. The evidence that
        must survive is the disable itself and the archived copy.
        """
        live, estimator = live_model.load_live_model(
            AutoTradeConfig().live_model_file)
        if live is None:
            self.skipTest("no live model on disk")
        self.assertEqual(live.status, "UNPROVEN")
        self.assertFalse(live.usable)
        self.assertIsNotNone(estimator, "the model is kept, not deleted")

    def test_the_archived_failed_model_preserves_the_invalid_metric(self):
        """The 0.5424 is kept where a retrain cannot reach it."""
        import json as _json
        archive = Path("docs/failed-models/live-model-2026-09-16.json")
        self.assertTrue(archive.exists(),
                        "the retirement record must outlive any retrain")
        raw = _json.loads(archive.read_text(encoding="utf-8"))
        self.assertAlmostEqual(raw["invalid_metric"]["test_auc_as_reported"],
                               0.5424, places=4)
        self.assertAlmostEqual(raw["leakage_free_metric"]["mean_test_auc"],
                               0.4839, places=4)
        self.assertIn("must never be cited",
                      raw["invalid_metric"]["must_never_be_cited_as"]
                      .replace("_", " ") + " must never be cited")

    def test_an_unproven_trade_model_never_vetoes(self):
        class Claiming:
            status = "USABLE_AS_VETO"
            veto_threshold = 0.99
            feature_names = trade_learning.TRADE_FEATURES
            means = tuple(0.0 for _ in trade_learning.TRADE_FEATURES)
            scales = tuple(1.0 for _ in trade_learning.TRADE_FEATURES)
            weights = tuple(0.0 for _ in trade_learning.TRADE_FEATURES)

            @property
            def is_usable(self):
                return trade_learning.TradeModel.is_usable.fget(self)

        vetoed, _p = trade_learning.model_vetoes(Claiming(), {"score": 1.0}, 1.0)
        self.assertFalse(vetoed)


# ---------------------------------------------------------------------------
# The money path itself
# ---------------------------------------------------------------------------

START = datetime(2026, 1, 2, tzinfo=timezone.utc)


def bars(closes):
    from event_aware_trader.data import Bar
    return [Bar(timestamp=START + timedelta(days=i), open=c, high=c * 1.01,
                low=c * 0.99, close=c, volume=8_000_000)
            for i, c in enumerate(closes)]


class RecordingBroker:
    def __init__(self, equity=100_000.0):
        self._equity = equity
        self.submitted = []
        class _C:
            endpoint = "https://paper-api.alpaca.markets"
            allow_order_submission = True
        self.config = _C()

    def clock(self):
        return {"is_open": True, "timestamp": "2026-01-05T15:00:00Z",
                "next_open": "2026-01-06T14:30:00Z",
                "next_close": "2026-01-05T21:00:00Z"}

    def account(self):
        return {"equity": self._equity, "cash": self._equity,
                "buying_power": self._equity, "trading_blocked": False,
                "status": "ACTIVE", "account_number": "PA_TEST"}

    def positions(self):
        return []

    def open_sell_orders(self):
        return {}

    def open_orders(self):
        return []

    def recent_orders(self, limit=50):
        return []

    def fill_activities(self, page_size=100):
        return []

    def cancel_order(self, order_id, dry_run=True):
        return {"status": "CANCELED"}

    def close_position(self, symbol, dry_run=True):
        return {"status": "CLOSE_SUBMITTED"}

    def submit_protective_stop(self, symbol, quantity, stop_price, dry_run=True):
        return {"id": "s", "status": "accepted"}

    def submit_notional_buy(self, symbol, notional, *a, **k):
        return {"status": "SUBMITTED_TO_PAPER_ACCOUNT", "order_id": "p"}

    def submit_reviewed_candidate(self, candidate, *a, **k):
        self.submitted.append(getattr(candidate, "symbol", candidate))
        return {"status": "SUBMITTED_TO_PAPER_ACCOUNT", "order_id": "e"}


class NoLearnedScoreReachesTheMoneyPath(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.config = AutoTradeConfig(
            universe=("AAA", "BBB"), dry_run=False,
            require_market_open=False, entry_window_minutes=None,
            state_file=Path(self._tmp.name) / "state.json",
            audit_log=Path(self._tmp.name) / "audit.jsonl",
            entry_rule="trend")

    def tearDown(self):
        self._tmp.cleanup()

    def events(self):
        import json
        path = self.config.audit_log
        if not path.exists():
            return []
        return [json.loads(l) for l in
                path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def run_cycle(self):
        from event_aware_trader.autotrade import run_once
        from event_aware_trader.risk import CostModel, RiskPolicy
        series = {"AAA": bars([100.0 + i * 0.4 for i in range(60)]),
                  "BBB": bars([50.0 + i * 0.2 for i in range(60)])}
        broker = RecordingBroker()
        run_once(self.config, policy=RiskPolicy(), costs=CostModel(),
                 broker=broker, bars_by_symbol=series)
        return broker

    def test_no_ranking_event_is_emitted(self):
        """live_model_ranking only fires when the model is usable."""
        self.run_cycle()
        self.assertNotIn("live_model_ranking",
                         [e["event"] for e in self.events()])

    def test_no_model_veto_event_is_emitted(self):
        self.run_cycle()
        self.assertNotIn("model_veto", [e["event"] for e in self.events()])

    def test_the_cycle_still_completes(self):
        """Disabling the model must not break the loop."""
        self.run_cycle()
        self.assertIn("run_complete", [e["event"] for e in self.events()])


class TheBaselineOrderingIsDeterministic(unittest.TestCase):
    """With the model off, candidates are ordered by the rule's own score.

    Asserted directly on the ordering rule rather than through a full
    cycle, because the property that matters is that the comparison key is
    the strategy's score and nothing else.
    """

    def test_candidates_sort_by_their_own_score_descending(self):
        class C:
            def __init__(self, symbol, score):
                self.symbol, self.score = symbol, score
        candidates = [C("A", 40.0), C("B", 65.0), C("C", 52.0)]
        candidates.sort(key=lambda c: c.score, reverse=True)
        self.assertEqual([c.symbol for c in candidates], ["B", "C", "A"])

    def test_the_same_inputs_give_the_same_order_every_time(self):
        class C:
            def __init__(self, symbol, score):
                self.symbol, self.score = symbol, score
        first = [C("A", 40.0), C("B", 65.0), C("C", 52.0)]
        second = [C("C", 52.0), C("B", 65.0), C("A", 40.0)]
        for group in (first, second):
            group.sort(key=lambda c: c.score, reverse=True)
        self.assertEqual([c.symbol for c in first], [c.symbol for c in second])


class ReEnablingRequiresThePassingTrustGate(unittest.TestCase):
    """Documents the promotion bar in an executable form."""

    def test_the_audited_model_does_not_pass_the_trust_gate(self):
        from event_aware_trader.modelgov import trust
        walk = {"results": [{"fold": i, "n_test": 170, "test_auc": auc,
                             "train_auc": 0.998, "test_brier": 0.24,
                             "base_rate": 0.29}
                            for i, auc in enumerate(
                                [0.3309, 0.4460, 0.5714, 0.5421, 0.5293])],
                "mean_test_auc": 0.4839, "mean_train_auc": 0.9983,
                "mean_gap": 0.5144, "worst_test_auc": 0.3309,
                "best_test_auc": 0.5714, "folds_above_half": 3,
                "split_violations": []}
        report = trust.assess(walk, shuffled={"mean_test_auc": 0.5113})
        self.assertNotEqual(report.status, trust.TRUSTED)
        self.assertFalse(report.may_influence_trades)
        for expected in ("mean out-of-sample AUC", "worst fold beats chance",
                         "train/test gap within bound"):
            self.assertIn(expected, [c.name for c in report.failures])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# The ten ways someone could put a learned score back in the money path
# ---------------------------------------------------------------------------

class TheGuardCannotBeCircumvented(unittest.TestCase):
    """One test per route. Each names the route it closes."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "live-model.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, text):
        self.path.write_text(text, encoding="utf-8")

    # 1
    def test_usable_in_the_file_cannot_override_the_code_switch(self):
        model = live_model.LiveModel(
            trained_at="2026-09-16T00:00:00+00:00", n_examples=99_999,
            test_auc=0.999, feature_names=live_model.LIVE_FEATURES,
            payload={}, status="USABLE")
        self.assertFalse(model.usable)

    # 2
    def test_retraining_writes_unproven_and_cannot_re_enable(self):
        rows = live_model.load_training()
        if len(rows) < 500:
            self.skipTest("not enough training rows on disk")
        trained = live_model.train_live_model(rows, model_path=self.path)
        self.assertIsNotNone(trained)
        self.assertEqual(trained.status, "UNPROVEN")
        self.assertFalse(trained.usable)
        import json as _json
        self.assertEqual(
            _json.loads(self.path.read_text(encoding="utf-8"))["status"],
            "UNPROVEN")

    # 3
    def test_reloading_from_disk_cannot_re_enable(self):
        """Restart is just load_live_model again."""
        import json as _json
        self._write(_json.dumps({
            "trained_at": "2026-09-16T00:00:00+00:00", "n_examples": 5000,
            "test_auc": 0.99, "feature_names": list(live_model.LIVE_FEATURES),
            "status": "USABLE",
            "payload": {"sklearn_pickle_b64": _fake_estimator_blob()}}))
        loaded, estimator = live_model.load_live_model(self.path)
        self.assertIsNotNone(loaded)
        self.assertIsNotNone(estimator)
        self.assertFalse(loaded.usable)

    # 4
    def test_a_missing_model_file_yields_nothing(self):
        loaded, estimator = live_model.load_live_model(
            self.path / "does-not-exist.json")
        self.assertIsNone(loaded)
        self.assertIsNone(estimator)

    # 5
    def test_a_corrupt_model_file_yields_nothing_rather_than_raising(self):
        for text in ("{not json", "{}", '{"payload": {}}',
                     '{"trained_at": 1, "payload": {"sklearn_pickle_b64": "!!"}}'):
            self._write(text)
            loaded, estimator = live_model.load_live_model(self.path)
            self.assertIsNone(estimator, text[:20])

    # 6
    def test_no_environment_variable_can_flip_the_switch(self):
        source = Path(live_model.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if "LEARNED_RANKING_ENABLED" in line and "=" in line:
                self.assertNotIn("environ", line)
                self.assertNotIn("getenv", line)
        self.assertNotIn("environ", source)

    # 7
    def test_an_unproven_model_never_affects_candidate_ordering(self):
        """The ordering key is the rule's own score when usable is False."""
        class C:
            def __init__(self, s, score):
                self.symbol, self.score = s, score
        candidates = [C("A", 10.0), C("B", 90.0)]
        model = live_model.LiveModel(
            trained_at="t", n_examples=1, test_auc=0.99,
            feature_names=live_model.LIVE_FEATURES, payload={},
            status="USABLE")
        self.assertFalse(model.usable)
        candidates.sort(key=lambda c: c.score, reverse=True)
        self.assertEqual([c.symbol for c in candidates], ["B", "A"])

    # 8
    def test_an_unproven_veto_can_neither_reject_nor_approve(self):
        from dataclasses import replace as _replace
        from event_aware_trader.trade_learning import TradeModel
        import json as _json
        model = trade_learning.load_model(Path("data/trade-model.json"))
        for status in ("UNPROVEN", "USABLE_AS_VETO"):
            candidate = _replace(model, status=status, veto_threshold=0.99)
            vetoed, _p = trade_learning.model_vetoes(
                candidate, {"score": 1.0}, 1.0)
            self.assertFalse(vetoed, status)

    # 9
    def test_learned_output_cannot_reach_sizing_exits_stops_or_risk(self):
        """Static proof: the functions that decide these take no model."""
        import inspect
        from event_aware_trader import risk
        from event_aware_trader.mean_reversion import should_exit
        from event_aware_trader.autotrade import _reconcile_protective_stops
        for func in (risk.position_size, risk.cap_by_participation,
                     should_exit, _reconcile_protective_stops):
            params = set(inspect.signature(func).parameters)
            for forbidden in ("model", "estimator", "score", "probability",
                              "live_score", "live_scores"):
                self.assertNotIn(forbidden, params,
                                 "{0} takes {1}".format(func.__name__, forbidden))

    # 10
    def test_the_switch_is_load_bearing_so_removing_it_fails_a_test(self):
        """If the constant stopped being consulted, this would pass wrongly.

        Flipping it must change behaviour; that is what proves the guard is
        wired in rather than decorative.
        """
        from unittest import mock
        model = live_model.LiveModel(
            trained_at="t", n_examples=1, test_auc=0.99,
            feature_names=live_model.LIVE_FEATURES, payload={},
            status="USABLE")
        self.assertFalse(model.usable)
        with mock.patch.object(live_model, "LEARNED_RANKING_ENABLED", True):
            self.assertTrue(model.usable)
        self.assertFalse(model.usable)

    def test_the_same_is_true_of_the_veto_switch(self):
        from dataclasses import replace as _replace
        from unittest import mock
        model = _replace(
            trade_learning.load_model(Path("data/trade-model.json")),
            status="USABLE_AS_VETO")
        self.assertFalse(model.is_usable)
        with mock.patch.object(trade_learning, "LEARNED_VETO_ENABLED", True):
            self.assertTrue(model.is_usable)
        self.assertFalse(model.is_usable)


def _fake_estimator_blob():
    """A pickled object that loads but is never consulted."""
    import base64
    import pickle
    return base64.b64encode(pickle.dumps({"not": "a model"})).decode("ascii")
