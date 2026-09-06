"""End-of-session report: what happened today, and what it means so far.

Written after the close each day. It answers the immediate question - what
did it trade, what did that earn - and keeps the cumulative one in view, so a
good day is never mistaken for a working system.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .record import (MINIMUM_INFORMATIVE_TRADES, buy_and_hold_return,
                     equity_base_from_log, from_audit_log, window_of)


@dataclass
class DayReport:
    session: str
    starting_equity: float
    ending_equity: float
    entries: List[Dict[str, object]] = field(default_factory=list)
    exits: List[Dict[str, object]] = field(default_factory=list)
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
    def realized_today(self) -> float:
        return sum(float(e.get("realized_pnl", 0.0) or 0.0) for e in self.exits)

    def as_dict(self) -> Dict[str, object]:
        wins = [e for e in self.exits if float(e.get("realized_pnl", 0.0) or 0.0) > 0]
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
            "closed_today": len(self.exits),
            "closed_profitable": len(wins),
            "closed_unprofitable": len(self.exits) - len(wins),
            "realized_today": round(self.realized_today, 2),
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
                    "reason": "stop" if e.get("armed") is False else "trailing stop",
                }
                for e in self.exits
            ],
            "still_open": [
                {"symbol": h.get("symbol"), "last": h.get("last"), "stop": h.get("stop"),
                 "unrealized": h.get("unrealized")}
                for h in self.open_positions
            ],
        }


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
        if event == "entry":
            report.entries.append(detail)
        elif event == "exit":
            report.exits.append(detail)
        elif event == "hold":
            report.holds += 1
            report.open_positions.append(detail)
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
    # Only the final observation of each symbol is still open at the close.
    seen: Dict[str, Dict[str, object]] = {}
    for h in report.open_positions:
        seen[str(h.get("symbol"))] = h
    report.open_positions = [v for k, v in seen.items()
                             if k not in {str(e.get("symbol")) for e in report.exits}]
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
        "closed_trades": verdict.get("trades", 0),
        "win_rate": verdict.get("win_rate"),
        "status": verdict.get("status"),
        "explanation": verdict.get("explanation"),
        "vs_buy_and_hold": verdict.get("vs_buy_and_hold"),
        "friction": verdict.get("friction"),
    }
    payload["profitable_today"] = day.day_pnl > 0
    payload["reminder"] = (
        "One session is not evidence. {0} closed trades are needed before the "
        "win rate means anything, and the status above says whether that point "
        "has been reached."
    ).format(MINIMUM_INFORMATIVE_TRADES)
    return payload
