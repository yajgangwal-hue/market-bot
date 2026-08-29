import unittest

from event_aware_trader.broker import (
    LIVE_ENDPOINT,
    PAPER_ENDPOINT,
    AlpacaPaperBroker,
    BrokerConfig,
    BrokerError,
)


def _config(**overrides):
    base = {"key_id": "test-key", "secret_key": "test-secret"}
    base.update(overrides)
    return BrokerConfig(**base)


class EndpointSafetyTests(unittest.TestCase):
    def test_live_endpoint_is_refused(self):
        with self.assertRaises(BrokerError) as ctx:
            AlpacaPaperBroker(_config(endpoint=LIVE_ENDPOINT))
        self.assertIn("live trading endpoint", str(ctx.exception))

    def test_unknown_endpoint_is_refused(self):
        with self.assertRaises(BrokerError):
            AlpacaPaperBroker(_config(endpoint="https://not-alpaca.example.com"))

    def test_paper_endpoint_is_accepted(self):
        broker = AlpacaPaperBroker(_config(endpoint=PAPER_ENDPOINT))
        self.assertEqual(broker.config.endpoint, PAPER_ENDPOINT)


class OrderSafetyTests(unittest.TestCase):
    """Two independent flags must both be cleared before anything is sent."""

    def setUp(self):
        self.broker = AlpacaPaperBroker(_config())

    def test_dry_run_is_the_default_and_sends_nothing(self):
        result = self.broker.submit_reviewed_candidate("SPY", 0.3, 758.0, 796.0)
        self.assertEqual(result["status"], "DRY_RUN_NOT_SUBMITTED")

    def test_submission_blocked_when_not_explicitly_enabled(self):
        result = self.broker.submit_reviewed_candidate("SPY", 0.3, 758.0, 796.0, dry_run=False)
        self.assertEqual(result["status"], "BLOCKED_ORDER_SUBMISSION_DISABLED")

    def test_non_positive_quantity_is_refused(self):
        for quantity in (0, -1.5):
            with self.assertRaises(BrokerError):
                self.broker.submit_reviewed_candidate("SPY", quantity)

    def test_fractional_order_warns_that_the_stop_is_not_at_the_broker(self):
        result = self.broker.submit_reviewed_candidate("SPY", 0.298357, 758.0, 796.0)
        self.assertTrue(result["fractional"])
        self.assertNotIn("order_class", result["would_submit"])
        self.assertEqual(result["locally_managed_stop"], 758.0)
        self.assertTrue(any("bracket" in w for w in result["warnings"]))

    def test_whole_share_order_uses_a_server_side_bracket(self):
        result = self.broker.submit_reviewed_candidate("SPY", 3.0, 758.0, 796.0)
        self.assertFalse(result["fractional"])
        self.assertEqual(result["would_submit"]["order_class"], "bracket")
        self.assertEqual(result["would_submit"]["stop_loss"]["stop_price"], 758.0)
        self.assertEqual(result["would_submit"]["qty"], "3")


class CredentialTests(unittest.TestCase):
    def test_missing_credentials_raise_with_guidance(self):
        import os

        saved = {k: os.environ.pop(k, None) for k in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")}
        try:
            with self.assertRaises(BrokerError) as ctx:
                BrokerConfig.from_environment()
            self.assertIn("APCA_API_KEY_ID", str(ctx.exception))
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
