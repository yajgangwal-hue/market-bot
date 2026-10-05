"""The owner's +0.5% target / -0.2% stop, tracked beside the bot - never traded.

On 2026-09-27 the owner asked for every position to be sold at +0.5% or at
-0.2%, because an unrealized gain can vanish at the open. Replayed on the
bot's own positions, that rule won about as often as chance gives for those
two levels, and trading it would have restarted the frozen evaluation. So the
owner chose to TRACK it instead. This module does that and nothing else: it
reads the audit log, places no order, and touches no stop, size or
fingerprinted value.

Each position is judged from its own entry:

- Every cycle (15 minutes) logs each held position's gain as the broker
  reports it, `hold.unrealized`. `hold.last` is the PREVIOUS session's close,
  not a live price, so it is not used.
- The tight rule sells at the first check where the gain is at or above +0.5%
  of cost, or at or below -0.2%.
- Inside a session a resting order fills AT its level, so the level is
  booked. At the first check of a later session the level was crossed
  overnight, and a resting order fills at the opening price; that check -
  normally about forty seconds after the open - stands in for it.
- A position the bot closed before either level was reached ends the same way
  under both rules.

Limits, stated so the numbers are not over-read:

- Checks are fifteen minutes apart and the last of a session is normally at
  15:45 ET, so a level touched between checks is missed. The stop is the
  nearer level, so most misses are stop touches - which flatters the tight
  rule.
- Neither side is charged a selling cost; the bot's open positions have not
  paid theirs yet either.
- Selling sooner would have freed cash for entries the bot skipped for want of
  it. Those trades are not modelled.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TARGET = 0.005
STOP = -0.002
RULE = "+0.5% target / -0.2% stop"
# The first session after the owner chose to track this rule rather than
# trade it (2026-09-27). The `held_since` block counts from here.
TRACKING_FROM = date(2026, 9, 28)

MEASURED = [
    "Tracked on paper beside the bot. The bot keeps its own rule, and no order "
    "is ever placed for the tight rule.",
    "Realized = recognized: closed, the gain is banked. Unrealized = "
    "unrecognized: still open, the gain can still change.",
    "Each position is judged from its own entry, on the broker's gain at every "
    "15-minute check.",
    "Inside a session the tight rule is booked at its level (+0.5% or -0.2%). "
    "When the level was crossed overnight it is booked at the first check of "
    "the day, which stands in for the opening price.",
    "A position the bot closed before either level was reached ends the same "
    "way under both rules.",
    "Checks are 15 minutes apart, so a level touched between two checks is "
    "missed. The stop is the nearer level, so this mostly flatters the tight "
    "rule.",
    "Neither side is charged a selling cost. Cash the tight rule would have "
    "freed sooner, and the trades it could have funded, are not modelled.",
]


def _number(value: object) -> Optional[float]:
    try:
        number = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    # json.loads accepts NaN and Infinity; one of those would poison a total.
    return number if number is None or math.isfinite(number) else None


@dataclass
class Position:
    """One holding, from its logged entry to its close - or to now."""

    symbol: str
    opened_at: str
    entry_price: float
    quantity: float
    # (timestamp, broker unrealized gain in dollars) for every check.
    checks: List[Tuple[str, float]] = field(default_factory=list)
    # The broker's share count, once one has been read; beats the order's.
    broker_quantity: Optional[float] = None
    closed_at: Optional[str] = None
    how: str = "open"
    realized: Optional[float] = None
    left_out: Optional[str] = None

    @property
    def shares(self) -> float:
        return self.broker_quantity or self.quantity

    @property
    def cost(self) -> float:
        return self.shares * self.entry_price


@dataclass
class TightOutcome:
    kind: str                       # "target", "stop" or "neither"
    at: Optional[str] = None
    booked: Optional[float] = None
    at_the_open: bool = False


def _read(audit_log: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    if not audit_log.exists():
        return rows
    for line in audit_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _genuine(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Drop the rows a contamination notice marks as synthetic.

    On 2026-09-22 unit tests wrote 34 fake rows into the real log. A notice
    naming their event types and timestamps was appended rather than deleting
    anything (scripts/annotate_audit_contamination.py). Among them are
    `stop_coverage` rows for a fake 300-share BAC, which this module would
    otherwise read as the broker's share count. Notices are honoured before
    any date cut, because a notice written later still describes earlier rows.
    """
    marks = []
    for row in rows:
        if row.get("event") != "audit_log_contamination_notice":
            continue
        detail = row.get("detail") or {}
        if isinstance(detail, dict):
            marks.append((set(detail.get("synthetic_events") or []),
                          [str(s) for s in detail.get("synthetic_timestamps") or []]))
    if not marks:
        return rows

    def synthetic(row: Dict[str, object]) -> bool:
        at = str(row.get("at", ""))
        return any(row.get("event") in events and any(at.startswith(s) for s in stamps)
                   for events, stamps in marks)

    return [row for row in rows if not synthetic(row)]


def positions_from_log(audit_log: Path, as_of: Optional[date] = None
                       ) -> Tuple[List[Position], List[Position]]:
    """(compared, left_out): every position the log records.

    A position is left out - listed, never silently dropped - when there is
    nothing to judge it on: no check was ever logged for it, it vanished from
    the checks with no close recorded, a second entry was logged before any
    close, or a close arrived with no logged entry.

    Session dates are the first ten characters of the UTC timestamp. Checks
    run between 09:30 and 16:00 ET, when the UTC date and the New York date
    are the same.
    """
    rows = _genuine(_read(audit_log))
    if as_of is not None:
        cutoff = as_of.isoformat()
        rows = [r for r in rows if str(r.get("at", ""))[:10] <= cutoff]

    open_positions: Dict[str, Position] = {}
    finished: List[Position] = []
    orphans: Dict[str, str] = {}
    last_check_day = ""
    for row in rows:
        event = row.get("event")
        detail = row.get("detail") or {}
        if not isinstance(detail, dict):
            continue
        symbol = str(detail.get("symbol") or "")
        if not symbol:
            continue
        at = str(row.get("at", ""))
        if event == "entry":
            earlier = open_positions.pop(symbol, None)
            if earlier is not None:
                earlier.left_out = ("a second entry was logged before any close, "
                                    "so how this one ended is unknown")
                finished.append(earlier)
            open_positions[symbol] = Position(
                symbol=symbol, opened_at=at,
                entry_price=(_number(detail.get("entry_price"))
                             or _number(detail.get("entry_reference")) or 0.0),
                quantity=_number(detail.get("quantity")) or 0.0)
        elif event == "hold":
            last_check_day = max(last_check_day, at[:10])
            held = open_positions.get(symbol)
            gain = _number(detail.get("unrealized"))
            if held is None:
                orphans.setdefault(symbol, at)
            elif gain is not None:
                held.checks.append((at, gain))
        elif event == "stop_coverage":
            held = open_positions.get(symbol)
            shares = _number(detail.get("held_quantity"))
            if held is not None and shares:
                held.broker_quantity = shares
        elif event in ("exit", "learned_from_external_exit"):
            held = open_positions.pop(symbol, None)
            if held is None:
                held = Position(symbol=symbol, opened_at="", entry_price=0.0,
                                quantity=0.0,
                                left_out="closed with no logged entry")
            held.closed_at = str(detail.get("closed_at") or at)
            held.how = ("closed by the rule" if event == "exit"
                        else "closed outside the bot")
            held.realized = _number(detail.get("realized_pnl")) or 0.0
            # The broker's own cost basis, known exactly once the position has
            # closed. The entry row's reference price was stale before the
            # freeze - 128.92 for a TJX position the broker filled at 126.42.
            price = _number(detail.get("entry_price"))
            shares = _number(detail.get("quantity"))
            if price:
                held.entry_price = price
            if shares:
                held.broker_quantity = shares
            finished.append(held)

    for held in open_positions.values():
        last_seen = held.checks[-1][0][:10] if held.checks else held.opened_at[:10]
        if last_check_day and last_seen < last_check_day:
            held.left_out = ("stopped appearing in the bot's checks with no close "
                             "recorded" if held.checks else
                             "never appeared in the bot's checks - the order may "
                             "not have filled")
        finished.append(held)

    compared: List[Position] = []
    left_out: List[Position] = []
    for held in sorted(finished, key=lambda p: p.opened_at):
        if held.left_out is None and not held.checks and held.how != "open":
            held.left_out = "closed before the bot's first check of it"
        if held.left_out is None and held.cost <= 0:
            held.left_out = "no cost basis was recorded"
        (left_out if held.left_out else compared).append(held)
    for symbol, at in sorted(orphans.items(), key=lambda item: item[1]):
        left_out.append(Position(symbol=symbol, opened_at=at, entry_price=0.0,
                                 quantity=0.0,
                                 left_out="checked while held, but no entry was logged"))
    return compared, left_out


def tight_outcome(position: Position) -> TightOutcome:
    """Where the +0.5% / -0.2% rule would have sold, if it would have."""
    cost = position.cost
    if cost <= 0:
        return TightOutcome("neither")
    day = position.opened_at[:10]
    for at, gain in position.checks:
        at_the_open = at[:10] != day
        day = at[:10]
        ratio = gain / cost
        if ratio >= TARGET:
            return TightOutcome("target", at, gain if at_the_open else cost * TARGET,
                                at_the_open)
        if ratio <= STOP:
            return TightOutcome("stop", at, gain if at_the_open else cost * STOP,
                                at_the_open)
    return TightOutcome("neither")


def _money(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def _row(position: Position) -> Dict[str, object]:
    cost = position.cost
    if position.how == "open":
        bot_realized = None
        bot_unrealized = position.checks[-1][1] if position.checks else 0.0
    else:
        bot_realized, bot_unrealized = position.realized or 0.0, None
    bot_gain = (bot_realized or 0.0) + (bot_unrealized or 0.0)

    outcome = tight_outcome(position)
    if outcome.kind == "neither":
        # Still holding under both rules, or closed with the bot before either
        # level was reached: the same result either way.
        rule_realized, rule_unrealized = bot_realized, bot_unrealized
        if position.how != "open":
            status = "closed with the bot - neither level was reached first"
        elif position.checks:
            status = "still open - neither level reached yet"
        else:
            status = "still open - not checked yet"
    else:
        rule_realized, rule_unrealized = outcome.booked, None
        status = {
            ("target", False): "sold at the +0.5% target",
            ("target", True): "sold at the open, above the +0.5% target",
            ("stop", False): "stopped out at -0.2%",
            ("stop", True): "stopped out at the open, below -0.2%",
        }[(outcome.kind, outcome.at_the_open)]
    rule_gain = (rule_realized or 0.0) + (rule_unrealized or 0.0)
    return {
        "symbol": position.symbol,
        "opened": position.opened_at,
        "shares": position.shares,
        "cost": _money(cost),
        "bot": {
            "status": position.how,
            "closed": position.closed_at,
            "realized": _money(bot_realized),
            "unrealized": _money(bot_unrealized),
            "gain": _money(bot_gain),
            "gain_pct": round(100 * bot_gain / cost, 3),
        },
        "tight_rule": {
            "outcome": outcome.kind,
            "status": status,
            "sold": outcome.at,
            "realized": _money(rule_realized),
            "unrealized": _money(rule_unrealized),
            "gain": _money(rule_gain),
            "gain_pct": round(100 * rule_gain / cost, 3),
        },
        "tight_rule_minus_bot": _money(rule_gain - bot_gain),
    }


def _totals(rows: List[Dict[str, object]]) -> Dict[str, object]:
    """Sums of the rows exactly as displayed, so a reader can add them up."""
    def side(key: str) -> Dict[str, object]:
        realized = round(sum(r[key]["realized"] or 0.0 for r in rows), 2)
        unrealized = round(sum(r[key]["unrealized"] or 0.0 for r in rows), 2)
        return {"realized": realized, "unrealized": unrealized,
                "total": round(realized + unrealized, 2)}

    bot, rule = side("bot"), side("tight_rule")
    outcomes = [r["tight_rule"]["outcome"] for r in rows]
    rule.update({
        "sold_at_target": outcomes.count("target"),
        "stopped_out": outcomes.count("stop"),
        "neither_level": outcomes.count("neither"),
    })
    return {"positions": len(rows), "bot": bot, "tight_rule": rule,
            "tight_rule_minus_bot": round(rule["total"] - bot["total"], 2)}


def compare(audit_log: Path, as_of: Optional[date] = None,
            since: Optional[date] = TRACKING_FROM) -> Dict[str, object]:
    """The tight rule beside the bot: every position, and the totals.

    `held_since` covers the positions held at any time from `since` on - open
    now, or closed on or after it - each still judged from its own entry. It
    is omitted before `since` arrives.
    """
    compared, left_out = positions_from_log(audit_log, as_of)
    rows = [_row(p) for p in compared]
    payload: Dict[str, object] = {
        "rule": RULE,
        "how_it_is_measured": MEASURED,
        "every_position": _totals(rows),
        "positions": rows,
        "not_compared": [{"symbol": p.symbol, "opened": p.opened_at,
                          "closed": p.closed_at, "reason": p.left_out}
                         for p in left_out],
    }
    if since is not None and (as_of or date.today()) >= since:
        start = since.isoformat()
        window = [row for row, p in zip(rows, compared)
                  if p.how == "open" or (p.closed_at or "")[:10] >= start]
        payload["held_since"] = dict({"since": start}, **_totals(window))
    return payload
