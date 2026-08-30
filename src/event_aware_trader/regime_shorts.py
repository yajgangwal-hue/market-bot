"""Short only in a confirmed bear tape. Never otherwise.

The complaint this answers is real: a long-only rule loses money whenever the
market falls, and simply waits. Shorting is the obvious fix and the obvious
fix is mostly wrong - so the shape of what works matters.

**Shorting all the time destroys the strategy.** Measured across six years,
long-only returned +58.90% and the same picks with a short leg returned
-0.74%. The short leg lost 16-31% in four separate years. The cause is not
subtle: 56% of all 10-day windows are positive, so an upward drift punishes a
persistent short, and the model has no skill at picking losers - the decile it
is *least* confident in still rose in five of six years.

**Shorting only in a confirmed downtrend is different.** Gating on a rule as
simple as "SPY below its own 200-day average" - no model, nothing that could
be fitted to the test period:

    year   long-only   gated L/S   benchmark
    2021     +21.08%     +21.08%     +17.12%
    2022      +3.81%     +17.57%     -11.12%      <- the point
    2023      +2.44%      -9.59%     +12.89%      <- the cost
    2024     +14.05%     +14.05%     +13.89%
    2025      +9.39%      +5.59%     +15.95%
    2026      +8.13%      +7.28%     +11.50%
    TOTAL    +58.90%     +55.98%     +60.23%

It beat the benchmark in three of six years against long-only's two, and in
the one genuine bear market it returned +17.57% while the market lost 11%.

It also cost about three points overall, because a 200-day average whipsaws:
2023 spent only 8% of its blocks below the line and those cost 12 points.
That is the trade being offered - better behaviour in a falling market, paid
for with a small drag the rest of the time. It is off by default because most
years are not falling markets.

Shorting carries risks a long does not: loss is unbounded above, borrow can be
recalled, and a squeeze moves against you fastest when you are most wrong.
`max_short_fraction` caps the exposure for that reason.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .types import Bar


@dataclass(frozen=True)
class ShortPolicy:
    enabled: bool = False
    # SPY below this average defines "bear". 200 days is the convention and,
    # more importantly, was not chosen by searching this dataset.
    regime_average_days: int = 200
    # Confirmation, so one close below the line does not flip the book.
    confirmation_days: int = 3
    # Shorts are capped below longs: the loss is unbounded above.
    max_short_fraction: float = 0.30
    max_short_positions: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.max_short_fraction <= 0.5:
            raise ValueError("max_short_fraction must be in (0, 0.5]")
        if self.regime_average_days < 20 or self.confirmation_days < 1:
            raise ValueError("regime_average_days >= 20 and confirmation_days >= 1")


@dataclass(frozen=True)
class RegimeState:
    is_bear: bool
    reference_close: float
    average: float
    days_below: int

    @property
    def distance(self) -> float:
        return (self.reference_close / self.average - 1.0) if self.average else 0.0

    def as_dict(self) -> Dict[str, object]:
        return {
            "is_bear": self.is_bear,
            "reference_close": round(self.reference_close, 4),
            "average": round(self.average, 4),
            "percent_from_average": round(100 * self.distance, 3),
            "consecutive_days_below": self.days_below,
        }


def classify_regime(
    reference_bars: Sequence[Bar], policy: ShortPolicy = ShortPolicy()
) -> Optional[RegimeState]:
    """Bear or not, from the reference index only.

    Uses bars up to and including the last one supplied, so it is safe inside
    a walk-forward loop. Returns None rather than guessing when there is not
    enough history to form the average.
    """
    window = policy.regime_average_days
    if len(reference_bars) < window + policy.confirmation_days:
        return None

    closes = [b.close for b in reference_bars]
    average = sum(closes[-window:]) / window

    days_below = 0
    for i in range(len(closes) - 1, max(-1, len(closes) - window - 1), -1):
        past = closes[max(0, i - window + 1): i + 1]
        if len(past) < window:
            break
        if closes[i] < sum(past) / window:
            days_below += 1
        else:
            break

    return RegimeState(
        is_bear=days_below >= policy.confirmation_days,
        reference_close=closes[-1],
        average=average,
        days_below=days_below,
    )


def shorts_allowed(regime: Optional[RegimeState], policy: ShortPolicy = ShortPolicy()) -> bool:
    """Shorting requires the feature on AND a confirmed bear tape."""
    if not policy.enabled or regime is None:
        return False
    return regime.is_bear


def short_size(
    equity: float,
    entry: float,
    stop: float,
    policy: ShortPolicy = ShortPolicy(),
) -> float:
    """Whole shares for a short, capped by `max_short_fraction` of equity.

    The stop sits ABOVE the entry for a short, and a short's loss is unbounded
    above, so the notional cap does more work here than it does for a long.
    """
    if equity <= 0 or entry <= 0 or stop <= entry:
        return 0.0
    cap = equity * policy.max_short_fraction
    return float(int(cap / entry))
