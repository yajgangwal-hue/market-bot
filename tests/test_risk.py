import unittest

from event_aware_trader.risk import CostModel, RiskPolicy, evaluate_guard, position_size


class RiskTests(unittest.TestCase):
    def test_position_size_includes_stop_and_costs(self):
        quantity, planned_risk = position_size(10_000, 100, 98, RiskPolicy(), CostModel())
        self.assertGreater(quantity, 0)
        self.assertLessEqual(planned_risk, 50.0)

    def test_daily_loss_guard_blocks_new_positions(self):
        decision = evaluate_guard(10_000, -150, 0, 0, "technology", (), RiskPolicy())
        self.assertFalse(decision.allowed)
        self.assertIn("Daily loss guard has been reached; stop for the day", decision.reasons)

    def test_correlation_bucket_guard_blocks_duplicate_exposure(self):
        decision = evaluate_guard(10_000, 0, 0, 1, "technology", ("technology",), RiskPolicy())
        self.assertFalse(decision.allowed)
        self.assertIn("Correlation bucket already has an open position", decision.reasons)


if __name__ == "__main__":
    unittest.main()


class FractionalSizingTests(unittest.TestCase):
    """A $1,000 account cannot buy a whole share of a $640 ETF at 0.5% risk."""

    def test_small_account_can_size_a_high_priced_symbol(self):
        quantity, planned_risk = position_size(1_000, 640, 624, RiskPolicy(), CostModel())
        self.assertGreater(quantity, 0)
        self.assertLess(quantity, 1.0)
        self.assertLessEqual(planned_risk, 1_000 * 0.005 + 1e-9)

    def test_whole_share_mode_still_rejects_the_same_case(self):
        policy = RiskPolicy(allow_fractional_shares=False)
        quantity, _ = position_size(1_000, 640, 624, policy, CostModel())
        self.assertEqual(quantity, 0)

    def test_risk_budget_is_never_exceeded_by_rounding(self):
        policy, costs = RiskPolicy(), CostModel()
        for equity in (250, 1_000, 5_000, 100_000):
            for entry, stop in ((640, 624), (52, 50.5), (315, 307)):
                _, planned_risk = position_size(equity, entry, stop, policy, costs)
                self.assertLessEqual(planned_risk, equity * policy.risk_per_trade + 1e-9)

    def test_dust_position_below_minimum_notional_is_rejected(self):
        quantity, _ = position_size(5, 640, 624, RiskPolicy(), CostModel())
        self.assertEqual(quantity, 0)
