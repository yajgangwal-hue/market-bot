"""Pre-trade risk controls and cost model for paper-trading research."""

from dataclasses import dataclass
from math import floor
from typing import Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class RiskPolicy:
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_weekly_loss: float = 0.06
    max_open_positions: int = 3
    max_notional_fraction: float = 0.95
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
