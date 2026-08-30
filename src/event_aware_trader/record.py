"""Read the accumulated paper record and say whether it proves anything.

The point of running for months is to answer one question: does this work?
That question is statistical, and the honest answer for a long time will be
"there is not enough evidence yet" - which is exactly the answer a person
watching a small positive number is least likely to give themselves.

At roughly three trades per six months, a year of running produces about six
trades. Six trades cannot distinguish a real edge from luck, and this module
says so numerically rather than leaving it to judgement: it reports the
confidence interval around the win rate, a bootstrap interval around mean
return, a sign-flip p-value against the null that the mean is zero, and how
many more trades would be needed before the question is even answerable.

`stats.py` already contained all of this machinery and nothing in the trading
path used it.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .stats import bootstrap_ci, sign_flip_pvalue, wilson_interval

# Below this, no statistical statement is worth making.
MINIMUM_INFORMATIVE_TRADES = 30
# A rule of thumb for detecting a modest edge at conventional power.
TRADES_FOR_A_MODEST_EDGE = 200


@dataclass
class TradeRecord:
    symbol: str
    opened: str
    closed: str
    net_pnl: float
    return_fraction: float

    @property
    def won(self) -> bool:
        return self.net_pnl > 0


@dataclass
class RecordReport:
    trades: List[TradeRecord] = field(default_factory=list)
    starting_equity: float = 1_000.0
    ending_equity: float = 1_000.0
    benchmark_return: Optional[float] = None
    sessions_observed: int = 0

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def returns(self) -> List[float]:
        return [t.return_fraction for t in self.trades]

    def verdict(self) -> Dict[str, object]:
        n = len(self.trades)
        if n == 0:
            return {
                "status": "NO_TRADES_YET",
                "explanation": (
                    "Nothing has traded. At about one trade per 51 sessions this is "
                    "the expected state for weeks at a time, not a malfunction."
                ),
                "trades_needed": MINIMUM_INFORMATIVE_TRADES,
            }

        interval = wilson_interval(self.wins, n)
        mean_return = sum(self.returns) / n
        boot = bootstrap_ci(self.returns) if n >= 5 else None
        pvalue = sign_flip_pvalue(self.returns) if n >= 5 else None

        # A confidence interval that still contains a coin flip means the
        # record is consistent with having no skill at all.
        spans_chance = bool(interval and interval[0] <= 0.5 <= interval[1])
        spans_zero = bool(boot and boot[0] <= 0.0 <= boot[1])

        if n < MINIMUM_INFORMATIVE_TRADES:
            status = "INSUFFICIENT_EVIDENCE"
            explanation = (
                "{0} trades is too few to distinguish skill from luck. Keep running; "
                "no conclusion either way is justified yet."
            ).format(n)
        elif spans_zero or spans_chance:
            status = "NOT_DISTINGUISHABLE_FROM_LUCK"
            explanation = (
                "With {0} trades the interval around the result still includes "
                "'no edge'. That is not proof it fails - it is the absence of proof "
                "that it works."
            ).format(n)
        elif mean_return > 0:
            status = "POSITIVE_AND_MEASURABLE"
            explanation = (
                "Over {0} trades the result is positive and its interval excludes "
                "zero. Compare it against buy-and-hold before concluding it is worth "
                "the effort."
            ).format(n)
        else:
            status = "NEGATIVE_AND_MEASURABLE"
            explanation = "Over {0} trades the result is reliably negative.".format(n)

        return {
            "status": status,
            "explanation": explanation,
            "trades": n,
            "wins": self.wins,
            "win_rate": round(self.wins / n, 4),
            "win_rate_95_interval": [round(v, 4) for v in interval] if interval else None,
            "win_rate_interval_includes_a_coin_flip": spans_chance,
            "mean_return_per_trade": round(mean_return, 6),
            "mean_return_95_interval": [round(v, 6) for v in boot] if boot else None,
            "mean_return_interval_includes_zero": spans_zero,
            "sign_flip_pvalue": None if pvalue is None else round(pvalue, 4),
            "trades_still_needed_for_a_first_read": max(0, MINIMUM_INFORMATIVE_TRADES - n),
            "trades_for_confidence_in_a_modest_edge": max(0, TRADES_FOR_A_MODEST_EDGE - n),
            "time_to_evidence": self._time_to_evidence(n),
        }

    def _time_to_evidence(self, n: int) -> Dict[str, object]:
        """How long the observed trade rate takes to reach an answerable sample.

        This is the number that decides whether "run it and see" is a plan or
        a wish. A rule that trades rarely enough can be *unfalsifiable in
        practice*: correct, careful, and still unanswerable within any horizon
        a person will actually wait.
        """
        if not self.sessions_observed or not n:
            return {"note": "Not enough observation to estimate a trade rate."}
        per_session = n / self.sessions_observed
        if per_session <= 0:
            return {"note": "No trades observed."}
        sessions_per_year = 252.0

        def years_for(target: int) -> float:
            return max(0.0, (target - n) / per_session / sessions_per_year)

        return {
            "trades_per_year_at_this_rate": round(per_session * sessions_per_year, 2),
            "years_to_a_first_read": round(years_for(MINIMUM_INFORMATIVE_TRADES), 1),
            "years_to_confidence_in_a_modest_edge": round(
                years_for(TRADES_FOR_A_MODEST_EDGE), 1
            ),
        }

    def as_dict(self) -> Dict[str, object]:
        total = (
            (self.ending_equity / self.starting_equity - 1.0) if self.starting_equity else 0.0
        )
        payload: Dict[str, object] = {
            "starting_equity": round(self.starting_equity, 2),
            "ending_equity": round(self.ending_equity, 2),
            "total_return_pct": round(100 * total, 3),
            "closed_trades": [
                {
                    "symbol": t.symbol, "opened": t.opened, "closed": t.closed,
                    "net_pnl": round(t.net_pnl, 2),
                    "return_pct": round(100 * t.return_fraction, 3),
                }
                for t in self.trades
            ],
            "assessment": self.verdict(),
        }
        if self.benchmark_return is not None:
            payload["benchmark_return_pct"] = round(100 * self.benchmark_return, 3)
            payload["beat_benchmark"] = bool(total > self.benchmark_return)
        return payload


def from_audit_log(path: Path, starting_equity: float = 1_000.0) -> RecordReport:
    """Rebuild the record from what autotrade actually did.

    Reads only `entry`/`exit` events, so a log full of `hold` and
    `run_complete` lines still produces a clean record.
    """
    report = RecordReport(starting_equity=starting_equity, ending_equity=starting_equity)
    if not path.exists():
        return report

    opened: Dict[str, Dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        event, detail = row.get("event"), row.get("detail", {})
        symbol = str(detail.get("symbol", ""))
        if not symbol:
            continue
        if event == "entry":
            opened[symbol] = {"at": row.get("at"), "quantity": detail.get("quantity")}
        elif event == "exit" and symbol in opened:
            entry = opened.pop(symbol)
            # An audit log records intent, not fills; P&L is only known when
            # the broker reports it, so this is left explicit rather than guessed.
            report.trades.append(
                TradeRecord(
                    symbol=symbol,
                    opened=str(entry.get("at")),
                    closed=str(row.get("at")),
                    net_pnl=float(detail.get("realized_pnl", 0.0) or 0.0),
                    return_fraction=float(detail.get("return_fraction", 0.0) or 0.0),
                )
            )
    return report


def from_portfolio(report_obj, benchmark_return: Optional[float] = None) -> RecordReport:
    """Build the same assessment from a simulated portfolio run."""
    out = RecordReport(
        starting_equity=report_obj.starting_cash,
        ending_equity=report_obj.equity,
        benchmark_return=benchmark_return,
        sessions_observed=getattr(report_obj, "days_simulated", 0),
    )
    for t in report_obj.trades:
        out.trades.append(
            TradeRecord(
                symbol=t.symbol,
                opened=t.entry_time.isoformat(),
                closed=t.exit_time.isoformat(),
                net_pnl=t.net_pnl,
                return_fraction=(t.exit_price / t.entry_price - 1.0) if t.entry_price else 0.0,
            )
        )
    return out
