"""Market-regime classification for the pre-trade gate.

The same trend rule behaves very differently in a calm advance and in a
high-volatility decline.  Two adjustments here are among the better-supported
ideas in the public literature, and both are risk-reducing rather than
return-promising:

* **Long-term trend filter** - long-only trend entries taken below a long
  moving average have historically been where the deep drawdowns come from.
* **Volatility targeting** - scaling exposure down when realised volatility is
  high stabilises risk per position.  It does not raise expected return, and it
  is applied here only as a *reduction*, never as leverage.

Regime is measured from the instrument's own history, and optionally from a
supplied benchmark series, using only bars that have already closed.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .indicators import (
    linear_regression,
    log_returns,
    percentile_rank,
    realized_volatility,
    sma,
    stdev,
    TRADING_DAYS_PER_YEAR,
)
from .types import Bar


@dataclass(frozen=True)
class RegimeConfig:
    long_trend_days: int = 200
    volatility_days: int = 20
    volatility_lookback: int = 252
    calm_percentile: float = 0.25
    elevated_percentile: float = 0.75
    stressed_percentile: float = 0.90
    target_volatility: float = 0.15
    min_risk_multiplier: float = 0.25
    block_below_long_trend: bool = True
    block_when_stressed: bool = True

    def __post_init__(self) -> None:
        if not 0.0 < self.target_volatility <= 1.0:
            raise ValueError("target_volatility must be in (0, 1]")
        if not 0.0 < self.min_risk_multiplier <= 1.0:
            raise ValueError("min_risk_multiplier must be in (0, 1]")
        thresholds = (self.calm_percentile, self.elevated_percentile, self.stressed_percentile)
        if not all(0.0 < value < 1.0 for value in thresholds):
            raise ValueError("percentile thresholds must be strictly between 0 and 1")
        if not self.calm_percentile < self.elevated_percentile < self.stressed_percentile:
            raise ValueError("percentile thresholds must increase: calm < elevated < stressed")


@dataclass(frozen=True)
class MarketRegime:
    trend: str
    volatility: str
    realized_volatility: Optional[float]
    volatility_percentile: Optional[float]
    long_trend_slope: Optional[float]
    distance_to_long_ma: Optional[float]
    risk_multiplier: float
    allows_new_long: bool
    reasons: Tuple[str, ...]
    blockers: Tuple[str, ...]

    def as_dict(self) -> Dict[str, object]:
        return {
            "trend": self.trend,
            "volatility": self.volatility,
            "realized_volatility": None if self.realized_volatility is None else round(self.realized_volatility, 6),
            "volatility_percentile": None if self.volatility_percentile is None else round(self.volatility_percentile, 4),
            "long_trend_slope": None if self.long_trend_slope is None else round(self.long_trend_slope, 6),
            "distance_to_long_ma": None if self.distance_to_long_ma is None else round(self.distance_to_long_ma, 6),
            "risk_multiplier": round(self.risk_multiplier, 4),
            "allows_new_long": self.allows_new_long,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
        }


def rolling_realized_volatility(
    closes: Sequence[float], window: int, points: int
) -> List[float]:
    """Realised volatility at each of the last ``points`` closes.

    Returned oldest-first so ``percentile_rank`` reads the final element as now.
    """
    returns = log_returns(closes)
    if len(returns) < window:
        return []
    series: List[float] = []
    first = max(window, len(returns) - points + 1)
    for end in range(first, len(returns) + 1):
        deviation = stdev(returns[end - window:end])
        if deviation is not None:
            series.append(deviation * (TRADING_DAYS_PER_YEAR ** 0.5))
    return series


def classify_regime(bars: Sequence[Bar], config: RegimeConfig = RegimeConfig()) -> MarketRegime:
    """Describe the current environment from closed bars only."""
    closes = [bar.close for bar in bars]
    reasons: List[str] = []
    blockers: List[str] = []

    long_ma = sma(closes, config.long_trend_days)
    distance = None
    trend = "undefined"
    slope = None
    if long_ma is None:
        reasons.append(
            "Fewer than {0} bars, so the long-term trend regime is unknown".format(config.long_trend_days)
        )
    else:
        distance = closes[-1] / long_ma - 1.0 if long_ma else None
        fit = linear_regression(closes[-config.long_trend_days:], config.long_trend_days)
        slope = fit[0] if fit else None
        above = closes[-1] > long_ma
        rising = slope is not None and slope > 0
        if above and rising:
            trend = "uptrend"
        elif not above and not rising:
            trend = "downtrend"
        else:
            trend = "transitional"
        reasons.append(
            "Price is {0:+.2%} versus its {1}-day average and that average is {2}".format(
                distance if distance is not None else 0.0,
                config.long_trend_days,
                "rising" if rising else "flat or falling",
            )
        )

    current_volatility = realized_volatility(closes, config.volatility_days)
    percentile = None
    volatility = "unknown"
    if current_volatility is None:
        reasons.append("Not enough returns to measure realised volatility")
    else:
        series = rolling_realized_volatility(closes, config.volatility_days, config.volatility_lookback)
        percentile = percentile_rank(series, config.volatility_lookback) if len(series) >= 20 else None
        if percentile is None:
            volatility = "unknown"
            reasons.append(
                "Realised volatility is {0:.1%} annualised; there is too little history to rank it".format(current_volatility)
            )
        else:
            if percentile >= config.stressed_percentile:
                volatility = "stressed"
            elif percentile >= config.elevated_percentile:
                volatility = "elevated"
            elif percentile <= config.calm_percentile:
                volatility = "calm"
            else:
                volatility = "normal"
            reasons.append(
                "Realised volatility is {0:.1%} annualised, the {1:.0%} percentile of the trailing window".format(
                    current_volatility, percentile
                )
            )

    risk_multiplier = 1.0
    if current_volatility and current_volatility > 0:
        # Reduce only. Scaling *up* in calm markets is how a quiet regime turns
        # into an oversized position exactly before volatility returns.
        risk_multiplier = min(1.0, config.target_volatility / current_volatility)
        risk_multiplier = max(config.min_risk_multiplier, risk_multiplier)
        if risk_multiplier < 1.0:
            reasons.append(
                "Volatility target scales planned risk to {0:.0%} of the normal budget".format(risk_multiplier)
            )

    if config.block_below_long_trend and trend == "downtrend":
        blockers.append(
            "Long-term regime is a downtrend; long-only entries below the {0}-day average are blocked".format(
                config.long_trend_days
            )
        )
    if config.block_when_stressed and volatility == "stressed":
        blockers.append(
            "Volatility is in the top {0:.0%} of its trailing range; new long candidates are blocked".format(
                1.0 - config.stressed_percentile
            )
        )

    return MarketRegime(
        trend=trend,
        volatility=volatility,
        realized_volatility=current_volatility,
        volatility_percentile=percentile,
        long_trend_slope=slope,
        distance_to_long_ma=distance,
        risk_multiplier=risk_multiplier,
        allows_new_long=not blockers,
        reasons=tuple(reasons),
        blockers=tuple(blockers),
    )
