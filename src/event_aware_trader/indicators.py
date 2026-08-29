"""Dependency-free technical calculations used by the signal and regime gates.

Every function reads only the values it is given and treats the final element as
"now".  None of them look ahead: a caller that passes ``bars[:i + 1]`` cannot
obtain information from ``bars[i + 1]``.  Each returns ``None`` rather than a
partial estimate when there is not enough history, so a caller is forced to
handle the short-history case instead of silently trading on a warm-up value.
"""

import math
from typing import List, Optional, Sequence, Tuple

from .types import Bar


TRADING_DAYS_PER_YEAR = 252


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return sum(values) / len(values)


def stdev(values: Sequence[float], sample: bool = True) -> Optional[float]:
    """Standard deviation; ``None`` when there are too few observations."""
    minimum = 2 if sample else 1
    if len(values) < minimum:
        return None
    average = mean(values)
    divisor = len(values) - 1 if sample else len(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / divisor)


def sma(values: Sequence[float], period: int) -> Optional[float]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return None
    return mean(values[-period:])


def ema(values: Sequence[float], period: int) -> Optional[float]:
    """Exponential average seeded with an SMA so the result is deterministic."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return None
    multiplier = 2.0 / (period + 1.0)
    current = mean(values[:period])
    for value in values[period:]:
        current = (value - current) * multiplier + current
    return current


def percentage_return(values: Sequence[float], periods: int) -> Optional[float]:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return values[-1] / values[-periods - 1] - 1.0


def log_returns(values: Sequence[float]) -> List[float]:
    """Bar-to-bar log returns, skipping any non-positive price pair."""
    result: List[float] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        current = values[index]
        if previous > 0 and current > 0:
            result.append(math.log(current / previous))
    return result


def true_ranges(bars: Sequence[Bar]) -> List[float]:
    """True range for every bar after the first."""
    result: List[float] = []
    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1].close
        result.append(
            max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close))
        )
    return result


def average_true_range(bars: Sequence[Bar], period: int = 14) -> Optional[float]:
    """Simple ATR using only information available at the last supplied bar."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(bars) < period + 1:
        return None
    ranges = true_ranges(bars[-period - 1:])
    return mean(ranges)


def wilder_atr(bars: Sequence[Bar], period: int = 14) -> Optional[float]:
    """Wilder-smoothed ATR.

    Wilder smoothing responds more slowly than a flat average, so a single wide
    bar cannot collapse position size on its own the way it can with a simple
    mean.  It needs roughly twice the history to stabilise.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if len(bars) < period + 1:
        return None
    ranges = true_ranges(bars)
    current = mean(ranges[:period])
    for value in ranges[period:]:
        current = (current * (period - 1) + value) / period
    return current


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI.  Used here to avoid buying an already-stretched move."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period + 1:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gain = mean(gains[:period])
    average_loss = mean(losses[:period])
    for index in range(period, len(gains)):
        average_gain = (average_gain * (period - 1) + gains[index]) / period
        average_loss = (average_loss * (period - 1) + losses[index]) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def adx(bars: Sequence[Bar], period: int = 14) -> Optional[Tuple[float, float, float]]:
    """Wilder's ADX with the directional indicators, as ``(adx, +di, -di)``.

    ADX separates "trending" from "chopping".  A moving-average cross in a
    directionless market is the classic way a trend rule bleeds money on costs,
    so the strategy uses this as a gate rather than as a return forecast.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if len(bars) < 2 * period + 1:
        return None
    plus_dm: List[float] = []
    minus_dm: List[float] = []
    ranges: List[float] = []
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]
        up_move = current.high - previous.high
        down_move = previous.low - current.low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        ranges.append(
            max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close))
        )
    smooth_tr = sum(ranges[:period])
    smooth_plus = sum(plus_dm[:period])
    smooth_minus = sum(minus_dm[:period])
    directional_indexes: List[float] = []
    for index in range(period, len(ranges)):
        smooth_tr = smooth_tr - smooth_tr / period + ranges[index]
        smooth_plus = smooth_plus - smooth_plus / period + plus_dm[index]
        smooth_minus = smooth_minus - smooth_minus / period + minus_dm[index]
        if smooth_tr <= 0:
            directional_indexes.append(0.0)
            continue
        plus_di = 100.0 * smooth_plus / smooth_tr
        minus_di = 100.0 * smooth_minus / smooth_tr
        total = plus_di + minus_di
        directional_indexes.append(100.0 * abs(plus_di - minus_di) / total if total else 0.0)
    if len(directional_indexes) < period:
        return None
    current_adx = mean(directional_indexes[:period])
    for value in directional_indexes[period:]:
        current_adx = (current_adx * (period - 1) + value) / period
    final_plus = 100.0 * smooth_plus / smooth_tr if smooth_tr > 0 else 0.0
    final_minus = 100.0 * smooth_minus / smooth_tr if smooth_tr > 0 else 0.0
    return current_adx, final_plus, final_minus


def donchian(bars: Sequence[Bar], period: int = 20, exclude_current: bool = True) -> Optional[Tuple[float, float]]:
    """Highest high and lowest low over ``period`` bars, as ``(high, low)``.

    ``exclude_current`` leaves out the final bar so a breakout test compares
    today against a channel today did not help build.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    window = bars[:-1] if exclude_current else bars
    if len(window) < period:
        return None
    recent = window[-period:]
    return max(bar.high for bar in recent), min(bar.low for bar in recent)


def realized_volatility(values: Sequence[float], period: int = 20, annualize: bool = True) -> Optional[float]:
    """Standard deviation of log returns over the last ``period`` returns."""
    if period < 2:
        raise ValueError("period must be at least two")
    returns = log_returns(values)
    if len(returns) < period:
        return None
    deviation = stdev(returns[-period:])
    if deviation is None:
        return None
    return deviation * math.sqrt(TRADING_DAYS_PER_YEAR) if annualize else deviation


def downside_volatility(returns: Sequence[float], annualize: bool = True) -> Optional[float]:
    """Volatility of negative returns only; the denominator of a Sortino ratio."""
    negatives = [value for value in returns if value < 0]
    if len(negatives) < 2:
        return None
    deviation = math.sqrt(sum(value ** 2 for value in negatives) / len(negatives))
    return deviation * math.sqrt(TRADING_DAYS_PER_YEAR) if annualize else deviation


def zscore(values: Sequence[float], period: int = 20) -> Optional[float]:
    """How many standard deviations the last value sits from its own average."""
    if period < 2:
        raise ValueError("period must be at least two")
    if len(values) < period:
        return None
    window = values[-period:]
    deviation = stdev(window)
    if deviation is None or deviation == 0:
        return None
    return (values[-1] - mean(window)) / deviation


def percentile_rank(values: Sequence[float], lookback: int = 252) -> Optional[float]:
    """Fraction of the lookback window at or below the current value, in [0, 1].

    Used for regime work: an absolute volatility threshold ages badly, but "this
    is the calmest quartile of the past year" stays interpretable.
    """
    if lookback < 2:
        raise ValueError("lookback must be at least two")
    if len(values) < 2:
        return None
    window = values[-lookback:]
    current = window[-1]
    return sum(1 for value in window if value <= current) / len(window)


def linear_regression(values: Sequence[float], period: int) -> Optional[Tuple[float, float]]:
    """Least-squares fit over the last ``period`` values, as ``(slope, r_squared)``.

    The slope is per bar in the units supplied; pass log prices to read it as a
    compounding rate.  R-squared measures how orderly the move is, which
    separates a steady advance from a spike that a stop cannot survive.
    """
    if period < 3:
        raise ValueError("period must be at least three")
    if len(values) < period:
        return None
    window = values[-period:]
    count = float(period)
    mean_x = (count - 1.0) / 2.0
    mean_y = mean(window)
    covariance = 0.0
    variance_x = 0.0
    for index, value in enumerate(window):
        delta_x = index - mean_x
        covariance += delta_x * (value - mean_y)
        variance_x += delta_x * delta_x
    if variance_x == 0:
        return None
    slope = covariance / variance_x
    total_sum_squares = sum((value - mean_y) ** 2 for value in window)
    if total_sum_squares == 0:
        return slope, 1.0
    residual = sum(
        (value - (mean_y + slope * (index - mean_x))) ** 2 for index, value in enumerate(window)
    )
    r_squared = max(0.0, min(1.0, 1.0 - residual / total_sum_squares))
    return slope, r_squared


def trend_quality(values: Sequence[float], period: int = 40) -> Optional[Tuple[float, float]]:
    """Annualised log-price slope and its R-squared over ``period`` bars."""
    positive = [value for value in values[-period:] if value > 0]
    if len(positive) < period:
        return None
    fit = linear_regression([math.log(value) for value in positive], period)
    if fit is None:
        return None
    slope, r_squared = fit
    return slope * TRADING_DAYS_PER_YEAR, r_squared


def prior_average_volume(bars: Sequence[Bar], period: int = 20) -> Optional[float]:
    """Average volume excluding the current bar to avoid contaminating RVOL."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(bars) < period + 1:
        return None
    return mean([bar.volume for bar in bars[-period - 1:-1]])


def correlation(left: Sequence[float], right: Sequence[float]) -> Optional[float]:
    """Pearson correlation over the overlapping tail of two series."""
    length = min(len(left), len(right))
    if length < 3:
        return None
    a = list(left[-length:])
    b = list(right[-length:])
    mean_a = mean(a)
    mean_b = mean(b)
    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    variance_a = sum((x - mean_a) ** 2 for x in a)
    variance_b = sum((y - mean_b) ** 2 for y in b)
    if variance_a <= 0 or variance_b <= 0:
        return None
    return covariance / math.sqrt(variance_a * variance_b)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Deepest peak-to-trough decline as a negative fraction."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def ulcer_index(equity_curve: Sequence[float]) -> float:
    """Root-mean-square drawdown.

    Unlike max drawdown this counts how *long* an account stays underwater, not
    only how deep one bad stretch went.
    """
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    squares = []
    for value in equity_curve:
        peak = max(peak, value)
        squares.append(0.0 if peak <= 0 else (min(0.0, value / peak - 1.0) * 100.0) ** 2)
    return math.sqrt(mean(squares)) if squares else 0.0
