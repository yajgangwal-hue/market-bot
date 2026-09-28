"""Exit placement: the barrier arithmetic and the optimal-trading-rule search.

PREPARED, NOT WIRED - nothing in the trading loop imports the module under
test. Synthetic inputs only; no market data is read.
"""

import math
import unittest

from event_aware_trader.exit_placement import (
    assess, break_even_hit_rate, continuation_value, expected_gross_gain,
    expected_holding_time, expected_ou_profit, optimal_rule, simulate_ou_rules,
    target_first_probability)


class BarrierArithmetic(unittest.TestCase):
    def test_with_no_edge_the_odds_are_stop_over_total_whatever_the_volatility(self):
        for vol in (0.005, 0.015, 0.05):
            self.assertAlmostEqual(target_first_probability(0.005, 0.002, 0.0, vol), 2 / 7)

    def test_the_closed_form_with_an_edge(self):
        # a = b = 2%, edge 0.2%/day, vol 2%/day -> 2 x edge / vol^2 = 10
        expected = (math.exp(0.2) - 1) / (math.exp(0.2) - math.exp(-0.2))
        self.assertAlmostEqual(target_first_probability(0.02, 0.02, 0.002, 0.02),
                               expected, places=12)

    def test_an_edge_tilts_the_odds_symmetrically(self):
        up = target_first_probability(0.02, 0.02, 0.002, 0.02)
        down = target_first_probability(0.02, 0.02, -0.002, 0.02)
        self.assertGreater(up, 0.5)
        self.assertAlmostEqual(up + down, 1.0, places=12)

    def test_an_extreme_edge_does_not_overflow(self):
        self.assertAlmostEqual(target_first_probability(0.5, 0.5, 5.0, 0.01), 1.0)
        self.assertAlmostEqual(target_first_probability(0.5, 0.5, -5.0, 0.01), 0.0)

    def test_holding_time_with_no_edge_is_target_times_stop_over_variance(self):
        self.assertAlmostEqual(expected_holding_time(0.005, 0.002, 0.0, 0.015),
                               0.005 * 0.002 / 0.015 ** 2)

    def test_holding_time_is_continuous_through_zero_edge(self):
        still = expected_holding_time(0.005, 0.002, 0.0, 0.015)
        self.assertAlmostEqual(expected_holding_time(0.005, 0.002, 1e-7, 0.015), still,
                               delta=1e-4 * still)

    def test_walds_identity_gain_is_edge_times_time(self):
        for a, b, mu, s in [(0.005, 0.002, 0.002, 0.015), (0.03, 0.05, 0.001, 0.02),
                            (0.02, 0.02, -0.003, 0.02)]:
            self.assertAlmostEqual(expected_gross_gain(a, b, mu, s),
                                   mu * expected_holding_time(a, b, mu, s), places=12)

    def test_with_no_edge_no_pair_makes_money(self):
        for a, b in [(0.005, 0.002), (0.002, 0.005), (0.05, 0.025)]:
            self.assertAlmostEqual(expected_gross_gain(a, b, 0.0, 0.02), 0.0, places=15)

    def test_break_even_hit_rate(self):
        self.assertAlmostEqual(break_even_hit_rate(0.005, 0.002, 0.0012), 0.0032 / 0.007)
        self.assertAlmostEqual(break_even_hit_rate(0.005, 0.002, 0.0), 2 / 7)

    def test_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            target_first_probability(0.0, 0.002, 0.0, 0.01)
        with self.assertRaises(ValueError):
            target_first_probability(0.005, 0.002, 0.0, 0.0)


class Assessment(unittest.TestCase):
    def test_the_owners_half_percent_target_and_fifth_percent_stop(self):
        result = assess(0.005, 0.002, daily_vol=0.015)
        self.assertAlmostEqual(result.target_first, 2 / 7)
        self.assertAlmostEqual(result.break_even, 0.0032 / 0.007)
        self.assertAlmostEqual(result.expected_minutes, 0.005 * 0.002 / 0.015 ** 2 * 390)
        self.assertAlmostEqual(result.net_per_trade, -0.0012)
        self.assertTrue(any("inside ordinary 15-minute noise" in n for n in result.notes))

    def test_an_edge_adds_almost_nothing_to_a_trade_that_lasts_minutes(self):
        result = assess(0.005, 0.002, daily_vol=0.015, drift_per_day=0.002)
        self.assertLess(result.gross_per_trade, 0.0002)     # about 0.009%
        self.assertLess(result.net_per_trade, -0.001)
        self.assertTrue(any("only minutes" in n for n in result.notes))

    def test_chance_and_the_assumed_edge_are_reported_apart(self):
        result = assess(0.05, 0.06, daily_vol=0.0139, drift_per_day=0.0005)
        self.assertAlmostEqual(result.chance_target_first, 6 / 11)
        self.assertGreater(result.target_first, result.chance_target_first)
        self.assertIn("{0:.0%} of the time".format(6 / 11), result.notes[0])
        self.assertIn("becomes {0:.0%}".format(result.target_first), result.notes[1])

    def test_a_wide_pair_is_measured_in_days_and_not_called_noise(self):
        result = assess(0.05, 0.05, daily_vol=0.015, drift_per_day=0.0005)
        self.assertGreater(result.expected_minutes, 390)
        self.assertFalse(any("inside ordinary 15-minute noise" in n for n in result.notes))
        self.assertTrue(any("trading days" in n for n in result.notes))
        self.assertFalse(any("only minutes" in n for n in result.notes))

    def test_as_dict_is_in_percent(self):
        payload = assess(0.005, 0.002, daily_vol=0.015).as_dict()
        self.assertEqual(payload["target_pct"], 0.5)
        self.assertEqual(payload["chance_target_first_pct"], 28.57)
        self.assertEqual(payload["target_first_pct"], 28.57)
        self.assertEqual(payload["net_per_trade_pct"], -0.12)


class OptimalTradingRule(unittest.TestCase):
    def test_on_a_random_walk_no_rule_has_an_edge(self):
        results = simulate_ou_rules([0.5, 1.0, 2.0, math.inf], [0.5, 1.0, 2.0, math.inf],
                                    half_life=math.inf, forecast=0.0, sigma=1.0,
                                    max_steps=20, paths=40000, seed=1)
        for r in results:
            self.assertLess(abs(r.mean), 4 * r.std / math.sqrt(40000))

    def test_with_no_levels_the_mean_matches_the_closed_form(self):
        [r] = simulate_ou_rules([math.inf], [math.inf], half_life=5, forecast=2.0,
                                sigma=1.0, max_steps=20, paths=40000, seed=2)
        self.assertAlmostEqual(expected_ou_profit(2.0, 5, 20), 1.875)
        self.assertAlmostEqual(r.mean, 1.875, delta=4 * r.std / math.sqrt(40000))
        self.assertEqual(r.target_share, 0.0)
        self.assertEqual(r.stop_share, 0.0)
        self.assertEqual(r.mean_steps, 20.0)

    def test_for_a_reverting_trade_every_stop_lowers_expected_profit(self):
        results = simulate_ou_rules([math.inf], [0.5, 1.0, 2.0, 3.0, math.inf],
                                    half_life=5, forecast=2.0, sigma=1.0, max_steps=20,
                                    paths=20000, seed=3)
        means = [r.mean for r in results]
        self.assertEqual(means, sorted(means))              # wider is better, every step
        self.assertEqual(optimal_rule(results, "mean").stop_loss, math.inf)

    def test_judged_on_smoothness_the_best_target_is_tighter_than_the_most_profitable(self):
        results = simulate_ou_rules([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, math.inf],
                                    [math.inf], half_life=5, forecast=2.0, sigma=1.0,
                                    max_steps=20, paths=20000, seed=4)
        by_profit = optimal_rule(results, "mean")
        by_sharpe = optimal_rule(results, "sharpe")
        self.assertLess(by_sharpe.profit_take, by_profit.profit_take)
        self.assertGreater(by_sharpe.target_share, by_profit.target_share)   # wins more often
        self.assertLess(by_sharpe.mean, by_profit.mean)                     # and makes less

    def test_the_search_is_reproducible_and_stays_on_the_grid(self):
        grid = dict(profit_takes=[1.0, 2.0], stop_losses=[1.0, math.inf], half_life=5,
                    forecast=1.0, sigma=1.0, max_steps=10, paths=5000, seed=9)
        first, second = simulate_ou_rules(**grid), simulate_ou_rules(**grid)
        self.assertEqual([(r.mean, r.std) for r in first], [(r.mean, r.std) for r in second])
        best = optimal_rule(first, "mean")
        self.assertIn((best.profit_take, best.stop_loss),
                      [(t, s) for t in (1.0, 2.0) for s in (1.0, math.inf)])

    def test_costs_are_charged_once_per_trade(self):
        base = simulate_ou_rules([1.0], [1.0], 5, 1.0, 1.0, 10, paths=5000, seed=5)[0]
        costed = simulate_ou_rules([1.0], [1.0], 5, 1.0, 1.0, 10, paths=5000, seed=5,
                                   round_trip_cost=0.25)[0]
        self.assertAlmostEqual(base.mean - costed.mean, 0.25)

    def test_the_objective_must_be_declared(self):
        results = simulate_ou_rules([1.0], [1.0], 5, 1.0, 1.0, 10, paths=100, seed=6)
        with self.assertRaises(ValueError):
            optimal_rule(results, "return")

    def test_continuation_value_changes_sign_at_the_fair_level(self):
        self.assertGreater(continuation_value(-1.0, 2.0, 5, 10), 0.0)
        self.assertAlmostEqual(continuation_value(2.0, 2.0, 5, 10), 0.0)
        self.assertLess(continuation_value(3.0, 2.0, 5, 10), 0.0)
        self.assertEqual(continuation_value(-1.0, 2.0, 5, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
