"""Smart-Money-Concepts structure detectors.

These implement the mechanical concepts taught in TJR's Boot Camp playlist -
break of structure, liquidity sweeps, fair value gaps, order blocks, and
equilibrium (premium/discount).  They are widely taught and precisely defined,
which is what makes them implementable at all; whether they carry an edge on
this universe is an empirical question the tests and the model answer, not
something assumed here.

**Confirmation lag is the whole ballgame.** A swing high is only knowable once
enough bars have printed *after* it, so a naive detector that scans the full
array marks swings it could not have seen at the time and every downstream
signal inherits that. Every function here takes bars up to "now" and returns
only structures already confirmed by that point. `confirmation_bars` is the
lag, and it is deliberately explicit rather than hidden in a default.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .types import Bar


@dataclass(frozen=True)
class SwingPoint:
    index: int
    price: float
    kind: str            # "high" or "low"
    confirmed_at: int    # the bar index at which this became knowable


@dataclass(frozen=True)
class StructureEvent:
    index: int
    kind: str            # "BOS" (continuation) or "CHOCH" (reversal)
    direction: str       # "bullish" or "bearish"
    level: float         # the swing level that was broken


@dataclass(frozen=True)
class FairValueGap:
    index: int           # the third bar of the pattern
    direction: str       # "bullish" or "bearish"
    top: float
    bottom: float

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass(frozen=True)
class OrderBlock:
    index: int
    direction: str       # "bullish" or "bearish"
    top: float
    bottom: float

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass(frozen=True)
class LiquiditySweep:
    index: int
    direction: str       # "bullish" = swept lows then closed back up
    level: float
    penetration: float   # how far beyond the level the wick reached


def find_swings(
    bars: Sequence[Bar], lookback: int = 2, confirmation_bars: Optional[int] = None
) -> List[SwingPoint]:
    """Fractal swing highs and lows, each dated to when it became knowable.

    A swing high at ``i`` needs ``lookback`` lower highs on each side, so it
    cannot be confirmed until bar ``i + lookback`` has printed.  ``confirmed_at``
    records that, and every consumer below filters on it.
    """
    if lookback < 1:
        raise ValueError("lookback must be at least one")
    confirm = lookback if confirmation_bars is None else confirmation_bars
    swings: List[SwingPoint] = []
    for i in range(lookback, len(bars) - lookback):
        window = bars[i - lookback : i + lookback + 1]
        centre = bars[i]
        if centre.high == max(b.high for b in window) and all(
            centre.high >= b.high for b in window
        ):
            swings.append(SwingPoint(i, centre.high, "high", i + confirm))
        if centre.low == min(b.low for b in window) and all(
            centre.low <= b.low for b in window
        ):
            swings.append(SwingPoint(i, centre.low, "low", i + confirm))
    return swings


def _visible(swings: Sequence[SwingPoint], as_of: int) -> List[SwingPoint]:
    return [s for s in swings if s.confirmed_at <= as_of]


def detect_structure(
    bars: Sequence[Bar], lookback: int = 2, as_of: Optional[int] = None
) -> List[StructureEvent]:
    """Break of structure and change of character, in order.

    BOS: price closes beyond the most recent confirmed swing in the direction
    the market is already going - a continuation.
    CHOCH: the first such break *against* the prevailing direction - the
    signal that structure may be turning.
    """
    end = len(bars) - 1 if as_of is None else as_of
    swings = find_swings(bars, lookback)
    events: List[StructureEvent] = []
    trend: Optional[str] = None

    # Re-filtering the whole swing list on every bar made this quadratic, and
    # since it runs once per candidate the screening pass was cubic overall.
    # Swings are produced in index order and confirm at index + lag, so a
    # single advancing pointer keeps the "already visible" set current in
    # linear time. Behaviour is unchanged - only the bookkeeping is.
    ordered = sorted(swings, key=lambda s: (s.confirmed_at, s.index))
    cursor = 0
    last_high: Optional[SwingPoint] = None
    last_low: Optional[SwingPoint] = None

    for i in range(1, min(end + 1, len(bars))):
        while cursor < len(ordered) and ordered[cursor].confirmed_at <= i:
            swing = ordered[cursor]
            if swing.kind == "high":
                if last_high is None or swing.index >= last_high.index:
                    last_high = swing
            else:
                if last_low is None or swing.index >= last_low.index:
                    last_low = swing
            cursor += 1

        close = bars[i].close
        if last_high is not None and last_high.index < i and close > last_high.price:
            kind = "CHOCH" if trend == "bearish" else "BOS"
            events.append(StructureEvent(i, kind, "bullish", last_high.price))
            trend = "bullish"
            continue
        if last_low is not None and last_low.index < i and close < last_low.price:
            kind = "CHOCH" if trend == "bullish" else "BOS"
            events.append(StructureEvent(i, kind, "bearish", last_low.price))
            trend = "bearish"
    return events


def find_fair_value_gaps(
    bars: Sequence[Bar], min_size_fraction: float = 0.0
) -> List[FairValueGap]:
    """Three-bar imbalances where bar 1 and bar 3 do not overlap.

    A bullish gap means the move up was fast enough that bar 3's low never
    traded down to bar 1's high, leaving unfilled interest between them.
    """
    gaps: List[FairValueGap] = []
    for i in range(2, len(bars)):
        first, third = bars[i - 2], bars[i]
        if third.low > first.high:
            size = third.low - first.high
            if third.close > 0 and size / third.close >= min_size_fraction:
                gaps.append(FairValueGap(i, "bullish", third.low, first.high))
        elif third.high < first.low:
            size = first.low - third.high
            if third.close > 0 and size / third.close >= min_size_fraction:
                gaps.append(FairValueGap(i, "bearish", first.low, third.high))
    return gaps


def find_order_blocks(
    bars: Sequence[Bar], impulse_bars: int = 3, lookback: int = 2
) -> List[OrderBlock]:
    """The last opposing candle before a move that breaks structure.

    A bullish order block is the final down-close candle before an advance
    that takes out a prior swing high.  The zone is that candle's range.
    """
    blocks: List[OrderBlock] = []
    for event in detect_structure(bars, lookback):
        i = event.index
        if event.direction == "bullish":
            for j in range(i - 1, max(-1, i - impulse_bars - 1), -1):
                if bars[j].close < bars[j].open:
                    blocks.append(OrderBlock(j, "bullish", bars[j].high, bars[j].low))
                    break
        else:
            for j in range(i - 1, max(-1, i - impulse_bars - 1), -1):
                if bars[j].close > bars[j].open:
                    blocks.append(OrderBlock(j, "bearish", bars[j].high, bars[j].low))
                    break
    return blocks


def find_liquidity_sweeps(
    bars: Sequence[Bar], lookback: int = 2, min_reversal: float = 0.0
) -> List[LiquiditySweep]:
    """Wicks that take out a prior swing then close back inside it.

    The stops resting beyond a swing are the liquidity; a sweep is price
    reaching through to take them and then rejecting, which is a different
    event from a genuine break and is why the close matters, not the wick.
    """
    swings = find_swings(bars, lookback)
    sweeps: List[LiquiditySweep] = []
    for i in range(1, len(bars)):
        bar = bars[i]
        seen = _visible(swings, i)
        for swing in reversed(seen):
            if swing.index >= i:
                continue
            if swing.kind == "low" and bar.low < swing.price <= bar.close:
                depth = swing.price - bar.low
                if bar.close > 0 and depth / bar.close >= min_reversal:
                    sweeps.append(LiquiditySweep(i, "bullish", swing.price, depth))
                break
            if swing.kind == "high" and bar.high > swing.price >= bar.close:
                depth = bar.high - swing.price
                if bar.close > 0 and depth / bar.close >= min_reversal:
                    sweeps.append(LiquiditySweep(i, "bearish", swing.price, depth))
                break
    return sweeps


def equilibrium(bars: Sequence[Bar], window: int = 40) -> Optional[Dict[str, float]]:
    """Premium/discount position of the last close within its recent range.

    0.0 is the low of the range, 1.0 the high, 0.5 equilibrium. The teaching
    is to buy in discount and sell in premium, so `position` below 0.5 is the
    side a long is supposed to be taken from.
    """
    if len(bars) < window:
        return None
    recent = bars[-window:]
    high = max(b.high for b in recent)
    low = min(b.low for b in recent)
    if high <= low:
        return None
    close = bars[-1].close
    position = (close - low) / (high - low)
    return {
        "range_high": high,
        "range_low": low,
        "equilibrium": (high + low) / 2.0,
        "position": position,
        "is_discount": 1.0 if position < 0.5 else 0.0,
        "distance_from_equilibrium": position - 0.5,
    }


def smc_features(bars: Sequence[Bar], lookback: int = 2, window: int = 40) -> Dict[str, float]:
    """Everything above, reduced to numbers a model or gate can consume.

    All of it is computed from bars up to and including the last one supplied,
    and swing-derived values respect their confirmation lag, so this is safe to
    call inside a walk-forward loop.
    """
    end = len(bars) - 1
    close = bars[-1].close if bars else 0.0
    out: Dict[str, float] = {
        "smc_bullish_bos": 0.0,
        "smc_bearish_bos": 0.0,
        "smc_bullish_choch": 0.0,
        "smc_bars_since_structure": float(len(bars)),
        "smc_in_bullish_fvg": 0.0,
        "smc_nearest_fvg_distance": 0.0,
        "smc_in_bullish_order_block": 0.0,
        "smc_recent_bullish_sweep": 0.0,
        "smc_equilibrium_position": 0.5,
        "smc_is_discount": 0.0,
    }
    if len(bars) < max(window, lookback * 2 + 2):
        return out

    events = detect_structure(bars, lookback, as_of=end)
    if events:
        last = events[-1]
        out["smc_bullish_bos"] = 1.0 if (last.kind == "BOS" and last.direction == "bullish") else 0.0
        out["smc_bearish_bos"] = 1.0 if (last.kind == "BOS" and last.direction == "bearish") else 0.0
        out["smc_bullish_choch"] = 1.0 if (last.kind == "CHOCH" and last.direction == "bullish") else 0.0
        out["smc_bars_since_structure"] = float(end - last.index)

    gaps = [g for g in find_fair_value_gaps(bars) if g.direction == "bullish" and g.index <= end]
    if gaps:
        nearest = min(gaps, key=lambda g: abs(g.midpoint - close))
        out["smc_in_bullish_fvg"] = 1.0 if nearest.contains(close) else 0.0
        out["smc_nearest_fvg_distance"] = (close - nearest.midpoint) / close if close else 0.0

    blocks = [b for b in find_order_blocks(bars, lookback=lookback)
              if b.direction == "bullish" and b.index <= end]
    if blocks:
        out["smc_in_bullish_order_block"] = 1.0 if any(b.contains(close) for b in blocks[-3:]) else 0.0

    sweeps = [s for s in find_liquidity_sweeps(bars, lookback) if s.direction == "bullish"]
    if sweeps and end - sweeps[-1].index <= 5:
        out["smc_recent_bullish_sweep"] = 1.0

    eq = equilibrium(bars, window)
    if eq:
        out["smc_equilibrium_position"] = eq["position"]
        out["smc_is_discount"] = eq["is_discount"]
    return out
