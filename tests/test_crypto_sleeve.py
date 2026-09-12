"""The crypto sleeve: an allocation, not a trading strategy.

Every crypto TRADING strategy tested in this project lost money in a real
account, for a structural reason - risk-budget sizing gives a 4-13%-a-day
asset a position too small to matter. So this holds BTC or holds nothing,
based on whether BTC is above its own 100-day average, which was the one
approach verified across two complete crypto cycles.

The decision is a pure function of (equity, held value, trend) precisely so it
can be tested exhaustively without a broker or a network. These tests pin the
behaviours that would cost money if they were wrong - above all that missing
data never liquidates a position.
"""

import unittest
from datetime import datetime, timedelta

from event_aware_trader.crypto_sleeve import SleeveConfig, plan, risk_on
from event_aware_trader.types import Bar


def bars(closes, start=datetime(2026, 1, 1)):
    return [Bar(timestamp=start + timedelta(days=i), open=c, high=c * 1.02,
                low=c * 0.98, close=c, volume=1_000.0)
            for i, c in enumerate(closes)]


class TrendTests(unittest.TestCase):
    def test_a_rising_series_is_risk_on(self):
        self.assertTrue(risk_on(bars([100.0 + i for i in range(200)]),
                                SleeveConfig()))

    def test_a_falling_series_is_risk_off(self):
        self.assertFalse(risk_on(bars([300.0 - i for i in range(200)]),
                                 SleeveConfig()))

    def test_too_little_history_is_UNKNOWN_not_risk_off(self):
        """The single most important distinction in this module.

        None means "cannot tell" and must lead to doing nothing. False means
        "measured, trend is down, sell". If a failed data fetch returned False
        the sleeve would liquidate on every outage.
        """
        self.assertIsNone(risk_on(bars([100.0] * 50), SleeveConfig()))

    def test_no_bars_at_all_is_unknown(self):
        self.assertIsNone(risk_on([], SleeveConfig()))

    def test_exactly_at_the_average_is_risk_off(self):
        """A flat series sits ON its average; not above it, so not held."""
        self.assertFalse(risk_on(bars([100.0] * 200), SleeveConfig()))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.config = SleeveConfig()

    def test_unknown_trend_does_nothing_even_holding_a_position(self):
        """An outage must never sell. This is the test that earns its keep."""
        decision = plan(100_000.0, 5_000.0, None, self.config)
        self.assertEqual(decision["action"], "hold")
        self.assertEqual(decision["delta"], 0.0)

    def test_risk_on_from_flat_buys_the_sleeve(self):
        decision = plan(100_000.0, 0.0, True, self.config)
        self.assertEqual(decision["action"], "buy")
        self.assertAlmostEqual(decision["target"], 5_000.0)
        self.assertAlmostEqual(decision["delta"], 5_000.0)

    def test_risk_off_while_holding_sells_it_all(self):
        decision = plan(100_000.0, 5_000.0, False, self.config)
        self.assertEqual(decision["action"], "sell")
        self.assertAlmostEqual(decision["target"], 0.0)
        self.assertAlmostEqual(decision["delta"], -5_000.0)

    def test_risk_off_while_flat_does_nothing(self):
        self.assertEqual(plan(100_000.0, 0.0, False, self.config)["action"],
                         "hold")

    def test_a_small_drift_is_not_worth_trading(self):
        """Without this the sleeve pays spread every cycle as equity wobbles."""
        decision = plan(100_000.0, 4_600.0, True, self.config)
        self.assertEqual(decision["action"], "hold")

    def test_a_large_drift_is_corrected(self):
        decision = plan(100_000.0, 2_000.0, True, self.config)
        self.assertEqual(decision["action"], "buy")
        self.assertAlmostEqual(decision["delta"], 3_000.0)

    def test_an_exit_is_never_blocked_by_the_tolerance(self):
        """Tolerance is measured against the target, and the target is zero on
        an exit - so a naive implementation could never clear it and would
        hold a losing position forever."""
        decision = plan(100_000.0, 120.0, False, self.config)
        self.assertEqual(decision["action"], "sell")
        self.assertAlmostEqual(decision["delta"], -120.0)

    def test_a_trivial_order_is_skipped(self):
        decision = plan(100_000.0, 10.0, False, self.config)
        self.assertEqual(decision["action"], "hold")

    def test_the_sleeve_scales_with_the_account(self):
        """Sized against total equity, so it stays 5% as the account grows."""
        self.assertAlmostEqual(plan(200_000.0, 0.0, True, self.config)["target"],
                               10_000.0)


class ConfigTests(unittest.TestCase):
    def test_the_default_is_five_percent(self):
        """20% scored better on the historical table and is deliberately not
        the default: that gap is entirely BTC's 30.7%/yr past return, and
        sizing against it optimises for a number nobody can promise."""
        self.assertAlmostEqual(SleeveConfig().fraction, 0.05)

    def test_it_refuses_to_be_most_of_the_account(self):
        with self.assertRaises(ValueError):
            SleeveConfig(fraction=0.8)

    def test_it_refuses_a_non_positive_fraction(self):
        with self.assertRaises(ValueError):
            SleeveConfig(fraction=0.0)

    def test_the_trend_window_is_the_verified_one(self):
        self.assertEqual(SleeveConfig().trend_days, 100)

    def test_a_meaninglessly_short_trend_window_is_refused(self):
        with self.assertRaises(ValueError):
            SleeveConfig(trend_days=5)


class WorstCaseTests(unittest.TestCase):
    def test_the_downside_is_bounded_by_the_weight(self):
        """BTC's worst measured drawdown was -48.2%. On a 5% sleeve that is
        -2.4% of the account, which is the whole reason for choosing 5%."""
        config = SleeveConfig()
        sleeve = 100_000.0 * config.fraction
        self.assertAlmostEqual(sleeve * 0.482 / 100_000.0, 0.0241, places=3)


class SpendingWhatTheAccountActuallyHasTests(unittest.TestCase):
    """The sleeve has to work while the equity book is full.

    `plan` is pure and knew nothing about cash, so it asked for its full 5%
    every cycle regardless of the balance. On an account 99.3% invested in
    equities that is a $5,000 order against $702, rejected by the broker every
    fifteen minutes for ever - and the sleeve would never start.

    Capping instead of refusing is what makes it converge: take the position
    it can afford now, top up as equity trades close, and let the 20%
    tolerance stop it churning once it arrives.
    """

    def _config(self):
        return SleeveConfig()

    def test_a_buy_is_capped_at_available_cash(self):
        decision = plan(100_000.0, 0.0, True, self._config(),
                        available_cash=702.52)
        self.assertEqual(decision["action"], "buy")
        self.assertAlmostEqual(decision["delta"], 702.52, places=2)
        self.assertIn("capped", decision["reason"])

    def test_it_asks_for_the_full_target_when_the_cash_is_there(self):
        decision = plan(100_000.0, 0.0, True, self._config(),
                        available_cash=50_000.0)
        self.assertAlmostEqual(decision["delta"], 5_000.0, places=2)
        self.assertNotIn("capped", decision["reason"])

    def test_it_waits_rather_than_placing_a_dust_order(self):
        # Below the minimum order it must hold and say why, not submit $3.
        decision = plan(100_000.0, 0.0, True, self._config(),
                        available_cash=3.0)
        self.assertEqual(decision["action"], "hold")
        self.assertEqual(decision["delta"], 0.0)
        self.assertIn("waiting for equity trades", decision["reason"])

    def test_a_sell_is_never_capped_by_cash(self):
        # Closing a position releases cash rather than needing it. Capping a
        # sell would strand the sleeve in a downtrend with an empty balance.
        decision = plan(100_000.0, 5_000.0, False, self._config(),
                        available_cash=0.0)
        self.assertEqual(decision["action"], "sell")
        self.assertAlmostEqual(decision["delta"], -5_000.0, places=2)

    def test_omitting_cash_preserves_the_original_behaviour(self):
        # Every figure measured for this sleeve was produced without the cap.
        with_none = plan(100_000.0, 0.0, True, self._config())
        self.assertAlmostEqual(with_none["delta"], 5_000.0, places=2)

    def test_it_converges_instead_of_churning(self):
        # Partial fills must keep topping up, then stop inside the tolerance.
        config = self._config()
        held = 0.0
        for _ in range(12):
            decision = plan(100_000.0, held, True, config, available_cash=800.0)
            if decision["action"] != "buy":
                break
            held += decision["delta"]
        self.assertGreater(held, 4_000.0,
                           "the sleeve never converged toward its target")
        settled = plan(100_000.0, held, True, config, available_cash=800.0)
        self.assertEqual(settled["action"], "hold",
                         "the sleeve kept buying past its target")
