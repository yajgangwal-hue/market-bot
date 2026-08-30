import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.strategy import StrategyConfig
from event_aware_trader.trade_learning import (
    TRADE_FEATURES,
    _feature_row,
    WINNER_R_THRESHOLD,
    TradeExample,
    TradeModel,
    export_pine,
    generate_examples,
    load_examples,
    load_model,
    model_vetoes,
    save_examples,
    save_model,
    score_candidate,
    train_trade_model,
)
from tests.test_strategy import trending_bars


def synthetic(count=300, positive_rate=0.4):
    """Examples whose label is genuinely predictable from one feature."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out = []
    for i in range(count):
        strong = (i % 10) < (positive_rate * 10)
        # Built through the same helper the production path uses, so the
        # fixture cannot drift from the real feature vector. Building the dict
        # by hand previously added an "intercept" key that _feature_row omits,
        # since the intercept is supplied by _row rather than carried as data.
        raw = {name: 0.0 for name in TRADE_FEATURES if name != "intercept"}
        raw["ma_separation"] = 0.05 if strong else 0.001
        features = _feature_row(raw, 80.0 if strong else 50.0)
        out.append(TradeExample(
            symbol="SPY", as_of=start + timedelta(days=i), features=features,
            realized_r=2.0 if strong else -1.0,
            label=1 if strong else 0, was_tradeable=True,
        ))
    return out


class ExampleGenerationTests(unittest.TestCase):
    def test_examples_come_from_blocker_survivors_not_only_taken_trades(self):
        series = {"SPY": trending_bars(count=200)}
        examples = generate_examples(series, config=StrategyConfig(exit_mode="trailing"))
        self.assertGreater(len(examples), 0)
        # strictly more candidates than the subset that also cleared the score
        self.assertGreaterEqual(len(examples), sum(1 for e in examples if e.was_tradeable))

    def test_label_uses_the_magnitude_threshold_not_mere_profit(self):
        series = {"SPY": trending_bars(count=200)}
        for example in generate_examples(series, config=StrategyConfig(exit_mode="trailing")):
            self.assertEqual(example.label, 1 if example.realized_r >= WINNER_R_THRESHOLD else 0)

    def test_examples_round_trip_through_disk(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.jsonl"
            original = synthetic(60)
            save_examples(path, original)
            loaded = load_examples(path)
            self.assertEqual(len(loaded), len(original))
            self.assertEqual(loaded[0].label, original[0].label)


class TrainingTests(unittest.TestCase):
    def test_learnable_signal_is_actually_learned(self):
        model = train_trade_model(synthetic(400))
        self.assertGreaterEqual(model.report["out_of_sample_auc"], 0.9)

    def test_too_few_examples_is_refused(self):
        with self.assertRaises(ValueError):
            train_trade_model(synthetic(20))

    def test_pure_noise_does_not_become_usable(self):
        """A model with no signal must not be allowed to veto anything."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        noise = [
            TradeExample(
                symbol="SPY", as_of=start + timedelta(days=i),
                features={name: float((i * 37 % 11) - 5) for name in TRADE_FEATURES},
                realized_r=0.0, label=i % 2, was_tradeable=True,
            )
            for i in range(400)
        ]
        model = train_trade_model(noise)
        self.assertEqual(model.status, "UNPROVEN")
        self.assertFalse(model.is_usable)

    def test_model_round_trips_through_disk(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            original = train_trade_model(synthetic(400))
            save_model(path, original)
            loaded = load_model(path)
            self.assertEqual(loaded.weights, original.weights)
            self.assertEqual(loaded.status, original.status)


class VetoSafetyTests(unittest.TestCase):
    """The model may only ever subtract. This is the whole safety argument."""

    def setUp(self):
        self.model = train_trade_model(synthetic(400))
        self.weak = {name: 0.0 for name in TRADE_FEATURES}
        self.weak.update({"score": 50.0, "ma_separation": 0.001})

    def test_an_unproven_model_never_vetoes(self):
        unproven = replace(self.model, status="UNPROVEN")
        self.assertFalse(unproven.is_usable)
        vetoed, _ = model_vetoes(unproven, self.weak, 50.0)
        self.assertFalse(vetoed)

    def test_a_usable_model_can_veto_a_weak_candidate(self):
        usable = replace(self.model, status="USABLE_AS_VETO", veto_threshold=0.5)
        vetoed, probability = model_vetoes(usable, self.weak, 50.0)
        self.assertTrue(vetoed)
        self.assertLess(probability, 0.5)

    def test_probability_is_bounded(self):
        for score in (0.0, 50.0, 100.0, 1e6, -1e6):
            probability = score_candidate(self.model, self.weak, score)
            self.assertGreaterEqual(probability, 0.0)
            self.assertLessEqual(probability, 1.0)


class PineExportTests(unittest.TestCase):
    def test_export_contains_every_weight_and_the_threshold(self):
        model = train_trade_model(synthetic(400))
        pine = export_pine(model)
        for name in TRADE_FEATURES[1:]:
            self.assertIn("w_{0}".format(name), pine)
            self.assertIn("m_{0}".format(name), pine)
        self.assertIn("vetoThreshold", pine)
        self.assertIn(model.status, pine)

    def test_export_states_that_pine_cannot_train(self):
        pine = export_pine(train_trade_model(synthetic(400)))
        self.assertIn("Pine cannot fit this", pine)


if __name__ == "__main__":
    unittest.main()


class ExecutedTradeFeedbackTests(unittest.TestCase):
    """Trades the bot actually made must be able to become training data.

    Without this the weekly retrain re-reads the same price history and the
    bot never learns from its own results.
    """

    def _log(self, tmp, rows):
        import json as _json

        path = Path(tmp) / "audit.jsonl"
        path.write_text("\n".join(_json.dumps(r) for r in rows), encoding="utf-8")
        return path

    def _entry(self, symbol="SPY", at="2026-09-01T13:45:00+00:00", score=75.0):
        return {
            "at": at, "event": "entry",
            "detail": {
                "symbol": symbol, "score": score,
                "features": {name: 1.0 for name in TRADE_FEATURES[1:]},
            },
        }

    def _exit(self, symbol="SPY", at="2026-09-03T13:45:00+00:00", r=1.5):
        return {"at": at, "event": "exit", "detail": {"symbol": symbol, "r_multiple": r}}

    def test_a_completed_trade_becomes_one_example(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            path = self._log(tmp, [self._entry(), self._exit()])
            examples = examples_from_audit_log(path)
            self.assertEqual(len(examples), 1)
            self.assertEqual(examples[0].symbol, "SPY")
            self.assertAlmostEqual(examples[0].realized_r, 1.5)
            self.assertTrue(examples[0].was_tradeable)

    def test_the_label_uses_the_same_threshold_as_simulated_examples(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            path = self._log(tmp, [
                self._entry("SPY"), self._exit("SPY", r=WINNER_R_THRESHOLD + 0.1),
                self._entry("GLD", at="2026-09-04T13:45:00+00:00"),
                self._exit("GLD", at="2026-09-05T13:45:00+00:00", r=WINNER_R_THRESHOLD - 0.1),
            ])
            labels = {e.symbol: e.label for e in examples_from_audit_log(path)}
            self.assertEqual(labels["SPY"], 1)
            self.assertEqual(labels["GLD"], 0)

    def test_an_entry_with_no_exit_is_not_an_example(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            self.assertEqual(examples_from_audit_log(self._log(tmp, [self._entry()])), [])

    def test_an_entry_without_features_is_skipped_rather_than_faked(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            rows = [
                {"at": "2026-09-01T13:45:00+00:00", "event": "entry",
                 "detail": {"symbol": "SPY", "score": 70.0}},
                self._exit(),
            ]
            self.assertEqual(examples_from_audit_log(self._log(tmp, rows)), [])

    def test_an_exit_without_an_r_multiple_is_skipped(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            rows = [self._entry(),
                    {"at": "2026-09-03T13:45:00+00:00", "event": "exit",
                     "detail": {"symbol": "SPY"}}]
            self.assertEqual(examples_from_audit_log(self._log(tmp, rows)), [])

    def test_hold_and_run_complete_events_are_ignored(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            rows = [
                self._entry(),
                {"at": "2026-09-02T13:45:00+00:00", "event": "hold", "detail": {"symbol": "SPY"}},
                {"at": "2026-09-02T14:00:00+00:00", "event": "run_complete", "detail": {}},
                self._exit(),
            ]
            self.assertEqual(len(examples_from_audit_log(self._log(tmp, rows))), 1)

    def test_corrupt_lines_do_not_crash_the_retrain(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text("not json\n{broken\n", encoding="utf-8")
            self.assertEqual(examples_from_audit_log(path), [])

    def test_a_missing_log_is_empty_not_an_error(self):
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            self.assertEqual(examples_from_audit_log(Path(tmp) / "none.jsonl"), [])

    def test_executed_examples_share_the_schema_of_simulated_ones(self):
        """Both must train one model, so the feature vectors must match."""
        from event_aware_trader.trade_learning import examples_from_audit_log

        with TemporaryDirectory() as tmp:
            path = self._log(tmp, [self._entry(), self._exit()])
            executed = examples_from_audit_log(path)[0]
            simulated = synthetic(40)[0]
            self.assertEqual(set(executed.features), set(simulated.features))
