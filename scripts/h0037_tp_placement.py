"""H-0037 engine: where the take profit should sit, replayed trade by trade.

The frozen baseline's 698 decade trades keep their entries, sizes and stops.
Each is replayed on its own daily bars under four take-profit placements:

  A  none - the frozen rule: stop, RSI(14) >= 60 at the close, 20 sessions
  B  the live one (EXP-0055): a resting sell limit at entry + 2.5 x entry ATR
  C  a resting sell limit at the bounce level - each session, the price at
     which today's close would put RSI(14) at 60, set from closes through the
     previous session (the bot's price files end at D-1)
  D  B and C together - one resting limit at the lower of the two

Fills: a stop fills at its level, or at the open when the open is through it;
a resting limit fills at its level, or at the open when the open is through
it. The open comes first, so an open through either decides the day; after
the open, a bar that reaches both a stop and a limit goes to the stop.
(portfolio.py checks the stop first even against an open through the limit;
the two differ only on a day that gaps through the target and later falls
through the stop.) Every fill pays the cost model's 6 bp a side. A sale at the
close by rule - the RSI exit in A and B, and the 20-session exit in all four -
also pays the rule-exit haircut h.

In C and D the close-based RSI exit cannot fire on its own: a close at or
above the bounce level means the session's high reached it, and the limit
already sold. RSI is Wilder's, exactly as the bot's indicators.rsi computes it.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

PERIOD = 14
RSI_EXIT = 60.0
SIDE_COST = 0.0006            # CostModel: 2 bp half-spread + 4 bp slippage, each side
HORIZON = 20
POLICIES = ("A", "B", "C", "D")


def wilder_averages(closes: Sequence[float], period: int = PERIOD) -> Tuple[List[float], List[float]]:
    """Average gain and loss through each close, exactly as indicators.rsi
    computes them (seeded with the simple mean of the first `period` changes,
    then Wilder's smoothing). NaN until there are period + 1 closes."""
    n = len(closes)
    ag = [math.nan] * n
    al = [math.nan] * n
    if n < period + 1:
        return ag, al
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, n)]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, n)]
    g = sum(gains[:period]) / period
    l_ = sum(losses[:period]) / period
    ag[period], al[period] = g, l_
    for i in range(period, len(gains)):
        g = (g * (period - 1) + gains[i]) / period
        l_ = (l_ * (period - 1) + losses[i]) / period
        ag[i + 1], al[i + 1] = g, l_
    return ag, al


def bounce_price(prev_close: float, ag: float, al: float, threshold: float = RSI_EXIT,
                 period: int = PERIOD) -> float:
    """The close today that would put RSI(period) exactly at `threshold`,
    given yesterday's close and Wilder averages."""
    k = threshold / (100.0 - threshold)              # the relative strength needed: 1.5 at 60
    m = period - 1
    if ag >= k * al:                                 # already there at an unchanged price
        return prev_close - (m * ag - m * k * al) / k
    return prev_close + m * (k * al - ag)


def replay(after: Sequence, ag: Sequence[float], al: Sequence[float], closes_prev: Sequence[float],
           raw_entry: float, stop: float, take: float, policy: str, haircut: float,
           horizon: int = HORIZON) -> Optional[Tuple[float, str, int]]:
    """(raw exit price, reason, sessions held) for one trade, or None when the
    data ends first. `after` are the bars after the entry session; ag[i],
    al[i], closes_prev[i] are the Wilder averages and close of the session
    BEFORE after[i]."""
    for i, bar in enumerate(after[:horizon]):
        held = i + 1
        if bar.open <= stop:
            return bar.open, "stop", held
        limit = None
        if policy in ("B", "D"):
            limit = take
        if policy in ("C", "D"):
            level = bounce_price(closes_prev[i], ag[i], al[i])
            limit = level if limit is None else min(limit, level)
        if limit is not None and bar.open >= limit:
            return bar.open, "limit", held
        if bar.low <= stop:
            return stop, "stop", held
        if limit is not None and bar.high >= limit:
            return limit, "limit", held
        if policy in ("A", "B"):
            # the RSI through this session's close, from yesterday's averages
            prev = closes_prev[i]
            change = bar.close - prev
            g = (ag[i] * (PERIOD - 1) + max(change, 0.0)) / PERIOD
            l_ = (al[i] * (PERIOD - 1) + max(-change, 0.0)) / PERIOD
            strength = 100.0 if l_ == 0 and g > 0 else (50.0 if l_ == 0 else 100.0 - 100.0 / (1.0 + g / l_))
            if strength >= RSI_EXIT:
                return bar.close * (1.0 - haircut), "reverted", held
        if held >= horizon:
            return bar.close * (1.0 - haircut), "time", held
    return None


def net_r(raw_exit: float, entry_fill: float, risk_per_share: float) -> float:
    """Profit per share after the exit's 6 bp, in units of the stop distance."""
    return (raw_exit * (1.0 - SIDE_COST) - entry_fill) / risk_per_share
