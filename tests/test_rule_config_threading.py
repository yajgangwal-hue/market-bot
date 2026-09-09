"""One rule config, three call sites, no possibility of disagreement.

`autotrade` constructed `MeanReversionConfig()` in three separate places: the
entry candidate, the stop reconstruction for a position it did not open, and
the exit. Each was the shipped default, so they agreed by luck rather than by
construction. The moment any cycle needs different parameters - a crypto cycle
must, because the equity floors cannot see crypto at all - they would silently
diverge, and the bot would enter on one rule and exit on another.

That is not a hypothetical failure mode in this project. test_entry_rule.py
was written because "trading one rule's entries against the other's exits
would measure neither", and this is the same defect one level down: same rule,
different parameters.

The fix threads a single config through all three. These tests assert the
property directly - change one dial and every site sees it.
"""

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.autotrade import (
    AutoTradeConfig, _mean_reversion_candidate, _mr)
from event_aware_trader.mean_reversion import (
    CRYPTO_MEAN_REVERSION, MeanReversionConfig)
from event_aware_trader.risk import CostModel, RiskPolicy
from event_aware_trader.strategy import StrategyConfig
from event_aware_trader.types import Action

from test_entry_rule import oversold_in_an_uptrend


class AccessorTests(unittest.TestCase):
    def test_the_default_is_the_shipped_equity_rule(self):
        self.assertEqual(_mr(AutoTradeConfig()), MeanReversionConfig())

    def test_an_override_is_returned_intact(self):
        tuned = replace(MeanReversionConfig(), rsi_entry=25.0)
        self.assertEqual(_mr(AutoTradeConfig(mean_reversion=tuned)), tuned)

    def test_the_crypto_preset_differs_where_it_must(self):
        """Each of these is why the shipped rule sees nothing in crypto."""
        shipped = MeanReversionConfig()
        self.assertLess(CRYPTO_MEAN_REVERSION.min_price, shipped.min_price)
        self.assertLess(CRYPTO_MEAN_REVERSION.min_average_dollar_volume,
                        shipped.min_average_dollar_volume)
        self.assertIsNone(CRYPTO_MEAN_REVERSION.max_atr_fraction)
        self.assertIsNotNone(shipped.max_atr_fraction)

    def test_the_crypto_preset_leaves_the_RULE_alone(self):
        """Floors are about seeing the instrument. The rule itself is unchanged,
        so a crypto cycle trades the strategy that was measured, not a new one."""
        shipped = MeanReversionConfig()
        for field in ("rsi_period", "rsi_entry", "rsi_exit", "trend_ma_days",
                      "stop_atr_multiple", "max_holding_bars"):
            self.assertEqual(getattr(CRYPTO_MEAN_REVERSION, field),
                             getattr(shipped, field), field)


class EntryUsesTheConfigTests(unittest.TestCase):
    def _candidate(self, rule_config):
        return _mean_reversion_candidate(
            "SPY", oversold_in_an_uptrend(), 100_000.0, RiskPolicy(),
            CostModel(), StrategyConfig.for_interval("1d", exit_mode="trailing"),
            rule_config=rule_config)

    def test_the_default_still_buys_the_fixture(self):
        self.assertEqual(self._candidate(None).action, Action.PAPER_LONG)

    def test_a_stricter_entry_threshold_refuses_it(self):
        """Proves the config actually reaches the entry decision."""
        strict = replace(MeanReversionConfig(), rsi_entry=5.0)
        self.assertNotEqual(self._candidate(strict).action, Action.PAPER_LONG)

    def test_a_different_stop_multiple_moves_the_stop(self):
        wide = replace(MeanReversionConfig(), stop_atr_multiple=5.0)
        tight = replace(MeanReversionConfig(), stop_atr_multiple=1.0)
        self.assertLess(self._candidate(wide).stop, self._candidate(tight).stop)

    def test_a_price_floor_above_the_fixture_blocks_it(self):
        floored = replace(MeanReversionConfig(), min_price=10_000.0)
        self.assertNotEqual(self._candidate(floored).action, Action.PAPER_LONG)


class NoConstructionSitesRemainTests(unittest.TestCase):
    def test_autotrade_builds_the_config_in_exactly_one_place(self):
        """A fourth site would reintroduce the divergence this prevents.

        The accessor is the only legitimate constructor; the entry helper's
        own `rule_config or MeanReversionConfig()` fallback is the second, for
        direct callers in tests.
        """
        source = Path(__file__).resolve().parents[1] / "src" / \
            "event_aware_trader" / "autotrade.py"
        text = source.read_text(encoding="utf-8")
        code = [line for line in text.splitlines()
                if "MeanReversionConfig()" in line
                and not line.strip().startswith("#")]
        self.assertEqual(len(code), 2, "\n".join(code))


if __name__ == "__main__":
    unittest.main()
