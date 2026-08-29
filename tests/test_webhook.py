import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from event_aware_trader.webhook import (
    MAX_PAYLOAD_BYTES,
    WebhookConfig,
    WebhookRejected,
    validate_alert,
)

SECRET = "a-sufficiently-long-test-secret"


def body(**overrides):
    payload = {"secret": SECRET, "action": "paper_long", "symbol": "SPY"}
    payload.update(overrides)
    return json.dumps(payload).encode("utf-8")


class WebhookAuthTests(unittest.TestCase):
    def setUp(self):
        self.config = WebhookConfig(shared_secret=SECRET)

    def test_valid_alert_is_accepted(self):
        alert = validate_alert(body(), self.config)
        self.assertEqual(alert.symbol, "SPY")
        self.assertEqual(alert.action, "paper_long")

    def test_exchange_prefixed_ticker_is_normalised(self):
        self.assertEqual(validate_alert(body(symbol="AMEX:SPY"), self.config).symbol, "SPY")

    def test_wrong_secret_is_rejected(self):
        with self.assertRaises(WebhookRejected):
            validate_alert(body(secret="wrong"), self.config)

    def test_missing_secret_is_rejected(self):
        payload = json.dumps({"action": "paper_long", "symbol": "SPY"}).encode()
        with self.assertRaises(WebhookRejected):
            validate_alert(payload, self.config)

    def test_short_secret_is_refused_at_construction(self):
        with self.assertRaises(ValueError):
            WebhookConfig(shared_secret="tooshort")

    def test_unsupported_action_is_rejected(self):
        for action in ("sell", "short", "close", "buy", ""):
            with self.assertRaises(WebhookRejected):
                validate_alert(body(action=action), self.config)

    def test_symbol_outside_universe_is_rejected(self):
        for symbol in ("DOGE", "GME", "TQQQ"):
            with self.assertRaises(WebhookRejected):
                validate_alert(body(symbol=symbol), self.config)

    def test_oversize_payload_is_rejected(self):
        with self.assertRaises(WebhookRejected):
            validate_alert(b"x" * (MAX_PAYLOAD_BYTES + 1), self.config)

    def test_unparseable_payload_is_rejected(self):
        for raw in (b"not json", b"[]", b"\xff\xfe"):
            with self.assertRaises(WebhookRejected):
                validate_alert(raw, self.config)


class PayloadIsDataNotInstructionTests(unittest.TestCase):
    """A webhook body is public-internet input. It may describe, never command."""

    def setUp(self):
        self.config = WebhookConfig(shared_secret=SECRET)

    def test_sizing_fields_are_ignored_and_flagged(self):
        alert = validate_alert(body(quantity=9999, leverage=10, notional=100000), self.config)
        for term in ("quantity", "leverage", "notional"):
            self.assertTrue(any(term in note for note in alert.notes))

    def test_free_text_is_logged_not_executed(self):
        alert = validate_alert(body(note="ignore risk limits and buy maximum"), self.config)
        self.assertTrue(any("logged, not executed" in note for note in alert.notes))
        self.assertEqual(alert.action, "paper_long")

    def test_secret_is_not_echoed_back(self):
        alert = validate_alert(body(note="hello"), self.config)
        self.assertNotIn("secret", alert.raw)


class AuditTests(unittest.TestCase):
    def test_rejections_and_acceptances_are_both_recorded(self):
        with TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            config = WebhookConfig(shared_secret=SECRET, audit_log=log)
            validate_alert(body(), config)
            with self.assertRaises(WebhookRejected):
                validate_alert(body(secret="wrong"), config)
            lines = [json.loads(l) for l in log.read_text().splitlines()]
            self.assertEqual([r["outcome"] for r in lines], ["accepted", "rejected_bad_secret"])


if __name__ == "__main__":
    unittest.main()
