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
