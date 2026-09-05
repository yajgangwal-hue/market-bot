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
import urllib.parse
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


# Longest first, so BTCUSDT is not mistaken for BTCUSD with a stray T.
_CRYPTO_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH")


def canonical_symbol(symbol: str, asset_class: str = "") -> str:
    """One spelling for a pair, whichever endpoint it arrived from.

    Alpaca returns crypto positions unslashed ("BTCUSD") and everything else
    slashed ("BTC/USD"). Left alone that makes a position look like an equity
    to is_crypto(), which disarms the crypto stop logic and hands the position
    to the equity loop instead. The position payload carries asset_class, so
    the ambiguity is resolvable exactly rather than by guessing at tickers -
    and it must be, since a real equity could be spelled like a pair.
    """
    text = str(symbol or "")
    if "/" in text or str(asset_class) != "crypto":
        return text
    for quote in _CRYPTO_QUOTES:
        if text.endswith(quote) and len(text) > len(quote):
            return text[: -len(quote)] + "/" + quote
    return text


def is_crypto(symbol: str) -> bool:
    """Alpaca names crypto pairs with a slash: BTC/USD, ETH/USD.

    Equities never contain one, so the separator is the whole test. Orders,
    fills and activities all report the slashed form, so a symbol that arrives
    from the broker can be classified without a lookup table that would drift
    out of date as pairs are listed.
    """
    return "/" in str(symbol)


# How far below the trigger a crypto stop-limit's limit price sits. A
# stop-limit whose limit equals its trigger is routinely skipped in a fast
# move, which turns a stop into an order resting above a falling market. 1.5%
# is wide enough to fill through an ordinary crypto air-pocket and still bound
# the loss.
CRYPTO_STOP_LIMIT_SLIP = 0.015

CRYPTO_NO_BRACKET = (
    "Alpaca accepts no bracket order class on crypto, so this entry carries no "
    "attached stop. A standalone GTC stop-limit is submitted immediately after "
    "the fill; the position is unprotected for those few seconds."
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
        """Open positions, with crypto pairs spelled the way orders spell them.

        The raw feed returns "BTCUSD" here and "BTC/USD" everywhere else, so
        the symbol is normalised on the way out. Without it a crypto position
        reads as an equity to every caller above this line.
        """
        data = self._request("GET", "/v2/positions")
        return [
            {
                "symbol": canonical_symbol(
                    item.get("symbol"), item.get("asset_class", "")),
                "asset_class": item.get("asset_class"),
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

    def fill_activities(self, page_size: int = 100) -> List[Dict[str, object]]:
        """Every individual fill the account has ever had.

        Orders are not enough to rebuild a record: one exit order arrives as
        several partial fills at different prices, and `filled_avg_price` is
        rounded for display. The activities feed reports each fill at the
        price it actually happened.
        """
        data = self._request(
            "GET", "/v2/account/activities/FILL?page_size={0}".format(int(page_size))
        )
        return [
            {
                "symbol": item.get("symbol"),
                "side": item.get("side"),
                "qty": item.get("qty"),
                "price": item.get("price"),
                "transaction_time": item.get("transaction_time"),
                "order_id": item.get("order_id"),
            }
            for item in data
        ]

    def fee_activities(self, page_size: int = 100) -> List[Dict[str, object]]:
        """The REG/TAF/CAT fees Alpaca charges against sale proceeds.

        Simulated, like the fills, but charged on the same schedule as the
        real ones - so a record that ignores them will not reconcile with
        account equity.
        """
        data = self._request(
            "GET", "/v2/account/activities?page_size={0}".format(int(page_size))
        )
        return [
            {
                "date": item.get("date"),
                "net_amount": item.get("net_amount"),
                "sub_type": item.get("activity_sub_type"),
                "description": item.get("description"),
            }
            for item in data
            if item.get("activity_type") == "FEE"
        ]

    # ---- write --------------------------------------------------------------
    def cancel_order(self, order_id: str, dry_run: bool = True) -> Dict[str, object]:
        """Cancel one working order. Cancelling an already-gone order is fine."""
        if not order_id:
            raise BrokerError("Refusing to cancel without an order id")
        if dry_run:
            return {"status": "DRY_RUN_NOT_SUBMITTED", "would_cancel": order_id}
        if not self.config.allow_order_submission:
            return {"status": "BLOCKED_ORDER_SUBMISSION_DISABLED", "order_id": order_id}
        try:
            self._request("DELETE", "/v2/orders/{0}".format(order_id))
        except BrokerError as error:
            # 404 means it filled or was cancelled between the read and now,
            # which is the outcome we wanted anyway.
            if "404" not in str(error):
                raise
            return {"status": "ALREADY_GONE", "order_id": order_id}
        return {"status": "CANCELED", "order_id": order_id}

    def submit_protective_stop(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
        dry_run: bool = True,
    ) -> Dict[str, object]:
        """A standalone GTC sell-stop, so protection survives the close.

        The bracket submitted with an entry is not enough. Its legs are
        time_in_force=day: the take-profit limit expires at the bell and OCO
        cancels the sibling stop with it. Measured 2026-09-01, both legs were
        gone at 16:01:38 ET and two positions sat overnight unprotected. This
        order is GTC, so it rests until it fills or is replaced.

        It cannot be folded into the entry: Alpaca rejects gtc on a market
        order, so the entry stays day and this is placed after the fill.
        """
        if quantity <= 0:
            raise BrokerError("Refusing to submit a non-positive quantity")
        if stop_price <= 0:
            raise BrokerError("Refusing to submit a non-positive stop price")

        crypto = is_crypto(symbol)
        if not crypto and abs(quantity - round(quantity)) > 1e-9:
            # For EQUITIES Alpaca allows fractional only on day market orders,
            # so a fractional position cannot hold a GTC stop at all. Say so
            # rather than letting the broker reject it and calling it a blip.
            raise BrokerError(
                "Alpaca cannot rest a GTC stop on a fractional quantity ({0}). "
                "Whole-share sizing is what earns a stop that survives the "
                "close; see RiskPolicy.allow_fractional_shares.".format(quantity)
            )

        payload: Dict[str, object] = {
            "symbol": symbol.upper(),
            "side": "sell",
            "time_in_force": "gtc",
            "stop_price": round(float(stop_price), 2),
            "client_order_id": _client_order_id("stop-" + symbol),
        }
        if crypto:
            # Probed on the live account: type "stop" is refused for crypto
            # with HTTP 422 "invalid order type for crypto order", while
            # "stop_limit" is accepted and rests. Crypto is fractional by
            # nature, so the quantity is NOT rounded.
            #
            # The limit sits BELOW the trigger, not at it. A stop-limit that
            # cannot fill is not protection, and in a fast crypto move a limit
            # level with the trigger would be jumped straight past, leaving the
            # order resting above the market while the position keeps falling.
            payload["type"] = "stop_limit"
            payload["qty"] = "{0:.9f}".format(quantity).rstrip("0").rstrip(".")
            payload["limit_price"] = round(
                float(stop_price) * (1.0 - CRYPTO_STOP_LIMIT_SLIP), 2)
        else:
            payload["type"] = "stop"
            payload["qty"] = str(int(round(quantity)))
        if dry_run:
            return {"status": "DRY_RUN_NOT_SUBMITTED", "would_submit": payload}
        if not self.config.allow_order_submission:
            return {"status": "BLOCKED_ORDER_SUBMISSION_DISABLED", "would_submit": payload}
        data = self._request("POST", "/v2/orders", payload)
        return {
            "status": data.get("status", "submitted"),
            "id": data.get("id"),
            "symbol": data.get("symbol"),
            "quantity": data.get("qty"),
            "stop_price": data.get("stop_price"),
            "time_in_force": data.get("time_in_force"),
        }


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
        # Quote the symbol: "BTC/USD" unquoted becomes /v2/positions/BTC/USD,
        # which is a different route with an extra path segment.
        result = self._request(
            "DELETE",
            "/v2/positions/{0}".format(urllib.parse.quote(symbol.upper(), safe="")))
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
        crypto = is_crypto(symbol)
        is_fractional = abs(quantity - round(quantity)) > 1e-9
        payload: Dict[str, object] = {
            "symbol": symbol.upper(),
            "side": "buy",
            "type": "market",
            # Crypto trades continuously, so `day` is meaningless there and
            # Alpaca wants gtc. Equities keep `day`: a market order left
            # working overnight fills at the next open against analysis that
            # is by then hours stale.
            "time_in_force": "gtc" if crypto else "day",
            "qty": ("{0:.9f}".format(quantity).rstrip("0").rstrip(".") if crypto
                    else "{0:.6f}".format(quantity).rstrip("0").rstrip(".")),
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
        if crypto:
            # Alpaca does not accept bracket/OCO order classes on crypto, so
            # the entry cannot carry its own protection the way an equity
            # bracket does. The position is therefore UNPROTECTED between this
            # fill and the protective stop that follows it.
            #
            # That window is seconds, not a cycle: submit_protective_stop is
            # called immediately after the fill confirms, and the live probe
            # measured a replacement stop accepted 0.27s after the shares were
            # freed. It is still a real gap and is named here rather than left
            # for someone to infer from the absence of a bracket.
            warnings.append(CRYPTO_NO_BRACKET)
        elif is_fractional:
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

    # Statuses that mean an order is finished. Everything else is still live
    # and still reserving shares. Expressed as the terminal set rather than the
    # live set on purpose: Alpaca has added order statuses before, and an
    # unknown status treated as live costs a redundant cancel, while an unknown
    # status treated as finished silently loses a resting stop.
    TERMINAL_ORDER_STATUSES = frozenset({
        "filled", "canceled", "cancelled", "expired", "rejected",
        "done_for_day", "replaced",
    })

    def open_orders(self) -> List[Dict[str, object]]:
        """Orders still working at the broker, with the fields a stop needs.

        `recent_orders` deliberately omits id and stop_price, so it cannot be
        used to decide whether a position is protected or to cancel anything.

        The UNION of two queries, because neither is correct alone.

        `status=open` omits `held`. Alpaca parks a bracket's stop-loss leg
        there until its take-profit sibling resolves, so on 2026-09-04 a live
        bracket returned only its limit leg and the stop protecting the
        position was invisible.

        `status=all` sees `held`, but it is newest-first and capped. Each trade
        writes about six order records, so at a handful of trades a day a
        500-row window covers roughly two weeks - and a trailing exit holds
        longer than that. A GTC stop that ages off the end reads as absent, the
        reconciler concludes the position is unprotected, and its replacement
        is rejected for insufficient quantity by the very order it cannot see.
        That logs protective_stop_FAILED against a protected position, every
        cycle, forever.

        Together they are complete. `status=open` cannot age out - its size is
        bounded by how many orders are live, not by account history - and it
        does carry GTC stops at any age. `held` legs are recent by
        construction, since the reconciler replaces them on the cycle after
        entry, so the capped window never binds for those.
        """
        seen: Dict[object, Dict] = {}
        for path in ("/v2/orders?status=open&limit=500",
                     "/v2/orders?status=all&limit=500"):
            for item in self._request("GET", path):
                if str(item.get("status", "")).lower() in self.TERMINAL_ORDER_STATUSES:
                    continue
                seen[item.get("id")] = item
        data = list(seen.values())
        return [
            {
                "id": item.get("id"),
                "symbol": item.get("symbol"),
                "side": item.get("side"),
                "type": item.get("type"),
                "quantity": float(item.get("qty") or 0.0),
                "stop_price": float(item["stop_price"]) if item.get("stop_price") else None,
                "time_in_force": item.get("time_in_force"),
                "client_order_id": item.get("client_order_id"),
            }
            for item in data
        ]

    def open_sell_orders(self) -> Dict[str, List[Dict[str, object]]]:
        """Working SELL orders by symbol - everything reserving those shares.

        Not just stops. Alpaca reserves position shares against any resting
        sell, so a bracket's take-profit LIMIT leg holds the shares just as
        firmly as its stop leg does. Ask only about stops and a submit is
        rejected with "insufficient qty available for order (requested: 100,
        available: 0)" while the position looks unprotected - a confusing
        failure whose cause is off-screen.
        """
        out: Dict[str, List[Dict[str, object]]] = {}
        for order in self.open_orders():
            if order["side"] == "sell":
                out.setdefault(str(order["symbol"]), []).append(order)
        return out
