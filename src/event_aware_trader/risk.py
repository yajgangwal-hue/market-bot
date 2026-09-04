"""Pre-trade risk controls and cost model for paper-trading research."""

from dataclasses import dataclass
from math import floor
from typing import Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class RiskPolicy:
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_weekly_loss: float = 0.06
    # Chosen by grid search fitted ONLY on 2017-2022, then checked once on
    # 2023-2026. The config that won training also won the held-out window,
    # which is the reason to trust it rather than suspect a fitted artefact:
    #
    #   positions  risk    train/yr   HELD-OUT/yr   maxDD
    #       3      0.005     -0.69%      (not top)   -12.68%   <- was shipped
    #       6      0.005     +0.03%       +2.63%      -6.08%   <- now
    #      10      0.005     -0.04%       +1.73%      -6.22%
    #      15      0.005     -0.04%       +1.73%      -6.22%
    #
    # Past 6 this stops binding - the strategy never finds more than about ten
    # simultaneous candidates, so 10 and 15 are the same run. Raising
    # risk_per_trade instead made every configuration worse, which is the same
    # result sizing has produced every time it has been tested here: size
    # multiplies edge, and there is not much edge to multiply.
    #
    # Honest framing: +2.63%/yr is against a market that returned +22.52%/yr
    # over that same span. This is the best of what was tested, not a good
    # return.
    max_open_positions: int = 6
    # How much of the account ONE position may occupy. This is not a leverage
    # limit - it is a concentration limit, and it turned out to matter more
    # than anything else measured.
    #
    # At 95%, sizing on a funded account produced $58,000 median positions and
    # then STARVED the bot: 314 qualifying signals were skipped for lack of
    # cash because one position held nearly the whole balance. Capping each
    # position instead lets the same capital work across more of them:
    #
    #     cap    trades/day   median size   skipped   month return
    #     95%          2.22       $58,322       314        -1.09%
    #     20%          5.61       $20,125       126        +0.72%
    #     10%          7.43       $10,084        27        +0.50%
    #
    # It also collapses the variance. Split the month in half and the 95% cap
    # swings +1.85% to -4.26%, while 20% swings +1.19% to -0.72% and 10% only
    # +1.08% to -0.44%. That -4.26% was concentration, not strategy.
    #
    # 20% keeps positions substantial while letting five a day run. On a very
    # small account it can block a high-priced name entirely, since whole
    # shares are required for a broker-side stop - raise it there.
    max_notional_fraction: float = 0.20
    # An additional ceiling expressed against the instrument's own liquidity,
    # not the account's size. None leaves sizing unchanged.
    #
    # This exists because admitting crypto meant dropping the $50,000,000
    # liquidity floor by four orders of magnitude, and that floor was the only
    # thing standing between the bot and an order larger than the venue. BTC on
    # Alpaca prints about $103,000 a day; a 20%-of-equity position on a
    # $100,000 account is $20,000, or a fifth of it. DOT prints $1,320, which a
    # $20,000 order would exceed fifteen-fold.
    #
    # 2% of median daily dollar volume is a conventional participation ceiling
    # and puts BTC near $2,000 rather than $20,000. It binds only where
    # liquidity is genuinely thin: at SPY's $35bn it is never the constraint.
    max_volume_participation: Optional[float] = 0.02
    # Whole-share sizing silently disqualifies a small account from the most
    # liquid instruments in the universe.  At 0.5% risk a $1,000 account has a
    # $5.00 risk budget, while one share of SPY with a 2-ATR stop risks about
    # $17, so floor(5/17) == 0 and the candidate is rejected for a reason that
    # has nothing to do with the quality of the setup.  Every broker this
    # project targets for paper trading supports fractional/notional orders,
    # so the default is fractional and the risk percentage stays unchanged.
    allow_fractional_shares: bool = True
    fractional_decimals: int = 6
    min_notional: float = 1.0

    def __post_init__(self) -> None:
        for name in ("risk_per_trade", "max_daily_loss", "max_weekly_loss", "max_notional_fraction"):
            value = getattr(self, name)
            if not 0 < value <= 1:
                raise ValueError("{0} must be in (0, 1]".format(name))
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least one")
        if not 0 <= self.fractional_decimals <= 9:
            raise ValueError("fractional_decimals must be between 0 and 9")
        if self.min_notional < 0:
            raise ValueError("min_notional cannot be negative")


# Named risk profiles, so a change in position size is a deliberate choice
# rather than a number edited in passing.
#
# Measured on 2017-2023 - seven years deliberately EXCLUDING the 2024-2026
# window these were compared on - total return by profile was:
#
#     conservative (0.5%)   -3.46%      worst year -2.37%   worst drawdown  -4.39%
#     moderate     (1.0%)  -10.50%      worst year -4.19%   worst drawdown  -8.09%
#     aggressive   (2.0%)  -16.09%      worst year -5.66%   worst drawdown -15.23%
#
# Larger positions did not produce larger profits on held-out data; they
# produced larger losses, because position size multiplies whatever edge is
# there and over those seven years the edge was negative.  The single period
# where aggressive sizing looked good (2024-2026, +30.6%) is the period the
# comparison was run on, which is exactly why it cannot be the evidence.
#
# `conservative` therefore remains the default. The others exist so the choice
# is explicit and reversible, not because the data recommends them.
RISK_PROFILES = {
    "conservative": {"risk_per_trade": 0.005, "max_daily_loss": 0.015, "max_weekly_loss": 0.06},
    "moderate": {"risk_per_trade": 0.010, "max_daily_loss": 0.030, "max_weekly_loss": 0.10},
    "aggressive": {"risk_per_trade": 0.020, "max_daily_loss": 0.050, "max_weekly_loss": 0.15},
    "maximum": {"risk_per_trade": 0.050, "max_daily_loss": 0.100, "max_weekly_loss": 0.25},
}


def policy_for_profile(name: str, **overrides) -> "RiskPolicy":
    """Build a RiskPolicy from a named profile."""
    if name not in RISK_PROFILES:
        raise ValueError(
            "Unknown risk profile {0!r}. Choose one of: {1}".format(
                name, ", ".join(sorted(RISK_PROFILES))
            )
        )
    settings = dict(RISK_PROFILES[name])
    settings.update(overrides)
    return RiskPolicy(**settings)


@dataclass(frozen=True)
class CostModel:
    """Conservative one-way execution estimate for liquid ETF research."""

    half_spread_bps: float = 2.0
    slippage_bps: float = 4.0
    commission_per_share: float = 0.0

    @property
    def one_way_bps(self) -> float:
        return self.half_spread_bps + self.slippage_bps

    def one_way_cost_per_share(self, price: float) -> float:
        if price <= 0:
            raise ValueError("price must be positive")
        return price * self.one_way_bps / 10_000.0 + self.commission_per_share

    def round_trip_cost_per_share(self, entry: float, exit_price: float) -> float:
        return self.one_way_cost_per_share(entry) + self.one_way_cost_per_share(exit_price)

    def buy_fill(self, observed_price: float) -> float:
        return observed_price * (1.0 + self.one_way_bps / 10_000.0)

    def sell_fill(self, observed_price: float) -> float:
        return observed_price * (1.0 - self.one_way_bps / 10_000.0)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reasons: Tuple[str, ...]


def cap_by_participation(
    quantity: float,
    entry: float,
    average_dollar_volume: Optional[float],
    participation: Optional[float],
) -> float:
    """Shrink a size that would be a large share of the instrument's volume.

    Returns the quantity unchanged when no cap is configured or no liquidity
    figure is available - refusing to guess is better than inventing a ceiling
    from a missing number. A cap that computes to zero returns zero, and the
    caller declines the trade rather than sending an order the book cannot
    absorb.
    """
    if not participation or not average_dollar_volume or entry <= 0:
        return quantity
    allowed = (float(average_dollar_volume) * float(participation)) / entry
    return min(quantity, max(0.0, allowed))


def position_size(
    equity: float,
    entry: float,
    stop: float,
    policy: RiskPolicy,
    costs: CostModel,
) -> Tuple[float, float]:
    """Size a long position from pre-defined risk, including estimated costs.

    Returns ``(quantity, planned_risk)``.  ``quantity`` is a float so a small
    account can express a position in a high-priced ETF; it is still an exact
    whole number when ``allow_fractional_shares`` is False.  Rounding is always
    downward so the realised risk can never exceed the budget.
    """
    if equity <= 0 or entry <= 0 or stop <= 0 or stop >= entry:
        return 0.0, 0.0
    loss_per_share = (entry - stop) + costs.round_trip_cost_per_share(entry, stop)
    if loss_per_share <= 0:
        return 0.0, 0.0
    risk_budget = equity * policy.risk_per_trade
    risk_limited = risk_budget / loss_per_share
    cash_limited = (equity * policy.max_notional_fraction) / entry
    raw = min(risk_limited, cash_limited)
    if raw <= 0:
        return 0.0, 0.0
    if policy.allow_fractional_shares:
        step = 10.0 ** policy.fractional_decimals
        quantity = floor(raw * step) / step
        if quantity * entry < policy.min_notional:
            return 0.0, 0.0
    else:
        quantity = float(floor(raw))
    if quantity <= 0:
        return 0.0, 0.0
    return quantity, quantity * loss_per_share


def evaluate_guard(
    equity: float,
    daily_realized_pnl: float,
    weekly_realized_pnl: float,
    open_positions: int,
    candidate_bucket: str,
    open_buckets: Iterable[str],
    policy: RiskPolicy,
) -> GuardDecision:
    """Reject a paper candidate when a hard risk rule has already been hit."""
    reasons = []
    if equity <= 0:
        reasons.append("Account equity is non-positive")
    if daily_realized_pnl <= -(equity * policy.max_daily_loss):
        reasons.append("Daily loss guard has been reached; stop for the day")
    if weekly_realized_pnl <= -(equity * policy.max_weekly_loss):
        reasons.append("Weekly loss guard has been reached; stop and review")
    if open_positions >= policy.max_open_positions:
        reasons.append("Maximum open-position count reached")
    current_buckets: Set[str] = set(open_buckets)
    if candidate_bucket in current_buckets:
        reasons.append("Correlation bucket already has an open position")
    return GuardDecision(allowed=not reasons, reasons=tuple(reasons))
