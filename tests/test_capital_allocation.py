"""Trading a slice of the account rather than all of it.

The slice has to compound, has to scale the loss guards with it, and must
never exceed what the account actually holds.
"""
import unittest

from event_aware_trader.autotrade import AutoTradeConfig, _allocated_equity


def sliced(base=1000.0, baseline=100_000.0):
    return AutoTradeConfig(capital_base=base, capital_baseline_equity=baseline)


class AllocationTests(unittest.TestCase):
    def test_no_settings_trades_the_whole_account(self):
        self.assertEqual(_allocated_equity(AutoTradeConfig(), 100_003.74), 100_003.74)

    def test_half_a_setting_is_ignored_rather_than_half_applied(self):
        """The CLI refuses this pairing; the helper must not guess either."""
        only_base = AutoTradeConfig(capital_base=1000.0)
        only_baseline = AutoTradeConfig(capital_baseline_equity=100_000.0)
        self.assertEqual(_allocated_equity(only_base, 100_003.74), 100_003.74)
        self.assertEqual(_allocated_equity(only_baseline, 100_003.74), 100_003.74)

    def test_the_slice_is_the_base_plus_what_the_account_has_made(self):
        self.assertAlmostEqual(_allocated_equity(sliced(), 100_003.74), 1_003.74, places=2)

    def test_profit_compounds_into_the_slice(self):
        """'Keep building on that number' - a gain enlarges the book."""
        self.assertAlmostEqual(_allocated_equity(sliced(), 100_050.00), 1_050.00, places=2)

    def test_a_loss_shrinks_the_slice(self):
        self.assertAlmostEqual(_allocated_equity(sliced(), 99_980.00), 980.00, places=2)

    def test_the_slice_never_exceeds_the_real_account(self):
        """A slice bigger than the account would size orders it cannot fill."""
        self.assertEqual(_allocated_equity(sliced(base=5_000.0, baseline=1_000.0), 900.0), 900.0)

    def test_an_exhausted_slice_floors_at_zero_rather_than_going_negative(self):
        self.assertEqual(_allocated_equity(sliced(), 98_500.00), 0.0)


class GuardScalingTests(unittest.TestCase):
    """The guards key off the same figure, so they scale with the slice."""

    def test_a_daily_guard_binds_on_the_slice_not_the_account(self):
        allocated = _allocated_equity(sliced(), 100_003.74)
        opening = allocated
        after_a_16_dollar_loss = _allocated_equity(sliced(), 100_003.74 - 16.0)
        drawdown = (after_a_16_dollar_loss - opening) / opening
        self.assertLess(drawdown, -0.015,
                        "a $16 loss must trip a 1.5% guard on a $1,000 book")

    def test_the_same_loss_would_not_bind_on_the_full_account(self):
        opening = 100_003.74
        drawdown = ((100_003.74 - 16.0) - opening) / opening
        self.assertGreater(drawdown, -0.015)


if __name__ == "__main__":
    unittest.main()
