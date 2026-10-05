"""A short sleeve as a SEPARATE strategy beside the frozen long book - research only.

Nothing here is imported by the live bot. It exists to answer, under sealed
hypotheses H-0027..H-0030, whether a short sleeve adds anything to the frozen
long-only account, and what a +0.5% / -0.2% exit pair really does.

WHY A NEW ENGINE rather than scripts/short_book_sim.py (2026-09-10). That
simulator filled a short's stop AT the stop even when the session opened
above it - the optimistic fill the long emulator abandoned as "every figure
this project published filled at the stop" - charged no dividends and no
rule-exit haircut, and sized by stop distance, the very thing EXP-0011 found
gives the best shorts the least money. This engine fixes all four and keeps
the long book untouched: the sleeve is an overlay on the frozen account's own
equity curve, so the control is exactly the frozen baseline.

CONVENTIONS, mirrored from the long emulator (portfolio.py) where one exists:

  entry       at the signal session's close (entry_fill="signal_close"),
              selling short `one_way_bps` worse than the close
  stop        a resting BUY stop k x ATR above the entry reference. If the
              session OPENS at or above it there was never a trade at the stop:
              the cover is the open (gap-through). Otherwise the stop price.
              Plus `one_way_bps`.
  rule exits  RSI cover and the time cap cover at the close, plus
              `one_way_bps`, plus the 0.652% rule-exit haircut - adverse for a
              buy-to-cover means HIGHER (portfolio.py charges `reverted` and
              `time_exit` the same way on the long side)
  take profit a resting BUY limit: at its level, or at the open on a gap down.
              Adverse ordering when one bar spans stop and target: stop first.
  borrow      `borrow_annual` on entry notional per calendar day held
  dividends   `dividend_annual` on entry notional per calendar day held - a
              short PAYS the dividend, and the split-adjusted price files carry
              the ex-date drop as if it were free. Without it shorts are
              flattered.
  SEC fee     `sec_fee_bps` on the short sale's proceeds
  Rule 201    no new short on a session whose close fell 10% or more from the
              prior close, or that followed one (the restriction runs the rest
              of that day and the next)
  sizing      equal notional: `notional_fraction` of account equity per short,
              whole shares; at most `max_positions` shorts and
              `max_short_fraction` of equity short in total; one per
              correlation bucket; never a name the long book holds
  no leverage long market value + short notional never exceeds equity at
              an entry; if the long book's own growth pushes it over, the
              youngest shorts are covered at that close (rule-exit pricing)
  collateral  in the parked account the short notional is assumed to earn no
              interest, so the sleeve is charged the bill rate on it
"""

import math
import statistics
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Indicators, computed once per symbol (Wilder, from the start of the series)
# ---------------------------------------------------------------------------


def wilder_rsi_series(closes: Sequence[float], period: int = 14) -> List[Optional[float]]:
    """RSI at every index, identical to indicators.rsi(closes[:i+1], period)."""
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def value(g, l):
        if l == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / l)

    out[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = value(avg_gain, avg_loss)
    return out


def wilder_atr_series(highs, lows, closes, period: int = 14) -> List[Optional[float]]:
    """ATR at every index, identical to indicators.wilder_atr(bars[:i+1], period)."""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n < period + 1:
        return out
    ranges = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                  abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    current = sum(ranges[:period]) / period
    out[period] = current
    for j in range(period, len(ranges)):
        current = (current * (period - 1) + ranges[j]) / period
        out[j + 1] = current
    return out


def rolling_mean(values: Sequence[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        if i >= window - 1:
            out[i] = total / window
    return out


@dataclass
class Series:
    """One symbol's bars as columns, with its indicators."""
    symbol: str
    dates: List[date]
    opens: List[float]
    highs: List[float]
    lows: List[float]
    closes: List[float]
    volumes: List[float]
    rsi: List[Optional[float]] = field(default_factory=list)
    atr: List[Optional[float]] = field(default_factory=list)
    sma200: List[Optional[float]] = field(default_factory=list)
    adv20: List[Optional[float]] = field(default_factory=list)
    index: Dict[date, int] = field(default_factory=dict)

    @classmethod
    def from_bars(cls, symbol, bars):
        s = cls(symbol=symbol, dates=[b.timestamp.date() for b in bars],
                opens=[b.open for b in bars], highs=[b.high for b in bars],
                lows=[b.low for b in bars], closes=[b.close for b in bars],
                volumes=[b.volume for b in bars])
        s.rsi = wilder_rsi_series(s.closes, 14)
        s.atr = wilder_atr_series(s.highs, s.lows, s.closes, 14)
        s.sma200 = rolling_mean(s.closes, 200)
        s.adv20 = rolling_mean([c * v for c, v in zip(s.closes, s.volumes)], 20)
        s.index = {d: i for i, d in enumerate(s.dates)}
        return s


MIN_HISTORY = 215          # the long rule's minimum_history: 200 + 14 + 1
MIN_PRICE = 20.0
MIN_ADV = 50_000_000.0
MAX_ATR_FRACTION = 0.035


def tradable(s: Series, i: int) -> bool:
    """The long rule's own liquidity/price/volatility filters, at index i."""
    if i + 1 < MIN_HISTORY:
        return False
    close, atr, adv = s.closes[i], s.atr[i], s.adv20[i]
    if close < MIN_PRICE or atr is None or adv is None or adv < MIN_ADV:
        return False
    return atr / close <= MAX_ATR_FRACTION


def rule_201_blocks(s: Series, i: int) -> bool:
    """A 10% decline on this session or the previous one restricts short sales."""
    for j in (i, i - 1):
        # "at least 10 percent": 100 -> 90 is -0.0999999... in floating point
        if j >= 1 and s.closes[j] / s.closes[j - 1] - 1.0 <= -0.10 + 1e-12:
            return True
    return False


# ---------------------------------------------------------------------------
# Signals. Each returns a score (higher = ranked first) or None.
# ---------------------------------------------------------------------------


def mirror_signal(s: Series, i: int, ctx) -> Optional[float]:
    """H-0027/H-0028: overbought (RSI >= 70) below the 200-day - a failed rally."""
    if not tradable(s, i) or s.sma200[i] is None or s.rsi[i] is None:
        return None
    if s.closes[i] >= s.sma200[i] or s.rsi[i] < 70.0:
        return None
    return s.rsi[i]


def relative_weakness_signal(s: Series, i: int, ctx) -> Optional[float]:
    """H-0029: below the 200-day, a new 50-session closing low, and at least 10
    points behind SPY over 63 sessions."""
    if not tradable(s, i) or s.sma200[i] is None or i < 63:
        return None
    if s.closes[i] >= s.sma200[i]:
        return None
    if s.closes[i] >= min(s.closes[i - 50:i]):
        return None
    spy_return = ctx.spy_return_63(s.dates[i])
    if spy_return is None:
        return None
    relative = (s.closes[i] / s.closes[i - 63] - 1.0) - spy_return
    if relative > -0.10:
        return None
    return -relative


def long_rule_signal(s: Series, i: int, ctx) -> Optional[float]:
    """The frozen long entry (mean_reversion.evaluate), for H-0030's population."""
    if not tradable(s, i) or s.sma200[i] is None or s.rsi[i] is None:
        return None
    if s.closes[i] <= s.sma200[i] or s.rsi[i] > 35.0:
        return None
    return -s.rsi[i]


# ---------------------------------------------------------------------------
# Costs and exits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Costs:
    one_way_bps: float = 6.0
    rule_exit_haircut: float = 0.00652
    borrow_annual: float = 0.005
    dividend_annual: float = 0.02
    sec_fee_bps: float = 0.278

    @property
    def one_way(self) -> float:
        return self.one_way_bps / 10_000.0


@dataclass(frozen=True)
class ShortExits:
    stop_atr: float = 2.5
    rsi_cover: Optional[float] = 40.0       # None = no RSI cover
    max_bars: int = 20
    target_pct: Optional[float] = None      # e.g. 0.005: cover 0.5% below entry
    stop_pct: Optional[float] = None        # e.g. 0.002: stop 0.2% above entry (replaces ATR)
    target_through: float = 0.0005          # a resting limit fills only if price trades 5 bp through it


@dataclass
class ShortTrade:
    symbol: str
    entry_date: date
    exit_date: Optional[date]
    entry_ref: float
    entry_fill: float
    stop: float
    target: Optional[float]
    quantity: float
    reason: str = ""
    exit_fill: float = 0.0
    bars_held: int = 0
    gap_through: bool = False
    mae: float = 0.0              # worst adverse move, fraction of entry (price up)
    mfe: float = 0.0              # best favourable move, fraction of entry (price down)
    borrow: float = 0.0
    dividends: float = 0.0
    fees: float = 0.0
    regime_bull: Optional[bool] = None
    regime_vol: str = ""
    equity_at_entry: float = 0.0

    @property
    def gross(self) -> float:
        return (self.entry_fill - self.exit_fill) * self.quantity

    @property
    def net(self) -> float:
        return self.gross - self.borrow - self.dividends - self.fees

    @property
    def notional(self) -> float:
        return self.entry_fill * self.quantity

    @property
    def net_pct(self) -> float:
        return self.net / self.notional if self.notional else 0.0

    @property
    def risk(self) -> float:
        return (self.stop - self.entry_ref) * self.quantity


def step_short(t: ShortTrade, s: Series, i: int, exits: ShortExits, costs: Costs,
               force: bool = False) -> bool:
    """Advance one open short through session i. Returns True when it closed."""
    t.bars_held += 1
    o, h, l, c = s.opens[i], s.highs[i], s.lows[i], s.closes[i]
    up = 1.0 + costs.one_way
    exit_raw, reason = None, ""
    if o >= t.stop:
        exit_raw, reason, t.gap_through = o, "stop", True
    elif t.target is not None and o <= t.target:
        exit_raw, reason = o, "take_profit"                 # gap down through the limit
    elif h >= t.stop:
        exit_raw, reason = t.stop, "stop"                   # adverse first on a two-sided bar
    elif t.target is not None and l <= t.target * (1.0 - exits.target_through):
        exit_raw, reason = t.target, "take_profit"
    # excursions: the whole bar while held; only up to the fill on a stop bar
    if reason == "stop":
        t.mae = max(t.mae, exit_raw / t.entry_fill - 1.0)
        t.mfe = max(t.mfe, 1.0 - min(o, exit_raw) / t.entry_fill)
    elif reason == "take_profit":
        t.mae = max(t.mae, o / t.entry_fill - 1.0)
        t.mfe = max(t.mfe, 1.0 - exit_raw / t.entry_fill)
    else:
        t.mae = max(t.mae, h / t.entry_fill - 1.0)
        t.mfe = max(t.mfe, 1.0 - l / t.entry_fill)
    if exit_raw is not None:
        fill = exit_raw * up if reason == "stop" else exit_raw     # a limit gets its price
        _close(t, s.dates[i], fill, reason, costs)
        return True
    rule = None
    if exits.rsi_cover is not None and s.rsi[i] is not None and s.rsi[i] <= exits.rsi_cover:
        rule = "reverted"
    elif t.bars_held >= exits.max_bars:
        rule = "time_exit"
    elif force:
        rule = "forced"
    if rule:
        _close(t, s.dates[i], c * (up + costs.rule_exit_haircut), rule, costs)
        return True
    return False


def _close(t: ShortTrade, day: date, fill: float, reason: str, costs: Costs) -> None:
    t.exit_date, t.exit_fill, t.reason = day, fill, reason
    days = max(1, (day - t.entry_date).days)
    t.borrow = t.notional * costs.borrow_annual * days / 365.0
    t.dividends = t.notional * costs.dividend_annual * days / 365.0
    t.fees = t.notional * costs.sec_fee_bps / 10_000.0


def open_short(s: Series, i: int, quantity: float, exits: ShortExits, costs: Costs) -> ShortTrade:
    ref = s.closes[i]
    fill = ref * (1.0 - costs.one_way)
    if exits.stop_pct is not None:
        stop = fill * (1.0 + exits.stop_pct)
    else:
        stop = ref + exits.stop_atr * s.atr[i]
    target = fill * (1.0 - exits.target_pct) if exits.target_pct is not None else None
    return ShortTrade(symbol=s.symbol, entry_date=s.dates[i], exit_date=None,
                      entry_ref=ref, entry_fill=fill, stop=stop, target=target,
                      quantity=quantity)


# ---------------------------------------------------------------------------
# Market context: SPY regime, volatility regime, bill rate
# ---------------------------------------------------------------------------


class Context:
    def __init__(self, spy: Series, tbill: Dict[date, float]):
        self.spy = spy
        self.tbill = tbill
        self._vol20: Dict[date, float] = {}
        rets = [None] + [spy.closes[i] / spy.closes[i - 1] - 1.0 for i in range(1, len(spy.closes))]
        for i in range(21, len(rets)):
            window = rets[i - 19:i + 1]
            self._vol20[spy.dates[i]] = statistics.pstdev(window) * math.sqrt(252)
        self._vol_dates = sorted(self._vol20)

    def spy_index(self, day: date) -> Optional[int]:
        return self.spy.index.get(day)

    def spy_return_63(self, day: date) -> Optional[float]:
        i = self.spy_index(day)
        if i is None or i < 63:
            return None
        return self.spy.closes[i] / self.spy.closes[i - 63] - 1.0

    def bull(self, day: date) -> Optional[bool]:
        i = self.spy_index(day)
        if i is None or self.spy.sma200[i] is None:
            return None
        return self.spy.closes[i] > self.spy.sma200[i]

    def bear_confirmed(self, day: date, sessions: int = 3) -> bool:
        i = self.spy_index(day)
        if i is None:
            return False
        for j in range(i - sessions + 1, i + 1):
            if j < 0 or self.spy.sma200[j] is None or self.spy.closes[j] >= self.spy.sma200[j]:
                return False
        return True

    def vol_regime(self, day: date) -> str:
        """calm / normal / stressed: SPY 20-day realised vol against its own
        trailing 252 sessions, terciles, point in time."""
        i = self.spy_index(day)
        if i is None or day not in self._vol20:
            return ""
        history = [self._vol20[d] for d in self.spy.dates[max(0, i - 251):i + 1] if d in self._vol20]
        if len(history) < 60:
            return ""
        ordered = sorted(history)
        low = ordered[len(ordered) // 3]
        high = ordered[(2 * len(ordered)) // 3]
        v = self._vol20[day]
        return "calm" if v <= low else ("stressed" if v > high else "normal")

    def rate(self, day: date) -> float:
        for back in range(8):
            probe = date.fromordinal(day.toordinal() - back)
            if probe in self.tbill:
                return self.tbill[probe]
        return 0.0


# ---------------------------------------------------------------------------
# The sleeve
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SleeveRules:
    signal: Callable = mirror_signal
    exits: ShortExits = ShortExits()
    costs: Costs = Costs()
    notional_fraction: float = 0.05
    max_positions: int = 6
    max_short_fraction: float = 0.30
    bear_gate: bool = False
    symbols: Optional[frozenset] = None       # restrict the short universe (ETF control)


@dataclass
class SleeveResult:
    trades: List[ShortTrade]
    pnl_curve: List[Tuple[date, float]]          # cumulative sleeve P&L, marked at each close
    notional_curve: List[Tuple[date, float]]     # short notional open at each close
    forced: int = 0
    skipped_rule_201: int = 0
    skipped_long_held: int = 0
    skipped_capacity: int = 0
    open_at_end: List[ShortTrade] = field(default_factory=list)


def run_sleeve(series: Dict[str, Series], ctx: Context, rules: SleeveRules,
               base_equity: Callable[[date], float],
               long_value: Callable[[date], float],
               long_holds: Callable[[str, date], bool],
               buckets: Dict[str, str]) -> SleeveResult:
    """The short sleeve over SPY's sessions, as an overlay on an account whose
    long book's equity and market value are given (zero for a standalone sleeve).

    Account equity at a close = base_equity + the sleeve's cumulative P&L.
    """
    open_trades: Dict[str, ShortTrade] = {}
    closed: List[ShortTrade] = []
    realized = 0.0
    pnl_curve, notional_curve = [], []
    result = SleeveResult(trades=closed, pnl_curve=pnl_curve, notional_curve=notional_curve)

    for day in ctx.spy.dates:
        # 1. manage open shorts on today's bar
        for sym in list(open_trades):
            s = series[sym]
            i = s.index.get(day)
            if i is None:
                continue
            t = open_trades[sym]
            if step_short(t, s, i, rules.exits, rules.costs):
                realized += t.net
                closed.append(t)
                del open_trades[sym]

        # 2. mark, and keep the account unlevered
        def unrealized():
            total = 0.0
            for sym, t in open_trades.items():
                s = series[sym]
                j = s.index.get(day)
                price = s.closes[j] if j is not None else _last_close(s, day)
                total += (t.entry_fill - price) * t.quantity
            return total

        def short_notional():
            total = 0.0
            for sym, t in open_trades.items():
                s = series[sym]
                j = s.index.get(day)
                price = s.closes[j] if j is not None else _last_close(s, day)
                total += price * t.quantity
            return total

        equity = base_equity(day) + realized + unrealized()
        while open_trades and long_value(day) + short_notional() > equity:
            # The long book has priority: its growth may not be blocked by the
            # sleeve, so the youngest short is covered at this close, priced
            # like any other rule exit. The bar was already stepped above.
            youngest = max(open_trades.values(), key=lambda x: (x.entry_date, x.symbol))
            s = series[youngest.symbol]
            j = s.index.get(day)
            if j is None:
                break
            _close(youngest, day, s.closes[j] * (1.0 + rules.costs.one_way
                                                 + rules.costs.rule_exit_haircut),
                   "forced", rules.costs)
            realized += youngest.net
            closed.append(youngest)
            del open_trades[youngest.symbol]
            result.forced += 1
            equity = base_equity(day) + realized + unrealized()

        # 3. new shorts at today's close
        if not (rules.bear_gate and not ctx.bear_confirmed(day)):
            candidates = []
            for sym, s in series.items():
                if sym in open_trades or (rules.symbols is not None and sym not in rules.symbols):
                    continue
                i = s.index.get(day)
                if i is None:
                    continue
                score = rules.signal(s, i, ctx)
                if score is None:
                    continue
                if rule_201_blocks(s, i):
                    result.skipped_rule_201 += 1
                    continue
                if long_holds(sym, day):
                    result.skipped_long_held += 1
                    continue
                candidates.append((-score, sym, i))
            candidates.sort()
            used_buckets = {buckets.get(t.symbol, "other") for t in open_trades.values()}
            for _, sym, i in candidates:
                if len(open_trades) >= rules.max_positions:
                    result.skipped_capacity += 1
                    continue
                bucket = buckets.get(sym, "other")
                if bucket in used_buckets:
                    continue
                s = series[sym]
                price = s.closes[i] * (1.0 - rules.costs.one_way)
                quantity = math.floor(rules.notional_fraction * equity / price)
                if quantity < 1:
                    continue
                current = short_notional()
                new = quantity * s.closes[i]
                if (current + new > rules.max_short_fraction * equity
                        or long_value(day) + current + new > equity):
                    result.skipped_capacity += 1
                    continue
                t = open_short(s, i, quantity, rules.exits, rules.costs)
                t.regime_bull = ctx.bull(day)
                t.regime_vol = ctx.vol_regime(day)
                t.equity_at_entry = equity
                t.mae = 0.0
                open_trades[sym] = t
                used_buckets.add(bucket)

        pnl_curve.append((day, realized + unrealized()))
        notional_curve.append((day, short_notional()))

    # still open at the end: marked, not closed
    result.open_at_end = list(open_trades.values())
    return result


def _last_close(s: Series, day: date) -> float:
    """The latest close on or before `day` (a symbol with no bar today)."""
    lo, hi = 0, len(s.dates) - 1
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if s.dates[mid] <= day:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return s.closes[best]


# ---------------------------------------------------------------------------
# Per-signal outcomes (H-0030): one trade per signal, no portfolio
# ---------------------------------------------------------------------------


@dataclass
class SignalOutcome:
    symbol: str
    day: date
    side: str
    net_pct: float
    reason: str
    bars: int
    gap: bool
    mae: float
    mfe: float


def long_outcome(s: Series, i: int, costs: Costs, target_pct=None, stop_pct=None,
                 ambiguous_target_first: bool = False, max_bars: int = 20,
                 target_through: float = 0.0005) -> Optional[SignalOutcome]:
    """One long from the close of session i, under the frozen exits (default) or a
    fixed +target / -stop pair. Mirrors portfolio.py's long conventions."""
    ref = s.closes[i]
    fill = ref * (1.0 + costs.one_way)
    if stop_pct is None:
        stop = ref - 2.5 * s.atr[i]
        target = None
    else:
        stop = fill * (1.0 - stop_pct)
        target = fill * (1.0 + target_pct)
    mae = mfe = 0.0
    for k in range(1, max_bars + 1):
        j = i + k
        if j >= len(s.closes):
            return None
        o, h, l, c = s.opens[j], s.highs[j], s.lows[j], s.closes[j]
        down = 1.0 - costs.one_way
        if o <= stop:
            return SignalOutcome(s.symbol, s.dates[i], "long", o * down / fill - 1.0, "stop", k, True,
                                 max(mae, 1 - o / fill), mfe)
        if target is not None and o >= target:
            return SignalOutcome(s.symbol, s.dates[i], "long", o / fill - 1.0, "take_profit", k, False,
                                 mae, max(mfe, o / fill - 1))
        hit_stop = l <= stop
        hit_target = target is not None and h >= target * (1.0 + target_through)
        if hit_stop and hit_target and ambiguous_target_first:
            hit_stop = False
        if hit_stop:
            return SignalOutcome(s.symbol, s.dates[i], "long", stop * down / fill - 1.0, "stop", k, False,
                                 max(mae, 1 - stop / fill), max(mfe, o / fill - 1))
        if hit_target:
            return SignalOutcome(s.symbol, s.dates[i], "long", target / fill - 1.0, "take_profit", k, False,
                                 max(mae, 1 - o / fill), max(mfe, target / fill - 1))
        mae = max(mae, 1 - l / fill)
        mfe = max(mfe, h / fill - 1)
        rsi_now = s.rsi[j]
        if target is None and rsi_now is not None and rsi_now >= 60.0:
            return SignalOutcome(s.symbol, s.dates[i], "long",
                                 c * (down - costs.rule_exit_haircut) / fill - 1.0, "reverted", k, False, mae, mfe)
        if k >= max_bars:
            return SignalOutcome(s.symbol, s.dates[i], "long",
                                 c * (down - costs.rule_exit_haircut) / fill - 1.0, "time_exit", k, False, mae, mfe)
    return None


def short_outcome(s: Series, i: int, costs: Costs, exits: ShortExits,
                  ambiguous_target_first: bool = False) -> Optional[SignalOutcome]:
    """One short from the close of session i, through the sleeve's own step_short."""
    t = open_short(s, i, 1.0, exits, costs)
    for k in range(1, exits.max_bars + 1):
        j = i + k
        if j >= len(s.closes):
            return None
        if ambiguous_target_first and t.target is not None:
            o, h, l = s.opens[j], s.highs[j], s.lows[j]
            if (o < t.stop and o > t.target and h >= t.stop
                    and l <= t.target * (1.0 - exits.target_through)):
                t.bars_held += 1
                t.mfe = max(t.mfe, 1.0 - t.target / t.entry_fill)
                _close(t, s.dates[j], t.target, "take_profit", costs)
                return SignalOutcome(s.symbol, s.dates[i], "short", t.net_pct, t.reason, t.bars_held,
                                     t.gap_through, t.mae, t.mfe)
        if step_short(t, s, j, exits, costs):
            return SignalOutcome(s.symbol, s.dates[i], "short", t.net_pct, t.reason, t.bars_held,
                                 t.gap_through, t.mae, t.mfe)
    return None


def non_overlapping(series: Dict[str, Series], signal, ctx, frozen_exit_bars) -> List[Tuple[str, int]]:
    """Signals, at most one open per symbol: after a signal the symbol is skipped
    until the frozen exit of that signal would have closed it. Overlapping
    signals on consecutive days are one bet, not several."""
    out = []
    for sym, s in sorted(series.items()):
        busy_until = -1
        for i in range(len(s.closes)):
            if i <= busy_until:
                continue
            if signal(s, i, ctx) is None:
                continue
            bars = frozen_exit_bars(s, i)
            if bars is None:
                continue
            out.append((sym, i))
            busy_until = i + bars
    return out


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def distribution(returns: Sequence[float]) -> Dict[str, object]:
    """Everything the owner asked for about one population of trade returns."""
    r = list(returns)
    if not r:
        return {"n": 0}
    wins = [x for x in r if x > 0]
    losses = [x for x in r if x <= 0]
    sd = statistics.stdev(r) if len(r) > 1 else 0.0
    gross_win, gross_loss = sum(wins), -sum(losses)
    return {
        "n": len(r),
        "mean": statistics.fmean(r), "median": statistics.median(r),
        "t_stat": (statistics.fmean(r) / (sd / math.sqrt(len(r)))) if sd > 0 else None,
        "win_rate": len(wins) / len(r),
        "mean_winner": statistics.fmean(wins) if wins else None,
        "median_winner": statistics.median(wins) if wins else None,
        "mean_loser": statistics.fmean(losses) if losses else None,
        "median_loser": statistics.median(losses) if losses else None,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
        "p05": percentile(r, 0.05), "p25": percentile(r, 0.25), "p50": percentile(r, 0.50),
        "p75": percentile(r, 0.75), "p90": percentile(r, 0.90), "p95": percentile(r, 0.95),
        "worst": min(r), "best": max(r),
    }


def daily_returns(curve: Sequence[Tuple[date, float]]) -> List[Tuple[date, float]]:
    out = []
    for k in range(1, len(curve)):
        prev = curve[k - 1][1]
        if prev > 0:
            out.append((curve[k][0], curve[k][1] / prev - 1.0))
    return out


def account_metrics(curve: Sequence[Tuple[date, float]], rf_annual: float = 0.023) -> Dict[str, object]:
    """CAGR, Sharpe (excess of a fixed rf), Sortino, drawdown, worst day, by year."""
    if len(curve) < 2:
        return {}
    start, end = curve[0][1], curve[-1][1]
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    total = end / start - 1.0
    rets = [r for _, r in daily_returns(curve)]
    rf_daily = (1.0 + rf_annual) ** (1 / 252) - 1.0
    excess = [r - rf_daily for r in rets]
    sd = statistics.stdev(rets)
    downside = math.sqrt(sum(min(0.0, e) ** 2 for e in excess) / len(excess))
    peak, worst_dd = start, 0.0
    for _, v in curve:
        peak = max(peak, v)
        worst_dd = min(worst_dd, v / peak - 1.0)
    by_year, prev = {}, start
    last = {}
    for d, v in curve:
        last[d.year] = v
    for y in sorted(last):
        by_year[y] = last[y] / prev - 1.0
        prev = last[y]
    cagr = (end / start) ** (1 / years) - 1.0 if end > 0 else -1.0
    streak = longest = 0
    for r in rets:
        streak = streak + 1 if r < 0 else 0
        longest = max(longest, streak)
    return {
        "total_return": total, "cagr": cagr,
        "volatility": sd * math.sqrt(252),
        "sharpe": statistics.fmean(excess) / sd * math.sqrt(252) if sd > 0 else None,
        "sortino": statistics.fmean(excess) / downside * math.sqrt(252) if downside > 0 else None,
        "downside_deviation": downside * math.sqrt(252),
        "max_drawdown": worst_dd,
        "calmar": cagr / abs(worst_dd) if worst_dd < 0 else None,
        "worst_day": min(rets), "best_day": max(rets),
        "longest_losing_streak_days": longest,
        "by_year": by_year,
    }


def correlation_beta(a: Sequence[float], b: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    """corr(a, b) and beta of a on b."""
    n = min(len(a), len(b))
    if n < 3:
        return None, None
    a, b = list(a[:n]), list(b[:n])
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)
    va = statistics.variance(a)
    vb = statistics.variance(b)
    if va <= 0 or vb <= 0:
        return None, None
    return cov / math.sqrt(va * vb), cov / vb
