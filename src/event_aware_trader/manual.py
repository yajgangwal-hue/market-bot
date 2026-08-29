"""Position book and daily brief for trading the rules by hand.

When the account lives in a broker you operate through TradingView, the bot
cannot see what you hold.  That has one awkward consequence: the trailing stop
is not a resting order the machine maintains, it is a number **you** have to
move.  Get that wrong for a week and the exit rule that made trailing worth
using is simply not running.

So this module keeps a small local record of what you entered, and turns it
into a short morning instruction list:

* which stops moved, and to exactly what price
* which positions the rules say are already out
* whether a new entry qualifies, with the exact share count for your equity

The book is a plain JSON file you can read and correct.  It is a *record of
what you did*, not an order system: nothing here contacts a broker, and a
position appears only because you added it after filling it yourself.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .indicators import wilder_atr
from .risk import CostModel, RiskPolicy, position_size
from .strategy import CORRELATION_BUCKETS, StrategyConfig, generate_candidate
from .types import Action, Bar, Event


@dataclass
class HeldPosition:
    """One position you actually filled, as you recorded it."""

    symbol: str
    quantity: float
    entry_price: float
    entry_date: str
    initial_stop: float
    current_stop: float
    highest_high: float = 0.0
    trailing_armed: bool = False
    note: str = ""

    @property
    def bucket(self) -> str:
        return CORRELATION_BUCKETS.get(self.symbol.upper(), "other")

    def risk_per_share(self) -> float:
        return self.entry_price - self.initial_stop


def load_positions(path: Path) -> List[HeldPosition]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("positions", []) if isinstance(raw, dict) else raw
    return [HeldPosition(**item) for item in entries]


def save_positions(path: Path, positions: Sequence[HeldPosition]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Manual record of filled positions. This file places no orders.",
        "positions": [asdict(p) for p in positions],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def advance_stop(
    position: HeldPosition,
    bars: Sequence[Bar],
    config: StrategyConfig = StrategyConfig(),
) -> Dict[str, object]:
    """Recompute the trailing stop from the bars seen since entry.

    Mirrors the ratchet in ``portfolio.py``: the original stop holds until the
    trade has earned ``trail_activate_r``, then the stop follows the running
    high and never loosens.
    """
    entry_date = position.entry_date[:10]
    since = [b for b in bars if b.timestamp.date().isoformat() >= entry_date]
    if not since:
        return {"symbol": position.symbol, "action": "no_data", "stop": position.current_stop}

    highest = max(position.highest_high, max(b.high for b in since))
    risk = position.risk_per_share()
    armed = position.trailing_armed
    if risk > 0 and (highest - position.entry_price) / risk >= config.trail_activate_r:
        armed = True

    proposed = position.current_stop
    if armed:
        atr = wilder_atr(bars, config.atr_days)
        if atr:
            proposed = max(position.current_stop, highest - config.trail_atr_multiple * atr)

    last = bars[-1]
    stop_breached = last.low <= proposed
    moved = proposed > position.current_stop + 1e-9

    result = {
        "symbol": position.symbol,
        "last_close": round(last.close, 2),
        "entry_price": round(position.entry_price, 2),
        "quantity": position.quantity,
        "market_value": round(position.quantity * last.close, 2),
        "unrealized": round((last.close - position.entry_price) * position.quantity, 2),
        "open_r": round((last.close - position.entry_price) / risk, 2) if risk > 0 else None,
        "previous_stop": round(position.current_stop, 2),
        "new_stop": round(proposed, 2),
        "trailing_armed": armed,
        "highest_high": round(highest, 2),
    }
    if stop_breached:
        result["action"] = "EXIT"
        result["instruction"] = (
            "SELL {0} {1} at market. The low ({2:.2f}) has traded through the stop "
            "({3:.2f}); the rule says this position is out."
        ).format(position.quantity, position.symbol, last.low, proposed)
    elif moved:
        result["action"] = "RAISE_STOP"
        result["instruction"] = "Move the {0} stop up from {1:.2f} to {2:.2f}.".format(
            position.symbol, position.current_stop, proposed
        )
    else:
        result["action"] = "HOLD"
        result["instruction"] = "Hold {0}. Stop stays at {1:.2f}.".format(
            position.symbol, position.current_stop
        )
    return result


def apply_stop_update(position: HeldPosition, update: Dict[str, object]) -> HeldPosition:
    """Fold a computed update back into the stored record."""
    position.current_stop = float(update.get("new_stop", position.current_stop))
    position.highest_high = float(update.get("highest_high", position.highest_high))
    position.trailing_armed = bool(update.get("trailing_armed", position.trailing_armed))
    return position


def daily_brief(
    series: Dict[str, List[Bar]],
    positions: Sequence[HeldPosition],
    equity: float,
    events: Sequence[Event] = (),
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
) -> Dict[str, object]:
    """Everything to do before the next open, in the order to do it."""
    held = {p.symbol.upper(): p for p in positions}
    open_buckets = {p.bucket for p in positions}

    manage: List[Dict[str, object]] = []
    invested = 0.0
    for position in positions:
        bars = series.get(position.symbol.upper())
        if not bars:
            manage.append({"symbol": position.symbol, "action": "no_data"})
            continue
        update = advance_stop(position, bars, config)
        manage.append(update)
        invested += float(update.get("market_value", 0.0) or 0.0)

    exiting = {u["symbol"] for u in manage if u.get("action") == "EXIT"}
    slots_used = len(positions) - len(exiting)

    new_candidates: List[Dict[str, object]] = []
    considered = 0
    for symbol, bars in sorted(series.items()):
        if symbol in held or len(bars) < config.minimum_history:
            continue
        considered += 1
        if slots_used >= policy.max_open_positions:
            continue
        candidate = generate_candidate(
            symbol, bars, events, equity, policy, costs, config,
            open_positions=slots_used, open_buckets=open_buckets,
        )
        if candidate.action != Action.PAPER_LONG:
            continue
        if candidate.entry is None or candidate.stop is None:
            continue
        quantity, planned_risk = position_size(equity, candidate.entry, candidate.stop, policy, costs)
        if quantity <= 0:
            continue
        new_candidates.append({
            "symbol": symbol,
            "score": round(candidate.score, 1),
            "reference_close": round(candidate.entry, 2),
            "initial_stop": round(candidate.stop, 2),
            "suggested_quantity": quantity,
            "approximate_notional": round(quantity * candidate.entry, 2),
            "planned_risk": round(planned_risk, 2),
            "correlation_bucket": candidate.correlation_bucket,
            "instruction": (
                "REVIEW, then if you agree: BUY {0:.6f} {1} at the open (~${2:.2f}), "
                "and place a stop at {3:.2f}. Risk if stopped: ${4:.2f}."
            ).format(quantity, symbol, quantity * candidate.entry, candidate.stop, planned_risk),
        })
    new_candidates.sort(key=lambda c: c["score"], reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "equity_used_for_sizing": round(equity, 2),
        "estimated_invested": round(invested, 2),
        "open_position_count": len(positions),
        "position_slots_free": max(0, policy.max_open_positions - slots_used),
        "manage_existing": manage,
        "new_candidates": new_candidates,
        "symbols_considered": considered,
        "summary": _summarise(manage, new_candidates),
        "note": (
            "Nothing here places an order. Every line is a suggestion to review "
            "before you act on it in your own broker."
        ),
    }


def _summarise(manage: Sequence[Dict[str, object]], new: Sequence[Dict[str, object]]) -> str:
    exits = [m["symbol"] for m in manage if m.get("action") == "EXIT"]
    raises = [m["symbol"] for m in manage if m.get("action") == "RAISE_STOP"]
    parts: List[str] = []
    if exits:
        parts.append("EXIT " + ", ".join(exits))
    if raises:
        parts.append("raise stops on " + ", ".join(raises))
    if new:
        parts.append("review {0} new candidate(s): {1}".format(
            len(new), ", ".join(c["symbol"] for c in new)))
    return "; ".join(parts) if parts else "Nothing to do. Hold everything, place nothing."
