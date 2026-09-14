"""The benchmark, measured the way the objective states it.

The objective is to outperform the S&P 500 on a risk-adjusted basis over a
multi-year period, measured against the index's TOTAL return - dividends
reinvested - over the identical window. Two things this module refuses to do,
because each is how that comparison quietly goes wrong:

  1. Compare against price return. SPY's price return 1996-2026 is 8.55% a
     year; with dividends it is roughly two points higher. Every number this
     project quoted against SPY before 2026-09-14 was the price figure, which
     flattered the bot by about two points a year. The benchmark series here
     is fetched with adjustment="all" so dividends are in the closes.

  2. Compare over different windows, or with a reconstructed account curve.
     The account side comes from the equity readings the bot wrote to its own
     audit log at the time - not from a curve assembled afterwards - and the
     two series are aligned on the days both have, base day included.

There is also a floor on how short a record may be before it is reported as
a verdict. Two sessions of paper trading against two sessions of SPY is a
number, not a finding. Below MINIMUM_SESSIONS the record is shown with its
flag set, and nothing downstream is allowed to call it a result.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

BENCHMARK = "SPY"

# Sessions before a forward comparison is a finding rather than a number.
# Sixty is about a quarter. Even that is short for a strategy that averages
# 3.4 positions - a single stopped-out name can move a quarter's excess return
# by more than the strategy's whole annual edge.
MINIMUM_SESSIONS = 60

# The audit-log fields that carry an account-level equity reading, in order of
# preference. `broker_equity` is the account as the broker reported it;
# `equity` on the same records is the allocated figure, which equals it unless
# capital_base is set.
EQUITY_KEYS = ("broker_equity", "equity")


@dataclass
class ForwardRecord:
    start: date
    end: date
    sessions: int
    account_start: float
    account_end: float
    benchmark_start: float
    benchmark_end: float

    @property
    def account_return(self) -> float:
        return self.account_end / self.account_start - 1.0

    @property
    def benchmark_return(self) -> float:
        return self.benchmark_end / self.benchmark_start - 1.0

    @property
    def excess(self) -> float:
        return self.account_return - self.benchmark_return

    @property
    def judgeable(self) -> bool:
        return self.sessions >= MINIMUM_SESSIONS

    def as_dict(self) -> Dict[str, object]:
        return {
            "start": self.start.isoformat(), "end": self.end.isoformat(),
            "sessions": self.sessions,
            "account_return_pct": round(100 * self.account_return, 3),
            "benchmark_return_pct": round(100 * self.benchmark_return, 3),
            "excess_pct": round(100 * self.excess, 3),
            "benchmark": BENCHMARK + " total return",
            "judgeable": self.judgeable,
            "minimum_sessions": MINIMUM_SESSIONS,
        }

    def __str__(self) -> str:
        verdict = ("" if self.judgeable else
                   "   [NOT A FINDING: {0} of {1} sessions]".format(
                       self.sessions, MINIMUM_SESSIONS))
        return ("{0} -> {1} ({2} sessions)  account {3:+.2%}  SPY total return "
                "{4:+.2%}  excess {5:+.2%}{6}").format(
                    self.start, self.end, self.sessions, self.account_return,
                    self.benchmark_return, self.excess, verdict)


def equity_by_day(audit_log: Path, since: date,
                  keys: Sequence[str] = EQUITY_KEYS) -> Dict[date, float]:
    """The LAST equity reading the bot recorded on each day, from its audit log.

    Recorded at the time, by the bot, from the broker - so the account side of
    the comparison is not something assembled later from memory. Days with no
    reading (weekends, a day the loop did not run) are simply absent and drop
    out of the alignment.
    """
    out: Dict[date, float] = {}
    if not audit_log.exists():
        return out
    with audit_log.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            detail = record.get("detail") or {}
            value = None
            for key in keys:
                if key in detail:
                    value = float(detail[key])
                    break
            if value is None:
                continue
            day = datetime.fromisoformat(record["at"]).date()
            if day >= since:
                out[day] = value          # later lines overwrite: last wins
    return out


def closes_by_day(bars: Iterable) -> Dict[date, float]:
    return {b.timestamp.date(): float(b.close) for b in bars}


def forward_record(account: Dict[date, float], benchmark: Dict[date, float],
                   start: date) -> Optional[ForwardRecord]:
    """Both series over the identical window: aligned on the days both have.

    The base is the first day on or after `start` that BOTH series cover, and
    the end is the last such day. A day only one side has - the account
    reading for a session where the bars have not printed yet, say - is left
    out rather than paired with the nearest neighbour.
    """
    common = sorted(d for d in account if d in benchmark and d >= start)
    if len(common) < 2:
        return None
    first, last = common[0], common[-1]
    return ForwardRecord(
        start=first, end=last, sessions=len(common),
        account_start=account[first], account_end=account[last],
        benchmark_start=benchmark[first], benchmark_end=benchmark[last])


def total_return(closes: Sequence[float]) -> Optional[float]:
    if len(closes) < 2 or closes[0] <= 0:
        return None
    return closes[-1] / closes[0] - 1.0


def annualised(total: float, days: int) -> Optional[float]:
    if days <= 0 or total <= -1.0:
        return None
    return (1.0 + total) ** (365.25 / days) - 1.0
