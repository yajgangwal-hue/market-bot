"""Every constraint H-0005 was sealed under, enforced rather than promised.

The classifier is arithmetic written before the sub-1.0R points existed,
so the tests below have to prove two things at once: that it returns
GRADIENT when a family really is one, and that it returns SPIKE on the
shape H-0003 actually produced. A rule that can only pass is not a rule.
"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.modelgov import gradient, prereg
from event_aware_trader.modelgov.adjudicate import (
    SelectionError, adjudicate, best_by_return, surviving)

SIX = [0.25, 0.50, 0.75, 1.00, 1.50, 2.00]

#: The three points already observed. Frozen in the registration.
FROZEN = {1.00: +13.7125, 1.50: -1.3647, 2.00: 0.0000}


class TheClassifierCanReturnEitherAnswer(unittest.TestCase):
    def test_the_shape_h0003_actually_produced_is_a_spike(self):
        """Sub-1.0R points flat: one dominating value, neighbours dead."""
        deltas = [0.2, 0.3, 0.5, 13.7125, -1.3647, 0.0]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertEqual(got.verdict, gradient.SPIKE)
        self.assertFalse(got.checks["G2 largest move <= 2.5x the "
                                    "second-largest positive"])

    def test_a_genuine_gradient_is_recognised(self):
        """Effect strengthens smoothly as the trigger falls."""
        deltas = [16.0, 14.0, 11.0, 13.7125, -1.3647, 0.0]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertEqual(got.verdict, gradient.GRADIENT, got.explain())
        self.assertTrue(got.is_gradient)

    def test_a_family_that_never_moves_is_inert(self):
        got = gradient.classify_family(SIX, [0.1, -0.2, 0.3, 0.0, -0.1, 0.0],
                                       expected_direction=-1)
        self.assertEqual(got.verdict, gradient.INERT)

    def test_g1_fails_when_too_few_thresholds_move(self):
        deltas = [-2.0, -3.0, -1.0, 13.7125, -1.3647, 0.0]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertFalse(got.checks[
            "G1 at least 3 thresholds move the result"])

    def test_g3_fails_when_the_maximum_is_isolated(self):
        deltas = [-1.5, 12.0, -1.6, -1.7, -1.8, -1.9]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertFalse(got.checks["G3 the maximum is not isolated"])

    def test_g4_fails_when_there_is_no_consistent_direction(self):
        deltas = [5.0, -4.0, 5.1, -4.1, 5.2, -4.2]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertFalse(got.checks["G4 |spearman| >= 0.6"])

    def test_the_wrong_direction_fails_even_with_a_strong_correlation(self):
        """A clean gradient pointing the way the registration did not."""
        deltas = [1.0, 2.0, 3.0, 13.7125, 14.0, 15.0]
        got = gradient.classify_family(SIX, deltas, expected_direction=-1)
        self.assertGreater(got.spearman, 0.6)
        self.assertFalse(got.checks["direction agrees with the registration"])
        self.assertEqual(got.verdict, gradient.SPIKE)

    def test_the_same_series_passes_direction_if_it_was_registered(self):
        deltas = [1.0, 2.0, 3.0, 13.7125, 14.0, 15.0]
        got = gradient.classify_family(SIX, deltas, expected_direction=+1)
        self.assertTrue(got.checks["direction agrees with the registration"])

    def test_all_five_adjacent_differences_are_reported(self):
        got = gradient.classify_family(SIX, [1, 2, 3, 4, 5, 6],
                                       expected_direction=+1)
        self.assertEqual(len(got.adjacent_differences), 5)
        self.assertEqual(got.adjacent_differences, [1, 1, 1, 1, 1])

    def test_an_unregistered_direction_is_refused(self):
        with self.assertRaises(ValueError):
            gradient.classify_family(SIX, [1] * 6, expected_direction=0)

    def test_the_constants_are_the_registered_ones(self):
        self.assertEqual(gradient.MAX_DOMINANCE_RATIO, 2.5)
        self.assertEqual(gradient.MIN_ABS_SPEARMAN, 0.6)
        self.assertEqual(gradient.MIN_MOVING_POINTS, 3)


class FrozenPriorObservationsCannotBeSilentlyReplaced(unittest.TestCase):
    def test_a_reproducing_implementation_passes(self):
        gradient.check_frozen({1.00: 13.7130}, FROZEN)

    def test_a_drifted_implementation_stops_the_experiment(self):
        with self.assertRaises(gradient.FrozenObservationChanged):
            gradient.check_frozen({1.00: 12.5}, FROZEN)

    def test_the_message_names_both_numbers(self):
        try:
            gradient.check_frozen({1.00: 12.5}, FROZEN)
        except gradient.FrozenObservationChanged as error:
            self.assertIn("13.71", str(error))
            self.assertIn("12.5", str(error))

    def test_a_tiny_rounding_difference_is_tolerated(self):
        gradient.check_frozen({1.50: -1.3650}, FROZEN)

    def test_thresholds_not_being_rechecked_are_ignored(self):
        gradient.check_frozen({0.25: 99.0}, FROZEN)

    def test_the_registration_carries_the_frozen_values(self):
        rows = [p for p in prereg.load() if p["hypothesis_id"] == "H-0005"]
        if not rows:
            self.skipTest("H-0005 not registered yet")
        frozen = rows[0]["parameters"]["frozen_prior_points_R"]
        self.assertAlmostEqual(float(frozen["1.0"]), 13.7125, places=3)


class TheRegistrationSaysWhatItMustSay(unittest.TestCase):
    def setUp(self):
        rows = [p for p in prereg.load() if p["hypothesis_id"] == "H-0005"]
        if not rows:
            self.skipTest("H-0005 not registered yet")
        self.h = rows[0]

    def test_the_grid_is_exactly_the_three_sub_one_R_values(self):
        self.assertEqual(self.h["parameters"]["new_thresholds_R"],
                         [0.25, 0.5, 0.75])
        self.assertEqual(self.h["max_configurations"], 3)

    def test_the_direction_is_declared(self):
        self.assertEqual(
            self.h["parameters"]["expected_spearman_direction"], -1)

    def test_the_three_configurations_are_one_family(self):
        self.assertIn("ONE hypothesis family",
                      self.h["parameters"]["family_rule"])
        self.assertIn("no individual configuration",
                      self.h["parameters"]["family_rule"].lower())

    def test_the_risk_clauses_are_stated_mathematically(self):
        text = self.h["acceptance_criteria"]
        self.assertIn("1.10 x", text)
        self.assertIn("abs(max_drawdown_candidate)", text)
        self.assertIn("volatility_candidate", text)

    def test_both_2025_bases_are_required(self):
        self.assertIn("INCLUDING and EXCLUDING 2025",
                      self.h["acceptance_criteria"])

    def test_the_thirty_year_window_is_called_contaminated_not_a_holdout(self):
        text = self.h["required_oos_test"]
        self.assertIn("CONTAMINATED", text)
        self.assertIn("not a", text.replace("\n", " "))
        self.assertIn("zero reads", text)

    def test_extra_thresholds_are_forbidden_by_name(self):
        text = self.h["search_procedure"]
        for banned in ("0.125", "0.375", "0.625", "0.875", "1.25"):
            self.assertIn(banned, text)

    def test_it_can_promote_nothing(self):
        self.assertIn("H-0005 alone can promote nothing",
                      self.h["promotion_requirements"])

    def test_a_tuned_grid_would_not_verify_against_the_seal(self):
        """The seal is what stops the grid moving after the surface shows."""
        import copy
        from event_aware_trader.modelgov.prereg import Hypothesis
        fields = {k: v for k, v in self.h.items()
                  if k not in ("seal", "registered_at", "code_commit")}
        tuned = copy.deepcopy(fields)
        tuned["parameters"]["new_thresholds_R"] = [0.30, 0.60, 0.90]
        self.assertNotEqual(Hypothesis(**tuned).seal(), self.h["seal"])


class AdjudicationStillGovernsSelection(unittest.TestCase):
    def test_no_caller_may_pick_by_return(self):
        with self.assertRaises(SelectionError):
            best_by_return([{"total_return": 1.0}])

    def test_every_configuration_is_adjudicated_none_pre_selected(self):
        baseline = {"label": "b", "total_return": 0.586, "max_drawdown": -0.13,
                    "annualised_volatility": 0.093,
                    "by_year": {y: 0.03 for y in range(2016, 2027)}}
        rows = [dict(baseline, label="x", total_return=0.60),
                dict(baseline, label="y", total_return=0.59)]
        verdicts = adjudicate(rows, baseline)
        self.assertEqual([v.label for v in verdicts], ["x", "y"])


class DeploymentRemainsImpossible(unittest.TestCase):
    def test_both_learned_components_are_off(self):
        from event_aware_trader import live_model, trade_learning
        self.assertFalse(live_model.LEARNED_RANKING_ENABLED)
        self.assertFalse(trade_learning.LEARNED_VETO_ENABLED)

    def test_nothing_is_promoted(self):
        from event_aware_trader.autotrade import AutoTradeConfig
        from event_aware_trader.live_model import is_promoted, load_live_model
        live, _est = load_live_model(AutoTradeConfig().live_model_file)
        if live is None:
            self.skipTest("no live model on disk")
        self.assertFalse(is_promoted(live))
        self.assertFalse(live.usable)

    def test_a_retrain_cannot_change_deployment_status(self):
        """It may write a research artifact; it may not deploy."""
        from event_aware_trader import live_model
        model = live_model.LiveModel(
            trained_at="2026-09-16T23:00:00+00:00", n_examples=99_999,
            test_auc=0.99, feature_names=live_model.LIVE_FEATURES,
            payload={}, status="USABLE")
        self.assertFalse(model.usable)


class TheThirtyYearWindowIsNotRead(unittest.TestCase):
    """Its access count is the audit trail; H-0005 must leave it alone."""

    def count(self):
        path = Path("docs/dataset-uses.jsonl")
        if not path.exists():
            self.skipTest("no dataset-use log")
        rows = [json.loads(l) for l in
                path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return sum(1 for r in rows if r.get("dataset") == "thirty_year")

    def test_the_count_is_the_recorded_thirteen(self):
        self.assertEqual(self.count(), 13,
                         "H-0005 must perform zero thirty-year reads")


if __name__ == "__main__":
    unittest.main()
