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



class AssetClassIsolationTests(unittest.TestCase):
    """Two loops, one account. Neither may touch the other's positions.

    The equity loop runs the US session; the crypto loop runs around the clock.
    Without confinement a 3am crypto cycle would evaluate an equity position on
    stale bars - and _reconcile_protective_stops cancels any resting sell it
    does not recognise, so it would strip the GTC stop off a stock while the
    market that could replace it is closed.
    """

    def setUp(self):
        from event_aware_trader.autotrade import AutoTradeConfig
        self.crypto = AutoTradeConfig(asset_class="crypto")
        self.equity = AutoTradeConfig(asset_class="equity")
        self.both = AutoTradeConfig()

    def test_a_crypto_cycle_owns_only_crypto(self):
        from event_aware_trader.autotrade import owns
        self.assertTrue(owns(self.crypto, "BTC/USD"))
        self.assertFalse(owns(self.crypto, "EWY"))

    def test_an_equity_cycle_owns_only_equities(self):
        from event_aware_trader.autotrade import owns
        self.assertTrue(owns(self.equity, "EWY"))
        self.assertFalse(owns(self.equity, "BTC/USD"))

    def test_the_default_owns_everything(self):
        from event_aware_trader.autotrade import owns
        self.assertTrue(owns(self.both, "EWY"))
        self.assertTrue(owns(self.both, "BTC/USD"))

    def test_the_two_classes_partition_the_universe(self):
        """No symbol is owned by both loops, and none by neither."""
        from event_aware_trader.autotrade import owns
        from event_aware_trader.strategy import DEFAULT_UNIVERSE
        for symbol in DEFAULT_UNIVERSE:
            self.assertNotEqual(
                owns(self.crypto, symbol), owns(self.equity, symbol),
                "%s is owned by both loops or by neither" % symbol)

    def test_the_default_is_all_so_existing_behaviour_is_unchanged(self):
        from event_aware_trader.autotrade import AutoTradeConfig
        self.assertEqual(AutoTradeConfig().asset_class, "all")


class SymbolNormalisationTests(unittest.TestCase):
    """Alpaca spells one pair two ways, and the mismatch disarms every stop.

    Measured live 2026-09-04: GET /v2/positions returns 'BTCUSD' with
    asset_class 'crypto', while orders, fills and activities all return
    'BTC/USD'. is_crypto() keys off the slash, so the position read as an
    equity - the crypto loop never protected it and the equity loop would have
    tried to, with a plain `stop` Alpaca refuses on crypto.
    """

    def test_an_unslashed_crypto_position_is_restored_to_its_pair(self):
        from event_aware_trader.broker import canonical_symbol
        self.assertEqual(canonical_symbol("BTCUSD", "crypto"), "BTC/USD")
        self.assertEqual(canonical_symbol("ETHUSD", "crypto"), "ETH/USD")

    def test_an_already_slashed_symbol_is_left_alone(self):
        from event_aware_trader.broker import canonical_symbol
        self.assertEqual(canonical_symbol("BTC/USD", "crypto"), "BTC/USD")

    def test_an_equity_is_never_rewritten(self):
        """A real ticker could be spelled like a pair, so asset_class decides."""
        from event_aware_trader.broker import canonical_symbol
        for symbol in ("EWY", "SPY", "USD", "BTC"):
            self.assertEqual(canonical_symbol(symbol, "us_equity"), symbol)

    def test_longer_quote_currencies_win(self):
        from event_aware_trader.broker import canonical_symbol
        self.assertEqual(canonical_symbol("BTCUSDT", "crypto"), "BTC/USDT")
        self.assertEqual(canonical_symbol("BTCUSDC", "crypto"), "BTC/USDC")

    def test_a_normalised_position_classifies_as_crypto(self):
        """The whole point: this is what was returning False."""
        from event_aware_trader.broker import canonical_symbol, is_crypto
        self.assertTrue(is_crypto(canonical_symbol("BTCUSD", "crypto")))

    def test_the_right_loop_claims_it(self):
        from event_aware_trader.autotrade import AutoTradeConfig, owns
        from event_aware_trader.broker import canonical_symbol
        symbol = canonical_symbol("BTCUSD", "crypto")
        self.assertTrue(owns(AutoTradeConfig(asset_class="crypto"), symbol))
        self.assertFalse(owns(AutoTradeConfig(asset_class="equity"), symbol))

    def test_close_position_quotes_the_slash(self):
        """Unquoted, /v2/positions/BTC/USD is a different route."""
        broker = _broker()
        seen = {}

        def fake_request(method, path, payload=None):
            seen["path"] = path
            return {"id": "x"}

        broker._request = fake_request
        broker.close_position("BTC/USD", dry_run=False)
        self.assertEqual(seen["path"], "/v2/positions/BTC%2FUSD")

if __name__ == "__main__":
    unittest.main()
