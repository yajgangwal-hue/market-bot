"""H-0033 engine: Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective
Intraday Momentum Strategy for S&P500 ETF (SPY)", replicated on 5-minute bars.

The rules, from the paper's own text (first version 2024-05-10, revised 2025-02-03):

  sigma(t, HH:MM)  mean over the previous 14 sessions of |Close(HH:MM) / Open(9:30) - 1|
  UpperBound       max(Open(t, 9:30), Close(t-1, 16:00)) * (1 + sigma)
  LowerBound       min(Open(t, 9:30), Close(t-1, 16:00)) * (1 - sigma)
  decisions        only at HH:00 and HH:30, 10:00 to 15:30, on the price at that time
  long             price above the upper bound AND above VWAP
                   (the trailing stop is max(UB, VWAP): below either, the long is closed)
  short            price below the lower bound AND below VWAP (stop min(LB, VWAP))
  otherwise        flat; everything is closed at the 16:00 close
  size (b)         AUM(t-1) / Open(t)                 - 100% of equity, no leverage
  size (c)         AUM(t-1) * min(4, 2% / sigma_SPY) / Open(t), sigma_SPY the standard
                   deviation of the previous 14 daily returns
  costs            $0.0035 commission + $0.001 slippage per share, each side

On 5-minute bars stamped by their start time, the price at HH:MM is the close
of the bar ending then (the paper uses the close of the minute ending then -
the same print), the open is the 09:30 bar's open, the previous close is the
last regular-session bar's close, and VWAP is sum(vw * v) / sum(v) over the
session's bars so far - identical to a minute-built VWAP.
"""

import json
import math
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
CHECKS = [(h, m) for h in range(10, 16) for m in (0, 30)]          # 10:00 .. 15:30
LOOKBACK = 14
# NYSE 13:00 closes, 2016-2026. The store carries after-hours bars on these
# afternoons; they are not the regular session. Checked against the data: these
# 21 days are exactly the 21 lowest afternoon/morning volume ratios.
EARLY_CLOSES = {date.fromisoformat(d) for d in (
    "2016-11-25", "2017-07-03", "2017-11-24", "2018-07-03", "2018-11-23", "2018-12-24",
    "2019-07-03", "2019-11-29", "2019-12-24", "2020-11-27", "2020-12-24", "2021-11-26",
    "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24",
    "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24")}


class Session:
    """One regular session: the 09:30 open, each half-hour check price and
    running VWAP, and the 16:00 close."""

    def __init__(self, day: date):
        self.day = day
        self.open: Optional[float] = None
        self.close: Optional[float] = None        # last regular bar's close, whatever time
        self.close_1600: Optional[float] = None    # the 15:55 bar's close, if the session ran full
        self.price: Dict[tuple, float] = {}
        self.vwap: Dict[tuple, float] = {}
        self._pv = 0.0
        self._v = 0.0

    @property
    def complete(self) -> bool:
        return (self.open is not None and self.close_1600 is not None
                and all(c in self.price for c in CHECKS))


def build_sessions(bars) -> Dict[date, Session]:
    """Regular-session bars only (09:30-15:55 starts), in time order."""
    out: Dict[date, Session] = {}
    rows = []
    for bar in bars:
        start = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")).astimezone(NEW_YORK)
        minutes = start.hour * 60 + start.minute
        last_start = 12 * 60 + 55 if start.date() in EARLY_CLOSES else 15 * 60 + 55
        if 9 * 60 + 30 <= minutes <= last_start:
            rows.append((start, bar))
    rows.sort(key=lambda r: r[0])
    for start, bar in rows:
        s = out.setdefault(start.date(), Session(start.date()))
        if start.hour == 9 and start.minute == 30:
            s.open = float(bar["o"])
        volume = float(bar.get("v") or 0.0)
        vw = float(bar.get("vw") or bar["c"])
        s._pv += vw * volume
        s._v += volume
        end_minutes = start.hour * 60 + start.minute + 5
        end = (end_minutes // 60, end_minutes % 60)
        s.close = float(bar["c"])
        if end in CHECKS or end == (16, 0):
            if end == (16, 0):
                s.close_1600 = float(bar["c"])
            else:
                s.price[end] = float(bar["c"])
                s.vwap[end] = (s._pv / s._v) if s._v > 0 else float(bar["c"])
    return out


def load_store(folder: Path) -> Dict[date, Session]:
    """Every quarterly file's bars, merged by timestamp before sessions are
    built: the first day of a quarter sits in two files, and building per file
    would let one copy replace the other."""
    merged: Dict[str, dict] = {}
    for path in sorted(Path(folder).glob("SPY_*.json")):
        for bar in json.loads(path.read_text(encoding="utf-8"))["bars"]["SPY"]:
            merged[str(bar["t"])] = bar
    return build_sessions(merged.values())


def run(sessions: Dict[date, Session], start: date, end: date, sizing: str = "full",
        cost_per_share: float = 0.0045, capital: float = 100_000.0) -> Dict[str, object]:
    """The strategy over [start, end]. Returns the daily equity curve and trade stats.

    Sessions that are not complete (an early close, a data gap) are not traded,
    and they do not enter sigma: the lookback is the previous 14 COMPLETE
    sessions. The previous close for the gap adjustment is the previous
    session's real last close, complete or not.
    """
    days = sorted(sessions)
    complete = [d for d in days if sessions[d].complete]
    equity, curve = capital, []
    trades = 0
    traded_days = 0
    daily_returns: List[float] = []
    for d in complete:
        if d < start or d > end:
            continue
        idx = complete.index(d)
        if idx < LOOKBACK + 1:
            continue
        s = sessions[d]
        prior = [sessions[x] for x in complete[idx - LOOKBACK:idx]]
        sigma = {c: statistics.fmean(abs(p.price[c] / p.open - 1.0) for p in prior) for c in CHECKS}
        prev_day = days[days.index(d) - 1]
        prev_close = sessions[prev_day].close
        if prev_close is None:
            continue
        top = max(s.open, prev_close)
        bottom = min(s.open, prev_close)
        if sizing == "full":
            exposure = 1.0
        else:
            # the paper's sigma_SPY: sample stdev (n - 1 = 13) of the previous 14 daily
            # close-to-close returns, every session counted, early closes included
            at = days.index(d)
            closes = [sessions[x].close for x in days[at - LOOKBACK - 1:at]]
            if at < LOOKBACK + 1 or any(c is None for c in closes):
                continue
            rets = [closes[k] / closes[k - 1] - 1.0 for k in range(1, len(closes))]
            vol = statistics.stdev(rets)
            exposure = min(4.0, 0.02 / vol) if vol > 0 else 4.0
        shares = math.floor(equity * exposure / s.open)
        position, pnl, day_trades = 0, 0.0, 0
        marks = [s.price[c] for c in CHECKS] + [s.close_1600]
        for k, c in enumerate(CHECKS):
            price, vwap = s.price[c], s.vwap[c]
            upper, lower = top * (1.0 + sigma[c]), bottom * (1.0 - sigma[c])
            want = 1 if (price > upper and price > vwap) else (-1 if (price < lower and price < vwap) else 0)
            if want != position:
                pnl -= abs(want - position) * shares * cost_per_share
                if want != 0:
                    day_trades += 1
                position = want
            pnl += position * shares * (marks[k + 1] - price)
        if position != 0:
            pnl -= shares * cost_per_share               # flat at the close
        trades += day_trades
        traded_days += 1 if day_trades else 0
        daily_returns.append(pnl / equity)
        equity += pnl
        curve.append((d, equity))
    return {"curve": curve, "daily_returns": daily_returns, "trades": trades,
            "traded_days": traded_days}


def metrics(curve, daily_returns, rf_annual: float = 0.0) -> Dict[str, object]:
    if len(curve) < 2:
        return {}
    start_value = curve[0][1] / (1.0 + daily_returns[0])
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    total = curve[-1][1] / start_value - 1.0
    rf = (1 + rf_annual) ** (1 / 252) - 1
    ex = [r - rf for r in daily_returns]
    sd = statistics.stdev(daily_returns)
    peak, dd = start_value, 0.0
    for _, v in curve:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1.0)
    years_map, prev = {}, start_value
    last = {}
    for d, v in curve:
        last[d.year] = v
    for y in sorted(last):
        years_map[y] = last[y] / prev - 1.0
        prev = last[y]
    return {"total_return": total, "cagr": (1 + total) ** (1 / years) - 1 if total > -1 else -1.0,
            "volatility": sd * math.sqrt(252),
            "sharpe": statistics.fmean(ex) / sd * math.sqrt(252) if sd > 0 else None,
            "max_drawdown": dd, "worst_day": min(daily_returns), "best_day": max(daily_returns),
            "t_mean_daily": statistics.fmean(daily_returns) / (sd / math.sqrt(len(daily_returns))),
            "by_year": years_map, "sessions": len(daily_returns)}


def spy_hold(sessions: Dict[date, Session], start: date, end: date):
    """SPY held close to close. The first return is start's close over the
    previous session's close, so pass the strategy's first traded session to
    compare the same days."""
    every = sorted(sessions)
    first = next((d for d in every if d >= start), None)
    if first is not None and every.index(first) > 0:
        start = every[every.index(first) - 1]
    days = [d for d in every if start <= d <= end and sessions[d].close is not None]
    curve, rets = [], []
    prev = None
    for d in days:
        close = sessions[d].close
        if prev is not None:
            rets.append(close / prev - 1.0)
            curve.append((d, close))
        prev = close
    return curve, rets
