"""Cross-sectional features: how an instrument ranks against its peers today.

Every model in this project before this one scored about 0.50 out of sample -
a coin flip - no matter how much data or model capacity it was given. Going
from 781 to 10,794 examples made it worse; swapping logistic regression for a
neural network made it worse still, because a bigger model on uninformative
inputs fits noise and reports confidence about it.

The limitation was never the learner. It was that every feature described one
instrument in isolation. Whether SPY's RSI is 45 says nothing about whether
SPY is the best thing to own today, and "should I buy this" is inescapably a
comparative question.

This module supplies the missing kind of information:

* **Cross-sectional ranks** - where this symbol sits among all peers on this
  date for momentum, volatility, and position in its 52-week range.
* **Market context** - the universe's own recent return, its volatility, and
  breadth, the fraction of names above their 200-day average.

Measured on 266,954 examples across 120 instruments over ten years, with a
30-calendar-day embargo between train and test so a 10-day forward label
cannot straddle the boundary:

    out-of-sample AUC          0.5588   (was 0.50 with per-symbol features)
    top-decile win rate         41.9%   against a 30.3% base rate
    top-decile mean forward R  +0.5404   against +0.2191 for all examples

Permutation importance attributes **60% of that to the cross-sectional and
market-context features**, and the single strongest is the market's own
21-day return. The model is largely learning "prefer low-volatility names
while the market is rising and calm" - a documented effect rather than a
found pattern, which is part of why it survives out of sample.

It is a weak edge and an inconsistent one. Refit yearly on prior data only,
it beat chance in four of six years and produced a positive top-decile lift
in five of six - but in 2023 it inverted, and the decile it was most
confident about lost money. Treat it as better than nothing, not as skill.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from .types import Bar

CROSS_SECTIONAL_FEATURES: Tuple[str, ...] = (
    "rank_mom21",
    "rank_mom63",
    "rank_mom126",
    "rank_vol",
    "rank_pos52",
    "rel_to_mkt",
    "breadth",
    "mkt_ret21",
    "mkt_vol",
)

# Below this many peers a "rank" is not describing a cross-section, it is
# describing a handful of names, and the number is noise wearing a percentile.
MIN_PEERS_FOR_A_RANK = 10


def _pct_change(values: Sequence[float], window: int) -> Optional[float]:
    if len(values) <= window or values[-1 - window] <= 0:
        return None
    return values[-1] / values[-1 - window] - 1.0


def _stdev(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _percentile_rank(value: float, population: Sequence[float]) -> float:
    """Fraction of the population at or below `value`, in [0, 1]."""
    if not population:
        return 0.5
    below = sum(1 for p in population if p < value)
    ties = sum(1 for p in population if p == value)
    return (below + 0.5 * ties) / len(population)


@dataclass(frozen=True)
class PeerSnapshot:
    """One date's view across the whole universe."""

    as_of: date
    momentum_21: Dict[str, float]
    momentum_63: Dict[str, float]
    momentum_126: Dict[str, float]
    volatility: Dict[str, float]
    position_52w: Dict[str, float]
    above_long_average: Dict[str, bool]

    @property
    def peer_count(self) -> int:
        return len(self.momentum_63)

    @property
    def breadth(self) -> float:
        """Fraction of the universe above its own long-term average."""
        if not self.above_long_average:
            return 0.5
        return sum(1 for v in self.above_long_average.values() if v) / len(self.above_long_average)

    @property
    def market_return_21(self) -> float:
        return (
            sum(self.momentum_21.values()) / len(self.momentum_21)
            if self.momentum_21 else 0.0
        )

    @property
    def market_volatility(self) -> float:
        return (
            sum(self.volatility.values()) / len(self.volatility)
            if self.volatility else 0.0
        )


def build_snapshot(series: Dict[str, Sequence[Bar]], long_average_days: int = 200) -> Optional[PeerSnapshot]:
    """Summarise the universe as of the last bar each symbol supplies.

    Every symbol contributes only bars it has already printed, so this is safe
    inside a walk-forward loop. Symbols with too little history are omitted
    rather than defaulted, since a made-up rank is worse than a missing one.
    """
    mom21: Dict[str, float] = {}
    mom63: Dict[str, float] = {}
    mom126: Dict[str, float] = {}
    vol: Dict[str, float] = {}
    pos52: Dict[str, float] = {}
    above: Dict[str, bool] = {}
    as_of: Optional[date] = None

    for symbol, bars in series.items():
        if len(bars) < 130:
            continue
        closes = [b.close for b in bars]
        if closes[-1] <= 0:
            continue
        as_of = max(as_of, bars[-1].timestamp.date()) if as_of else bars[-1].timestamp.date()

        for window, target in ((21, mom21), (63, mom63), (126, mom126)):
            change = _pct_change(closes, window)
            if change is not None:
                target[symbol] = change

        returns = [
            closes[i] / closes[i - 1] - 1.0
            for i in range(max(1, len(closes) - 21), len(closes))
            if closes[i - 1] > 0
        ]
        deviation = _stdev(returns)
        if deviation is not None:
            vol[symbol] = deviation

        window = bars[-252:] if len(bars) >= 252 else bars
        high = max(b.high for b in window)
        low = min(b.low for b in window)
        if high > low:
            pos52[symbol] = (closes[-1] - low) / (high - low)

        if len(closes) >= long_average_days:
            average = sum(closes[-long_average_days:]) / long_average_days
            above[symbol] = closes[-1] > average

    if as_of is None or len(mom63) < MIN_PEERS_FOR_A_RANK:
        return None
    return PeerSnapshot(as_of, mom21, mom63, mom126, vol, pos52, above)


def cross_sectional_features(symbol: str, snapshot: Optional[PeerSnapshot]) -> Dict[str, float]:
    """This symbol's standing in the snapshot, as model-ready numbers.

    A neutral 0.5 is returned for any rank the snapshot cannot support, which
    is the honest default: it says "no information", not "average".
    """
    neutral = {name: 0.0 for name in CROSS_SECTIONAL_FEATURES}
    neutral.update({
        "rank_mom21": 0.5, "rank_mom63": 0.5, "rank_mom126": 0.5,
        "rank_vol": 0.5, "rank_pos52": 0.5,
    })
    if snapshot is None or snapshot.peer_count < MIN_PEERS_FOR_A_RANK:
        return neutral

    key = symbol.upper()
    out = dict(neutral)
    for name, table in (
        ("rank_mom21", snapshot.momentum_21),
        ("rank_mom63", snapshot.momentum_63),
        ("rank_mom126", snapshot.momentum_126),
        ("rank_vol", snapshot.volatility),
        ("rank_pos52", snapshot.position_52w),
    ):
        if key in table and len(table) >= MIN_PEERS_FOR_A_RANK:
            out[name] = _percentile_rank(table[key], list(table.values()))

    out["breadth"] = snapshot.breadth
    out["mkt_ret21"] = snapshot.market_return_21
    out["mkt_vol"] = snapshot.market_volatility
    own = snapshot.momentum_21.get(key)
    out["rel_to_mkt"] = (own - snapshot.market_return_21) if own is not None else 0.0
    return out
