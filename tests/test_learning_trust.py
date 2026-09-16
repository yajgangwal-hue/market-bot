"""The learning gate. Its default is NO, and every threshold is declared.

These tests exist because the shipped trainer's 0.5424 was produced by a
single 75/25 cut with no purge, attached to an artifact that had since
been refit on 100% of the data. The machinery below is what makes that
impossible to repeat, so the machinery itself has to be pinned:

  the split cannot touch          train ends before test, horizon purged
  the gate cannot be flattered    a leaking split or a passing control
                                  voids the result whatever the AUC
  the lineage cannot be rewritten hash-chained, append-only, duplicate ids
                                  refused
"""

import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.modelgov import lineage, trust, walkforward

FEATURES = ("a", "b")


def corpus(n=600, start=date(2015, 1, 1), signal=True, seed=0):
    """A dated corpus. With `signal`, feature `a` is genuinely predictive."""
    import random
    rng = random.Random(seed)
    rows = []
    day = start
    for i in range(n):
        label = 1 if rng.random() < 0.35 else 0
        a = (label + rng.gauss(0, 0.6)) if signal else rng.gauss(0, 1)
        # The convention is DECLARED. An undeclared row is excluded by
        # design now, so a fixture that omits it is testing nothing.
        rows.append({"at": day.isoformat(), "decision_at": day.isoformat(),
                     "outcome_at": (day + timedelta(days=5)).isoformat(),
                     "timestamp_convention": "decision", "schema": 2,
                     "symbol": "S%d" % (i % 20),
                     "label": label, "f": {"a": a, "b": rng.gauss(0, 1)}})
        day += timedelta(days=3)
    return rows


class TheSplitCannotTouch(unittest.TestCase):
    def setUp(self):
        self.rows = corpus()
        self.folds = walkforward.make_folds(self.rows, n_folds=4)

    def test_folds_are_produced(self):
        self.assertGreaterEqual(len(self.folds), 3)

    def test_training_always_ends_before_testing_begins(self):
        for fold in self.folds:
            self.assertEqual(walkforward.check_no_overlap(fold), [],
                             "fold {0}".format(fold.index))

    def test_a_purge_gap_of_at_least_the_horizon_is_left(self):
        for fold in self.folds:
            newest_train = max(walkforward.example_date(r) for r in fold.train)
            oldest_test = min(walkforward.example_date(r) for r in fold.test)
            self.assertGreaterEqual((oldest_test - newest_train).days,
                                    walkforward.horizon_sessions())

    def test_no_example_appears_in_both_sides(self):
        for fold in self.folds:
            train_ids = {id(r) for r in fold.train}
            self.assertFalse(train_ids & {id(r) for r in fold.test})

    def test_test_periods_move_forward_and_do_not_overlap(self):
        for earlier, later in zip(self.folds, self.folds[1:]):
            self.assertLessEqual(earlier.test_end, later.test_end)
            self.assertGreater(later.test_start, earlier.test_start)

    def test_the_horizon_comes_from_the_rule_not_a_constant(self):
        from event_aware_trader.mean_reversion import MeanReversionConfig
        self.assertEqual(walkforward.horizon_sessions(),
                         MeanReversionConfig().max_holding_bars)

    def test_a_touching_split_is_reported_as_a_violation(self):
        """The checker must be able to fail."""
        fold = self.folds[0]
        bad = walkforward.Fold(
            index=99, train_start=fold.train_start, train_end=fold.train_end,
            test_start=fold.test_start, test_end=fold.test_end,
            train=list(fold.train), test=list(fold.train[-5:]))
        self.assertTrue(walkforward.check_no_overlap(bad))

    def test_rolling_windows_are_shorter_than_expanding_ones(self):
        expanding = walkforward.make_folds(self.rows, n_folds=4, expanding=True)
        rolling = walkforward.make_folds(self.rows, n_folds=4, expanding=False)
        self.assertLessEqual(len(rolling[-1].train), len(expanding[-1].train))


class TheGateCannotBeFlattered(unittest.TestCase):
    def good(self, **kw):
        base = {"results": [{"fold": i, "n_test": 60, "test_auc": 0.60,
                             "train_auc": 0.68, "test_brier": 0.16,
                             "base_rate": 0.35} for i in range(4)],
                "mean_test_auc": 0.60, "mean_train_auc": 0.68,
                "mean_gap": 0.08, "worst_test_auc": 0.58,
                "best_test_auc": 0.62, "folds_above_half": 4,
                "split_violations": []}
        base.update(kw)
        return base

    def control(self, auc=0.50):
        return {"mean_test_auc": auc}

    def test_a_sound_model_can_reach_trusted(self):
        report = trust.assess(self.good(), shuffled=self.control())
        self.assertEqual(report.status, trust.TRUSTED)
        self.assertTrue(report.may_influence_trades)

    def test_a_missing_control_alone_prevents_trust(self):
        report = trust.assess(self.good(), shuffled=None)
        self.assertNotEqual(report.status, trust.TRUSTED)
        self.assertIn("shuffled-label control was run",
                      [c.name for c in report.failures])

    def test_a_passing_control_voids_the_result_however_good_the_auc(self):
        """A high control means the split leaks, not that the model is good."""
        report = trust.assess(self.good(mean_test_auc=0.95,
                                        worst_test_auc=0.93),
                              shuffled=self.control(auc=0.80))
        self.assertEqual(report.status, trust.UNTRUSTED)
        self.assertFalse(report.may_influence_trades)

    def test_a_split_violation_voids_the_result(self):
        report = trust.assess(
            self.good(split_violations=["train and test touch"]),
            shuffled=self.control())
        self.assertEqual(report.status, trust.UNTRUSTED)

    def test_memorisation_is_caught_by_the_gap_even_with_a_passing_auc(self):
        report = trust.assess(
            self.good(mean_train_auc=0.99, mean_gap=0.39),
            shuffled=self.control())
        self.assertNotEqual(report.status, trust.TRUSTED)
        self.assertIn("train/test gap within bound",
                      [c.name for c in report.failures])

    def test_one_carrying_fold_does_not_earn_trust(self):
        results = [{"fold": 0, "n_test": 60, "test_auc": 0.90,
                    "train_auc": 0.95, "test_brier": 0.16, "base_rate": 0.35}]
        results += [{"fold": i, "n_test": 60, "test_auc": 0.44,
                     "train_auc": 0.52, "test_brier": 0.16,
                     "base_rate": 0.35} for i in range(1, 4)]
        report = trust.assess(
            self.good(results=results, mean_test_auc=0.555,
                      worst_test_auc=0.44, folds_above_half=1),
            shuffled=self.control())
        self.assertNotEqual(report.status, trust.TRUSTED)

    def test_worse_than_base_rate_calibration_blocks_trust(self):
        results = [{"fold": i, "n_test": 60, "test_auc": 0.60,
                    "train_auc": 0.65, "test_brier": 0.30,
                    "base_rate": 0.35} for i in range(4)]
        report = trust.assess(self.good(results=results),
                              shuffled=self.control())
        self.assertIn("calibration beats the base rate",
                      [c.name for c in report.failures])

    def test_too_few_folds_prevents_any_conclusion(self):
        report = trust.assess(
            self.good(results=self.good()["results"][:2]),
            shuffled=self.control())
        self.assertIn("enough folds", [c.name for c in report.failures])

    def test_the_base_rate_brier_bar_is_what_it_claims(self):
        self.assertAlmostEqual(trust.base_rate_brier(0.35), 0.2275, places=6)


class TheModelMayDecline(unittest.TestCase):
    def test_a_confident_model_keeps_accuracy_as_coverage_falls(self):
        probs = [0.95, 0.92, 0.05, 0.08, 0.52, 0.48, 0.51, 0.49]
        labels = [1, 1, 0, 0, 0, 1, 1, 0]
        curve = trust.abstention_curve(probs, labels, bands=(0.0, 0.3))
        self.assertAlmostEqual(curve[0]["coverage"], 1.0)
        self.assertAlmostEqual(curve[1]["coverage"], 0.5)
        self.assertEqual(curve[1]["accuracy"], 1.0)

    def test_declining_everything_is_reported_rather_than_crashing(self):
        curve = trust.abstention_curve([0.5, 0.5], [1, 0], bands=(0.4,))
        self.assertEqual(curve[0]["coverage"], 0.0)
        self.assertIsNone(curve[0]["accuracy"])


class LineageCannotBeRewritten(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "lineage.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def model(self, **kw):
        base = dict(
            trained_at="2026-09-16T00:00:00+00:00",
            information_cutoff="2026-09-15",
            train_interval="1996-12-05..2024-01-01",
            validate_interval="folds",
            test_interval="2024-01-01..2026-09-15",
            dataset_fingerprint="abc123", dataset_rows=1531,
            feature_version="live_v1", features=["a", "b"],
            code_commit="deadbeef",
            hyperparameters={"max_depth": 4},
            evaluation={"mean_test_auc": 0.48},
            trust_status=trust.OBSERVE_ONLY)
        base.update(kw)
        return lineage.ModelRecord(**base)

    def test_the_id_is_a_digest_of_what_defines_the_model(self):
        a = self.model().compute_id()
        b = self.model().compute_id()
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("M-"))

    def test_a_different_dataset_is_a_different_model(self):
        self.assertNotEqual(self.model().compute_id(),
                            self.model(dataset_fingerprint="xyz").compute_id())

    def test_a_different_hyperparameter_is_a_different_model(self):
        self.assertNotEqual(
            self.model().compute_id(),
            self.model(hyperparameters={"max_depth": 6}).compute_id())

    def test_the_same_model_cannot_be_recorded_twice(self):
        lineage.record(self.model(), self.path)
        with self.assertRaises(ValueError):
            lineage.record(self.model(trust_status=trust.TRUSTED), self.path)

    def test_editing_a_record_breaks_the_chain(self):
        lineage.record(self.model(), self.path)
        lineage.record(self.model(dataset_fingerprint="second"), self.path)
        rows = [json.loads(l) for l in
                self.path.read_text(encoding="utf-8").splitlines()]
        rows[0]["payload"]["trust_status"] = trust.TRUSTED
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows), encoding="utf-8")
        check = lineage.verify_chain(self.path)
        self.assertFalse(check["intact"])
        self.assertEqual(check["broken_at"], 0)

    def test_a_broken_chain_refuses_to_load(self):
        lineage.record(self.model(), self.path)
        rows = [json.loads(l) for l in
                self.path.read_text(encoding="utf-8").splitlines()]
        rows[0]["payload"]["dataset_rows"] = 99999
        self.path.write_text(json.dumps(rows[0], sort_keys=True) + "\n",
                             encoding="utf-8")
        with self.assertRaises(ValueError):
            lineage.load(self.path)

    def test_no_trusted_model_means_the_baseline_stands(self):
        lineage.record(self.model(), self.path)
        self.assertIsNone(lineage.latest_trusted(self.path))

    def test_a_trusted_model_is_findable(self):
        lineage.record(self.model(trust_status=trust.TRUSTED), self.path)
        found = lineage.latest_trusted(self.path)
        self.assertIsNotNone(found)
        self.assertEqual(found["trust_status"], trust.TRUSTED)


class TheLearningPackageIsNotInTheMoneyPath(unittest.TestCase):
    def test_no_production_module_imports_it(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1] / "src" / "event_aware_trader"
        offenders = []
        for path in root.glob("*.py"):
            # An IMPORT, not a mention. live_model.py and
            # trade_learning.py name modelgov in the comment explaining
            # how a model earns its way back, which is documentation
            # rather than a dependency.
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")) and "modelgov" in stripped:
                    offenders.append("{0}: {1}".format(path.name, stripped))
        self.assertEqual(offenders, [])

    def test_the_live_loop_imports_with_learning_blocked(self):
        import importlib
        import sys

        class Blocker:
            def find_spec(self, name, path=None, target=None):
                if name.startswith("event_aware_trader.modelgov"):
                    raise ImportError("BLOCKED: " + name)
                return None

        blocker = Blocker()
        sys.meta_path.insert(0, blocker)
        try:
            for module in ("event_aware_trader.autotrade",
                           "event_aware_trader.live_model",
                           "event_aware_trader.broker"):
                importlib.import_module(module)
        finally:
            sys.meta_path.remove(blocker)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Pre-registration. The Phase 5 failure, closed.
# ---------------------------------------------------------------------------

class APostHocHypothesisCannotMasquerade(unittest.TestCase):
    def setUp(self):
        self._tmp2 = TemporaryDirectory()
        self.path = Path(self._tmp2.name) / "prereg.jsonl"

    def tearDown(self):
        self._tmp2.cleanup()

    def hypothesis(self, **kw):
        from event_aware_trader.modelgov.prereg import Hypothesis
        base = dict(
            statement="a trailing stop converts giveback into return",
            rationale="time exits give back 4.18% of the available move",
            rule="raise the stop to the running high minus B x ATR",
            parameters={"arm_at_R": [1.0, 1.5], "atr_multiple": [2.0]},
            search_procedure="full grid, once",
            max_configurations=2,
            datasets=["decade"], information_boundary="bars up to the decision",
            execution_assumptions="frozen", primary_metric="total return",
            secondary_metrics=["sharpe"], acceptance_criteria="beats baseline",
            rejection_criteria="does not", robustness_requirements=["monotone"],
            complexity_penalty="2 points", required_oos_test="none available",
            promotion_requirements=["new fingerprint"])
        base.update(kw)
        return Hypothesis(**base)

    def test_a_run_matching_its_registration_verifies(self):
        from event_aware_trader.modelgov.prereg import register, verify
        register(self.hypothesis(hypothesis_id="H-1"), self.path)
        got = verify("H-1", self.hypothesis(), self.path)
        self.assertEqual(got["hypothesis_id"], "H-1")

    def test_a_changed_threshold_refuses_to_run_as_confirmatory(self):
        """The Phase 5 move: pick the parameter after seeing the surface."""
        from event_aware_trader.modelgov.prereg import (
            RegistrationError, register, verify)
        register(self.hypothesis(hypothesis_id="H-1"), self.path)
        tuned = self.hypothesis(
            parameters={"arm_at_R": [1.25], "atr_multiple": [2.5]})
        with self.assertRaises(RegistrationError):
            verify("H-1", tuned, self.path)

    def test_a_changed_rejection_rule_refuses_too(self):
        """The other Phase 5 move: write the kill criterion afterwards."""
        from event_aware_trader.modelgov.prereg import (
            RegistrationError, register, verify)
        register(self.hypothesis(hypothesis_id="H-1"), self.path)
        with self.assertRaises(RegistrationError):
            verify("H-1", self.hypothesis(
                rejection_criteria="unless it wins in 2018"), self.path)

    def test_an_unregistered_hypothesis_cannot_be_confirmatory(self):
        from event_aware_trader.modelgov.prereg import RegistrationError, verify
        with self.assertRaises(RegistrationError):
            verify("H-nope", self.hypothesis(), self.path)

    def test_a_registration_cannot_be_edited_after_the_fact(self):
        from event_aware_trader.modelgov.prereg import register, verify_chain
        register(self.hypothesis(hypothesis_id="H-1"), self.path)
        register(self.hypothesis(hypothesis_id="H-2"), self.path)
        rows = [json.loads(l) for l in
                self.path.read_text(encoding="utf-8").splitlines()]
        rows[0]["payload"]["parameters"] = {"arm_at_R": [1.25]}
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows), encoding="utf-8")
        check = verify_chain(self.path)
        self.assertFalse(check["intact"])
        self.assertEqual(check["broken_at"], 0)

    def test_the_same_id_cannot_be_registered_twice(self):
        from event_aware_trader.modelgov.prereg import RegistrationError, register
        register(self.hypothesis(hypothesis_id="H-1"), self.path)
        with self.assertRaises(RegistrationError):
            register(self.hypothesis(hypothesis_id="H-1"), self.path)

    def test_the_trial_cap_is_carried_and_summed(self):
        from event_aware_trader.modelgov.prereg import declared_trials, register
        register(self.hypothesis(hypothesis_id="H-1", max_configurations=6),
                 self.path)
        register(self.hypothesis(hypothesis_id="H-2", max_configurations=3),
                 self.path)
        self.assertEqual(declared_trials(self.path), 9)

    def test_the_shipped_registrations_are_intact(self):
        from event_aware_trader.modelgov.prereg import verify_chain
        check = verify_chain()
        self.assertTrue(check["intact"], check.get("reason"))
        self.assertGreaterEqual(check["registrations"], 4)
