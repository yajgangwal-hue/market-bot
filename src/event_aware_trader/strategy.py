"""A long-only candidate gate for liquid ETF research.

The gate is two separate mechanisms, and keeping them separate is the point:

* **Blockers** are hard, non-negotiable conditions.  Any one of them rejects the
  candidate outright, no matter how attractive everything else looks.  They
  encode the things that are known to destroy accounts - illiquidity, no trend,
  costs larger than the expected move, a risk limit already breached.
* **Score** is a weighted sum of bounded, named components that only ever runs
  *after* every blocker has passed.  It ranks survivors; it does not rescue a
  failure, and it is not a probability of profit.

Every component is reported with its own value and contribution, so a reader can
see exactly which evidence carried a candidate over the line.
"""

import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .events import active_event_impact, in_event_blackout
from .indicators import (
    adx,
    average_true_range,
    donchian,
    percentage_return,
    prior_average_volume,
    rsi,
    sma,
    trend_quality,
    wilder_atr,
)
from .regime import MarketRegime, RegimeConfig, classify_regime
from .risk import CostModel, RiskPolicy, evaluate_guard, position_size
from .types import Action, Bar, Candidate, Event, ScoreComponent


# One position per bucket at a time.  Two names in the same bucket are close
# to the same trade twice, which doubles the intended risk while looking like
# diversification.  The bucket, not the ticker, is what the cap counts.
CORRELATION_BUCKETS: Dict[str, str] = {
    # broad equity
    "SPY": "broad_equity",
    "DIA": "broad_equity",
    "IWM": "small_cap",
    # sectors
    "QQQ": "technology",
    "XLK": "technology",
    "XLE": "energy",
    "USO": "energy",
    "XLF": "financials",
    "XLV": "healthcare",
    "XLP": "staples",
    "XLU": "utilities",
    "XLI": "industrials",
    "XLB": "materials",
    "XLY": "discretionary",
    "VNQ": "real_estate",
    # duration and metals
    "TLT": "duration",
    "GLD": "precious_metals",
    "SLV": "precious_metals",
    # international
    "EFA": "developed_intl",
    "EEM": "emerging",
}
DEFAULT_UNIVERSE = tuple(CORRELATION_BUCKETS.keys())


@dataclass(frozen=True)
class ScoreWeights:
    """Maximum points each evidence component can contribute.

    Positive weights sum to 100 so the score reads as a percentage of available
    evidence.  ``extension_penalty`` is subtracted, so the achievable range is
    ``[-extension_penalty - event_alignment, 100]``.
    """

    trend_structure: float = 16.0
    trend_quality: float = 13.0
    trend_strength: float = 12.0
    momentum: float = 13.0
    participation: float = 10.0
    volatility_fit: float = 8.0
    breakout: float = 8.0
    regime: float = 8.0
    event_alignment: float = 12.0
    extension_penalty: float = 10.0

    @property
    def positive_total(self) -> float:
        return (
            self.trend_structure + self.trend_quality + self.trend_strength + self.momentum
            + self.participation + self.volatility_fit + self.breakout + self.regime
            + self.event_alignment
        )


@dataclass(frozen=True)
class StrategyConfig:
    short_ma_days: int = 20
    long_ma_days: int = 50
    atr_days: int = 14
    volume_days: int = 20
    momentum_days: int = 5
    trend_quality_days: int = 40
    adx_days: int = 14
    breakout_days: int = 20
    rsi_days: int = 14
    min_price: float = 20.0
    min_average_dollar_volume: float = 50_000_000.0
    min_relative_volume: float = 1.20
    min_atr_fraction: float = 0.003
    max_atr_fraction: float = 0.10
    min_adx: float = 18.0
    min_trend_r_squared: float = 0.40
    max_atr_extension: float = 4.0
    stop_atr_multiple: float = 2.0
    reward_to_risk: float = 2.0
    minimum_score: float = 70.0
    # How long a simulated position may stay open before it is closed at the
    # market.  This was a literal 5 buried in the backtest loop while it
    # decided roughly seven out of ten exits: with a 2-ATR stop and a 2R
    # target, a 5-bar window is usually too short for the target to be
    # reached, so most trades ended at whatever the clock happened to show.
    # Naming it makes that trade-off visible and testable.
    max_holding_bars: int = 5
    # "fixed_time" closes at max_holding_bars no matter what the position is
    # doing.  On the two-year record that clock decided 9 of 13 exits while
    # only one trade ever reached its target, so the rule was risking 1R to
    # collect roughly +0.14R and the account sat in cash 85% of the time.
    # "trailing" instead keeps a winner invested: the stop ratchets up behind
    # the running high and never loosens, the fixed target is dropped so an
    # advance is not truncated, and the position closes only when the trail is
    # hit.  It is a different bet - it trades a higher win rate for a longer
    # right tail - so it is opt-in and measured, not the default.
    # "trailing" is the default because it beat "fixed_time" in all 15
    # parameter combinations tested over the two-year record, not at a single
    # lucky setting - a broad plateau rather than a knife-edge.  2.5 ATR is
    # the *middle* of that plateau, deliberately not its peak (2.0 ATR scored
    # highest); picking the maximum of a sweep is how a backtest gets fitted
    # to its own noise.  Seven trades still prove nothing on their own.
    exit_mode: str = "trailing"
    trail_atr_multiple: float = 2.5
    trail_activate_r: float = 0.5
    max_trailing_bars: int = 250

    @property
    def stays_invested(self) -> bool:
        return self.exit_mode == "trailing"

    # Bars per US equity session, used to scale daily-calibrated magnitudes.
    # A move scales with the square root of time, so a 15-minute bar sees
    # roughly 1/sqrt(26) of a session's range, not 1/26 of it.
    BARS_PER_SESSION = {"1d": 1.0, "1h": 6.5, "30m": 13.0, "15m": 26.0, "5m": 78.0}

    @classmethod
    def for_interval(cls, interval: str = "1d", **overrides) -> "StrategyConfig":
        """Return a config whose magnitude bounds match the bar size.

        Only the *scale* of the thresholds changes.  The shape of the rules -
        which blockers are hard, what the score weighs, how the stop trails -
        is identical, so an intraday run is the same strategy observed more
        often rather than a different one.
        """
        if interval not in cls.BARS_PER_SESSION:
            raise ValueError("Unsupported interval: {0!r}".format(interval))
        import math as _math

        per_session = cls.BARS_PER_SESSION[interval]
        scale = 1.0 / _math.sqrt(per_session)
        settings = dict(
            volatility_scale=scale,
            score_separation_max=0.03 * scale,
            score_momentum_min=-0.02 * scale,
            score_momentum_max=0.04 * scale,
            score_breakout_min=-0.03 * scale,
            min_atr_fraction=0.003 * scale,
            max_atr_fraction=0.10 * scale,
            # Dollar volume is a per-bar figure, so it falls linearly with the
            # number of bars in a session, not with the square root.
            min_average_dollar_volume=50_000_000.0 / per_session,
        )
        settings.update(overrides)
        return cls(**settings)
    blackout_minutes: int = 90
    min_net_reward_to_risk: float = 1.2
    use_wilder_atr: bool = True
    use_regime_filter: bool = True
    use_volatility_targeting: bool = True
    # Relative volume, trend fit, and short-horizon momentum were each a hard
    # blocker *and* a scored component whose scale started at the blocker
    # threshold.  A component that can never observe a low value is dead
    # weight, and ANDing six independent ~50% filters left a 0.15% pass rate:
    # three candidates in two years across seven ETFs, which is too few to
    # measure anything.  These three are preferences, not the illiquidity and
    # cost failures that actually destroy an account, so by default they now
    # rank a survivor instead of rejecting it.  Set any flag True to restore
    # the previous hard gate.
    # The score's magnitude bounds were literals tuned to daily bars: a 3%
    # gap between the 20- and 50-bar averages, a 4% five-bar move.  On 15-minute
    # bars the same structures are roughly a seventh the size, so every
    # magnitude component scored near zero and the total could not reach the
    # threshold however good the setup was - 174 candidates cleared every
    # blocker and only one ever cleared the score.  `volatility_scale` divides
    # the bounds so the same shape is graded on the scale it actually occurs
    # at.  1.0 is daily; `for_interval` derives the rest.
    volatility_scale: float = 1.0
    score_separation_max: float = 0.03
    score_momentum_min: float = -0.02
    score_momentum_max: float = 0.04
    score_breakout_min: float = -0.03
    score_extension_max: float = 2.0

    strict_participation_gate: bool = False
    strict_momentum_gate: bool = False
    strict_trend_fit_gate: bool = False
    weights: ScoreWeights = ScoreWeights()

    def __post_init__(self) -> None:
        if self.short_ma_days >= self.long_ma_days:
            raise ValueError("short_ma_days must be shorter than long_ma_days")
        if self.min_atr_fraction >= self.max_atr_fraction:
            raise ValueError("min_atr_fraction must be below max_atr_fraction")
        if self.reward_to_risk <= 0 or self.stop_atr_multiple <= 0:
            raise ValueError("reward_to_risk and stop_atr_multiple must be positive")
        if self.max_holding_bars < 1:
            raise ValueError("max_holding_bars must be at least one")
        if self.volatility_scale <= 0:
            raise ValueError("volatility_scale must be positive")
        if self.exit_mode not in ("fixed_time", "trailing"):
            raise ValueError("exit_mode must be 'fixed_time' or 'trailing'")
        if self.trail_atr_multiple <= 0:
            raise ValueError("trail_atr_multiple must be positive")
        if not 0.0 <= self.min_trend_r_squared <= 1.0:
            raise ValueError("min_trend_r_squared must be between 0 and 1")

    @property
    def minimum_history(self) -> int:
        """Bars needed before every indicator is defined without warm-up bias."""
        return max(
            self.long_ma_days,
            self.trend_quality_days,
            2 * self.adx_days + 1,
            self.volume_days + 1,
            self.atr_days + 1,
            self.momentum_days + 1,
            self.breakout_days + 1,
            self.rsi_days + 1,
        )


def correlation_bucket(symbol: str) -> str:
    return CORRELATION_BUCKETS.get(symbol.upper(), "other")


def _scale(value: Optional[float], low: float, high: float) -> float:
    """Map ``value`` onto [0, 1] across the interval ``[low, high]``."""
    if value is None or high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _band_fit(value: Optional[float], low: float, high: float) -> float:
    """Peak at the log-centre of a band, falling to zero at either edge."""
    if value is None or value <= 0 or low <= 0 or high <= low or not low <= value <= high:
        return 0.0
    position = (math.log(value) - math.log(low)) / (math.log(high) - math.log(low))
    return max(0.0, 1.0 - abs(2.0 * position - 1.0))


def _rejected(
    symbol: str,
    as_of: datetime,
    bucket: str,
    reasons: List[str],
    blockers: List[str],
    features: Dict[str, Optional[float]],
    regime: Optional[MarketRegime] = None,
) -> Candidate:
    return Candidate(
        symbol=symbol,
        action=Action.REJECT,
        as_of=as_of,
        score=0.0,
        entry=None,
        stop=None,
        target=None,
        quantity=0,
        planned_risk=0.0,
        modeled_round_trip_cost=0.0,
        event_impact=0.0,
        reasons=reasons,
        blockers=blockers,
        correlation_bucket=bucket,
        score_breakdown=[],
        features=features,
        regime=regime.as_dict() if regime else {},
    )


def generate_candidate(
    symbol: str,
    bars: Sequence[Bar],
    events: Sequence[Event],
    equity: float,
    policy: RiskPolicy = RiskPolicy(),
    costs: CostModel = CostModel(),
    config: StrategyConfig = StrategyConfig(),
    daily_realized_pnl: float = 0.0,
    weekly_realized_pnl: float = 0.0,
    open_positions: int = 0,
    open_buckets: Sequence[str] = (),
    regime_config: RegimeConfig = RegimeConfig(),
) -> Candidate:
    """Evaluate only data available at the last supplied bar's close.

    The function has no order-routing side effects.  ``PAPER_LONG`` means the
    *research conditions* cleared; it is not an instruction to buy.
    """
    if not bars:
        raise ValueError("At least one bar is required")
    symbol = symbol.upper()
    as_of = bars[-1].timestamp
    bucket = correlation_bucket(symbol)
    reasons: List[str] = []
    blockers: List[str] = []
    features: Dict[str, Optional[float]] = {}

    if symbol not in DEFAULT_UNIVERSE:
        blockers.append("Symbol is outside the liquid, unleveraged default ETF universe")
    if len(bars) < config.minimum_history:
        blockers.append("Need at least {0} bars for non-look-ahead indicators".format(config.minimum_history))
    blackout = in_event_blackout(as_of, events, config.blackout_minutes)
    if blackout:
        blockers.append("Scheduled-event blackout: {0}".format(blackout.title))
    guard = evaluate_guard(
        equity, daily_realized_pnl, weekly_realized_pnl, open_positions, bucket, open_buckets, policy
    )
    blockers.extend(guard.reasons)
    if blockers:
        return _rejected(symbol, as_of, bucket, reasons, blockers, features)

    closes = [bar.close for bar in bars]
    close = bars[-1].close
    short_ma = sma(closes, config.short_ma_days)
    long_ma = sma(closes, config.long_ma_days)
    atr = wilder_atr(bars, config.atr_days) if config.use_wilder_atr else average_true_range(bars, config.atr_days)
    average_volume = prior_average_volume(bars, config.volume_days)
    momentum = percentage_return(closes, config.momentum_days)
    quality = trend_quality(closes, config.trend_quality_days)
    strength = adx(bars, config.adx_days)
    channel = donchian(bars, config.breakout_days)
    relative_strength_index = rsi(closes, config.rsi_days)

    required = {
        "short moving average": short_ma,
        "long moving average": long_ma,
        "ATR": atr,
        "average volume": average_volume,
        "momentum": momentum,
    }
    unavailable = sorted(name for name, value in required.items() if value is None)
    if unavailable or not atr or atr <= 0 or not average_volume:
        blockers.append(
            "Indicators could not be computed from the supplied history: {0}".format(
                ", ".join(unavailable) or "ATR or volume was zero"
            )
        )
        return _rejected(symbol, as_of, bucket, reasons, blockers, features)

    regime = classify_regime(bars, regime_config)
    relative_volume = bars[-1].volume / average_volume if average_volume else 0.0
    average_dollar_volume = average_volume * close
    atr_fraction = atr / close if close else 0.0
    extension_atr = (close - short_ma) / atr if atr else 0.0
    trend_slope, trend_r_squared = quality if quality else (None, None)
    adx_value, plus_di, minus_di = strength if strength else (None, None, None)
    channel_high, channel_low = channel if channel else (None, None)
    breakout_distance = (close / channel_high - 1.0) if channel_high else None
    event_impact, event_evidence = active_event_impact(symbol, events, as_of)

    features = {
        "close": close,
        "short_ma": short_ma,
        "long_ma": long_ma,
        "ma_separation": short_ma / long_ma - 1.0 if long_ma else None,
        "atr": atr,
        "atr_fraction": atr_fraction,
        "extension_atr": extension_atr,
        "relative_volume": relative_volume,
        "average_dollar_volume": average_dollar_volume,
        "momentum": momentum,
        "rsi": relative_strength_index,
        "adx": adx_value,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "trend_slope_annualized": trend_slope,
        "trend_r_squared": trend_r_squared,
        "breakout_distance": breakout_distance,
        "realized_volatility": regime.realized_volatility,
        "volatility_percentile": regime.volatility_percentile,
        "event_impact": event_impact,
    }

    # ---- Blockers -----------------------------------------------------------
    if close < config.min_price:
        blockers.append("Price below ${0:.2f} minimum".format(config.min_price))
    if average_dollar_volume < config.min_average_dollar_volume:
        blockers.append("Average dollar volume below ${0:,.0f} liquidity floor".format(config.min_average_dollar_volume))
    if config.strict_participation_gate and relative_volume < config.min_relative_volume:
        blockers.append("Relative volume {0:.2f} is below {1:.2f}".format(relative_volume, config.min_relative_volume))
    if not config.min_atr_fraction <= atr_fraction <= config.max_atr_fraction:
        blockers.append("ATR fraction {0:.2%} is outside the tradable range".format(atr_fraction))
    if close <= short_ma or short_ma <= long_ma:
        blockers.append(
            "Trend filter failed: price > {0}-day > {1}-day is required".format(config.short_ma_days, config.long_ma_days)
        )
    if config.strict_momentum_gate and momentum <= 0:
        blockers.append("Short-horizon momentum is non-positive")
    if adx_value is not None and adx_value < config.min_adx:
        blockers.append(
            "ADX {0:.1f} is below {1:.1f}; the market is ranging and a trend entry pays costs for nothing".format(
                adx_value, config.min_adx
            )
        )
    if config.strict_trend_fit_gate and trend_r_squared is not None and trend_r_squared < config.min_trend_r_squared:
        blockers.append(
            "Trend fit R-squared {0:.2f} is below {1:.2f}; the advance is too erratic to place a stop against".format(
                trend_r_squared, config.min_trend_r_squared
            )
        )
    if extension_atr > config.max_atr_extension:
        blockers.append(
            "Price is {0:.1f} ATRs above the {1}-day average; entering an extended move puts the stop past normal noise".format(
                extension_atr, config.short_ma_days
            )
        )
    if event_impact < -0.10:
        blockers.append("Reviewed event scenario conflicts with a new long candidate")
    if config.use_regime_filter:
        blockers.extend(regime.blockers)

    # ---- Position plan ------------------------------------------------------
    entry = close
    stop = entry - config.stop_atr_multiple * atr
    target = entry + config.reward_to_risk * (entry - stop)
    if stop <= 0:
        blockers.append("Calculated stop is non-positive")
    round_trip_cost = costs.round_trip_cost_per_share(entry, target)
    expected_move = target - entry
    if expected_move <= 2.0 * round_trip_cost:
        blockers.append("Expected move does not clear twice the modeled round-trip cost")

    net_reward = expected_move - round_trip_cost
    net_risk = (entry - stop) + costs.round_trip_cost_per_share(entry, stop)
    net_reward_to_risk = net_reward / net_risk if net_risk > 0 else None
    breakeven_win_rate = 1.0 / (1.0 + net_reward_to_risk) if net_reward_to_risk and net_reward_to_risk > 0 else None
    cost_to_edge_ratio = round_trip_cost / expected_move if expected_move > 0 else None
    if net_reward_to_risk is not None and net_reward_to_risk < config.min_net_reward_to_risk:
        blockers.append(
            "After costs the reward-to-risk is only {0:.2f}; below the {1:.2f} floor the rule needs a win rate it has not earned".format(
                net_reward_to_risk, config.min_net_reward_to_risk
            )
        )

    effective_policy = policy
    if config.use_volatility_targeting and regime.risk_multiplier < 1.0:
        effective_policy = replace(policy, risk_per_trade=policy.risk_per_trade * regime.risk_multiplier)
    quantity, planned_risk = position_size(equity, entry, stop, effective_policy, costs)
    if quantity <= 0:
        blockers.append(
            "Risk budget of {0:.2f} cannot fund a position at the defined stop "
            "(fractional sizing {1})".format(
                equity * effective_policy.risk_per_trade,
                "enabled" if effective_policy.allow_fractional_shares else "disabled",
            )
        )

    if blockers:
        candidate = _rejected(symbol, as_of, bucket, reasons, blockers, features, regime)
        return replace(
            candidate,
            entry=round(entry, 4),
            stop=round(stop, 4) if stop > 0 else None,
            target=round(target, 4),
            event_impact=round(event_impact, 3),
            net_reward_to_risk=None if net_reward_to_risk is None else round(net_reward_to_risk, 4),
            breakeven_win_rate=None if breakeven_win_rate is None else round(breakeven_win_rate, 4),
            cost_to_edge_ratio=None if cost_to_edge_ratio is None else round(cost_to_edge_ratio, 4),
        )

    # ---- Score: ranks survivors, never rescues a failure --------------------
    weights = config.weights
    components: List[ScoreComponent] = []

    separation = short_ma / long_ma - 1.0
    structure_value = 0.5 * _scale(separation, 0.0, config.score_separation_max) + 0.5 * _scale(
        extension_atr, 0.0, config.score_extension_max
    )
    components.append(ScoreComponent(
        "trend_structure", separation, structure_value * weights.trend_structure, weights.trend_structure,
        "{0}-day average is {1:+.2%} above the {2}-day, price {3:.1f} ATRs above the short average".format(
            config.short_ma_days, separation, config.long_ma_days, extension_atr),
    ))

    quality_floor = config.min_trend_r_squared if config.strict_trend_fit_gate else 0.0
    quality_value = _scale(trend_r_squared, quality_floor, 0.95)
    components.append(ScoreComponent(
        "trend_quality", trend_r_squared or 0.0, quality_value * weights.trend_quality, weights.trend_quality,
        "Log-price fit over {0} bars has R-squared {1:.2f}".format(config.trend_quality_days, trend_r_squared or 0.0),
    ))

    strength_value = _scale(adx_value, config.min_adx, 40.0)
    components.append(ScoreComponent(
        "trend_strength", adx_value or 0.0, strength_value * weights.trend_strength, weights.trend_strength,
        "ADX is {0:.1f} with +DI {1:.1f} against -DI {2:.1f}".format(adx_value or 0.0, plus_di or 0.0, minus_di or 0.0),
    ))

    # A shallow pullback inside an intact uptrend is a normal entry, so the
    # scale starts below zero rather than at the old rejection threshold.
    momentum_floor = 0.0 if config.strict_momentum_gate else config.score_momentum_min
    momentum_value = _scale(momentum, momentum_floor, config.score_momentum_max)
    components.append(ScoreComponent(
        "momentum", momentum, momentum_value * weights.momentum, weights.momentum,
        "{0}-bar return is {1:+.2%}".format(config.momentum_days, momentum),
    ))

    participation_floor = config.min_relative_volume if config.strict_participation_gate else 0.80
    participation_value = _scale(relative_volume, participation_floor, 2.0)
    components.append(ScoreComponent(
        "participation", relative_volume, participation_value * weights.participation, weights.participation,
        "Volume is {0:.2f}x its prior {1}-bar average".format(relative_volume, config.volume_days),
    ))

    volatility_value = _band_fit(atr_fraction, config.min_atr_fraction, config.max_atr_fraction)
    components.append(ScoreComponent(
        "volatility_fit", atr_fraction, volatility_value * weights.volatility_fit, weights.volatility_fit,
        "ATR is {0:.2%} of price, inside the {1:.2%}-{2:.2%} band".format(
            atr_fraction, config.min_atr_fraction, config.max_atr_fraction),
    ))

    breakout_value = _scale(breakout_distance, config.score_breakout_min, 0.0)
    components.append(ScoreComponent(
        "breakout", breakout_distance if breakout_distance is not None else 0.0,
        breakout_value * weights.breakout, weights.breakout,
        "Close is {0:+.2%} against the prior {1}-bar high".format(
            breakout_distance if breakout_distance is not None else 0.0, config.breakout_days),
    ))

    regime_scores = {"calm": 1.0, "normal": 0.75, "elevated": 0.35, "stressed": 0.0, "unknown": 0.5}
    regime_value = regime_scores.get(regime.volatility, 0.5)
    if regime.trend == "downtrend":
        regime_value *= 0.5
    components.append(ScoreComponent(
        "regime", regime_value, regime_value * weights.regime, weights.regime,
        "{0} trend in a {1} volatility environment".format(regime.trend, regime.volatility),
    ))

    event_contribution = max(-weights.event_alignment, min(weights.event_alignment, event_impact * weights.event_alignment))
    components.append(ScoreComponent(
        "event_alignment", event_impact, event_contribution, weights.event_alignment,
        "; ".join(event_evidence) if event_evidence else "No usable, timestamped event scenario was applied",
    ))

    overextension = max(0.0, extension_atr - config.max_atr_extension * 0.6)
    penalty = -_scale(overextension, 0.0, config.max_atr_extension * 0.4) * weights.extension_penalty
    if penalty < 0:
        components.append(ScoreComponent(
            "extension_penalty", extension_atr, penalty, 0.0,
            "Price is {0:.1f} ATRs above the short average; a late entry gives back part of the move".format(extension_atr),
        ))

    score = sum(component.contribution for component in components)
    reasons.extend(
        "{0}: {1} ({2:+.1f} of {3:.0f})".format(
            component.name, component.detail, component.contribution, component.maximum
        )
        for component in components
    )
    reasons.append(
        "Plan risks {0:.2f} to make {1:.2f} after modeled costs; the rule must win {2:.0%} of the time to break even".format(
            net_risk, net_reward, breakeven_win_rate if breakeven_win_rate else 0.0
        )
    )
    reasons.extend(regime.reasons)

    if score < config.minimum_score:
        action = Action.WATCH
        reasons.append(
            "Evidence score {0:.1f} is below the {1:.1f} gate; wait for another completed bar".format(
                score, config.minimum_score
            )
        )
    else:
        action = Action.PAPER_LONG
        reasons.append("Research gate passed; record as a paper trade only")

    return Candidate(
        symbol=symbol,
        action=action,
        as_of=as_of,
        score=round(score, 2),
        entry=round(entry, 4),
        stop=round(stop, 4),
        target=round(target, 4),
        quantity=quantity,
        planned_risk=round(planned_risk, 2),
        modeled_round_trip_cost=round(round_trip_cost * quantity, 2),
        event_impact=round(event_impact, 3),
        reasons=reasons,
        blockers=blockers,
        correlation_bucket=bucket,
        score_breakdown=components,
        features=features,
        regime=regime.as_dict(),
        net_reward_to_risk=round(net_reward_to_risk, 4) if net_reward_to_risk else None,
        breakeven_win_rate=round(breakeven_win_rate, 4) if breakeven_win_rate else None,
        cost_to_edge_ratio=round(cost_to_edge_ratio, 4) if cost_to_edge_ratio else None,
    )
