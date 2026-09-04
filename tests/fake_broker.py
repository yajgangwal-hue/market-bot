"""Offline broker double so the loop can be exercised without credentials."""
class FakeBroker:
    def __init__(self, equity=1000.0, positions=None, blocked=False, market_open=True,
                 fail_times=0):
        self._equity=equity; self._positions=positions or []; self._blocked=blocked
        self._market_open=market_open
        self._fail_times=fail_times      # transient failures before succeeding
        self.calls=0
        self.submitted=[]; self.closed=[]
        class _C: endpoint="https://paper-api.alpaca.markets"; allow_order_submission=True
        self.config=_C()
    def clock(self):
        return {"is_open": self._market_open, "timestamp": "2026-09-01T14:00:00Z",
                "next_open": "2026-09-02T13:30:00Z", "next_close": "2026-09-01T20:00:00Z"}
    def account(self):
        self.calls += 1
        if self.calls <= self._fail_times:
            from event_aware_trader.broker import BrokerError
            raise BrokerError("transient upstream error (500)")
        return {"equity":self._equity,"cash":self._equity,"buying_power":self._equity,
                "trading_blocked":self._blocked,"status":"ACTIVE","account_number":"FAKE"}
    def positions(self): return list(self._positions)
    def recent_orders(self, limit=50): return []
    def submit_reviewed_candidate(self, symbol, quantity, stop=None, target=None, dry_run=True):
        self.submitted.append((symbol,quantity,stop,dry_run))
        return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "SUBMITTED_TO_PAPER_ACCOUNT"}
    def close_position(self, symbol, dry_run=True):
        self.closed.append((symbol,dry_run)); return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "CLOSE_SUBMITTED"}

    # ---- protective-stop surface -------------------------------------------
    # `events` records the ORDER of operations, because cancel-before-submit is
    # a correctness property here, not a style choice: the shares stay reserved
    # until the cancel lands, so a submit that runs first is rejected.
    def _init_stops(self):
        if not hasattr(self, "open_sells"):
            self.open_sells = {}      # symbol -> [order dicts]
            self.canceled = []
            self.protective = []
            self.events = []
            self.protect_error = None

    def open_sell_orders(self):
        self._init_stops()
        return {s: list(v) for s, v in self.open_sells.items() if v}

    def cancel_order(self, order_id, dry_run=True):
        self._init_stops()
        self.canceled.append(order_id)
        self.events.append(("cancel", order_id))
        for symbol, orders in self.open_sells.items():
            self.open_sells[symbol] = [o for o in orders if o["id"] != order_id]
        return {"status": "DRY_RUN_NOT_SUBMITTED" if dry_run else "CANCELED"}

    def submit_protective_stop(self, symbol, quantity, stop_price, dry_run=True):
        self._init_stops()
        self.events.append(("submit", symbol))
        if self.protect_error:
            from event_aware_trader.broker import BrokerError
            raise BrokerError(self.protect_error)
        # Mirror Alpaca: any resting sell reserves the shares.
        if self.open_sells.get(symbol):
            from event_aware_trader.broker import BrokerError
            raise BrokerError(
                "insufficient qty available for order (requested: {0}, available: 0)".format(quantity))
        self.protective.append((symbol, quantity, stop_price, dry_run))
        self.open_sells.setdefault(symbol, []).append({
            "id": "gtc-" + symbol, "symbol": symbol, "side": "sell", "type": "stop",
            "quantity": quantity, "stop_price": stop_price, "time_in_force": "gtc",
            "client_order_id": "eat-stop-" + symbol,
        })
        return {"status": "DRY_RUN_NOT_SUBMITTED" if dry_run else "accepted"}
