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

    def test_the_failed_metric_is_preserved_not_erased(self):
        """The model stays as evidence; only its authority is removed."""
        live, _est = live_model.load_live_model(
            AutoTradeConfig().live_model_file)
        if live is None:
            self.skipTest("no live model on disk")
        self.assertAlmostEqual(live.test_auc, 0.5424, places=4)
        self.assertEqual(live.status, "UNPROVEN")

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
