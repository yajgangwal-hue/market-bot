"""Phase 5 §7. What was true at the moment each trade was opened.

The question this file exists to answer is not "what correlates with a
winning trade" - that is easy and mostly noise - but "is there a class of
setup the frozen rule keeps taking that it should not".

Every feature here is computed from bars UP TO AND INCLUDING the entry
bar. That is not a stylistic preference: a feature that peeks one bar
ahead will separate winners from losers perfectly and teach nothing. The
outcome fields are kept separate from the feature fields for the same
reason, so an accidental join cannot mix them.

One feature the daily-bar emulator genuinely cannot supply is time of day.
It is reported as unavailable rather than approximated, because the entry
window is the last 20 minutes of the session and every trade would carry
the same fabricated value.
"""

from dataclasses import dataclass, field
from datetime import date
from statistics import pstdev
from typing import Dict, List, Optional, Sequence

TIME_OF_DAY_AVAILABLE = False


def _returns(closes: Sequence[float]) -> List[float]:
    return [closes[i] / closes[i - 1] - 1.0
            for i in range(1, len(closes)) if closes[i - 1]]


def simple_average(values: Sequence[float]) -> Optional[float]:
    values = list(values)
    return sum(values) / len(values) if values else None


@dataclass
class MarketContext:
    """Index-level state on one session, from that session and earlier."""
    above_ma50: Optional[bool] = None
    above_ma200: Optional[bool] = None
    drawdown: Optional[float] = None        # from the running high, <= 0
    volatility_20: Optional[float] = None   # daily stdev over 20 sessions
    return_60: Optional[float] = None


def market_context(bars) -> Dict[date, MarketContext]:
    """Index context by session, each built only from bars up to that day.

    The running high is cumulative rather than forward-looking: on day i it
    is the highest close in bars[0..i], which is what a participant on that
    day would have known.
    """
    out: Dict[date, MarketContext] = {}
    closes: List[float] = []
    running_high = None
    for bar in bars:
        closes.append(bar.close)
        running_high = bar.close if running_high is None else max(running_high,
                                                                  bar.close)
        ctx = MarketContext()
        if len(closes) >= 50:
            ma50 = simple_average(closes[-50:])
            ctx.above_ma50 = bar.close > ma50 if ma50 else None
        if len(closes) >= 200:
            ma200 = simple_average(closes[-200:])
            ctx.above_ma200 = bar.close > ma200 if ma200 else None
        if running_high:
            ctx.drawdown = bar.close / running_high - 1.0
        if len(closes) >= 21:
            daily = _returns(closes[-21:])
            ctx.volatility_20 = pstdev(daily) if len(daily) > 1 else None
        if len(closes) >= 61 and closes[-61]:
            ctx.return_60 = closes[-1] / closes[-61] - 1.0
        out[bar.timestamp.date()] = ctx
    return out


@dataclass
class TradeAnatomy:
    """One trade, split into what was known and what happened."""
    # identity
    symbol: str
    entry_date: str
    exit_date: str
    sector: str
    # decision-time features
    price: Optional[float] = None
    atr_fraction: Optional[float] = None
    above_ma200_by: Optional[float] = None    # close/sma200 - 1
    drop_5: Optional[float] = None            # 5-session return into the entry
    gap: Optional[float] = None               # entry open vs prior close
    volume_ratio: Optional[float] = None      # entry volume / 20-day average
    relative_strength_60: Optional[float] = None
    market_above_ma50: Optional[bool] = None
    market_above_ma200: Optional[bool] = None
    market_drawdown: Optional[float] = None
    market_volatility_20: Optional[float] = None
    # outcome - never a feature
    r_multiple: float = 0.0
    net_pnl: float = 0.0
    exit_reason: str = ""
    bars_held: int = 0

    def features(self) -> Dict[str, object]:
        out = dict(self.__dict__)
        for outcome in ("r_multiple", "net_pnl", "exit_reason", "bars_held"):
            out.pop(outcome)
        return out


def _window_ending(bars, day: date, length: int):
    """Bars up to and including `day`, most recent `length` of them."""
    upto = [b for b in bars if b.timestamp.date() <= day]
    return upto[-length:] if upto else []


def anatomise(trades, series: Dict[str, List], market: Dict[date, MarketContext],
              buckets: Dict[str, str],
              atr_period: int = 14) -> List[TradeAnatomy]:
    """Describe every trade by the state that preceded it."""
    from ..indicators import average_true_range

    out: List[TradeAnatomy] = []
    for trade in trades:
        bars = series.get(trade.symbol) or []
        day = trade.entry_time.date()
        upto = [b for b in bars if b.timestamp.date() <= day]
        if len(upto) < 2:
            continue
        entry_bar = upto[-1]
        previous = upto[-2]
        closes = [b.close for b in upto]

        atr = average_true_range(upto[-(atr_period + 1):], atr_period) \
            if len(upto) > atr_period else None
        ma200 = simple_average(closes[-200:]) if len(closes) >= 200 else None
        volumes = [b.volume for b in upto[-21:-1]]
        average_volume = simple_average(volumes)
        ctx = market.get(day, MarketContext())

        own_60 = (closes[-1] / closes[-61] - 1.0
                  if len(closes) >= 61 and closes[-61] else None)
        relative = (own_60 - ctx.return_60
                    if own_60 is not None and ctx.return_60 is not None else None)

        out.append(TradeAnatomy(
            symbol=trade.symbol,
            entry_date=day.isoformat(),
            exit_date=trade.exit_time.date().isoformat(),
            sector=buckets.get(trade.symbol, "unclassified"),
            price=entry_bar.close,
            atr_fraction=(atr / entry_bar.close if atr and entry_bar.close
                          else None),
            above_ma200_by=(entry_bar.close / ma200 - 1.0 if ma200 else None),
            drop_5=(closes[-1] / closes[-6] - 1.0
                    if len(closes) >= 6 and closes[-6] else None),
            gap=(entry_bar.open / previous.close - 1.0
                 if previous.close else None),
            volume_ratio=(entry_bar.volume / average_volume
                          if average_volume else None),
            relative_strength_60=relative,
            market_above_ma50=ctx.above_ma50,
            market_above_ma200=ctx.above_ma200,
            market_drawdown=ctx.drawdown,
            market_volatility_20=ctx.volatility_20,
            r_multiple=trade.r_multiple,
            net_pnl=trade.net_pnl,
            exit_reason=trade.exit_reason,
            bars_held=trade.bars_held))
    return out


# ---------------------------------------------------------------------------
# Describing a split without pretending it is a finding
# ---------------------------------------------------------------------------

@dataclass
class Bucket:
    label: str
    trades: int
    total_pnl: float
    median_r: Optional[float]
    mean_r: Optional[float]
    win_rate: Optional[float]
    # The share of this bucket that ended at the stop. Reported everywhere
    # because the decade anatomy found the stop bucket alone costs more
    # than the strategy earns: 239 trades, -$213,599, against +$57,560 net.
    # Any filter worth testing has to move THIS number.
    stop_rate: Optional[float] = None

    def as_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


def _median(values: Sequence[float]) -> Optional[float]:
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def bucket(rows: Sequence[TradeAnatomy], label: str) -> Bucket:
    rs = [r.r_multiple for r in rows]
    return Bucket(
        label=label,
        trades=len(rows),
        total_pnl=round(sum(r.net_pnl for r in rows), 2),
        median_r=(round(_median(rs), 4) if rs else None),
        mean_r=(round(sum(rs) / len(rs), 4) if rs else None),
        win_rate=(round(sum(1 for r in rows if r.net_pnl > 0) / len(rows), 4)
                  if rows else None),
        stop_rate=(round(sum(1 for r in rows if r.exit_reason == "stop")
                         / len(rows), 4) if rows else None))


def split_by(rows: Sequence[TradeAnatomy], attribute: str,
             edges: Sequence[float]) -> List[Bucket]:
    """Quantile-free split at explicit edges, so the cuts are declared.

    Edges chosen from the data are a form of fitting. These are passed in
    by the caller and written down in the report.
    """
    out = []
    values = [(getattr(r, attribute), r) for r in rows]
    known = [(v, r) for v, r in values if v is not None]
    previous = None
    for edge in list(edges) + [None]:
        if edge is None:
            chosen = [r for v, r in known if previous is None or v >= previous]
            name = "{0} >= {1}".format(attribute, previous)
        else:
            chosen = [r for v, r in known
                      if (previous is None or v >= previous) and v < edge]
            name = ("{0} < {1}".format(attribute, edge) if previous is None
                    else "{0} {1}..{2}".format(attribute, previous, edge))
        out.append(bucket(chosen, name))
        previous = edge
    missing = [r for v, r in values if v is None]
    if missing:
        out.append(bucket(missing, "{0} unavailable".format(attribute)))
    return out


def split_by_flag(rows: Sequence[TradeAnatomy], attribute: str) -> List[Bucket]:
    groups: Dict[object, List[TradeAnatomy]] = {}
    for r in rows:
        groups.setdefault(getattr(r, attribute), []).append(r)
    return [bucket(v, "{0}={1}".format(attribute, k))
            for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))]


def split_by_key(rows: Sequence[TradeAnatomy], attribute: str,
                 minimum: int = 20) -> List[Bucket]:
    groups: Dict[object, List[TradeAnatomy]] = {}
    for r in rows:
        groups.setdefault(getattr(r, attribute), []).append(r)
    kept = [(k, v) for k, v in groups.items() if len(v) >= minimum]
    return sorted((bucket(v, "{0}={1}".format(attribute, k)) for k, v in kept),
                  key=lambda b: b.total_pnl)
