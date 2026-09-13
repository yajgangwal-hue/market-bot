"""One evaluation for every configuration, so comparisons are the same shape.

THE OBJECTIVE THIS SCORES. The agent's persistent objective, stated as a game
mechanic rather than a claim about anything it experiences:

    "Maximise long-term account growth while minimising the probability of
     catastrophic loss and shutdown."

Growth is geometric - the account compounds - so the headline is CAGR, not
average trade return. Shutdown is a drawdown the owner will not sit through,
so the second headline is the probability of reaching one. Everything else
here explains those two: where the money came from, what it cost in losing
trades, and - the part this project had never measured - how much of each
trade's available profit the exit actually kept.

Nothing in this module is a strategy. It only measures.

EXIT EFFICIENCY, the metric the exit work is judged on. For every closed
trade the simulator now records the highest high and lowest low seen while
open. From those:

    captured   = (exit - entry) / (highest_high - entry)
                 share of the best available profit the exit kept. 1.0 is a
                 perfect exit at the top; negative means the trade closed
                 below entry after having been in profit.
    gave_back  = (highest_high - exit) / entry
                 the profit that was there and was not taken, as a fraction
                 of entry. This is the "winner became a loser" failure the
                 owner named, in one number.
    heat       = (entry - lowest_low) / entry
                 the worst the trade went against before it closed.

An exit rule that raises `captured` while lowering `gave_back`, without
raising `heat`, is doing its job. One that raises the win rate while lowering
`captured` is taking small profits early - the rescue-exit failure, measured
on 2026-09-11 at -1.4 CAGR points.

PROBABILITY OF RUIN is estimated by block-bootstrapping the daily equity
returns: resample contiguous blocks of returns, rebuild the curve, and count
the share of resampled paths that breach the drawdown threshold. Blocks
rather than single days, so volatility clustering - the thing that produces
real drawdowns - survives the resampling.
"""

from dataclasses import dataclass, field
from datetime import date
from math import sqrt
from random import Random
from statistics import mean, median, pstdev
from typing import Dict, List, Optional, Sequence, Tuple

RUIN_DRAWDOWN = 0.25          # the drawdown treated as "shut off"
BOOTSTRAP_PATHS = 500
BLOCK_DAYS = 20


@dataclass
class Evaluation:
    label: str
    days: int
    years: float
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: Optional[float]
    sortino: Optional[float]
    ruin_probability: float
    trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    average_win: float
    average_loss: float
    average_hold_days: float
    longest_losing_run: int
    captured: float
    gave_back: float
    heat: float
    by_exit_reason: Dict[str, Dict[str, float]] = field(default_factory=dict)
    first_half_cagr: float = 0.0
    second_half_cagr: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        out = dict(self.__dict__)
        for key, value in list(out.items()):
            if isinstance(value, float):
                out[key] = round(value, 6)
        return out


def _daily_returns(curve: Sequence[Tuple[object, float]]) -> List[float]:
    out = []
    for i in range(1, len(curve)):
        previous, current = curve[i - 1][1], curve[i][1]
        if previous > 0:
            out.append(current / previous - 1.0)
    return out


def _max_drawdown(values: Sequence[float]) -> float:
    peak, worst = values[0] if values else 1.0, 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def _cagr(first: float, last: float, years: float) -> float:
    if first <= 0 or last <= 0 or years <= 0:
        return -1.0
    return (last / first) ** (1.0 / years) - 1.0


def _ratio(returns: Sequence[float], downside_only: bool) -> Optional[float]:
    if len(returns) < 20:
        return None
    average = mean(returns)
    if downside_only:
        downs = [min(0.0, r) for r in returns]
        deviation = sqrt(sum(d * d for d in downs) / len(downs))
    else:
        deviation = pstdev(returns)
    if deviation <= 0:
        return None
    return average / deviation * sqrt(252.0)


def ruin_probability(returns: Sequence[float], threshold: float = RUIN_DRAWDOWN,
                     paths: int = BOOTSTRAP_PATHS, block: int = BLOCK_DAYS,
                     seed: int = 20260913) -> float:
    """Share of block-bootstrapped equity paths that breach `threshold`."""
    if len(returns) < block * 2:
        return 0.0
    rng = Random(seed)
    breached = 0
    length = len(returns)
    for _ in range(paths):
        resampled: List[float] = []
        while len(resampled) < length:
            start = rng.randrange(0, length - block + 1)
            resampled.extend(returns[start:start + block])
        equity, peak = 1.0, 1.0
        for r in resampled[:length]:
            equity *= 1.0 + r
            peak = max(peak, equity)
            if equity / peak - 1.0 <= -threshold:
                breached += 1
                break
    return breached / paths


def _exit_quality(trade) -> Optional[Tuple[float, float, float]]:
    """(captured, gave_back, heat) for one trade, or None if unmeasurable."""
    entry = float(getattr(trade, "entry_price", 0.0) or 0.0)
    exit_price = float(getattr(trade, "exit_price", 0.0) or 0.0)
    high = float(getattr(trade, "highest_high", 0.0) or 0.0)
    low = float(getattr(trade, "lowest_low", 0.0) or 0.0)
    if entry <= 0 or exit_price <= 0 or high <= 0:
        return None
    available = high - entry
    captured = ((exit_price - entry) / available) if available > 0 else 1.0
    gave_back = max(0.0, high - exit_price) / entry
    heat = (max(0.0, entry - low) / entry) if low > 0 else 0.0
    return captured, gave_back, heat


def evaluate(report, label: str = "", split: Optional[date] = None) -> Evaluation:
    """Score a PortfolioReport. Works on any object with the same fields."""
    curve = list(report.equity_curve)
    values = [v for _s, v in curve]
    returns = _daily_returns(curve)
    days = len(curve)
    years = days / 252.0 if days else 0.0
    first, last = (values[0], values[-1]) if values else (1.0, 1.0)

    trades = list(report.trades)
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    gross_win = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))

    run, longest = 0, 0
    for t in sorted(trades, key=lambda x: x.exit_time):
        run = run + 1 if t.net_pnl <= 0 else 0
        longest = max(longest, run)

    quality = [q for q in (_exit_quality(t) for t in trades) if q is not None]
    captured = mean(q[0] for q in quality) if quality else 0.0
    gave_back = mean(q[1] for q in quality) if quality else 0.0
    heat = mean(q[2] for q in quality) if quality else 0.0

    by_reason: Dict[str, Dict[str, float]] = {}
    for reason in sorted({t.exit_reason for t in trades}):
        subset = [t for t in trades if t.exit_reason == reason]
        sub_quality = [q for q in (_exit_quality(t) for t in subset) if q]
        by_reason[reason] = {
            "trades": len(subset),
            "win_rate": sum(1 for t in subset if t.net_pnl > 0) / len(subset),
            "total_pnl": sum(t.net_pnl for t in subset),
            "captured": mean(q[0] for q in sub_quality) if sub_quality else 0.0,
            "gave_back": mean(q[1] for q in sub_quality) if sub_quality else 0.0,
        }

    first_half = second_half = 0.0
    if split is not None and curve:
        at = next((i for i, (s, _v) in enumerate(curve)
                   if getattr(s, "date", lambda: s)() >= split), None)
        if at:
            first_half = _cagr(values[0], values[at], at / 252.0)
            second_half = _cagr(values[at], values[-1], (days - at) / 252.0)

    return Evaluation(
        label=label,
        days=days,
        years=years,
        total_return=(last / first - 1.0) if first > 0 else 0.0,
        cagr=_cagr(first, last, years),
        max_drawdown=_max_drawdown(values) if values else 0.0,
        sharpe=_ratio(returns, downside_only=False),
        sortino=_ratio(returns, downside_only=True),
        ruin_probability=ruin_probability(returns),
        trades=len(trades),
        win_rate=(len(wins) / len(trades)) if trades else 0.0,
        profit_factor=(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        expectancy=(sum(t.net_pnl for t in trades) / len(trades)) if trades else 0.0,
        average_win=(gross_win / len(wins)) if wins else 0.0,
        average_loss=(-gross_loss / len(losses)) if losses else 0.0,
        average_hold_days=mean(t.bars_held for t in trades) if trades else 0.0,
        longest_losing_run=longest,
        captured=captured,
        gave_back=gave_back,
        heat=heat,
        by_exit_reason=by_reason,
        first_half_cagr=first_half,
        second_half_cagr=second_half,
    )


def table(rows: Sequence[Evaluation]) -> str:
    """The comparison, one line per configuration."""
    head = ("{0:<30}{1:>8}{2:>8}{3:>7}{4:>7}{5:>8}{6:>7}{7:>7}{8:>9}{9:>9}"
            "{10:>9}{11:>9}").format(
        "", "CAGR", "maxDD", "Sharpe", "ruin", "trades", "win%", "PF",
        "captured", "gaveback", "1st", "2nd")
    lines = [head, "-" * len(head)]
    for e in rows:
        lines.append("{0:<30}{1:>8.2%}{2:>8.1%}{3:>7}{4:>7.1%}{5:>8}{6:>7.0%}"
                     "{7:>7.2f}{8:>9.2f}{9:>9.2%}{10:>9.2%}{11:>9.2%}".format(
                         e.label[:30], e.cagr, e.max_drawdown,
                         "-" if e.sharpe is None else "{0:.2f}".format(e.sharpe),
                         e.ruin_probability, e.trades, e.win_rate,
                         min(e.profit_factor, 99.0), e.captured, e.gave_back,
                         e.first_half_cagr, e.second_half_cagr))
    return "\n".join(lines)
