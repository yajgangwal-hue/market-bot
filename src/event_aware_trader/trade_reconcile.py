"""Rebuild a completed trade from the broker's own fills.

WHY THIS EXISTS. The learning loop records a training example at the moment
the bot's own rule closes a position. That covers one of the four ways a
position actually ends:

  1. the rule closes it            -> recorded (autotrade.run_once)
  2. its resting GTC stop fires    -> NOT recorded before 2026-09-14
  3. a tool closes it              -> NOT recorded (scripts/exit_at_peak.py)
  4. the owner closes it by hand   -> NOT recorded

Two, three and four all end the same way from the loop's point of view: next
cycle the symbol is simply not in `broker.positions()` any more, the branch
that would have appended an example never runs, and the entry features sit
in the state file forever. On 2026-09-14 four trades - TJX, VNQ (by hand),
RTX, LIN (by the peak-exit tool) - closed and the learner was told about
none of them.

The bias that creates is the dangerous part. Path 2 is the STOP, which in
thirty years of simulation is 35% of all trades and carries every one of the
large losses. A learner fed only paths 1 and 3 is trained on a record with
its worst outcomes deleted, and would conclude the strategy loses less than
it does.

This module rebuilds those trades from the fills feed - the broker's own
record of what happened at what price - so a trade teaches the model the
same thing however it ended. It is pure: no broker, no files, no clock.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# Quantities are floats (crypto is fractional), so "flat" needs a tolerance
# rather than == 0. Well below one share of anything.
FLAT = 1e-9


@dataclass
class RoundTrip:
    """One completed buy-to-flat cycle, at the prices that actually filled."""
    symbol: str
    quantity: float
    entry_price: float          # volume-weighted over every buy fill
    exit_price: float           # volume-weighted over every sell fill
    closed_at: Optional[str]    # transaction_time of the fill that went flat
    fills: int = 0

    @property
    def realized(self) -> float:
        return (self.exit_price - self.entry_price) * self.quantity

    @property
    def return_fraction(self) -> float:
        return (self.exit_price / self.entry_price - 1.0) if self.entry_price > 0 else 0.0


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def latest_round_trip(fills: Sequence[Dict], symbol: str) -> Optional[RoundTrip]:
    """The most recent completed buy-to-flat cycle for `symbol`.

    Walks the symbol's fills oldest-first, carrying a running position. A trip
    completes when that position returns to flat, which is what makes this
    correct for the two cases a simpler reading gets wrong: an exit that
    arrives as several partial fills at different prices, and a symbol the
    strategy has entered and exited more than once. Only the LAST completed
    trip is returned - earlier ones were already recorded when they happened.

    Returns None when the symbol never went flat inside the window given,
    which is the honest answer: the fills feed is paginated and an entry old
    enough to fall outside it cannot be rebuilt from this alone.
    """
    wanted = symbol.upper()
    mine = [f for f in fills if str(f.get("symbol", "")).upper() == wanted]
    mine.sort(key=lambda f: str(f.get("transaction_time") or ""))

    position = 0.0
    buy_qty = buy_cost = sell_qty = sell_proceeds = 0.0
    count = 0
    completed: Optional[RoundTrip] = None

    for fill in mine:
        side = str(fill.get("side") or "").lower()
        qty = abs(_number(fill.get("qty")))
        price = _number(fill.get("price"))
        if qty <= 0 or price <= 0:
            continue
        count += 1
        if side.startswith("buy"):
            # A buy while flat starts a new trip; anything accumulated before
            # it belonged to a trip that never closed and is discarded.
            if position <= FLAT and sell_qty <= FLAT:
                buy_qty = buy_cost = 0.0
                count = 1
            position += qty
            buy_qty += qty
            buy_cost += qty * price
        elif side.startswith("sell"):
            position -= qty
            sell_qty += qty
            sell_proceeds += qty * price
            if position <= FLAT and buy_qty > 0 and sell_qty > 0:
                completed = RoundTrip(
                    symbol=wanted, quantity=sell_qty,
                    entry_price=buy_cost / buy_qty,
                    exit_price=sell_proceeds / sell_qty,
                    closed_at=fill.get("transaction_time"), fills=count)
                position = 0.0
                buy_qty = buy_cost = sell_qty = sell_proceeds = 0.0
                count = 0
    return completed


def r_multiple(entry_price: float, exit_price: float,
               initial_stop: float) -> Optional[float]:
    """Outcome in units of the risk taken, the label the model trains on.

    None when the risk per share is not positive - a stop at or above the
    entry. Dividing by it would produce an enormous or sign-flipped R and
    teach the model something that did not happen, so the trade is skipped
    and said to be skipped rather than recorded with a fabricated label.
    """
    risk_per_share = entry_price - initial_stop
    if risk_per_share <= 0 or entry_price <= 0:
        return None
    return (exit_price - entry_price) / risk_per_share


def orphaned_symbols(open_features: Dict[str, Dict],
                     held: Sequence[str]) -> List[str]:
    """Symbols carrying entry features with no position behind them any more."""
    current = {str(s).upper() for s in held}
    return sorted(s for s in open_features if str(s).upper() not in current)
