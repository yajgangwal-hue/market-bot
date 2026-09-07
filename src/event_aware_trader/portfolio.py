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
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from .indicators import rsi, wilder_atr
from .risk import CostModel, RiskPolicy, evaluate_guard, position_size
from .mean_reversion import MeanReversionConfig
from .mean_reversion import evaluate as mean_reversion_signal
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
    initial_stop: float = 0.0
    exit_stop: float = 0.0


@dataclass
class PortfolioReport:
    starting_cash: float
    cash: float
    invested: float
    equity: float
    trades: List[ClosedTrade] = field(default_factory=list)
    open_positions: List[OpenPosition] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    # Uninvested cash at each step. The strategy holds about 3.4 positions and
    # sits in cash the rest of the time; without this there was no way to see
    # how much of the account was idle while the market compounded.
    cash_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    days_simulated: int = 0
    rejected_for_capacity: int = 0
    gapped_through_stop: int = 0

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


def _is_daily(series: Dict[str, List[Bar]]) -> bool:
    """One bar per calendar date for every symbol."""
    return all(
        len({b.timestamp.date() for b in bars}) == len(bars)
        for bars in series.values() if bars
    )


def _bar_key(bar: Bar, daily: bool) -> datetime:
    """A timeline key that two data sources can agree on.

    Keying on ``.date()`` would collapse the 26 fifteen-minute bars of a
    session into one entry and silently discard 25 of them, which made this
    simulator daily-only. Keying on the full timestamp lets the same code run
    any interval; the loss guards below still bucket by calendar day and ISO
    week, because those limits are defined per day and per week no matter how
    finely the session is sliced.

    But the price files on disk come from two sources with two conventions:
    120 of them are naive and stamped 16:00 local (the session close), and 110
    are timezone-aware and stamped 04:00+00:00 (midnight ET). Sorting the two
    together raised "can't compare offset-naive and offset-aware datetimes",
    and merely stripping the tzinfo would have been worse than the crash - the
    same trading day would appear as two different keys twelve hours apart, so
    half the universe would be invisible on any given step and positions would
    never see each other's cash.

    For daily data the calendar date is the only key both conventions agree
    on, so that is what is used. Intraday keeps the full timestamp, normalised
    to naive UTC so a mixed set still sorts.
    """
    stamp = bar.timestamp
    if daily:
        return datetime(stamp.year, stamp.month, stamp.day)
    if stamp.tzinfo is not None:
        return stamp.astimezone(timezone.utc).replace(tzinfo=None)
    return stamp


def _merged_timestamps(series: Dict[str, List[Bar]], daily: bool) -> List[datetime]:
    """Every distinct step across the universe, in order."""
    seen = set()
    for bars in series.values():
        seen.update(_bar_key(bar, daily) for bar in bars)
    return sorted(seen)


def run_portfolio(
    series: Dict[str, List[Bar]],
    events: Sequence[Event] = (),
    starting_cash: float = 1_000.0,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
    warmup: Optional[int] = None,
    veto=None,
    trade_from: Optional[date] = None,
    entry_rule: str = "trend",
    mr_config: Optional[MeanReversionConfig] = None,
    conviction=None,
) -> PortfolioReport:
    """Simulate one account trading every symbol in ``series`` together.

    `entry_rule` selects which rule decides entries AND exits, because the two
    belong together: mean reversion places a fixed stop and leaves on RSI
    recovery, while the trend path trails. This module only knew the trend
    rule, which is why it went unused once the live config moved to mean
    reversion - and why every profitability figure this project has quoted was
    produced by `backtest.run_backtest`, which gives each symbol its own
    private cash balance and therefore answers a question nobody has.
    """
    if entry_rule not in {"trend", "mean_reversion"}:
        raise ValueError("entry_rule must be 'trend' or 'mean_reversion'")
    mr_cfg = mr_config or MeanReversionConfig()
    if starting_cash <= 0:
        raise ValueError("starting_cash must be positive")

    daily_bars = _is_daily(series)
    by_stamp: Dict[str, Dict[datetime, Bar]] = {
        symbol: {_bar_key(bar, daily_bars): bar for bar in bars}
        for symbol, bars in series.items()
    }
    history: Dict[str, List[Bar]] = {symbol: [] for symbol in series}
    warmup_bars = warmup if warmup is not None else config.minimum_history

    cash = starting_cash
    open_positions: Dict[str, OpenPosition] = {}
    pending: List[Tuple[str, float, float, float, float, datetime, float]] = []
    report = PortfolioReport(starting_cash=starting_cash, cash=cash, invested=0.0, equity=cash)
    daily_realized: Dict[date, float] = {}
    session_bar_counts: Dict[date, int] = {}
    weekly_realized: Dict[tuple, float] = {}

    for stamp in _merged_timestamps(series, daily_bars):
        todays_bars = {s: by_stamp[s][stamp] for s in series if stamp in by_stamp[s]}
        if not todays_bars:
            continue
        report.days_simulated += 1
        current = stamp.date()
        week_key = stamp.isocalendar()[:2]

        # ---- 1. fill queued entries at today's open -------------------------
        for symbol, quantity, stop, target, planned_risk, signal_time, signal_entry in pending:
            bar = todays_bars.get(symbol)
            if bar is None or symbol in open_positions:
                continue
            fill = costs.buy_fill(bar.open)

            # The stop was derived from the signal bar's close, but the fill
            # happens at the next bar's open.  An overnight or intraday gap can
            # move price through that stop before the position exists, and two
            # different failures follow:
            #
            #   * A fill *below* the stop enters a position that is already
            #     stopped out.  Closing it "at the stop" then books a profit,
            #     which is incoherent, and a live broker would reject or
            #     instantly trigger the order.
            #   * A fill just *above* the stop leaves a tiny risk-per-share,
            #     and since size is risk-budget divided by risk-per-share, that
            #     silently produces a maximum-sized position on the setup whose
            #     premise just broke.
            #
            # Both mean the same thing: the gap invalidated the plan. Skip it.
            planned_risk_per_share = signal_entry - stop
            actual_risk_per_share = fill - stop
            if actual_risk_per_share <= 0:
                report.gapped_through_stop += 1
                continue
            if planned_risk_per_share > 0 and actual_risk_per_share < 0.5 * planned_risk_per_share:
                report.gapped_through_stop += 1
                continue

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
            if entry_rule == "mean_reversion":
                # Deliberately not routed through mean_reversion.should_exit:
                # that function guards against a daily bar whose low predates
                # an intraday entry, which is a live concern. Here the fill
                # happens at THIS bar's open, so the whole bar is after the
                # entry and the stop is legitimately checkable on it.
                if bar.low <= position.stop:
                    exit_raw, exit_reason = position.stop, "stop"
                else:
                    closes = [b.close for b in history[symbol]] + [bar.close]
                    strength = rsi(closes, mr_cfg.rsi_period)
                    if strength is not None and strength >= mr_cfg.rsi_exit:
                        exit_raw, exit_reason = bar.close, "reverted"
                    elif position.bars_held >= mr_cfg.max_holding_bars:
                        exit_raw, exit_reason = bar.close, "time_exit"
            elif config.exit_mode == "quick_target":
                # Bank a small gain as soon as it is available. Adverse first
                # when a single bar spans both, since the intraday order is
                # unknowable from this data.
                quick = position.raw_entry + config.quick_target_r * (
                    position.raw_entry - position.initial_stop)
                if bar.low <= position.initial_stop:
                    exit_raw, exit_reason = position.initial_stop, "stop"
                elif bar.high >= quick:
                    exit_raw, exit_reason = quick, "quick_target"
                elif position.bars_held >= config.max_holding_bars:
                    exit_raw, exit_reason = bar.close, "time_exit"
            elif config.stays_invested:
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
                    initial_stop=position.initial_stop,
                    exit_stop=position.stop,
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
        step_stamp = next(iter(todays_bars.values())).timestamp
        report.equity_curve.append((step_stamp, equity))
        report.cash_curve.append((step_stamp, cash))

        # Candidates queued earlier in this same loop are not open positions
        # yet, but they will be by tomorrow's open.  Counting only
        # `open_positions` here would let two names from one correlation
        # bucket queue on the same day and defeat the cap the guard exists to
        # enforce, so pending entries are folded into both checks.
        # `trade_from` lets earlier bars supply indicator warmup while entries
        # begin only inside the window under study, so a phase test measures
        # that phase rather than everything that led up to it.
        # History was appended above, so warmup still accumulates here; only
        # new entries are withheld until the window opens.
        if trade_from is not None and current < trade_from:
            continue

        # Opening-volatility blackout. Only meaningful intraday: on daily bars
        # there is one bar per session and `session_bar_index` is always 0.
        if config.intraday_open_blackout_bars > 0:
            index_in_session = session_bar_counts.get(current, 0)
            session_bar_counts[current] = index_in_session + 1
            if index_in_session < config.intraday_open_blackout_bars and not daily_bars:
                continue

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
            if entry_rule == "mean_reversion":
                signal = mean_reversion_signal(symbol, history[symbol], mr_cfg)
                if not signal.is_buy or signal.stop is None:
                    continue
                if signal.stop >= signal.close:
                    continue
                entry_ref, stop_ref = signal.close, signal.stop
                # No profit target: this rule leaves on RSI recovery, the stop
                # or the holding cap. A sentinel keeps the tuple shape without
                # ever being reachable, and the exit branch above never reads
                # it under this rule.
                target_ref = entry_ref * 1_000_000.0
            else:
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
                # A learned model may only ever remove a candidate the
                # hand-built gate already accepted; it can never add one.
                if veto is not None and veto(candidate):
                    continue
                entry_ref, stop_ref, target_ref = (
                    candidate.entry, candidate.stop, candidate.target)
            quantity, planned_risk = position_size(equity, entry_ref, stop_ref, policy, costs)
            # Conviction weighting: the same total risk appetite, concentrated
            # on the setups that measure better. `conviction` returns a
            # multiplier around 1.0 and is handed the history available at the
            # signal bar, so it can see nothing the rule could not.
            if conviction is not None and quantity > 0:
                scale = conviction(symbol, history[symbol])
                if scale is not None and scale > 0:
                    quantity *= scale
                    planned_risk *= scale
            if quantity <= 0:
                continue
            pending.append((
                symbol, quantity, stop_ref, target_ref,
                planned_risk, bar.timestamp, entry_ref,
            ))
            pending_buckets.add(CORRELATION_BUCKETS.get(symbol, "other"))

    last_bars = {s: bars[-1] for s, bars in series.items() if bars}
    report.cash = cash
    report.invested = sum(
        p.quantity * last_bars[p.symbol].close for p in open_positions.values() if p.symbol in last_bars
    )
    report.equity = report.cash + report.invested
    report.open_positions = list(open_positions.values())
    return report
