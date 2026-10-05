"""H-0034 / H-0035 engine: the two other published index day-trading rules by
Zarattini & Aziz, tested on SPY 5-minute bars.

H-0034 - "Can Day Trading Really Be Profitable?" (first version 2023-04-24),
5-minute opening range breakout, from the paper's text and its Table 1:
  direction   the first 5-minute candle: up (close > open) long, down short,
              open == close (doji) no trade
  entry       the open of the second 5-minute candle (09:35)
  stop        long: the first candle's low; short: its high.  R = |entry - stop|
  target      10R, else out at the 16:00 close
  size        Shares = int(min(A * 0.01 / R, 4 * A / P))  - 1% risk, 4x cap
  costs       paper: $0.0005 a share, no slippage

H-0035 - "Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading
Systems" (dated 2023-11-13):
  VWAP        sum(HLC * volume) / sum(volume), regular session only, HLC the
              typical price (high + low + close) / 3
  first trade after the first candle closes: long above VWAP, short below
  after       reverse whenever a candle closes on the other side of VWAP;
              always long or short until the 16:00 close; nothing overnight
  size        all equity, no leverage
  costs       paper: $0.0005 a share, no slippage
The paper used 1-minute candles and says the same rule can be run on
5-minute candles; the store holds 5-minute bars, so this is that version.

Fills, both rules. A decision made on a candle's close is filled at the next
candle's open (the 16:00 exit is the last candle's close). A target inside a
candle fills at its level (a resting limit); a stop inside a candle fills one
cent beyond its level (a stop order fills at the next price, and SPY's tick is
a cent); either fills at the candle's open when the candle opens beyond it;
when one candle reaches both, the stop is assumed first.

Validation of the candle logic. On a driftless walk that moves one cent at a
time from $450 (SPY's tick; 2,916 ticks a candle), the engine with stops at
their level matched an exact tick-by-tick simulation on 3,932 of 3,932 trades.
Coarser synthetic paths flatter level fills because they hide the overshoot
between steps (60 steps a candle: +0.068R a trade against -0.008R exact; 600
steps: a +0.022R gap). A real stop order fills at the next available price,
so the one-cent allowance is deliberate and conservative.
"""

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from h0033_noise_area import EARLY_CLOSES, NEW_YORK

BARS_PER_SESSION = 78                       # 09:30 .. 15:55 starts
STOP_SLIPPAGE = 0.01                        # dollars a share beyond the stop level


def load_bars(folder: Path) -> Dict[date, List[dict]]:
    """Regular-session bars per session, merged by timestamp across the
    quarterly files (the first day of a quarter sits in two), after-hours bars
    on 13:00 early closes dropped. Each bar: minute (from midnight), o h l c v."""
    merged: Dict[str, dict] = {}
    for path in sorted(Path(folder).glob("SPY_*.json")):
        for bar in json.loads(path.read_text(encoding="utf-8"))["bars"]["SPY"]:
            merged[str(bar["t"])] = bar
    return sessions_from(merged.values())


def sessions_from(bars) -> Dict[date, List[dict]]:
    out: Dict[date, List[dict]] = {}
    for bar in bars:
        start = datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00")).astimezone(NEW_YORK)
        minute = start.hour * 60 + start.minute
        last = 12 * 60 + 55 if start.date() in EARLY_CLOSES else 15 * 60 + 55
        if 9 * 60 + 30 <= minute <= last:
            out.setdefault(start.date(), []).append(
                {"minute": minute, "o": float(bar["o"]), "h": float(bar["h"]),
                 "l": float(bar["l"]), "c": float(bar["c"]), "v": float(bar.get("v") or 0.0)})
    for day in out:
        out[day].sort(key=lambda b: b["minute"])
    return out


def complete(bars: List[dict]) -> bool:
    return (len(bars) == BARS_PER_SESSION
            and all(b["minute"] == 9 * 60 + 30 + 5 * i for i, b in enumerate(bars)))


def orb_day(bars: List[dict], equity: float, cost: float, stop_slippage: float = STOP_SLIPPAGE):
    """One session of the opening range breakout. Returns (pnl, traded, outcome)."""
    first, second = bars[0], bars[1]
    if first["c"] == first["o"]:
        return 0.0, False, "doji"
    side = 1 if first["c"] > first["o"] else -1
    entry = second["o"]
    stop = first["l"] if side == 1 else first["h"]
    risk = (entry - stop) * side
    if risk <= 0:                                   # opened through the stop already
        return 0.0, False, "no_risk"
    target = entry + side * 10.0 * risk
    shares = math.floor(min(equity * 0.01 / risk, 4.0 * equity / entry))
    if shares <= 0:
        return 0.0, False, "no_size"
    exit_price, outcome = bars[-1]["c"], "close"
    for k, bar in enumerate(bars[1:], start=1):
        o = entry if k == 1 else bar["o"]
        if side == 1:
            if o <= stop:
                exit_price, outcome = o, "stop"
                break
            if bar["l"] <= stop:
                exit_price, outcome = stop - stop_slippage, "stop"
                break
            if o >= target:
                exit_price, outcome = o, "target"
                break
            if bar["h"] >= target:
                exit_price, outcome = target, "target"
                break
        else:
            if o >= stop:
                exit_price, outcome = o, "stop"
                break
            if bar["h"] >= stop:
                exit_price, outcome = stop + stop_slippage, "stop"
                break
            if o <= target:
                exit_price, outcome = o, "target"
                break
            if bar["l"] <= target:
                exit_price, outcome = target, "target"
                break
    pnl = side * shares * (exit_price - entry) - 2.0 * shares * cost
    return pnl, True, outcome


def vwap_day(bars: List[dict], equity: float, cost: float):
    """One session of VWAP trend trading. Returns (pnl, trades)."""
    pv = vol = 0.0
    position, shares, entry_price = 0, 0, 0.0
    pnl, trades = 0.0, 0
    for k, bar in enumerate(bars):
        typical = (bar["h"] + bar["l"] + bar["c"]) / 3.0
        pv += typical * bar["v"]
        vol += bar["v"]
        if k == len(bars) - 1 or vol <= 0:
            continue
        vwap = pv / vol
        want = 1 if bar["c"] > vwap else (-1 if bar["c"] < vwap else position)
        if want != position and want != 0:
            fill = bars[k + 1]["o"]
            if position != 0:
                pnl += position * shares * (fill - entry_price) - shares * cost
            shares = math.floor((equity + pnl) / fill)
            position, entry_price = want, fill
            pnl -= shares * cost
            trades += 1
    if position != 0:
        pnl += position * shares * (bars[-1]["c"] - entry_price) - shares * cost
    return pnl, trades


def run(sessions: Dict[date, List[dict]], start: date, end: date, rule: str,
        cost_per_share: float, capital: float = 100_000.0,
        stop_slippage: float = STOP_SLIPPAGE) -> Dict[str, object]:
    """The rule over every complete session in [start, end]; a session with no
    trade counts as a zero return. Incomplete sessions are skipped."""
    equity, curve, rets = capital, [], []
    trades = traded = 0
    outcomes: Dict[str, int] = {}
    for day in sorted(sessions):
        if day < start or day > end or not complete(sessions[day]):
            continue
        if rule == "orb":
            pnl, did, outcome = orb_day(sessions[day], equity, cost_per_share, stop_slippage)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            n = 1 if did else 0
        else:
            pnl, n = vwap_day(sessions[day], equity, cost_per_share)
        trades += n
        traded += 1 if n else 0
        rets.append(pnl / equity)
        equity += pnl
        curve.append((day, equity))
    return {"curve": curve, "daily_returns": rets, "trades": trades,
            "traded_days": traded, "outcomes": outcomes}
