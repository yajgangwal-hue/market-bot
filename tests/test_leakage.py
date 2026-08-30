import random
import unittest
from datetime import date, timedelta

from event_aware_trader.leakage import (
    IMPLAUSIBLE_AUC,
    SINGLE_FEATURE_ALARM,
    audit_for_leakage,
)


def dataset(n=3000, leak=False, seed=1):
    rng = random.Random(seed)
    start = date(2020, 1, 1)
    X, y, D = [], [], []
    for i in range(n):
        signal = rng.gauss(0, 1)
        label = 1 if signal + rng.gauss(0, 3) > 0 else 0     # weak, realistic
        row = [signal, rng.gauss(0, 1), rng.gauss(0, 1)]
        if leak:
            row.append(float(label))                          # the answer itself
        X.append(row); y.append(label)
        D.append(start + timedelta(days=i // 8))
    return X, y, D


class LeakDetectionTests(unittest.TestCase):
    def test_a_leaked_outcome_is_caught(self):
        X, y, D = dataset(leak=True)
        report = audit_for_leakage(X, y, D, ["a", "b", "c", "leaked"])
        self.assertFalse(report.trustworthy)
        self.assertIn("single_feature_knows_the_answer",
                      [f.check for f in report.triggered])

    def test_the_leaked_feature_is_named(self):
        X, y, D = dataset(leak=True)
        report = audit_for_leakage(X, y, D, ["a", "b", "c", "leaked"])
        finding = next(f for f in report.findings
                       if f.check == "single_feature_knows_the_answer")
        self.assertIn("leaked", finding.detail)

    def test_an_implausible_score_is_flagged(self):
        X, y, D = dataset(leak=True)
        report = audit_for_leakage(X, y, D, ["a", "b", "c", "leaked"])
        self.assertTrue(any(f.check == "implausible_score" and f.triggered
                            for f in report.findings))

    def test_an_honest_weak_dataset_does_not_trip_the_score_alarm(self):
        """The point is to catch fakes, not to reject real thin edges."""
        X, y, D = dataset(leak=False)
        report = audit_for_leakage(X, y, D, ["a", "b", "c"])
        score_alarm = next(f for f in report.findings if f.check == "implausible_score")
        self.assertFalse(score_alarm.triggered)
        self.assertLess(report.test_auc, IMPLAUSIBLE_AUC)


class ContractTests(unittest.TestCase):
    def test_every_check_runs_and_is_reported(self):
        X, y, D = dataset()
        report = audit_for_leakage(X, y, D, ["a", "b", "c"])
        checks = {f.check for f in report.findings}
        for expected in ("implausible_score", "memorisation",
                         "single_feature_knows_the_answer", "shuffled_split_flatters"):
            self.assertIn(expected, checks)

    def test_a_tiny_sample_declines_rather_than_guessing(self):
        X, y, D = dataset(n=50)
        report = audit_for_leakage(X, y, D, ["a", "b", "c"])
        self.assertEqual([f.check for f in report.findings], ["sample"])

    def test_a_single_class_declines(self):
        start = date(2020, 1, 1)
        X = [[float(i), 1.0] for i in range(400)]
        report = audit_for_leakage(X, [1]*400, [start + timedelta(days=i//8) for i in range(400)])
        self.assertEqual([f.check for f in report.findings], ["sample"])

    def test_the_report_says_a_high_score_means_look_for_a_bug(self):
        X, y, D = dataset()
        payload = audit_for_leakage(X, y, D, ["a", "b", "c"]).as_dict()
        self.assertIn("reason to look for a bug", payload["note"])

    def test_direction_does_not_hide_a_leak(self):
        """An inverted leaked column separates outcomes just as well."""
        X, y, D = dataset(leak=True)
        flipped = [row[:3] + [1.0 - row[3]] for row in X]
        report = audit_for_leakage(flipped, y, D, ["a", "b", "c", "inverted_leak"])
        self.assertTrue(any(f.check == "single_feature_knows_the_answer" and f.triggered
                            for f in report.findings))


if __name__ == "__main__":
    unittest.main()
