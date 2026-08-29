"""Receiver for TradingView alert webhooks.

TradingView cannot execute an order for you.  Its Broker REST API is
implemented *by brokers* so their customers can trade from a TradingView
chart; it is not offered to individuals and issues no API keys to them.  The
only outbound automation TradingView provides is an alert that POSTs JSON to
a URL you host.  So the real pipeline is:

    TradingView alert  ->  this receiver  ->  risk re-validation  ->  broker

The middle step is the point of this module.  A webhook endpoint is a public
URL: anything on the internet that learns it can POST to it, and TradingView
itself sends no signature.  A receiver that executes whatever arrives is a
hole through which an attacker - or a stale alert, or a duplicate retry - can
move real money.

So a payload is treated as **untrusted data, never as an instruction**:

* A shared secret must match, compared with `hmac.compare_digest`.
* The payload must parse into a known schema.  Unknown fields are ignored
  rather than forwarded.
* The symbol must be inside the configured universe.
* Any free-text field is logged, never executed.  A payload that says
  "ignore risk limits" or "size 100%" is data describing an attack, not a
  configuration change.
* The trade is re-derived locally from the bot's own rules and current market
  data.  The alert may say *when* to look; it never says how much to buy.
  Position size always comes from `position_size`, never from the payload.
* Submission still requires the broker's own two flags, so the default path
  ends in a dry run.
"""

import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .strategy import DEFAULT_UNIVERSE

MAX_PAYLOAD_BYTES = 4096
ALLOWED_ACTIONS = {"paper_long"}


class WebhookRejected(Exception):
    """Payload failed authentication or validation; nothing was acted on."""


@dataclass
class WebhookConfig:
    shared_secret: str
    universe: Sequence[str] = DEFAULT_UNIVERSE
    max_age_seconds: int = 300
    audit_log: Optional[Path] = None

    def __post_init__(self) -> None:
        if len(self.shared_secret) < 16:
            raise ValueError(
                "shared_secret must be at least 16 characters; a webhook URL is public"
            )


@dataclass
class ValidatedAlert:
    symbol: str
    action: str
    received_at: datetime
    raw: Dict[str, object] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


def _audit(config: WebhookConfig, outcome: str, detail: Dict[str, object]) -> None:
    if config.audit_log is None:
        return
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "detail": detail,
    }
    config.audit_log.parent.mkdir(parents=True, exist_ok=True)
    with config.audit_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def validate_alert(body: bytes, config: WebhookConfig) -> ValidatedAlert:
    """Authenticate and validate one webhook body. Raises WebhookRejected."""
    if len(body) > MAX_PAYLOAD_BYTES:
        _audit(config, "rejected_oversize", {"bytes": len(body)})
        raise WebhookRejected("Payload exceeds {0} bytes".format(MAX_PAYLOAD_BYTES))

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _audit(config, "rejected_unparseable", {"error": str(error)})
        raise WebhookRejected("Payload is not valid JSON") from error

    if not isinstance(payload, dict):
        _audit(config, "rejected_not_object", {})
        raise WebhookRejected("Payload must be a JSON object")

    supplied = str(payload.get("secret", ""))
    # compare_digest keeps the comparison constant-time against a guessing probe
    if not hmac.compare_digest(supplied, config.shared_secret):
        _audit(config, "rejected_bad_secret", {"symbol": payload.get("symbol")})
        raise WebhookRejected("Shared secret did not match")

    action = str(payload.get("action", "")).strip().lower()
    if action not in ALLOWED_ACTIONS:
        _audit(config, "rejected_action", {"action": action})
        raise WebhookRejected("Unsupported action: {0!r}".format(action))

    symbol = str(payload.get("symbol", "")).strip().upper()
    # TradingView tickers can arrive exchange-prefixed, e.g. AMEX:SPY
    if ":" in symbol:
        symbol = symbol.split(":")[-1]
    if symbol not in set(config.universe):
        _audit(config, "rejected_symbol", {"symbol": symbol})
        raise WebhookRejected("Symbol {0!r} is outside the configured universe".format(symbol))

    notes: List[str] = []
    for key in ("note", "comment", "message", "text"):
        if key in payload:
            notes.append("{0}={1!r} (logged, not executed)".format(key, str(payload[key])[:200]))
    for key in ("quantity", "qty", "size", "notional", "risk", "leverage", "stop", "target"):
        if key in payload:
            notes.append(
                "{0} present in payload and IGNORED; sizing is derived locally".format(key)
            )

    alert = ValidatedAlert(
        symbol=symbol,
        action=action,
        received_at=datetime.now(timezone.utc),
        raw={k: v for k, v in payload.items() if k != "secret"},
        notes=notes,
    )
    _audit(config, "accepted", {"symbol": symbol, "action": action, "notes": notes})
    return alert
