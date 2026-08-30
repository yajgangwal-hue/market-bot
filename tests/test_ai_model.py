import unittest

from event_aware_trader.ai_model import (
    MAX_OVERFIT_GAP,
    MIN_USABLE_AUC,
    ModelResult,
    select_model,
)


def _result(train, test):
    return ModelResult("m", train_auc=train, test_auc=test, test_brier=0.2, base_brier=0.2)


class VerdictTests(unittest.TestCase):
    def test_chance_level_is_not_usable(self):
        self.assertFalse(_result(0.62, 0.50).usable)

    def test_memorisation_is_rejected_even_with_a_good_test_score(self):
        """A large train-test gap means it fit noise, whatever the test says."""
        result = _result(1.00, MIN_USABLE_AUC + 0.05)
        self.assertTrue(result.beats_chance)
        self.assertTrue(result.memorised)
        self.assertFalse(result.usable)

    def test_a_modest_well_generalising_model_is_usable(self):
        result = _result(MIN_USABLE_AUC + 0.06, MIN_USABLE_AUC + 0.02)
        self.assertLess(result.overfit_gap, MAX_OVERFIT_GAP)
        self.assertTrue(result.usable)


class SelectionTests(unittest.TestCase):
    def test_pure_noise_selects_nothing(self):
        """The defensive property: no signal must mean no endorsement."""
        import random

        rng = random.Random(7)
        features = [[rng.gauss(0, 1) for _ in range(8)] for _ in range(600)]
        labels = [rng.randint(0, 1) for _ in range(600)]
        report = select_model(features, labels)
        self.assertIsNone(report.chosen)
        self.assertIn("chance", report.reason.lower())

    def test_a_genuinely_learnable_signal_is_found(self):
        import random

        rng = random.Random(11)
        features, labels = [], []
        for _ in range(800):
            strong = rng.random() < 0.4
            base = 2.0 if strong else -2.0
            features.append([base + rng.gauss(0, 0.4) for _ in range(4)])
            labels.append(1 if strong else 0)
        report = select_model(features, labels)
        self.assertIsNotNone(report.chosen)
        best = max(report.results, key=lambda r: r.test_auc)
        self.assertGreater(best.test_auc, 0.9)

    def test_too_few_examples_declines_rather_than_guessing(self):
        # Features must actually vary, or this hits the constant-feature guard
        # first and tests the wrong refusal.
        features = [[float(i), float(i % 7)] for i in range(40)]
        report = select_model(features, [i % 2 for i in range(40)])
        self.assertIsNone(report.chosen)
        self.assertIn("not enough", report.reason.lower())

    def test_a_single_class_declines(self):
        report = select_model([[float(i), 1.0] for i in range(200)], [1] * 200)
        self.assertIsNone(report.chosen)

    def test_all_constant_features_decline(self):
        report = select_model([[1.0, 1.0] for _ in range(200)], [i % 2 for i in range(200)])
        self.assertIsNone(report.chosen)

    def test_a_constant_column_does_not_break_the_fit(self):
        """event_impact is constant 0.0 when no event file is configured."""
        import random

        rng = random.Random(3)
        features, labels = [], []
        for _ in range(600):
            strong = rng.random() < 0.4
            features.append([2.0 if strong else -2.0, 0.0, rng.gauss(0, 1)])
            labels.append(1 if strong else 0)
        report = select_model(features, labels)
        self.assertTrue(report.results, "selection produced no results at all")

    def test_wide_scale_columns_do_not_break_the_fit(self):
        import random

        rng = random.Random(5)
        features, labels = [], []
        for _ in range(600):
            strong = rng.random() < 0.4
            features.append([2.0 if strong else -2.0, rng.uniform(1e8, 5e10)])
            labels.append(1 if strong else 0)
        report = select_model(features, labels)
        for result in report.results:
            self.assertFalse("failed" in result.name, result.name)


if __name__ == "__main__":
    unittest.main()
