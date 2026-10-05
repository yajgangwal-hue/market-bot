"""End-of-session report: what happened today, and what it means so far.

Written after the close each day. It answers the immediate question - what
did it trade, what did that earn - and keeps the cumulative one in view, so a
good day is never mistaken for a working system.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .record import (MINIMUM_INFORMATIVE_TRADES, buy_and_hold_return,
                     equity_base_from_log, from_audit_log, window_of)
from .tight_exit_shadow import compare as compare_tight_exit


@dataclass
class DayReport:
    session: str
    starting_equity: float
    ending_equity: float
    entries: List[Dict[str, object]] = field(default_factory=list)
    exits: List[Dict[str, object]] = field(default_factory=list)
    # Positions that closed WITHOUT the rule's exit: a stop, a tool or the
    # account owner (audit event `learned_from_external_exit`). Until
    # 2026-09-26 the report ignored them, so on 2026-09-21 it said nothing
    # closed and listed five positions as held overnight, when all five had
    # been closed at 10:05 ET for -$1,145.64.
    outside_exits: List[Dict[str, object]] = field(default_factory=list)
    # Close requests the bot submitted but could not confirm as filled. They
    # stay visible without being added to recognized P&L or the win count.
    unconfirmed_exits: List[Dict[str, object]] = field(default_factory=list)
    holds: int = 0
    vetoed: int = 0
    cycles: int = 0
    open_positions: List[Dict[str, object]] = field(default_factory=list)
    # A day with no trades is the normal case here, so the report has to say
    # WHY rather than just showing a zero and leaving it ambiguous.
    closest: List[Dict[str, object]] = field(default_factory=list)
    score_gate: float = 0.0
    incomplete_cycles: int = 0
    worst_missing: int = 0

    @property
    def day_pnl(self) -> float:
        return self.ending_equity - self.starting_equity

    @property
    def day_return(self) -> float:
        return (self.day_pnl / self.starting_equity) if self.starting_equity else 0.0

    @property
    def realized_by_rule(self) -> float:
        return sum(float(e.get("realized_pnl", 0.0) or 0.0) for e in self.exits)

    @property
    def realized_outside_the_rule(self) -> float:
        return sum(float(e.get("realized_pnl", 0.0) or 0.0) for e in self.outside_exits)

    @property
    def realized_today(self) -> float:
        """Everything realized today - the rule's closes AND outside ones."""
        return self.realized_by_rule + self.realized_outside_the_rule

    def as_dict(self) -> Dict[str, object]:
        closes = list(self.exits) + list(self.outside_exits)
        wins = [e for e in closes if float(e.get("realized_pnl", 0.0) or 0.0) > 0]
        marked_open = []
        unmarked_open = 0
        for position in self.open_positions:
            value = position.get("unrealized")
            try:
                if value is None:
                    raise ValueError("missing mark")
                value = float(value)
                if not math.isfinite(value):
                    raise ValueError("non-finite mark")
                marked_open.append(value)
            except (TypeError, ValueError):
                unmarked_open += 1
        return {
            "session": self.session,
            "cycles_run": self.cycles,
            # Present on a no-trade day: what came closest and how far short.
            "closest_candidates": self.closest,
            "score_gate": self.score_gate,
            # Non-zero means some cycles scored a smaller universe than
            # intended, which makes that day's decisions less trustworthy.
            "cycles_with_missing_data": self.incomplete_cycles,
            "worst_symbols_missing": self.worst_missing,
            "opened_today": len(self.entries),
            "closed_today": len(closes),
            "closed_by_rule_today": len(self.exits),
            "closed_outside_the_rule_today": len(self.outside_exits),
            "unconfirmed_close_requests": len(self.unconfirmed_exits),
            "closed_profitable": len(wins),
            "closed_unprofitable": len(closes) - len(wins),
            "realized_today": round(self.realized_today, 2),
            "realized_by_rule_today": round(self.realized_by_rule, 2),
            "realized_outside_the_rule_today": round(self.realized_outside_the_rule, 2),
            # Open-position marks are not proceeds and are not realized gains.
            # Report the known subtotal separately, with completeness, so a
            # missing broker mark cannot silently look like a zero.
            "open_unrealized_pnl_marked_subtotal": round(sum(marked_open), 2),
            "open_unrealized_positions_with_mark": len(marked_open),
            "open_unrealized_positions_missing_mark": unmarked_open,
            "open_unrealized_pnl_complete": unmarked_open == 0,
            "recognized_gains_note": (
                "Rule-exit P&L uses broker-confirmed fills and is gross before "
                "account fees. Open marks remain unrealized; unconfirmed close "
                "requests are shown separately and excluded from realized totals."),
            "unconfirmed_exits": [
                {"symbol": e.get("symbol"),
                 "reason": e.get("exit_reason"),
                 "order_id": (e.get("confirmation") or {}).get("order_id"),
                 "status": (e.get("confirmation") or {}).get("status")}
                for e in self.unconfirmed_exits
            ],
            "starting_equity": round(self.starting_equity, 2),
            "ending_equity": round(self.ending_equity, 2),
            "day_pnl": round(self.day_pnl, 2),
            "day_return_pct": round(100 * self.day_return, 4),
            "positions_held_overnight": len(self.open_positions),
            "trades": [
                {
                    "symbol": e.get("symbol"),
                    "realized_pnl": round(float(e.get("realized_pnl", 0.0) or 0.0), 2),
                    "return_pct": round(100 * float(e.get("return_fraction", 0.0) or 0.0), 3),
                    "r_multiple": e.get("r_multiple"),
                    # The rule's own exit, by the reason the live loop logs
                    # (`exit_reason`: stop, reverted, time, take_profit). This
                    # used to read "trailing stop" whenever the row lacked
                    # `armed: False` - i.e. for every live exit - though
                    # production has no trailing stop.
                    "reason": str(e.get("exit_reason") or e.get("reason")
                                  or "rule exit"),
                }
                for e in self.exits
            ] + [
                {
                    "symbol": e.get("symbol"),
                    "realized_pnl": round(float(e.get("realized_pnl", 0.0) or 0.0), 2),
                    "return_pct": round(100 * float(e.get("return_fraction", 0.0) or 0.0), 3),
                    "r_multiple": e.get("r_multiple"),
                    "reason": _outside_reason(e),
                }
                for e in self.outside_exits
            ],
            "still_open": [
                {"symbol": h.get("symbol"), "last": h.get("last"), "stop": h.get("stop"),
                 "take_profit": h.get("take_profit"), "unrealized": h.get("unrealized")}
                for h in self.open_positions
            ],
        }


def _outside_reason(detail: Dict[str, object]) -> str:
    """Say what the price shows about an outside close, and no more.

    The broker cannot tell this report who closed a position. A sell stop
    fills at or below its trigger, so a fill ABOVE the protective stop was not
    that stop; one at or below it is consistent with the stop. Nothing here
    claims who pressed the button.
    """
    try:
        price = float(detail.get("exit_price"))
        stop = float(detail.get("initial_stop"))
    except (TypeError, ValueError):
        return "closed outside the rule"
    take_profit = detail.get("take_profit")
    if take_profit is not None and price >= float(take_profit) * (1.0 - 1e-4):
        # EXP-0056: the take profit rests at the broker, so it can fill
        # between the bot's checks.
        return "closed at or above its take profit (consistent with the resting take-profit order)"
    if price > stop:
        return "closed outside the rule, above its protective stop (not the stop)"
    return "closed outside the rule, at or below its protective stop"


def build_day_report(
    audit_log: Path,
    session: Optional[date] = None,
    starting_equity: Optional[float] = None,
) -> DayReport:
    """Reconstruct one session from the audit log."""
    day = (session or date.today()).isoformat()
    report = DayReport(session=day, starting_equity=starting_equity or 0.0,
                       ending_equity=starting_equity or 0.0)
    if not audit_log.exists():
        return report

    first_equity: Optional[float] = None
    last_equity: Optional[float] = None
    # The position book through the day, in the order events were logged: a
    # hold refreshes a position, an entry opens one, and a close - by the rule
    # OR from outside - removes it. What is left at the end was held
    # overnight. The previous version kept every symbol held at any point
    # unless the RULE closed it, so outside closes were reported as still open
    # and same-day entries were not reported at all.
    book: Dict[str, Dict[str, object]] = {}
    for line in audit_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not str(row.get("at", "")).startswith(day):
            continue
        event, detail = row.get("event"), row.get("detail") or {}
        if row.get("dry_run") and event in {"entry", "exit"}:
            continue
        symbol = str(detail.get("symbol") or "")
        if event == "entry":
            report.entries.append(detail)
            if symbol:
                book[symbol] = {
                    "symbol": symbol,
                    "last": detail.get("entry_reference", detail.get("entry_price")),
                    "stop": detail.get("stop"),
                    "take_profit": detail.get("take_profit"),
                    # Opened this session and not yet marked by a later cycle.
                    "unrealized": None,
                }
        elif event == "exit":
            if detail.get("realized_pnl_confirmed") is False:
                report.unconfirmed_exits.append(detail)
            else:
                report.exits.append(detail)
            book.pop(symbol, None)
        elif event == "exit_fill_unconfirmed":
            report.unconfirmed_exits.append(detail)
        elif event == "learned_from_external_exit":
            report.outside_exits.append(detail)
            book.pop(symbol, None)
        elif event == "hold":
            report.holds += 1
            report.open_positions.append(detail)
            if symbol:
                book[symbol] = detail
        elif event == "model_veto":
            report.vetoed += 1
        elif event == "no_entries_closest_candidates":
            # Keep the last cycle's view; it is the most recent state of the
            # market rather than a stale one from the open.
            report.closest = list(detail.get("closest") or [])
            report.score_gate = float(detail.get("gate") or 0.0)
        elif event == "universe_incomplete":
            report.incomplete_cycles += 1
            report.worst_missing = max(report.worst_missing,
                                       int(detail.get("missing") or 0))
        elif event == "run_complete":
            report.cycles += 1
            equity = detail.get("equity")
            if equity is not None:
                if first_equity is None:
                    first_equity = float(equity)
                last_equity = float(equity)

    if first_equity is not None:
        report.starting_equity = starting_equity or first_equity
    if last_equity is not None:
        report.ending_equity = last_equity
    # Only what the book still holds at the end of the session was held
    # overnight, each with its latest observation.
    report.open_positions = list(book.values())
    return report


def render(audit_log: Path, session: Optional[date] = None,
           starting_equity: Optional[float] = None,
           benchmark_bars: Optional[Sequence[object]] = None) -> Dict[str, object]:
    """The day, plus the cumulative verdict, in one payload.

    `benchmark_bars` are daily bars for whatever the record should be judged
    against - SPY by default, supplied by the caller so this module stays out
    of the business of reading price files. Without them the assessment can
    only say the record is positive, which is the number least able to tell
    anyone whether the effort was worth making.
    """
    day = build_day_report(audit_log, session, starting_equity)
    # Inception equity, not this session's opening equity: the record spans
    # every trade, so the base it is divided by has to span the same period.
    # `day.starting_equity` is 0.0 for any session with no recorded cycle,
    # which silently fell back to the 1,000.0 placeholder and reported a
    # return a hundred times too large.
    inception = equity_base_from_log(audit_log)
    overall = from_audit_log(audit_log, inception or day.starting_equity or 1000.0)
    overall.equity_base_is_real = bool(inception or day.starting_equity)
    if benchmark_bars:
        window = window_of(overall)
        if window:
            overall.benchmark_return = buy_and_hold_return(
                benchmark_bars, window[0], window[1])
    verdict = overall.verdict()
    payload = day.as_dict()
    payload["since_inception"] = {
        # The RULE's closed trades: what every statistic in this block judges.
        "closed_trades": verdict.get("trades", 0),
        "win_rate": verdict.get("win_rate"),
        "status": verdict.get("status"),
        "explanation": verdict.get("explanation"),
        "vs_buy_and_hold": verdict.get("vs_buy_and_hold"),
        "friction": verdict.get("friction"),
        # Closes the rule did not make, shown beside it so the account's real
        # realized result is never hidden behind the rule's.
        "closed_outside_the_rule": {
            k: v for k, v in overall.outside_summary().items() if k != "trades"},
        "account_realized_pnl": round(overall.account_realized_pnl(), 2),
    }
    # The owner's +0.5% target / -0.2% stop beside the bot, position by
    # position (owner's choice, 2026-09-27: track it, do not trade it).
    # Read-only. A fault here must never cost the owner the rest of the
    # report, so it is reported in place of the comparison instead.
    try:
        payload["tight_exit_comparison"] = compare_tight_exit(
            audit_log, as_of=session or date.today())
    except Exception as error:   # reporting only; nothing downstream trades on it
        payload["tight_exit_comparison"] = {
            "error": "{0}: {1}".format(type(error).__name__, error)}
    payload["profitable_today"] = day.day_pnl > 0
    payload["reminder"] = (
        "One session is not evidence. {0} closed trades are needed before the "
        "win rate means anything, and the status above says whether that point "
        "has been reached."
    ).format(MINIMUM_INFORMATIVE_TRADES)
    return payload
