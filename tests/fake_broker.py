"""Offline broker double so the loop can be exercised without credentials."""
class FakeBroker:
    def __init__(self, equity=1000.0, positions=None, blocked=False, market_open=True,
                 fail_times=0, cash=None):
        # Cash and equity are SEPARATE, because on a real account they are and
        # the difference is what several behaviours turn on. The double
        # returned one number for both until 2026-09-10, which made it
        # impossible to express the ordinary case of a mostly-invested account
        # - six positions and $702.87 of cash against $99,523 of equity - and
        # so impossible to test anything that depends on it.
        self._equity=equity; self._cash=equity if cash is None else cash
        self._positions=positions or []; self._blocked=blocked
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
        return {"equity":self._equity,"cash":self._cash,"buying_power":self._equity,
                "trading_blocked":self._blocked,"status":"ACTIVE","account_number":"FAKE"}
    def positions(self): return list(self._positions)
    def recent_orders(self, limit=50): return []

    # The fills feed. Real: every individual fill the account has had, which
    # is how a trade closed by its own stop - or by hand - is rebuilt into a
    # training example. Empty is the honest default (a fresh account has no
    # fills); a test that exercises reconstruction sets `fills` explicitly.
    #
    # It is here rather than on one test's local double because the double
    # must offer the same surface as the real broker. When this method was
    # missing, adding the reconciler to run_once broke three unrelated tests
    # with AttributeError - the double silently not matching the thing it
    # stands in for is the same defect class as the dry-run cancel above.
    def fill_activities(self, page_size=100):
        return list(getattr(self, "fills", []))
    def submit_reviewed_candidate(self, symbol, quantity, stop=None, target=None, dry_run=True):
        self.submitted.append((symbol,quantity,stop,dry_run))
        return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "SUBMITTED_TO_PAPER_ACCOUNT"}
    def close_position(self, symbol, dry_run=True):
        # Mirrors Alpaca: a resting sell order reserves the whole position, so
        # closing it while the protective stop is live is refused outright.
        #   HTTP 403 {"available":"0","held_for_orders":"106",
        #             "message":"insufficient qty available for order"}
        # Without this the double accepted a close the real broker rejects,
        # and the exit path shipped unable to close a protected position.
        self._init_stops()
        if not dry_run and self.open_sells.get(symbol):
            from event_aware_trader.broker import BrokerError
            raise BrokerError(
                "Alpaca returned HTTP 403 for DELETE /v2/positions/{0}. Its "
                "response: insufficient qty available for order".format(symbol))
        self.events.append(("close", symbol))
        self.closed.append((symbol,dry_run)); return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "CLOSE_SUBMITTED"}

    # ---- cash parking -------------------------------------------------------
    def submit_notional_buy(self, symbol, notional, dry_run=True):
        from event_aware_trader.broker import BrokerError
        if notional <= 0:
            raise BrokerError("Refusing to park a non-positive amount")
        self._init_stops()
        self.parked_buys.append((symbol, notional, dry_run))
        self.events.append(("park", symbol))
        return {"status": "DRY_RUN_NOT_SUBMITTED" if dry_run
                else "SUBMITTED_TO_PAPER_ACCOUNT"}

    def submit_sell(self, symbol, quantity, dry_run=True):
        from event_aware_trader.broker import BrokerError
        if quantity <= 0:
            raise BrokerError("Refusing to sell a non-positive quantity")
        self._init_stops()
        self.parked_sells.append((symbol, quantity, dry_run))
        self.events.append(("unpark", symbol))
        return {"status": "DRY_RUN_NOT_SUBMITTED" if dry_run
                else "SUBMITTED_TO_PAPER_ACCOUNT"}

    # ---- protective-stop surface -------------------------------------------
    # `events` records the ORDER of operations, because cancel-before-submit is
    # a correctness property here, not a style choice: the shares stay reserved
    # until the cancel lands, so a submit that runs first is rejected.
    def _init_stops(self):
        if not hasattr(self, "open_sells"):
            self.open_sells = {}      # symbol -> [order dicts]
            self.canceled = []
            self.protective = []
            self.parked_buys = []
            self.parked_sells = []
            self.events = []
            self.protect_error = None

    def open_sell_orders(self):
        self._init_stops()
        return {s: list(v) for s, v in self.open_sells.items() if v}

    def cancel_order(self, order_id, dry_run=True):
        # A DRY RUN MUST NOT FREE THE SHARES. The real broker returns
        # DRY_RUN_NOT_SUBMITTED and leaves the order resting; this double used
        # to remove it from open_sells either way and only vary the status
        # string. That made every cancel-then-close test pass against code
        # that cannot work live - the exit path called cancel_order() without
        # passing the flag, so it cancelled as a dry run, the shares stayed
        # reserved, and Alpaca refused the close with 403. Exactly the defect
        # class that let fractional protective stops ship.
        self._init_stops()
        self.canceled.append(order_id)
        self.events.append(("cancel", order_id))
        if dry_run:
            return {"status": "DRY_RUN_NOT_SUBMITTED", "would_cancel": order_id}
        for symbol, orders in self.open_sells.items():
            self.open_sells[symbol] = [o for o in orders if o["id"] != order_id]
        return {"status": "CANCELED", "order_id": order_id}

    def submit_protective_stop(self, symbol, quantity, stop_price, dry_run=True):
        self._init_stops()
        self.events.append(("submit", symbol))
        if self.protect_error:
            from event_aware_trader.broker import BrokerError
            raise BrokerError(self.protect_error)
        # Mirror Alpaca: a GTC stop cannot rest on a fractional quantity.
        # Without this the double accepted the 76.5-share order the real
        # broker refused all session on 2026-09-08, and the ordering bug that
        # produced it shipped untested. Crypto is exempt at the real broker
        # (stop_limit rests on a fraction) and no crypto test uses this path.
        if float(quantity) != int(quantity):
            from event_aware_trader.broker import BrokerError
            raise BrokerError(
                "Alpaca cannot rest a GTC stop on a fractional quantity "
                "({0}).".format(quantity))
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
