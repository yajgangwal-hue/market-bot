"""Offline broker double so the loop can be exercised without credentials."""
class FakeBroker:
    def __init__(self, equity=1000.0, positions=None, blocked=False):
        self._equity=equity; self._positions=positions or []; self._blocked=blocked
        self.submitted=[]; self.closed=[]
        class _C: endpoint="https://paper-api.alpaca.markets"; allow_order_submission=True
        self.config=_C()
    def account(self):
        return {"equity":self._equity,"cash":self._equity,"buying_power":self._equity,
                "trading_blocked":self._blocked,"status":"ACTIVE","account_number":"FAKE"}
    def positions(self): return list(self._positions)
    def recent_orders(self, limit=50): return []
    def submit_reviewed_candidate(self, symbol, quantity, stop=None, target=None, dry_run=True):
        self.submitted.append((symbol,quantity,stop,dry_run))
        return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "SUBMITTED_TO_PAPER_ACCOUNT"}
    def close_position(self, symbol, dry_run=True):
        self.closed.append((symbol,dry_run)); return {"status":"DRY_RUN_NOT_SUBMITTED" if dry_run else "CLOSE_SUBMITTED"}
