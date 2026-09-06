"""Significance tools that try to disprove an apparent edge.

A backtest that reports only a return and a win rate invites the reader to
mistake a small sample for a discovery.  Everything here exists to answer one
question honestly: *would results this good show up anyway, by chance, from a
rule with no edge?*  The estimators are deliberately conservative, deterministic
given a seed, and free of third-party dependencies.
"""

import math
import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple


EULER_MASCHERONI = 0.5772156649015329


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def normal_quantile(probability: float) -> float:
    """Inverse normal CDF (Acklam's rational approximation, ~1e-9 absolute)."""
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be strictly between 0 and 1")
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    low, high = 0.02425, 1.0 - 0.02425
    if probability < low:
        q = math.sqrt(-2.0 * math.log(probability))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if probability > high:
        q = math.sqrt(-2.0 * math.log(1.0 - probability))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    q = probability - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _variance(values: Sequence[float], sample: bool = True) -> float:
    if len(values) < 2:
        return 0.0
    average = _mean(values)
    divisor = len(values) - 1 if sample else len(values)
    return sum((value - average) ** 2 for value in values) / divisor


def _no_dispersion(values: Sequence[float], deviation: float) -> bool:
    """True when the spread is only floating-point residue.

    `deviation == 0` is not a sufficient test. The variance of ten identical
    0.01s is about 1e-36 rather than exactly zero, so the guard passed, the
    division went ahead, and a Sharpe ratio of 1.2e16 was returned as though
    it were a measurement. A strategy exiting every trade at a fixed target
    produces exactly that input.

    The threshold is relative to the size of the values so it behaves the same
    on returns of 0.01 and on P&L in thousands.
    """
    scale = max((abs(value) for value in values), default=0.0) or 1.0
    return deviation <= scale * 1e-12


def skewness(values: Sequence[float]) -> float:
    """Population skewness; zero when the sample cannot support an estimate."""
    if len(values) < 3:
        return 0.0
    average = _mean(values)
    deviation = math.sqrt(_variance(values, sample=False))
    if deviation == 0:
        return 0.0
    return sum(((value - average) / deviation) ** 3 for value in values) / len(values)


def kurtosis(values: Sequence[float]) -> float:
    """Non-excess kurtosis (3.0 for a normal distribution)."""
    if len(values) < 4:
        return 3.0
    average = _mean(values)
    deviation = math.sqrt(_variance(values, sample=False))
    if deviation == 0:
        return 3.0
    return sum(((value - average) / deviation) ** 4 for value in values) / len(values)


def sharpe_ratio(returns: Sequence[float], periods_per_year: int = 252, risk_free_rate: float = 0.0) -> Optional[float]:
    """Annualised Sharpe ratio from per-period returns."""
    if len(returns) < 2:
        return None
    per_period_rf = risk_free_rate / periods_per_year
    excess = [value - per_period_rf for value in returns]
    deviation = math.sqrt(_variance(excess))
    if _no_dispersion(excess, deviation):
        return None
    return _mean(excess) / deviation * math.sqrt(periods_per_year)


def sortino_ratio(returns: Sequence[float], periods_per_year: int = 252, target: float = 0.0) -> Optional[float]:
    """Annualised Sortino ratio; penalises downside deviation only."""
    if len(returns) < 2:
        return None
    downside = [min(0.0, value - target) for value in returns]
    deviation = math.sqrt(sum(value ** 2 for value in downside) / len(downside))
    if _no_dispersion(downside, deviation):
        return None
    return (_mean(returns) - target) / deviation * math.sqrt(periods_per_year)


def probabilistic_sharpe_ratio(
    returns: Sequence[float],
    benchmark_sharpe: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """Probability the true Sharpe ratio exceeds ``benchmark_sharpe``.

    Bailey and Lopez de Prado's PSR.  It corrects the naive Sharpe for sample
    size, negative skew, and fat tails - exactly the three properties that make
    a short stop-loss track record look better than it is.
    """
    if len(returns) < 4:
        return None
    deviation = math.sqrt(_variance(returns))
    if _no_dispersion(returns, deviation):
        return None
    observed = _mean(returns) / deviation
    target = benchmark_sharpe / math.sqrt(periods_per_year)
    skew = skewness(returns)
    kurt = kurtosis(returns)
    denominator = 1.0 - skew * observed + (kurt - 1.0) / 4.0 * observed ** 2
    if denominator <= 0:
        return None
    return normal_cdf((observed - target) * math.sqrt(len(returns) - 1) / math.sqrt(denominator))


def deflated_sharpe_ratio(
    returns: Sequence[float],
    trials: int,
    trial_sharpe_variance: Optional[float] = None,
    periods_per_year: int = 252,
) -> Optional[float]:
    """PSR against the Sharpe ratio a *lucky* trial would reach after ``trials``.

    Testing many rules and reporting the best one is the most common way a
    backtest lies.  This raises the bar to the expected maximum Sharpe of that
    many no-edge trials, so the reported number already pays for the search.
    """
    if trials < 1:
        raise ValueError("trials must be at least one")
    if len(returns) < 4:
        return None
    if trials == 1:
        return probabilistic_sharpe_ratio(returns, 0.0, periods_per_year)
    # Without an observed spread across trials, assume unit variance: the
    # standard conservative choice when the search history was not recorded.
    #
    # `trial_sharpe_variance` is in ANNUALISED Sharpe units, matching the
    # `benchmark_sharpe` that probabilistic_sharpe_ratio expects and
    # de-annualises internally. The expected maximum is therefore already
    # annualised, and the `* sqrt(periods_per_year)` that used to sit on the
    # next line annualised it a second time.
    #
    # The effect was total rather than marginal: at 94.5 trades a year the bar
    # for 20 trials became an annualised Sharpe of 18.5 instead of 1.90, so
    # every strategy ever passed to this function scored 0.0 and the deflation
    # looked like a damning verdict on everything. Nothing in the codebase
    # called it and no test pinned it, which is why it survived.
    variance = 1.0 if trial_sharpe_variance is None else trial_sharpe_variance
    upper = normal_quantile(1.0 - 1.0 / trials)
    lower = normal_quantile(1.0 - 1.0 / (trials * math.e))
    annualised_threshold = math.sqrt(variance) * (
        (1.0 - EULER_MASCHERONI) * upper + EULER_MASCHERONI * lower)
    return probabilistic_sharpe_ratio(returns, annualised_threshold, periods_per_year)


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = _mean,
    confidence: float = 0.95,
    iterations: int = 2000,
    seed: int = 20260828,
) -> Optional[Tuple[float, float]]:
    """Percentile bootstrap interval for any statistic of a sample."""
    if len(values) < 3 or not 0.5 < confidence < 1.0:
        return None
    generator = random.Random(seed)
    count = len(values)
    estimates = []
    for _ in range(iterations):
        sample = [values[generator.randrange(count)] for _ in range(count)]
        estimates.append(statistic(sample))
    estimates.sort()
    tail = (1.0 - confidence) / 2.0
    low = estimates[max(0, int(tail * iterations) - 1)]
    high = estimates[min(iterations - 1, int((1.0 - tail) * iterations))]
    return low, high


def block_bootstrap_ci(
    values: Sequence[float],
    block_size: int = 5,
    confidence: float = 0.95,
    iterations: int = 2000,
    seed: int = 20260828,
) -> Optional[Tuple[float, float]]:
    """Moving-block bootstrap interval for the mean.

    Trade results arrive in streaks: a regime that suits the rule produces
    several wins in a row.  Resampling single results pretends that structure
    away and reports an interval that is too narrow, so blocks are resampled
    instead.
    """
    if len(values) < max(3, block_size) or block_size < 1:
        return None
    generator = random.Random(seed)
    count = len(values)
    blocks_needed = int(math.ceil(count / block_size))
    estimates = []
    for _ in range(iterations):
        sample: List[float] = []
        for _ in range(blocks_needed):
            start = generator.randrange(max(1, count - block_size + 1))
            sample.extend(values[start:start + block_size])
        estimates.append(_mean(sample[:count]))
    estimates.sort()
    tail = (1.0 - confidence) / 2.0
    low = estimates[max(0, int(tail * iterations) - 1)]
    high = estimates[min(iterations - 1, int((1.0 - tail) * iterations))]
    return low, high


def sign_flip_pvalue(values: Sequence[float], iterations: int = 5000, seed: int = 20260828) -> Optional[float]:
    """One-sided randomisation p-value that the mean is greater than zero.

    Each result keeps its magnitude and gets a random sign.  Under a no-edge
    null a win and a loss of that size were equally likely, so the fraction of
    reshuffles that beat the observed mean is a direct significance estimate
    that assumes nothing about the shape of the distribution.
    """
    if len(values) < 5:
        return None
    generator = random.Random(seed)
    observed = _mean(values)
    at_least_as_extreme = 0
    for _ in range(iterations):
        flipped = _mean([value if generator.random() < 0.5 else -value for value in values])
        if flipped >= observed:
            at_least_as_extreme += 1
    return (at_least_as_extreme + 1) / (iterations + 1)


def monte_carlo_pvalue(observed: float, null_samples: Sequence[float]) -> Optional[float]:
    """Share of null draws at least as good as the observed statistic."""
    if not null_samples:
        return None
    at_least_as_extreme = sum(1 for value in null_samples if value >= observed)
    return (at_least_as_extreme + 1) / (len(null_samples) + 1)


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> Optional[Tuple[float, float]]:
    """Wilson score interval for a proportion; correct for small samples."""
    if trials <= 0 or successes < 0 or successes > trials:
        return None
    z = normal_quantile(1.0 - (1.0 - confidence) / 2.0)
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (proportion + z * z / (2.0 * trials)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def auc_roc(labels: Sequence[int], scores: Sequence[float]) -> Optional[float]:
    """Rank-based area under the ROC curve, with ties handled by mid-rank."""
    if len(labels) != len(scores) or not labels:
        return None
    positives = sum(1 for label in labels if label == 1)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ordered = sorted(range(len(scores)), key=lambda index: scores[index])
    ranks = [0.0] * len(scores)
    position = 0
    while position < len(ordered):
        end = position
        while end + 1 < len(ordered) and scores[ordered[end + 1]] == scores[ordered[position]]:
            end += 1
        average_rank = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            ranks[ordered[index]] = average_rank
        position = end + 1
    positive_rank_sum = sum(rank for rank, label in zip(ranks, labels) if label == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def log_loss(labels: Sequence[int], probabilities: Sequence[float], epsilon: float = 1e-12) -> Optional[float]:
    if not labels or len(labels) != len(probabilities):
        return None
    total = 0.0
    for label, probability in zip(labels, probabilities):
        clipped = min(1.0 - epsilon, max(epsilon, probability))
        total += -(label * math.log(clipped) + (1 - label) * math.log(1.0 - clipped))
    return total / len(labels)


def paired_bootstrap_better(
    reference_losses: Sequence[float],
    candidate_losses: Sequence[float],
    iterations: int = 2000,
    seed: int = 20260828,
) -> Optional[float]:
    """Probability the candidate's per-item loss really is lower.

    Both loss series are resampled with the *same* indices so the comparison
    stays paired.  A model that beats a base rate on one lucky slice of the
    holdout will not survive this.
    """
    if len(reference_losses) != len(candidate_losses) or len(reference_losses) < 5:
        return None
    generator = random.Random(seed)
    count = len(reference_losses)
    wins = 0
    for _ in range(iterations):
        indices = [generator.randrange(count) for _ in range(count)]
        reference = sum(reference_losses[index] for index in indices) / count
        candidate = sum(candidate_losses[index] for index in indices) / count
        if candidate < reference:
            wins += 1
    return wins / iterations


def longest_run(values: Sequence[float], predicate: Callable[[float], bool]) -> int:
    longest = 0
    current = 0
    for value in values:
        if predicate(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def describe_sample(values: Sequence[float], label: str = "sample") -> Dict[str, object]:
    """Compact, honest description of a result distribution."""
    if not values:
        return {"label": label, "count": 0}
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    median = ordered[midpoint] if len(ordered) % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / 2.0
    return {
        "label": label,
        "count": len(values),
        "mean": round(_mean(values), 6),
        "median": round(median, 6),
        "stdev": round(math.sqrt(_variance(values)), 6),
        "skewness": round(skewness(values), 6),
        "kurtosis": round(kurtosis(values), 6),
        "minimum": round(min(values), 6),
        "maximum": round(max(values), 6),
    }
