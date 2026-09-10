"""The short book, through a real account simulator rather than a per-trade screen.

Per-trade statistics are not portfolio returns, and this project has already
paid for forgetting that once: the crypto mean-reversion family screened at
+14.9% and came back at -38.6% through the account engine. The four things
that did it were one shared cash balance, the position and correlation caps,
real sizing off a risk budget, and entry at the next open. All four are here.

WHAT IS BEING SIMULATED. The mirror of the shipped long rule:

    long  (shipped)   RSI <= 35, ABOVE the 200-day, exit RSI >= 60, stop below
    short (here)      RSI >= 70, BELOW the 200-day, exit RSI <= 40, stop ABOVE

Per trade over thirty years that measured +1.200% net on 1,217 signals, 50%
wins, the threshold gradient intact across the whole range, and positive in 21
of 31 years including bull markets. It also concentrates: 2022 alone is about
60% of the profit, and excluding it and the thin 1996-99 years leaves +0.34% a
trade - still nearly three times the round trip, but thin.

WHY A SEPARATE MODULE rather than a flag on portfolio.py. The long engine is
live and validated, and shorting inverts almost every assumption inside it -
the stop is above entry not below, the exit compares high not low, profit is
entry minus exit, and a "sell" closes nothing. Threading a direction flag
through those would put the live long path one bad branch away from a bug, to
express what is honestly a second strategy.

CASH. A short is modelled as consuming its notional, exactly as a long does.
That is conservative rather than realistic - a real short receives proceeds
and posts margin - and it is deliberate: it keeps the book from silently
running leverage the long side has always refused, and it makes the two books'
capital demands directly comparable.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from event_aware_trader.data import load_bars
from event_aware_trader.indicators import rsi, sma, wilder_atr
from event_aware_trader.mean_reversion import MeanReversionConfig
from event_aware_trader.risk import CostModel, RiskPolicy, position_size
from event_aware_trader.strategy import CORRELATION_BUCKETS, DEFAULT_UNIVERSE, is_crypto

WINDOW = 400
BORROW_PER_DAY = 0.005 / 365.0


@dataclass
class ShortConfig:
    entry_rsi: float = 70.0
    exit_rsi: float = 40.0
    rsi_period: int = 14
    trend_ma_days: int = 200
    atr_days: int = 14
    stop_atr_multiple: float = 2.5
    max_holding_bars: int = 20
    max_atr_fraction: Optional[float] = 0.035
    min_price: float = 20.0
    min_average_dollar_volume: float = 50_000_000.0

    @property
    def minimum_history(self) -> int:
        return max(self.trend_ma_days, 200) + self.rsi_period + 1


@dataclass
class ShortPosition:
    symbol: str
    bucket: str
    quantity: float
    entry_price: float
    stop: float
    entry_time: datetime
    bars_held: int = 0


@dataclass
class ShortReport:
    starting_cash: float
    cash: float
    equity: float
    trades: List[dict] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)

    @property
    def max_drawdown(self) -> float:
        peak, worst = self.starting_cash, 0.0
        for _, value in self.equity_curve:
            peak = max(peak, value)
            if peak > 0:
                worst = min(worst, value / peak - 1.0)
        return worst


def short_signal(bars, config):
    """A short entry, or None. Mirrors mean_reversion.evaluate exactly."""
    if len(bars) < config.minimum_history:
        return None
    closes = [b.close for b in bars]
    close = closes[-1]
    strength = rsi(closes, config.rsi_period)
    if strength is None or strength < config.entry_rsi:
        return None
    atr = wilder_atr(bars, config.atr_days)
    if not atr or close <= 0 or close < config.min_price:
        return None
    if config.max_atr_fraction and atr / close > config.max_atr_fraction:
        return None
    average = sma(closes, config.trend_ma_days)
    # BELOW the long-term average - the mirror of "inside an intact uptrend".
    if average is None or close >= average:
        return None
    dollar_volume = sum(b.close * b.volume for b in bars[-20:]) / 20.0
    if dollar_volume < config.min_average_dollar_volume:
        return None
    return close, close + config.stop_atr_multiple * atr


def run_short_book(series, starting_cash=100_000.0, policy=None, costs=None,
                   config=None, trade_from=None):
    policy = policy or RiskPolicy()
    costs = costs or CostModel()
    config = config or ShortConfig()

    days = sorted({b.timestamp.date() for bars in series.values() for b in bars})
    indexed = {s: {b.timestamp.date(): b for b in bars} for s, bars in series.items()}
    history: Dict[str, List] = {s: [] for s in series}

    cash = starting_cash
    open_positions: Dict[str, ShortPosition] = {}
    pending: List[tuple] = []
    report = ShortReport(starting_cash=starting_cash, cash=cash, equity=cash)

    for day in days:
        todays = {s: indexed[s][day] for s in series if day in indexed[s]}
        if not todays:
            continue

        # ---- 1. fill what was queued yesterday, at TODAY's open -------------
        for symbol, quantity, stop in pending:
            bar = todays.get(symbol)
            if bar is None:
                continue
            # Selling short: the fill is worse when it is LOWER, the mirror of
            # a long paying up.
            fill = bar.open * (1.0 - costs.one_way_bps / 10_000.0)
            if fill <= 0 or fill >= stop:
                continue
            outlay = fill * quantity
            if outlay > cash:
                continue
            cash -= outlay
            open_positions[symbol] = ShortPosition(
                symbol=symbol, bucket=CORRELATION_BUCKETS.get(symbol, "other"),
                quantity=quantity, entry_price=fill, stop=stop,
                entry_time=bar.timestamp)
        pending = []

        # ---- 2. manage what is open ----------------------------------------
        for symbol in list(open_positions):
            bar = todays.get(symbol)
            if bar is None:
                continue
            position = open_positions[symbol]
            position.bars_held += 1
            exit_raw = reason = None
            # A short is stopped out when price rises through the stop.
            if bar.high >= position.stop:
                exit_raw, reason = position.stop, "stop"
            else:
                closes = [b.close for b in history[symbol]] + [bar.close]
                strength = rsi(closes, config.rsi_period)
                if strength is not None and strength <= config.exit_rsi:
                    exit_raw, reason = bar.close, "reverted"
                elif position.bars_held >= config.max_holding_bars:
                    exit_raw, reason = bar.close, "time_exit"
            if exit_raw is None:
                continue
            # Buying back: the fill is worse when it is HIGHER.
            fill = exit_raw * (1.0 + costs.one_way_bps / 10_000.0)
            borrow = position.entry_price * position.quantity * \
                BORROW_PER_DAY * position.bars_held
            # Proceeds released plus the gain, which for a short is entry
            # minus exit rather than the other way round.
            gain = (position.entry_price - fill) * position.quantity
            cash += position.entry_price * position.quantity + gain - borrow
            report.trades.append({
                "symbol": symbol, "entry_time": position.entry_time,
                "exit_time": bar.timestamp, "entry": position.entry_price,
                "exit": fill, "net": gain - borrow, "reason": reason,
                "bars_held": position.bars_held,
            })
            del open_positions[symbol]

        # ---- 3. mark the book and look for new shorts -----------------------
        for symbol, bar in todays.items():
            history[symbol].append(bar)
        # A short's value moves against the position: owing more is worth less.
        owed = sum(p.quantity * todays[p.symbol].close
                   for p in open_positions.values() if p.symbol in todays)
        held_at_entry = sum(p.quantity * p.entry_price
                            for p in open_positions.values())
        equity = cash + held_at_entry + (held_at_entry - owed) \
            if False else cash + (2 * held_at_entry - owed)
        stamp = next(iter(todays.values())).timestamp
        report.equity_curve.append((stamp, equity))

        if trade_from is not None and day < trade_from:
            continue

        buckets = [p.bucket for p in open_positions.values()]
        for symbol, bar in sorted(todays.items()):
            if symbol in open_positions or len(history[symbol]) < config.minimum_history:
                continue
            if len(open_positions) + len(pending) >= policy.max_open_positions:
                break
            bucket = CORRELATION_BUCKETS.get(symbol, "other")
            if bucket in buckets:
                continue
            found = short_signal(history[symbol][-WINDOW:], config)
            if not found:
                continue
            entry_ref, stop_ref = found
            # position_size expects the risk distance as (entry - stop); for a
            # short that distance is (stop - entry), so it is mirrored here
            # rather than teaching the sizer about direction.
            quantity, _risk = position_size(
                equity, entry_ref, entry_ref - (stop_ref - entry_ref),
                policy, costs)
            if quantity <= 0:
                continue
            pending.append((symbol, quantity, stop_ref))
            buckets.append(bucket)

    report.cash = cash
    report.equity = report.equity_curve[-1][1] if report.equity_curve else cash
    return report


def load(folder, since=None):
    out = {}
    for symbol in sorted(s for s in DEFAULT_UNIVERSE if not is_crypto(s)):
        path = Path(__file__).with_name(folder) / (symbol + ".csv")
        if not path.exists():
            continue
        bars = load_bars(path)
        if since:
            bars = [b for b in bars if b.timestamp.date() >= since]
        if len(bars) >= 400:
            out[symbol] = bars
    return out


def describe(label, report, split):
    curve = report.equity_curve
    if not curve:
        print("{0:<26}{1:>10}".format(label, "no data"), flush=True)
        return
    years = (curve[-1][0] - curve[0][0]).days / 365.25
    total = report.equity / report.starting_cash - 1.0
    cagr = ((report.equity / report.starting_cash) ** (1 / years) - 1.0
            if years > 0 and report.equity > 0 else -1.0)
    at_split = None
    for stamp, value in curve:
        if stamp.date() <= split:
            at_split = value
    first = (at_split / report.starting_cash - 1.0) if at_split else 0.0
    wins = sum(1 for t in report.trades if t["net"] > 0)
    print("{0:<26}{1:>10.1%}{2:>9.2%}{3:>9.1%}{4:>10.1%}{5:>8}{6:>7.0%}".format(
        label, total, cagr, report.max_drawdown, first,
        len(report.trades), wins / len(report.trades) if report.trades else 0.0),
        flush=True)


def main():
    head = "{0:<26}{1:>10}{2:>9}{3:>9}{4:>10}{5:>8}{6:>7}".format(
        "variant", "total", "CAGR", "maxDD", "to split", "trades", "win%")

    print("=== DECADE 2016-2026 ===", flush=True)
    decade = load("deep")
    print("symbols {0}".format(len(decade)), flush=True)
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for entry_rsi in (65.0, 70.0, 75.0):
        report = run_short_book(decade, config=ShortConfig(entry_rsi=entry_rsi))
        describe("short rsi >= {0:.0f}".format(entry_rsi), report,
                 date(2021, 3, 1))

    print("\n=== THIRTY YEARS 1996-2026 ===", flush=True)
    long_series = load("long", since=date(1996, 1, 1))
    print("symbols {0}".format(len(long_series)), flush=True)
    print(head, flush=True)
    print("-" * len(head), flush=True)
    for entry_rsi in (65.0, 70.0):
        report = run_short_book(long_series, config=ShortConfig(entry_rsi=entry_rsi))
        describe("short rsi >= {0:.0f}".format(entry_rsi), report,
                 date(2011, 1, 1))


if __name__ == "__main__":
    main()
