"""Consistency statistics, and the deflated-Sharpe bug that nothing caught.

`stats.py` has carried a Sharpe ratio, a probabilistic Sharpe and a deflated
Sharpe since the beginning, and no caller anywhere in the codebase used any of
them. The record could report a win rate and a p-value but had no measure of
consistency at all - which is the thing that actually decides whether a
strategy is worth running.

Wiring them in surfaced a units bug in `deflated_sharpe_ratio`: the trial
variance is expressed in annualised Sharpe units, and the threshold was then
annualised a second time. At 94.5 trades a year the bar for 20 trials became
an annualised Sharpe of 18.5 rather than 1.90, so every strategy scored 0.0.
These tests pin the units so it cannot come back.
"""

import math
import random
import unittest

from event_aware_trader.record import (
    DECAY_HAIRCUT,
    MINIMUM_SESSIONS_FOR_RATE,
    RecordReport,
    TradeRecord,
)
from event_aware_trader.stats import (
    EULER_MASCHERONI,
    deflated_sharpe_ratio,
    normal_cdf,
    normal_quantile,
    sharpe_ratio,
)


def record_of(mean, sd, n, sessions=504, trials=1, seed=7):
    generator = random.Random(seed)
    report = RecordReport(starting_equity=100_000.0, sessions_observed=sessions,
                          equity_base_is_real=True, trials_tested=trials)
    for _ in range(n):
        value = generator.gauss(mean, sd)
        report.trades.append(
            TradeRecord("SPY", "2026-01-01", "2026-01-05", value * 1000, value))
    report.ending_equity = 100_000.0 + sum(t.net_pnl for t in report.trades)
    return report


class GuardTests(unittest.TestCase):
    def test_a_handful_of_trades_has_no_measurable_consistency(self):
        verdict = record_of(0.01, 0.03, 4).consistency()
        self.assertIn("at least 5 closed trades", verdict["note"])

    def test_a_short_observation_window_cannot_supply_a_trade_rate(self):
        """Three trades over three sessions annualises to 252 a year."""
        verdict = record_of(0.01, 0.03, 10, sessions=3).consistency()
        self.assertIn("cannot supply one", verdict["note"])
        self.assertNotIn("annualised_sharpe", verdict)

    def test_the_same_guard_applies_to_time_to_evidence(self):
        horizon = record_of(0.01, 0.03, 10, sessions=3).verdict()["time_to_evidence"]
        self.assertIn("too short a window", horizon["note"])
        self.assertEqual(horizon["sessions_observed"], 3)

    def test_a_real_window_does_produce_figures(self):
        verdict = record_of(0.01, 0.03, 40, sessions=MINIMUM_SESSIONS_FOR_RATE).consistency()
        self.assertIn("annualised_sharpe", verdict)

    def test_identical_returns_have_no_dispersion_to_measure(self):
        report = RecordReport(sessions_observed=504)
        for _ in range(10):
            report.trades.append(
                TradeRecord("SPY", "2026-01-01", "2026-01-05", 10.0, 0.01))
        self.assertIn("no dispersion", report.consistency()["note"])


class SharpeTests(unittest.TestCase):
    def test_sharpe_is_annualised_from_the_observed_trade_rate(self):
        report = record_of(0.0125, 0.04, 189, sessions=504)
        verdict = report.consistency()
        breadth = 189 / 504.0 * 252.0
        self.assertAlmostEqual(verdict["breadth_trades_per_year"], round(breadth, 1))
        expected = sharpe_ratio(report.returns, periods_per_year=breadth)
        self.assertAlmostEqual(verdict["annualised_sharpe"], round(expected, 3))

    def test_the_grinold_decomposition_round_trips(self):
        """IR = IC x sqrt(breadth), so IC = IR / sqrt(breadth)."""
        verdict = record_of(0.0125, 0.04, 189, sessions=504).consistency()
        rebuilt = (verdict["implied_information_coefficient"]
                   * math.sqrt(verdict["breadth_trades_per_year"]))
        self.assertAlmostEqual(rebuilt, verdict["annualised_sharpe"], places=2)

    def test_expected_losing_months_follows_the_monthly_sharpe(self):
        verdict = record_of(0.005, 0.04, 189, sessions=504).consistency()
        sharpe = verdict["annualised_sharpe"]
        expected = 12.0 * normal_cdf(-sharpe / math.sqrt(12.0))
        self.assertAlmostEqual(verdict["expected_losing_months_per_year"],
                               round(expected, 1))

    def test_even_an_excellent_strategy_loses_several_months_a_year(self):
        """Sharpe 1.0 loses 4.6 months of an average year."""
        self.assertAlmostEqual(12.0 * normal_cdf(-1.0 / math.sqrt(12.0)), 4.6, places=1)
        self.assertAlmostEqual(12.0 * normal_cdf(-2.0 / math.sqrt(12.0)), 3.4, places=1)

    def test_decay_adjustment_halves_the_edge_and_the_sharpe(self):
        verdict = record_of(0.0125, 0.04, 189, sessions=504).consistency()
        self.assertAlmostEqual(verdict["decay_adjusted_sharpe"],
                               round(verdict["annualised_sharpe"] * DECAY_HAIRCUT, 3))
        self.assertAlmostEqual(verdict["decay_adjusted_mean_return"],
                               round(verdict["mean_return_per_trade"] * DECAY_HAIRCUT, 6))

    def test_an_implausible_implied_ic_is_called_out(self):
        """A world-class forecaster runs an IC near 0.05."""
        verdict = record_of(0.05, 0.03, 20, sessions=252).consistency()
        self.assertGreater(verdict["implied_information_coefficient"], 0.15)
        self.assertIn("sample is too small", verdict["reading"])


class DeflatedSharpeTests(unittest.TestCase):
    """The units bug: the threshold was annualised twice."""

    RETURNS = [r for r in record_of(0.0125, 0.04, 189, sessions=504).returns]

    def test_a_strong_strategy_is_not_scored_zero(self):
        """Before the fix every strategy scored 0.0, at every trial count."""
        got = deflated_sharpe_ratio(self.RETURNS, trials=20, periods_per_year=94.5)
        self.assertIsNotNone(got)
        self.assertGreater(got, 0.5)

    def test_the_threshold_is_the_expected_max_of_the_trial_sharpes(self):
        """With unit variance, 20 trials implies an annualised bar near 1.90."""
        trials = 20
        upper = normal_quantile(1.0 - 1.0 / trials)
        lower = normal_quantile(1.0 - 1.0 / (trials * math.e))
        bar = (1.0 - EULER_MASCHERONI) * upper + EULER_MASCHERONI * lower
        self.assertAlmostEqual(bar, 1.90, places=1)

    def test_more_trials_means_a_lower_score(self):
        scores = [deflated_sharpe_ratio(self.RETURNS, trials=t, periods_per_year=94.5)
                  for t in (2, 10, 20, 100, 1000)]
        for earlier, later in zip(scores, scores[1:]):
            self.assertGreater(earlier, later)

    def test_a_marginal_strategy_does_not_survive_a_wide_search(self):
        """Sharpe near 1.0 found after 100 variants is probably the search."""
        marginal = record_of(0.003, 0.04, 189, sessions=504).returns
        few = deflated_sharpe_ratio(marginal, trials=2, periods_per_year=94.5)
        many = deflated_sharpe_ratio(marginal, trials=100, periods_per_year=94.5)
        self.assertGreater(few, 0.5)
        self.assertLess(many, 0.10)

    def test_a_single_trial_needs_no_deflation(self):
        from event_aware_trader.stats import probabilistic_sharpe_ratio
        self.assertAlmostEqual(
            deflated_sharpe_ratio(self.RETURNS, trials=1, periods_per_year=94.5),
            probabilistic_sharpe_ratio(self.RETURNS, 0.0, 94.5))

    def test_zero_trials_is_refused(self):
        with self.assertRaises(ValueError):
            deflated_sharpe_ratio(self.RETURNS, trials=0)

    def test_the_record_only_deflates_when_trials_are_declared(self):
        self.assertNotIn("deflated_sharpe_probability",
                         record_of(0.0125, 0.04, 189, trials=1).consistency())
        self.assertIn("deflated_sharpe_probability",
                      record_of(0.0125, 0.04, 189, trials=20).consistency())


if __name__ == "__main__":
    unittest.main()
