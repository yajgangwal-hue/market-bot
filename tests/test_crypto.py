"""Crypto support, pinned against what the live paper account actually accepts.

Every claim here was probed on 2026-09-04 with about $10 of BTC rather than
read from documentation:

    stop / gtc        REJECTED  HTTP 422 "invalid order type for crypto order"
    stop_limit / gtc  ACCEPTED  rested at 71886.6 on qty 0.00012249

and Alpaca reported the pair as "BTC/USD" in orders, fills and activities.
"""
import unittest

from event_aware_trader.broker import (
    CRYPTO_STOP_LIMIT_SLIP,
    AlpacaPaperBroker,
    BrokerConfig,
    BrokerError,
    is_crypto,
)
from event_aware_trader.data import price_file, price_file_name
from event_aware_trader.risk import RiskPolicy, cap_by_participation
from event_aware_trader.strategy import CORRELATION_BUCKETS, CRYPTO_UNIVERSE


def _broker(**overrides):
    base = {"key_id": "k", "secret_key": "s", "allow_order_submission": True}
    base.update(overrides)
    return AlpacaPaperBroker(BrokerConfig(**base))


class DetectionTests(unittest.TestCase):
    def test_a_slash_means_crypto(self):
        self.assertTrue(is_crypto("BTC/USD"))
        self.assertTrue(is_crypto("ETH/USD"))

    def test_equities_are_not_crypto(self):
        for symbol in ("SPY", "BRK-B", "EWY", "INTC"):
            self.assertFalse(is_crypto(symbol), symbol)


class UniverseTests(unittest.TestCase):
    def test_every_crypto_pair_shares_one_correlation_bucket(self):
        """Holding three of these is one position taken three times."""
        buckets = {CORRELATION_BUCKETS[s] for s in CRYPTO_UNIVERSE}
        self.assertEqual(buckets, {"crypto"})


class PriceFileTests(unittest.TestCase):
    def test_a_slashed_symbol_does_not_become_a_directory(self):
        self.assertEqual(price_file_name("BTC/USD"), "BTC-USD")
        self.assertNotIn("/", price_file_name("BTC/USD"))

    def test_equity_names_are_untouched(self):
        self.assertEqual(price_file_name("SPY"), "SPY")

    def test_the_path_is_a_single_file(self):
        path = price_file("data", "BTC/USD")
        self.assertEqual(path.name, "BTC-USD.csv")
        self.assertEqual(path.parent.name, "data")


class ProtectiveStopShapeTests(unittest.TestCase):
    """`stop` is refused for crypto; `stop_limit` is what rests."""

    def setUp(self):
        self.broker = _broker(allow_order_submission=False)

    def test_crypto_uses_stop_limit_not_stop(self):
        payload = self.broker.submit_protective_stop(
            "BTC/USD", 0.00012249, 71886.6, dry_run=True)["would_submit"]
        self.assertEqual(payload["type"], "stop_limit")
        self.assertEqual(payload["time_in_force"], "gtc")

    def test_the_limit_sits_below_the_trigger(self):
        """A stop-limit priced at its trigger is skipped in a fast move."""
        payload = self.broker.submit_protective_stop(
            "BTC/USD", 0.001, 50_000.0, dry_run=True)["would_submit"]
        self.assertLess(payload["limit_price"], payload["stop_price"])
        self.assertAlmostEqual(
            payload["limit_price"], 50_000.0 * (1 - CRYPTO_STOP_LIMIT_SLIP), places=2)

    def test_a_fractional_crypto_quantity_is_allowed(self):
        payload = self.broker.submit_protective_stop(
            "ETH/USD", 0.0731, 2000.0, dry_run=True)["would_submit"]
        self.assertEqual(float(payload["qty"]), 0.0731)

    def test_a_fractional_equity_quantity_is_still_refused(self):
        with self.assertRaises(BrokerError):
            self.broker.submit_protective_stop("SPY", 1.5, 700.0, dry_run=True)

    def test_equities_still_use_a_plain_stop(self):
        payload = self.broker.submit_protective_stop(
            "SPY", 10, 700.0, dry_run=True)["would_submit"]
        self.assertEqual(payload["type"], "stop")
        self.assertNotIn("limit_price", payload)


class EntryShapeTests(unittest.TestCase):
    def setUp(self):
        self.broker = _broker(allow_order_submission=False)

    def test_crypto_entry_carries_no_bracket(self):
        """Alpaca accepts no bracket order class on crypto."""
        preview = self.broker.submit_reviewed_candidate(
            "BTC/USD", 0.001, stop=70_000.0, target=90_000.0, dry_run=True)
        self.assertNotIn("order_class", preview["would_submit"])
        self.assertTrue(any("bracket" in w for w in preview["warnings"]))

    def test_crypto_entry_is_gtc(self):
        payload = self.broker.submit_reviewed_candidate(
            "BTC/USD", 0.001, stop=70_000.0, target=90_000.0,
            dry_run=True)["would_submit"]
        self.assertEqual(payload["time_in_force"], "gtc")

    def test_an_equity_entry_still_gets_its_bracket(self):
        payload = self.broker.submit_reviewed_candidate(
            "SPY", 10, stop=700.0, target=900.0, dry_run=True)["would_submit"]
        self.assertEqual(payload["order_class"], "bracket")
        self.assertEqual(payload["time_in_force"], "day")


class ParticipationCapTests(unittest.TestCase):
    """The cap that replaces the liquidity floor crypto could not clear."""

    def test_a_thin_book_shrinks_the_order(self):
        # BTC prints about $103,000 a day on Alpaca; 2% is ~$2,060.
        capped = cap_by_participation(0.25, 80_000.0, 103_000.0, 0.02)
        self.assertAlmostEqual(capped * 80_000.0, 2_060.0, places=2)

    def test_a_deep_book_never_binds(self):
        """2% of SPY's volume is $700m; a $20,000 order is untouched."""
        self.assertEqual(
            cap_by_participation(26.0, 772.0, 35_125_967_644.0, 0.02), 26.0)

    def test_no_cap_configured_changes_nothing(self):
        self.assertEqual(cap_by_participation(26.0, 772.0, 1_000.0, None), 26.0)

    def test_a_missing_volume_figure_is_not_guessed_at(self):
        self.assertEqual(cap_by_participation(26.0, 772.0, None, 0.02), 26.0)

    def test_the_default_policy_carries_a_cap(self):
        self.assertEqual(RiskPolicy().max_volume_participation, 0.02)


if __name__ == "__main__":
    unittest.main()
