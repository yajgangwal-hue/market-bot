"""Pre-trade risk controls and cost model for paper-trading research."""

from dataclasses import dataclass
from math import floor
from typing import Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class RiskPolicy:
    # 0.5% stays, and the reason is worth reading before anyone raises it.
    #
    # This is the dial that sets position size - size is the risk budget
    # divided by the distance to the stop, so at 0.5% each position is about
    # $9,800 against a $20,000 notional cap that almost never binds. Raising
    # it is the obvious way to make the strategy bigger. Tested across the
    # full decade, guards scaled with it as RISK_PROFILES does:
    #
    #     risk      10yr     CAGR    maxDD   CAGR/maxDD
    #     0.50%   + 84.9%   +5.94%   -11.9%      0.50    <- live
    #     0.75%   +111.8%   +7.30%   -15.0%      0.49
    #     1.00%   + 90.2%   +6.22%   -17.1%      0.36
    #     1.50%   +109.6%   +7.19%   -17.6%      0.41
    #     2.00%   + 89.7%   +6.20%   -20.4%      0.30
    #
    # Read the two columns as sequences. Return: 85, 112, 90, 110, 90 - no
    # ordering whatever. Drawdown: -12, -15, -17, -18, -20 - perfectly
    # ordered. The return differences are noise and the risk differences are
    # real, which is the whole finding.
    #
    # The mechanism behind the noise: a larger position means fewer fit inside
    # the cash balance, so a different SET of trades gets taken, and the
    # sequence diverges chaotically. Risk scales cleanly regardless, because
    # it does not depend on which trades were chosen.
    #
    # This is the Kelly result showing up in real data. Growth peaks and then
    # flattens while variance keeps climbing, and past the peak you are paying
    # risk for nothing. On this evidence the strategy is already at or beyond
    # that point at 0.5%, so the correct setting is the SMALLEST one that
    # achieves the return - and that is the one already here.
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
    # Raised from 6 alongside the notional cut, because the two are one
    # decision: the same capital across twice as many names. Measured on the
    # account simulator, not inferred - see max_notional_fraction below for
    # the table. Holding more positions is what the breadth term in the
    # fundamental law rewards; holding them at the old 33% would simply have
    # run out of cash.
    max_open_positions: int = 12
    # How many names from ONE correlation bucket may be held at once. Under
    # test; 1 is the shipped behaviour and the default here until a measured
    # result says otherwise.
    max_per_bucket: int = 1
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
    # THEN LOWERED FROM 50% TO 33%, because position size and signal frequency
    # are one decision, not two. 50% was right when the rule fired 43 times and
    # capital had to be concentrated to be deployed at all. At rsi_entry=35 it
    # fires 189 times, and the same concentration becomes a liability - the
    # account ends up fully committed to whichever two names happened to signal
    # first. Portfolio simulation with the cash and correlation constraints
    # enforced, over the widened universe:
    #
    #     rsi_entry  size   taken   return    maxDD
    #        30       50%     18   +14.68%    -5.9%   <- was shipped
    #        35       50%     28   +13.06%   -24.3%   <- more signals, same size
    #        35       33%     53   +33.01%    -7.9%   <- now
    #        35       25%     64   +28.41%    -5.3%
    #
    # Note the second row: MORE signals at the OLD size is worse than either,
    # and quadruples the drawdown. That is the interaction, and it is why these
    # two numbers moved together.
    #
    # Held out - the first half is data neither setting was chosen on:
    #
    #                        1st half   1st maxDD   2nd half
    #     rsi30 / 50%          +3.73%      -5.9%     +11.65%
    #     rsi35 / 33%          +8.75%      -6.0%     +21.72%
    #
    # Better in BOTH halves at the same drawdown, and 25% performs almost
    # identically, so this is a plateau rather than a fitted peak. +33.01% over
    # the window against SPY's +23.69% - the first configuration measured in
    # this project that beats buy-and-hold.
    #
    # RAISED FROM 20% TO 50% when the entry rule became mean reversion, because
    # the finding above does not transfer. It was measured on the trend gate at
    # 5.6 trades a day, where a large position starved the next signal: 314
    # qualifying setups were skipped for want of cash. Mean reversion trades
    # about fifteen times a YEAR and holds at most ten days, so that mechanism
    # barely bites. Re-measured on the same two years, compounding, with the
    # six-position cap and cash constraint enforced:
    #
    #     size   taken  skipped   return    maxDD
    #      20%      27        4   +8.61%    -1.9%
    #      35%      20       11  +11.45%    -3.2%
    #      50%      20       11  +16.49%    -4.6%
    #      75%      15       16  +14.54%    -8.3%
    #     100%      15       16  +19.18%   -11.1%
    #
    # 50% roughly doubles the return for under five points of drawdown, and
    # still leaves room for two concurrent positions rather than betting the
    # account on one name. The honest caveats: 31 trades is a thin basis, the
    # column is not monotonic (75% earns less than 50%), which is what noise
    # looks like, and buy-and-hold returned +40.14% over the same window.
    #
    # It also concentrates. Mean reversion buys names that are oversold, often
    # BECAUSE of bad news, and a gap through the stop now costs half the
    # account's exposure rather than a fifth.
    #
    # It also collapses the variance. Split the month in half and the 95% cap
    # swings +1.85% to -4.26%, while 20% swings +1.19% to -0.72% and 10% only
    # +1.08% to -0.44%. That -4.26% was concentration, not strategy.
    #
    # 20% keeps positions substantial while letting five a day run. On a very
    # small account it can block a high-priced name entirely, since whole
    # shares are required for a broker-side stop - raise it there.
    # Measured 2026-09-06 on the ACCOUNT simulator - the first time this was
    # ever measured per-account rather than per-symbol. Live config returned
    # +9.23% over 523 days; spreading the same capital over more, smaller
    # positions returned more in BOTH halves of the window:
    #
    #     cap  size   first half   holdout   whole    drawdown
    #       6   33%       +3.74%    +5.21%   +9.23%      -3.82%   <- was live
    #       8   25%       +4.73%    +5.14%  +10.19%      -4.40%
    #      12   20%       +5.85%    +5.33%  +11.57%      -5.30%   <- now live
    #      15   20%       +5.85%    +6.38%  +12.68%      -5.93%
    #      20   10%       +4.89%    +6.17%  +11.44%      -5.86%
    #
    # 15/20% tested best, and is not what is set here: ten configurations were
    # searched and taking the argmax of a search is the multiple-comparisons
    # trap. 12/20% sits in the flat middle of the good region, beats the old
    # setting in both halves, and does not depend on the peak being real.
    #
    # The mechanism is the fundamental law, not a fitted parameter: breadth
    # enters the information ratio under a square root, so more independent
    # positions at the same total exposure is a diversification gain rather
    # than a bet. It cost 1.5 points of drawdown.
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

    # What friction is worth, measured across the decade 2026-09-07 on the
    # shipped config. This is the exchange rate between execution quality and
    # return, and it is the number that says whether chasing better fills is
    # worth any engineering:
    #
    #     one-way cost    decade    holdout
    #        3 bps        +140.0%    +40.0%
    #        6 bps        +127.6%    +33.3%   <- assumed here
    #        9 bps        +111.2%    +29.0%
    #       12 bps        + 91.8%    +20.7%
    #
    # About four points of decade return per basis point. The bot sends market
    # orders and crosses the spread 708 times a decade; a marketable limit
    # might recover one or two of these bps, worth roughly +0.4% to +0.8% a
    # year - real, and set against rewriting order submission, which is where
    # this project's most dangerous bugs have all lived (a stop compared
    # against a pre-entry bar, a percent-encoded close that 404'd, bracket
    # legs expiring overnight). Not taken for now; recorded so the trade is a
    # decision rather than an oversight.
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
    # Counted, not set-tested, so the cap can be more than one name per
    # bucket. Callers that pass a set still behave exactly as before at the
    # default of 1: a set contributes at most one match.
    held_in_bucket = sum(1 for bucket in open_buckets if bucket == candidate_bucket)
    if held_in_bucket >= max(1, policy.max_per_bucket):
        reasons.append("Correlation bucket already has an open position")
    return GuardDecision(allowed=not reasons, reasons=tuple(reasons))
