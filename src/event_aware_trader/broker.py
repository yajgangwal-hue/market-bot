"""Read-mostly adapter for a real Alpaca **paper** brokerage account.

Why this module exists
----------------------
Until now the project simulated an account balance with a Python float.  That
is fine for a backtest and useless for the question "would this actually have
filled?".  An Alpaca paper account is a real account at a real broker: real
symbols, real market data, real order types, real rejections, real settlement
rules - with simulated money.  It is the honest place to find out that an
order would have been rejected for a reason no backtest models.

What this module deliberately does not do
-----------------------------------------
* It never reads a credential from a file.  Both keys come from the
  environment, so a key cannot be committed by accident.
* It refuses to talk to the live endpoint at all.  ``_require_paper_endpoint``
  raises on any host that is not the paper host, so a typo in an environment
  variable cannot quietly route an order to real money.
* It submits nothing unless the caller passes ``allow_order_submission=True``
  *and* the individual call passes ``dry_run=False``.  Both default to the
  safe value.
* It has no strategy logic and cannot decide to trade.  It executes a plan a
  human has already reviewed.

Setup (the account and the keys are yours to create; this code never will):

1. Open a paper account at https://alpaca.markets and generate paper API keys.
2. Export them in the shell you run this from - never in a file:

       export APCA_API_KEY_ID=...
       export APCA_API_SECRET_KEY=...

3. Confirm the connection:

       event-aware-trader account
"""

import itertools
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
LIVE_ENDPOINT = "https://api.alpaca.markets"

# Alpaca supports fractional quantities only for market and limit DAY orders.
# A bracket (entry plus stop plus target as one server-side order) requires a
# whole share count.  Pretending otherwise would produce an order the API
# rejects, so the split is made explicit here rather than discovered in a log.
FRACTIONAL_ORDER_LIMITATION = (
    "Alpaca does not accept a bracket order for a fractional quantity. The entry is "
    "submitted as a plain market order and the stop and target are returned for local "
    "management; they are NOT resting at the broker."
)


class BrokerError(RuntimeError):
    """Raised for a configuration, credential, or endpoint safety failure."""


@dataclass(frozen=True)
class BrokerConfig:
    key_id: str
    secret_key: str
    endpoint: str = PAPER_ENDPOINT
    timeout_seconds: int = 15
    allow_order_submission: bool = False

    @classmethod
    def from_environment(cls, allow_order_submission: bool = False) -> "BrokerConfig":
        key_id = os.environ.get("APCA_API_KEY_ID", "").strip()
        secret_key = os.environ.get("APCA_API_SECRET_KEY", "").strip()
        if not key_id or not secret_key:
            raise BrokerError(
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your shell. "
                "Generate paper keys at https://alpaca.markets; do not put them in a file."
            )
        endpoint = os.environ.get("APCA_API_BASE_URL", PAPER_ENDPOINT).strip().rstrip("/")
        return cls(
            key_id=key_id,
            secret_key=secret_key,
            endpoint=endpoint,
            allow_order_submission=allow_order_submission,
        )


def _require_paper_endpoint(endpoint: str) -> None:
    """Refuse to operate against anything but the paper host."""
    normalised = endpoint.strip().rstrip("/").lower()
    if normalised == LIVE_ENDPOINT:
        raise BrokerError(
            "Refusing to run against the live trading endpoint. This project is paper-only; "
            "unset APCA_API_BASE_URL or point it at {0}.".format(PAPER_ENDPOINT)
        )
    if normalised != PAPER_ENDPOINT:
        raise BrokerError(
            "Unrecognised endpoint {0!r}. Only the Alpaca paper endpoint {1} is allowed.".format(
                endpoint, PAPER_ENDPOINT
            )
        )


_ORDER_SEQUENCE = itertools.count()


def _client_order_id(symbol: str) -> str:
    """Stable, unique, and obviously ours. Kept short and [A-Za-z0-9-] only.

    The timestamp alone is not unique. At microsecond resolution two calls in
    the same loop collided 2 times in 50 on this machine, and Alpaca rejects a
    duplicate client_order_id - which would drop a real order. The counter
    makes it exact within a process; across processes the microsecond stamp
    separates them, and cycles are minutes apart.
    """
    from datetime import datetime, timezone
    stamp = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
    clean = "".join(c for c in symbol.upper() if c.isalnum())
    return "eat-{0}-{1}-{2}".format(clean, stamp, next(_ORDER_SEQUENCE))


class AlpacaPaperBroker:
    """Minimal stdlib client for the Alpaca paper API."""

    def __init__(self, config: Optional[BrokerConfig] = None) -> None:
        self.config = config or BrokerConfig.from_environment()
        _require_paper_endpoint(self.config.endpoint)

    # ---- transport ---------------------------------------------------------
    def _request(self, method: str, path: str, payload: Optional[Dict] = None) -> Dict:
        url = "{0}{1}".format(self.config.endpoint, path)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("APCA-API-KEY-ID", self.config.key_id)
        request.add_header("APCA-API-SECRET-KEY", self.config.secret_key)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            if error.code in (401, 403):
                raise BrokerError(
                    "Alpaca rejected the credentials ({0}). Check that these are *paper* keys.".format(error.code)
                ) from error
            raise BrokerError("Alpaca returned HTTP {0}: {1}".format(error.code, detail)) from error
        except urllib.error.URLError as error:
            raise BrokerError("Could not reach Alpaca: {0}".format(error.reason)) from error
        return json.loads(raw) if raw.strip() else {}

    # ---- read ---------------------------------------------------------------
    def account(self) -> Dict[str, object]:
        data = self._request("GET", "/v2/account")
        equity = float(data.get("equity", 0.0))
        return {
            "account_number": data.get("account_number"),
            "status": data.get("status"),
            "equity": equity,
            "cash": float(data.get("cash", 0.0)),
            "buying_power": float(data.get("buying_power", 0.0)),
            "pattern_day_trader": bool(data.get("pattern_day_trader", False)),
            "daytrade_count": data.get("daytrade_count"),
            "trading_blocked": bool(data.get("trading_blocked", False)),
            "fractionable_supported": True,
            "endpoint": self.config.endpoint,
            "note": "Alpaca paper account. Balances are simulated; market data and rules are real.",
        }

    def clock(self) -> Dict[str, object]:
        """Alpaca's own market clock.

        Authoritative in a way a local timestamp is not: it knows holidays,
        half-days, and early closes, none of which a launchd calendar entry
        does.
        """
        data = self._request("GET", "/v2/clock")
        return {
            "is_open": bool(data.get("is_open", False)),
            "timestamp": data.get("timestamp"),
            "next_open": data.get("next_open"),
            "next_close": data.get("next_close"),
        }

    def positions(self) -> List[Dict[str, object]]:
        data = self._request("GET", "/v2/positions")
        return [
            {
                "symbol": item.get("symbol"),
                "quantity": float(item.get("qty", 0.0)),
                "average_entry_price": float(item.get("avg_entry_price", 0.0)),
                "market_value": float(item.get("market_value", 0.0)),
                "unrealized_pnl": float(item.get("unrealized_pl", 0.0)),
            }
            for item in data
        ]

    def recent_orders(self, limit: int = 50) -> List[Dict[str, object]]:
        data = self._request("GET", "/v2/orders?status=all&limit={0}".format(int(limit)))
        return [
            {
                "symbol": item.get("symbol"),
                "side": item.get("side"),
                "quantity": item.get("qty"),
                "filled_quantity": item.get("filled_qty"),
                "filled_avg_price": item.get("filled_avg_price"),
                "status": item.get("status"),
                "submitted_at": item.get("submitted_at"),
                "order_class": item.get("order_class"),
            }
            for item in data
        ]

    # ---- write --------------------------------------------------------------
    def close_position(self, symbol: str, dry_run: bool = True) -> Dict[str, object]:
        """Flatten one position at market.

        Closing is the risk-*reducing* direction, so it is not gated on the
        same two flags as opening: a stop that will not fire because a config
        flag was left unset is worse than one that fires unexpectedly. It
        still honours dry_run so a scheduled run can be rehearsed.
        """
        preview: Dict[str, object] = {
            "would_close": symbol.upper(),
            "endpoint": self.config.endpoint,
        }
        if dry_run:
            preview["status"] = "DRY_RUN_NOT_SUBMITTED"
            return preview
        result = self._request("DELETE", "/v2/positions/{0}".format(symbol.upper()))
        preview["status"] = "CLOSE_SUBMITTED"
        preview["order_id"] = result.get("id")
        return preview

    def submit_reviewed_candidate(
        self,
        symbol: str,
        quantity: float,
        stop: Optional[float] = None,
        target: Optional[float] = None,
        dry_run: bool = True,
    ) -> Dict[str, object]:
        """Submit a human-reviewed plan. Both safety flags must be cleared.

        ``dry_run`` stays True unless the caller sets it False, and the config
        must additionally have been built with ``allow_order_submission=True``.
        """
        if quantity <= 0:
            raise BrokerError("Refusing to submit a non-positive quantity")
        is_fractional = abs(quantity - round(quantity)) > 1e-9
        payload: Dict[str, object] = {
            "symbol": symbol.upper(),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "qty": "{0:.6f}".format(quantity).rstrip("0").rstrip("."),
            # Tag every order as ours. Alpaca surfaces this id, and so does
            # anything reading the same account - TradingView's trading panel
            # included - which is what makes a bot fill distinguishable from
            # one placed by hand in the same paper account.
            #
            # Microseconds, not seconds: Alpaca rejects a duplicate
            # client_order_id, and two symbols submitted in the same cycle
            # land inside the same second.
            "client_order_id": _client_order_id(symbol),
        }
        warnings: List[str] = []
        if is_fractional:
            warnings.append(FRACTIONAL_ORDER_LIMITATION)
        elif stop is not None and target is not None:
            payload["order_class"] = "bracket"
            payload["stop_loss"] = {"stop_price": round(stop, 2)}
            payload["take_profit"] = {"limit_price": round(target, 2)}

        preview = {
            "would_submit": payload,
            "endpoint": self.config.endpoint,
            "fractional": is_fractional,
            "locally_managed_stop": stop if is_fractional else None,
            "locally_managed_target": target if is_fractional else None,
            "warnings": warnings,
        }
        if dry_run:
            preview["status"] = "DRY_RUN_NOT_SUBMITTED"
            return preview
        if not self.config.allow_order_submission:
            preview["status"] = "BLOCKED_ORDER_SUBMISSION_DISABLED"
            preview["reason"] = (
                "Order submission is disabled. Rebuild the config with "
                "allow_order_submission=True only after reviewing the plan."
            )
            return preview
        result = self._request("POST", "/v2/orders", payload)
        preview["status"] = "SUBMITTED_TO_PAPER_ACCOUNT"
        preview["order_id"] = result.get("id")
        preview["order_status"] = result.get("status")
        return preview
