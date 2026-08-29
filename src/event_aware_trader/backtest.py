"""Conservative daily-bar backtest with an untouched final test segment.

It is intentionally a diagnostic.  There is no parameter search, and signals
only use bars that closed before the next bar's simulated entry.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence

from .risk import CostModel, RiskPolicy, position_size
from .strategy import StrategyConfig, generate_candidate
from .types import Action, Bar, Event, Trade


@dataclass(frozen=True)
class BacktestReport:
    label: str
    trades: List[Trade]
    starting_equity: float
    ending_equity: float
    net_return: float
    max_drawdown: float
    win_rate: float
    expectancy_r: float
    profit_factor: float
    total_costs: float

    def as_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "trade_count": len(self.trades),
            "starting_equity": round(self.starting_equity, 2),
            "ending_equity": round(self.ending_equity, 2),
            "net_return": round(self.net_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "win_rate": round(self.win_rate, 6),
            "expectancy_r": round(self.expectancy_r, 6),
            "profit_factor": None if self.profit_factor == float("inf") else round(self.profit_factor, 6),
            "total_costs": round(self.total_costs, 2),
            "trades": [trade.as_dict() for trade in self.trades],
        }


@dataclass(frozen=True)
class WalkForwardReport:
    in_sample: BacktestReport
    out_of_sample: BacktestReport
    split_index: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "method": "Fixed-rule chronological split; the final segment is untouched by parameter selection.",
            "split_index": self.split_index,
            "in_sample": self.in_sample.as_dict(),
            "out_of_sample": self.out_of_sample.as_dict(),
        }


def _summary(label: str, trades: List[Trade], starting_equity: float, equity_curve: List[float]) -> BacktestReport:
    ending_equity = equity_curve[-1] if equity_curve else starting_equity
    peak = starting_equity
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak:
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    expectancy_r = sum(trade.r_multiple for trade in trades) / len(trades) if trades else 0.0
    gross_wins = sum(trade.net_pnl for trade in wins)
    gross_losses = abs(sum(trade.net_pnl for trade in losses))
    profit_factor = gross_wins / gross_losses if gross_losses else (float("inf") if gross_wins else 0.0)
    return BacktestReport(
        label=label,
        trades=trades,
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        net_return=ending_equity / starting_equity - 1.0,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        expectancy_r=expectancy_r,
        profit_factor=profit_factor,
        total_costs=sum(trade.costs for trade in trades),
    )


def run_backtest(
    symbol: str,
    bars: Sequence[Bar],
    events: Sequence[Event],
    start_index: int,
    end_index: int,
    starting_equity: float = 10_000.0,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
    label: str = "sample",
) -> BacktestReport:
    """Run a single-position simulation over a half-open signal index range.

    At index ``i`` the strategy sees only ``bars[:i + 1]``.  It submits a
    simulated next-open entry at ``i + 1`` and never consults subsequent bars
    while deciding whether to enter.
    """
    if starting_equity <= 0:
        raise ValueError("starting_equity must be positive")
    first = max(start_index, config.minimum_history - 1)
    last = min(end_index, len(bars) - 1)
    equity = starting_equity
    equity_curve = [equity]
    trades: List[Trade] = []
    daily_realized: Dict[date, float] = {}
    weekly_realized: Dict[tuple, float] = {}
    index = first
    while index < last:
        visible = bars[: index + 1]
        # `generate_candidate` applies timestamp availability internally. Passing
        # the full sequence avoids unsafe naive/aware datetime comparisons here.
        signal_day = visible[-1].timestamp.date()
        signal_week = visible[-1].timestamp.isocalendar()[:2]
        candidate = generate_candidate(
            symbol,
            visible,
            events,
            equity,
            policy,
            costs,
            config,
            daily_realized_pnl=daily_realized.get(signal_day, 0.0),
            weekly_realized_pnl=weekly_realized.get(signal_week, 0.0),
        )
        if candidate.action != Action.PAPER_LONG or candidate.entry is None or candidate.stop is None or candidate.target is None:
            index += 1
            continue
        entry_bar = bars[index + 1]
        raw_entry = entry_bar.open
        entry_price = costs.buy_fill(raw_entry)
        fixed_stop = candidate.stop
        fixed_target = entry_price + config.reward_to_risk * (entry_price - fixed_stop)
        quantity, planned_risk = position_size(equity, entry_price, fixed_stop, policy, costs)
        if quantity <= 0:
            index += 1
            continue
        raw_exit_price = None
        exit_price = None
        exit_time = None
        exit_reason = "time_exit"
        hold = config.max_holding_bars
        exit_index = min(index + hold, last)
        for probe in range(index + 1, min(index + hold + 1, last + 1)):
            bar = bars[probe]
            stop_hit = bar.low <= fixed_stop
            target_hit = bar.high >= fixed_target
            if stop_hit and target_hit:
                # With daily bars the intraday order is unknowable. Use the adverse outcome.
                raw_exit_price = fixed_stop
                exit_price = costs.sell_fill(raw_exit_price)
                exit_reason = "stop_and_target_same_bar_conservative_stop"
                exit_time = bar.timestamp
                exit_index = probe
                break
            if stop_hit:
                raw_exit_price = fixed_stop
                exit_price = costs.sell_fill(raw_exit_price)
                exit_reason = "stop"
                exit_time = bar.timestamp
                exit_index = probe
                break
            if target_hit:
                raw_exit_price = fixed_target
                exit_price = costs.sell_fill(raw_exit_price)
                exit_reason = "target"
                exit_time = bar.timestamp
                exit_index = probe
                break
        if exit_price is None:
            time_bar = bars[exit_index]
            raw_exit_price = time_bar.close
            exit_price = costs.sell_fill(raw_exit_price)
            exit_time = time_bar.timestamp
        assert raw_exit_price is not None
        gross_pnl = (raw_exit_price - raw_entry) * quantity
        net_pnl = (exit_price - entry_price) * quantity - (costs.commission_per_share * 2.0 * quantity)
        estimated_costs = gross_pnl - net_pnl
        r_multiple = net_pnl / planned_risk if planned_risk else 0.0
        trade = Trade(
            symbol=symbol.upper(),
            signal_time=visible[-1].timestamp,
            entry_time=entry_bar.timestamp,
            exit_time=exit_time,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            stop=fixed_stop,
            target=fixed_target,
            gross_pnl=gross_pnl,
            costs=estimated_costs,
            net_pnl=net_pnl,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
        )
        trades.append(trade)
        equity += net_pnl
        equity_curve.append(equity)
        exit_day = exit_time.date()
        exit_week = exit_time.isocalendar()[:2]
        daily_realized[exit_day] = daily_realized.get(exit_day, 0.0) + net_pnl
        weekly_realized[exit_week] = weekly_realized.get(exit_week, 0.0) + net_pnl
        index = exit_index + 1
    return _summary(label, trades, starting_equity, equity_curve)


def walk_forward_backtest(
    symbol: str,
    bars: Sequence[Bar],
    events: Sequence[Event],
    initial_equity: float = 10_000.0,
    out_of_sample_fraction: float = 0.30,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
) -> WalkForwardReport:
    if not 0.10 <= out_of_sample_fraction <= 0.50:
        raise ValueError("out_of_sample_fraction must be between 0.10 and 0.50")
    split = int(len(bars) * (1.0 - out_of_sample_fraction))
    if split <= config.minimum_history or len(bars) - split < 10:
        raise ValueError("Need more bars for the requested walk-forward split")
    in_sample = run_backtest(
        symbol, bars, events, config.minimum_history - 1, split - 1, initial_equity, policy, costs, config, "in_sample"
    )
    out_of_sample = run_backtest(
        symbol, bars, events, split, len(bars) - 1, initial_equity, policy, costs, config, "out_of_sample"
    )
    return WalkForwardReport(in_sample=in_sample, out_of_sample=out_of_sample, split_index=split)
