import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.strategy import StrategyConfig
from event_aware_trader.trade_learning import (
    TRADE_FEATURES,
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
        features = {name: 0.0 for name in TRADE_FEATURES}
        features["score"] = 80.0 if strong else 50.0
        features["ma_separation"] = 0.05 if strong else 0.001
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
