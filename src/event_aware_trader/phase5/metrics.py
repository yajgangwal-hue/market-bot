"""Phase 5 §9. The full metric set, including the ones that spoil a story.

`evaluation.evaluate` already gives CAGR, Sharpe, Sortino, drawdown, win
rate, profit factor and expectancy. This adds what the brief asks for and
that function does not report: annualised volatility, Calmar, the share of
profitable years, median and mean trade, turnover, modelled transaction
costs, exposure, the worst single loss, and per-year and per-regime
breakdowns.

Two of these exist specifically to stop a candidate looking better than it
is. **Volatility and Calmar** catch the candidate that earns more only by
risking more - the brief requires such a candidate to be identified as
such rather than ranked first. **Turnover and costs** catch the candidate
whose edge is smaller than the friction needed to harvest it, which is the
usual fate of a filter that trades more often.
"""

from dataclasses import dataclass, field
from datetime import date
from statistics import pstdev
from typing import Dict, List, Optional, Sequence, Tuple

TRADING_DAYS = 252.0


def _median(values: Sequence[float]) -> Optional[float]:
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def daily_returns(curve: Sequence[Tuple[object, float]]) -> List[float]:
    out = []
    for i in range(1, len(curve)):
        previous, current = curve[i - 1][1], curve[i][1]
        if previous > 0:
            out.append(current / previous - 1.0)
    return out


def annualised_volatility(curve) -> Optional[float]:
    returns = daily_returns(curve)
    if len(returns) < 2:
        return None
    return pstdev(returns) * (TRADING_DAYS ** 0.5)


def yearly_returns(curve) -> Dict[int, float]:
    """Calendar-year return of the equity curve, first and last year included.

    Partial years are kept and labelled by their year rather than dropped:
    dropping a bad partial year is a quiet way to raise the share of
    profitable ones.
    """
    by_year: Dict[int, List[float]] = {}
    for stamp, value in curve:
        year = stamp.year if hasattr(stamp, "year") else date.today().year
        by_year.setdefault(year, []).append(value)
    return {y: (v[-1] / v[0] - 1.0) if v and v[0] else 0.0
            for y, v in sorted(by_year.items())}


def modelled_costs(trades, costs) -> float:
    """What the simulator charged in spread and slippage, reconstructed.

    The simulator folds friction into the fill prices, so the figure is not
    stored anywhere. It is rebuilt from the round-trip notional and the
    cost model's own basis points, and is an estimate of a modelled
    quantity - not a measurement of a real one.
    """
    rate = (costs.half_spread_bps + costs.slippage_bps) / 10_000.0
    total = 0.0
    for t in trades:
        total += abs(t.quantity) * (abs(t.entry_price) + abs(t.exit_price)) * rate
        total += abs(t.quantity) * 2 * getattr(costs, "commission_per_share", 0.0)
    return total


def exposure(report) -> Optional[float]:
    """Mean invested fraction across the run, from the cash curve."""
    equity = dict(report.equity_curve)
    if not report.cash_curve or not equity:
        return None
    shares = []
    for stamp, cash in report.cash_curve:
        total = equity.get(stamp)
        if total and total > 0:
            shares.append(max(0.0, 1.0 - cash / total))
    return sum(shares) / len(shares) if shares else None


def turnover(report) -> Optional[float]:
    """Round-trip notional per year, as a multiple of starting capital."""
    curve = report.equity_curve
    if not curve or not report.starting_cash:
        return None
    years = len(curve) / TRADING_DAYS
    if years <= 0:
        return None
    traded = sum(abs(t.quantity) * (abs(t.entry_price) + abs(t.exit_price))
                 for t in report.trades)
    return traded / report.starting_cash / years


@dataclass
class FullMetrics:
    label: str
    # return and risk
    total_return: float = 0.0
    cagr: float = 0.0
    annualised_volatility: Optional[float] = None
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    max_drawdown: float = 0.0
    calmar: Optional[float] = None
    profitable_years: Optional[float] = None
    years: float = 0.0
    # trades
    trades: int = 0
    win_rate: float = 0.0
    average_trade: Optional[float] = None
    median_trade: Optional[float] = None
    average_winner: Optional[float] = None
    average_loser: Optional[float] = None
    worst_loss: Optional[float] = None
    profit_factor: float = 0.0
    expectancy: float = 0.0
    longest_losing_run: int = 0
    average_hold_days: float = 0.0
    stop_rate: Optional[float] = None
    # frictions
    turnover: Optional[float] = None
    transaction_costs: Optional[float] = None
    exposure: Optional[float] = None
    # breakdowns
    by_year: Dict[int, float] = field(default_factory=dict)
    by_exit_reason: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        out = {}
        for key, value in self.__dict__.items():
            out[key] = round(value, 6) if isinstance(value, float) else value
        return out

    def headline(self) -> Dict[str, object]:
        """The subset used for baseline-versus-candidate comparison."""
        return {k: getattr(self, k) for k in (
            "total_return", "cagr", "annualised_volatility", "sharpe",
            "sortino", "max_drawdown", "calmar", "profitable_years",
            "trades", "win_rate", "average_trade", "median_trade",
            "worst_loss", "profit_factor", "expectancy", "stop_rate",
            "turnover", "transaction_costs", "exposure")}


def measure(report, label: str, costs=None) -> FullMetrics:
    """Every §9 metric from one portfolio report."""
    from ..evaluation import evaluate
    from ..risk import CostModel

    costs = costs or CostModel()
    scored = evaluate(report, label)
    curve = report.equity_curve
    trades = list(report.trades)
    pnls = [t.net_pnl for t in trades]
    years = yearly_returns(curve)
    vol = annualised_volatility(curve)

    return FullMetrics(
        label=label,
        total_return=scored.total_return,
        cagr=scored.cagr,
        annualised_volatility=vol,
        sharpe=scored.sharpe,
        sortino=scored.sortino,
        max_drawdown=scored.max_drawdown,
        calmar=(scored.cagr / abs(scored.max_drawdown)
                if scored.max_drawdown else None),
        profitable_years=(sum(1 for v in years.values() if v > 0) / len(years)
                          if years else None),
        years=scored.years,
        trades=len(trades),
        win_rate=scored.win_rate,
        average_trade=(sum(pnls) / len(pnls) if pnls else None),
        median_trade=_median(pnls),
        average_winner=scored.average_win,
        average_loser=scored.average_loss,
        worst_loss=(min(pnls) if pnls else None),
        profit_factor=scored.profit_factor,
        expectancy=scored.expectancy,
        longest_losing_run=scored.longest_losing_run,
        average_hold_days=scored.average_hold_days,
        stop_rate=(sum(1 for t in trades if t.exit_reason == "stop") / len(trades)
                   if trades else None),
        turnover=turnover(report),
        transaction_costs=modelled_costs(trades, costs),
        exposure=exposure(report),
        by_year=years,
        by_exit_reason=scored.by_exit_reason)


def compare(candidate: FullMetrics, baseline: FullMetrics) -> Dict[str, object]:
    """Candidate minus baseline, plus the risk warning the brief requires."""
    out: Dict[str, object] = {}
    a, b = candidate.headline(), baseline.headline()
    for key, value in a.items():
        other = b.get(key)
        if isinstance(value, (int, float)) and isinstance(other, (int, float)):
            out[key] = round(float(value) - float(other), 6)
    riskier = []
    if (candidate.annualised_volatility and baseline.annualised_volatility
            and candidate.annualised_volatility >
            baseline.annualised_volatility * 1.10):
        riskier.append("annualised volatility is more than 10% higher")
    if abs(candidate.max_drawdown) > abs(baseline.max_drawdown) * 1.10:
        riskier.append("maximum drawdown is more than 10% deeper")
    out["higher_risk"] = riskier
    out["return_bought_with_risk"] = bool(riskier and
                                          candidate.cagr > baseline.cagr)
    return out
