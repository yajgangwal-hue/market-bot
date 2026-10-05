"""H-0032 engine: market intraday momentum on SPY 5-minute bars (Gao, Han, Li & Zhou, JFE 2018).

The one documented intraday effect with academic standing that this project had
never tested, because it needs intraday bars (docs/2026-09-19-day-trading-deep-dive.md
section 7). The preserved store spy-5min-2016-2026-quarterly-43 has them.

Definitions, as the paper's:
  first half-hour return  previous session's close -> 10:00 ET
  last half-hour return   15:30 ET -> 16:00 ET close
Prices are 5-minute bar CLOSES, bars stamped by their UTC start time:
  10:00 = close of the 09:55 bar, 15:30 = close of the 15:25 bar,
  16:00 = close of the 15:55 bar. A session missing any of them (an early
  close, a data gap) is skipped, and so is the session after it, whose
  first-half-hour return would have no previous close.
"""

import json
import math
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
STAMPS = {(9, 55): "p1000", (15, 25): "p1530", (15, 55): "p1600"}


def session_prices(bars) -> Dict[date, Dict[str, float]]:
    """{session date: {p1000, p1530, p1600}} from one symbol's 5-minute bars."""
    out: Dict[date, Dict[str, float]] = {}
    for bar in bars:
        start = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")).astimezone(NEW_YORK)
        key = STAMPS.get((start.hour, start.minute))
        if key is None:
            continue
        out.setdefault(start.date(), {})[key] = float(bar["c"])
    return {d: p for d, p in out.items() if len(p) == 3}


def load_store(folder: Path) -> Dict[date, Dict[str, float]]:
    prices: Dict[date, Dict[str, float]] = {}
    for path in sorted(Path(folder).glob("SPY_*.json")):
        bars = json.loads(path.read_text(encoding="utf-8"))["bars"]["SPY"]
        prices.update(session_prices(bars))
    return prices


def daily_rows(prices: Dict[date, Dict[str, float]], last_day: Optional[date] = None
               ) -> List[Tuple[date, float, float, float]]:
    """(session, first half-hour return, last half-hour return, close-to-close)."""
    days = sorted(d for d in prices if last_day is None or d <= last_day)
    rows = []
    for prev, day in zip(days, days[1:]):
        if (day - prev).days > 4:          # a gap longer than a long weekend: no clean previous close
            continue
        p0, p = prices[prev], prices[day]
        rows.append((day, p["p1000"] / p0["p1600"] - 1.0,
                     p["p1600"] / p["p1530"] - 1.0,
                     p["p1600"] / p0["p1600"] - 1.0))
    return rows


def ols(x: List[float], y: List[float]) -> Dict[str, float]:
    n = len(x)
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    beta = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
    alpha = my - beta * mx
    resid = [b - alpha - beta * a for a, b in zip(x, y)]
    s2 = sum(e * e for e in resid) / (n - 2)
    se = math.sqrt(s2 / sxx)
    ss_tot = sum((b - my) ** 2 for b in y)
    return {"beta": beta, "t": beta / se, "r2": 1.0 - sum(e * e for e in resid) / ss_tot, "n": n}


def strategy_returns(rows, cost_round_trip: float, long_short: bool = False):
    """Per session: the trade's net return, or None when flat."""
    out = []
    for day, first, last, _ in rows:
        if first > 0:
            out.append((day, last - cost_round_trip))
        elif long_short and first < 0:
            out.append((day, -last - cost_round_trip))
        else:
            out.append((day, None))
    return out


def summarise(trades) -> Dict[str, object]:
    r = [x for _, x in trades if x is not None]
    if len(r) < 2:
        return {"n": len(r)}
    sd = statistics.stdev(r)
    return {"n": len(r), "mean": statistics.fmean(r), "t": statistics.fmean(r) / (sd / math.sqrt(len(r))),
            "win_rate": sum(1 for x in r if x > 0) / len(r), "median": statistics.median(r)}


def account(trades, rows, bill_rate) -> Dict[str, object]:
    """$1 traded on signal sessions, idle cash at the bill rate, against SPY held."""
    value, spy, prev_day = 1.0, 1.0, None
    by_year, spy_year = {}, {}
    for (day, x), (_, _, _, cc) in zip(trades, rows):
        days = (day - prev_day).days if prev_day else 1
        value *= (1.0 + bill_rate(day) * days / 365.0) * (1.0 + (x or 0.0))
        spy *= 1.0 + cc
        by_year.setdefault(day.year, [value, value])[1] = value
        spy_year.setdefault(day.year, [spy, spy])[1] = spy
        prev_day = day
    years = (rows[-1][0] - rows[0][0]).days / 365.25
    yearly = {}
    prev_v, prev_s = 1.0, 1.0
    for y in sorted(by_year):
        yearly[y] = {"strategy": by_year[y][1] / prev_v - 1.0, "spy_price": spy_year[y][1] / prev_s - 1.0}
        prev_v, prev_s = by_year[y][1], spy_year[y][1]
    return {"cagr": value ** (1 / years) - 1.0, "spy_price_cagr": spy ** (1 / years) - 1.0,
            "years_beating_spy_price": sum(1 for v in yearly.values() if v["strategy"] > v["spy_price"]),
            "years": len(yearly), "by_year": yearly}
