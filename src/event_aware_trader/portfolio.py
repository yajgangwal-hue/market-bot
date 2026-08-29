"""Single-account portfolio simulation across the whole universe.

``backtest.run_backtest`` simulates one symbol against its own private
starting balance.  Running it seven times answers "how would seven separate
accounts have done", which is not the question anyone actually has.  A real
account has **one** cash balance: capital committed to XLE is capital that
cannot also back a QQQ entry, the open-position cap applies across all
symbols at once, and a loss in one name closes the daily guard for every
other.  Those interactions are the whole point of a portfolio, and they are
invisible to a per-symbol run.

Ordering within a day is deliberate and conservative:

1. Queued entries fill at today's open.
2. Open positions are then checked against today's range.  A position that
   filled this morning can be stopped out this afternoon; when a single daily
   bar touches both stop and target the adverse fill is assumed, because the
   intraday sequence is unknowable from daily data.
3. Only after the close are new signals formed, and they queue for the *next*
   open.  Nothing entered on the strength of a bar it could not have seen.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .indicators import wilder_atr
from .risk import CostModel, RiskPolicy, evaluate_guard, position_size
from .strategy import CORRELATION_BUCKETS, StrategyConfig, generate_candidate
from .types import Action, Bar, Event


@dataclass
class OpenPosition:
    symbol: str
    bucket: str
    quantity: float
    entry_price: float
    raw_entry: float
    stop: float
    target: float
    entry_time: datetime
    signal_time: datetime
    planned_risk: float
    bars_held: int = 0
    highest_high: float = 0.0
    initial_stop: float = 0.0
    trailing_active: bool = False


@dataclass
class ClosedTrade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    quantity: float
    entry_price: float
    exit_price: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    bars_held: int


@dataclass
class PortfolioReport:
    starting_cash: float
    cash: float
    invested: float
    equity: float
    trades: List[ClosedTrade] = field(default_factory=list)
    open_positions: List[OpenPosition] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    days_simulated: int = 0
    rejected_for_capacity: int = 0

    @property
    def wins(self) -> List[ClosedTrade]:
        return [t for t in self.trades if t.net_pnl > 0]

    @property
    def losses(self) -> List[ClosedTrade]:
        return [t for t in self.trades if t.net_pnl <= 0]

    @property
    def win_rate(self) -> float:
        return len(self.wins) / len(self.trades) if self.trades else 0.0

    @property
    def realized_pnl(self) -> float:
        return sum(t.net_pnl for t in self.trades)

    @property
    def max_drawdown(self) -> float:
        peak, worst = self.starting_cash, 0.0
        for _, value in self.equity_curve:
            peak = max(peak, value)
            if peak > 0:
                worst = min(worst, value / peak - 1.0)
        return worst


def _merged_dates(series: Dict[str, List[Bar]]) -> List[date]:
    seen = set()
    for bars in series.values():
        seen.update(bar.timestamp.date() for bar in bars)
    return sorted(seen)


def run_portfolio(
    series: Dict[str, List[Bar]],
    events: Sequence[Event] = (),
    starting_cash: float = 1_000.0,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
    warmup: Optional[int] = None,
) -> PortfolioReport:
    """Simulate one account trading every symbol in ``series`` together."""
    if starting_cash <= 0:
        raise ValueError("starting_cash must be positive")

    by_date: Dict[str, Dict[date, Bar]] = {
        symbol: {bar.timestamp.date(): bar for bar in bars} for symbol, bars in series.items()
    }
    history: Dict[str, List[Bar]] = {symbol: [] for symbol in series}
    warmup_bars = warmup if warmup is not None else config.minimum_history

    cash = starting_cash
    open_positions: Dict[str, OpenPosition] = {}
    pending: List[Tuple[str, float, float, float, float, datetime]] = []
    report = PortfolioReport(starting_cash=starting_cash, cash=cash, invested=0.0, equity=cash)
    daily_realized: Dict[date, float] = {}
    weekly_realized: Dict[tuple, float] = {}

    for current in _merged_dates(series):
        todays_bars = {s: by_date[s][current] for s in series if current in by_date[s]}
        if not todays_bars:
            continue
        report.days_simulated += 1
        week_key = next(iter(todays_bars.values())).timestamp.isocalendar()[:2]

        # ---- 1. fill queued entries at today's open -------------------------
        for symbol, quantity, stop, target, planned_risk, signal_time in pending:
            bar = todays_bars.get(symbol)
            if bar is None or symbol in open_positions:
                continue
            fill = costs.buy_fill(bar.open)
            outlay = fill * quantity
            if outlay > cash:  # capital already committed elsewhere
                report.rejected_for_capacity += 1
                continue
            cash -= outlay
            open_positions[symbol] = OpenPosition(
                symbol=symbol,
                bucket=CORRELATION_BUCKETS.get(symbol, "other"),
                quantity=quantity,
                entry_price=fill,
                raw_entry=bar.open,
                stop=stop,
                target=target,
                entry_time=bar.timestamp,
                signal_time=signal_time,
                planned_risk=planned_risk,
                highest_high=bar.high,
                initial_stop=stop,
            )
        pending = []

        # ---- 2. manage open positions against today's range -----------------
        for symbol in list(open_positions):
            bar = todays_bars.get(symbol)
            if bar is None:
                continue
            position = open_positions[symbol]
            position.bars_held += 1
            position.highest_high = max(position.highest_high, bar.high)

            exit_raw = exit_reason = None
            if config.stays_invested:
                # Ratchet the stop up behind the run, never down.  The original
                # stop stays in force until the trade has earned
                # `trail_activate_r`, so a position is not shaken out by noise
                # before it has done anything.
                risk_per_share = position.raw_entry - position.initial_stop
                if risk_per_share > 0:
                    gain_r = (position.highest_high - position.raw_entry) / risk_per_share
                    if gain_r >= config.trail_activate_r:
                        position.trailing_active = True
                if position.trailing_active:
                    atr = wilder_atr(history[symbol], config.atr_days) if config.use_wilder_atr else None
                    if atr:
                        position.stop = max(
                            position.stop, position.highest_high - config.trail_atr_multiple * atr
                        )
                if bar.low <= position.stop:
                    exit_raw = position.stop
                    exit_reason = "trailing_stop" if position.trailing_active else "stop"
                elif position.bars_held >= config.max_trailing_bars:
                    exit_raw, exit_reason = bar.close, "max_hold_backstop"
            else:
                stop_hit = bar.low <= position.stop
                target_hit = bar.high >= position.target
                if stop_hit and target_hit:
                    exit_raw, exit_reason = position.stop, "stop_and_target_same_bar_conservative_stop"
                elif stop_hit:
                    exit_raw, exit_reason = position.stop, "stop"
                elif target_hit:
                    exit_raw, exit_reason = position.target, "target"
                elif position.bars_held >= config.max_holding_bars:
                    exit_raw, exit_reason = bar.close, "time_exit"
            if exit_raw is None:
                continue

            fill = costs.sell_fill(exit_raw)
            proceeds = fill * position.quantity
            cash += proceeds
            net = (fill - position.entry_price) * position.quantity
            report.trades.append(
                ClosedTrade(
                    symbol=symbol,
                    entry_time=position.entry_time,
                    exit_time=bar.timestamp,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    exit_price=fill,
                    net_pnl=net,
                    r_multiple=net / position.planned_risk if position.planned_risk else 0.0,
                    exit_reason=exit_reason,
                    bars_held=position.bars_held,
                )
            )
            daily_realized[current] = daily_realized.get(current, 0.0) + net
            weekly_realized[week_key] = weekly_realized.get(week_key, 0.0) + net
            del open_positions[symbol]

        # ---- 3. after the close, form signals for the next open -------------
        for symbol, bar in todays_bars.items():
            history[symbol].append(bar)
        invested = sum(
            p.quantity * todays_bars[p.symbol].close
            for p in open_positions.values()
            if p.symbol in todays_bars
        )
        equity = cash + invested
        report.equity_curve.append((next(iter(todays_bars.values())).timestamp, equity))

        # Candidates queued earlier in this same loop are not open positions
        # yet, but they will be by tomorrow's open.  Counting only
        # `open_positions` here would let two names from one correlation
        # bucket queue on the same day and defeat the cap the guard exists to
        # enforce, so pending entries are folded into both checks.
        open_buckets = {p.bucket for p in open_positions.values()}
        pending_buckets = set()
        for symbol, bar in todays_bars.items():
            if symbol in open_positions or len(history[symbol]) < warmup_bars:
                continue
            if any(queued[0] == symbol for queued in pending):
                continue
            guard = evaluate_guard(
                equity,
                daily_realized.get(current, 0.0),
                weekly_realized.get(week_key, 0.0),
                len(open_positions) + len(pending),
                CORRELATION_BUCKETS.get(symbol, "other"),
                open_buckets | pending_buckets,
                policy,
            )
            if not guard.allowed:
                continue
            candidate = generate_candidate(
                symbol,
                history[symbol],
                events,
                equity,
                policy,
                costs,
                config,
                open_positions=len(open_positions) + len(pending),
                open_buckets=open_buckets | pending_buckets,
                daily_realized_pnl=daily_realized.get(current, 0.0),
                weekly_realized_pnl=weekly_realized.get(week_key, 0.0),
            )
            if candidate.action != Action.PAPER_LONG:
                continue
            if candidate.entry is None or candidate.stop is None or candidate.target is None:
                continue
            quantity, planned_risk = position_size(equity, candidate.entry, candidate.stop, policy, costs)
            if quantity <= 0:
                continue
            pending.append((symbol, quantity, candidate.stop, candidate.target, planned_risk, bar.timestamp))
            pending_buckets.add(CORRELATION_BUCKETS.get(symbol, "other"))

    last_bars = {s: bars[-1] for s, bars in series.items() if bars}
    report.cash = cash
    report.invested = sum(
        p.quantity * last_bars[p.symbol].close for p in open_positions.values() if p.symbol in last_bars
    )
    report.equity = report.cash + report.invested
    report.open_positions = list(open_positions.values())
    return report
