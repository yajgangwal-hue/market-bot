"""A small, ring-fenced crypto sleeve: hold BTC only while BTC is in an uptrend.

WHY THIS EXISTS, and why it is nothing like the equity book.

Every crypto TRADING strategy tested in this project lost money in a real
account - mean reversion, trend following, breakout, cross-sectional momentum,
on both Alpaca's history and a decade of verified Yahoo data. The reason was
structural rather than a bad parameter: the equity book sizes positions by
risk budget over stop distance, and an asset with four to thirteen percent
daily range gets a position so small it cannot matter. SHIB earned 1.5% of the
account; if it tripled the account gained 3%.

So this is not a trading strategy. It is an ALLOCATION, held or not held:

    BTC above its own 100-day average   ->  hold the sleeve in BTC
    otherwise                           ->  hold nothing

That overlay was verified across two complete crypto cycles on data validated
against Alpaca's own prices - it cut the 2018 bear from -74% to -40% and the
2022 bear from -79% to -24%, and beat buy-and-hold on return AND drawdown.

WHY 5%, AND WHY NOT MORE. Measured against the equity book over 2015-2026,
using BTC alone rather than a basket chosen in hindsight:

    allocation       CAGR    maxDD   ret/DD
    equities only   7.60%   -14.1%     0.54
    5% BTC          9.13%   -13.5%     0.68
    10% BTC        10.63%   -13.7%     0.78
    20% BTC        13.54%   -15.5%     0.87

Correlation of daily returns is +0.035 - near zero - which is what lets a
42%-volatility asset be added while drawdown goes DOWN rather than up. That
diversification is real and is the honest case for holding any at all.

The return improvement is NOT an edge. At near-zero correlation a 5% sleeve
contributes about 0.05 x BTC's return, and BTC returned 30.7% a year over this
window; 0.05 x 30.7% is the +1.5 CAGR points the table shows. If crypto
returns nothing, this sleeve adds nothing. The larger weights score better
only because they multiply that same historical return, so choosing 20% would
be optimising against a number nobody can promise. 5% bounds the worst case at
about -2.4% of the account.

NO STOP, DELIBERATELY. The regime filter is the risk control: the sleeve exits
when BTC loses its 100-day average, which is what was measured. A stop would
be a different strategy from the one tested, and on crypto it would be hit by
ordinary noise. The exposure is bounded by the 5% weight instead.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .indicators import sma


# Round-trip cost of one switch, per pair, as a fraction. MEASURED from
# Alpaca's own quotes, not assumed: 2026-09-12 for the ten universe pairs,
# 2026-09-13 for the meme pairs. The equity cost model assumes 0.0012 for
# everything; crypto spans a factor of thirty. Any rule that touches a pair
# other than BTC or ETH must be measured at that pair's own cost, because at
# 30-70bps a switch the 100-day trend allocation loses on every meme coin
# tested (DOGE 2.7% a year at a -95% drawdown against 5.4% for holding it;
# SHIB +46% then -30% by half; PEPE and TRUMP negative both ways).
MEASURED_ROUND_TRIP = {
    "ETH/USD": 0.000237, "BTC/USD": 0.000342, "SOL/USD": 0.000589,
    "UNI/USD": 0.001685, "AAVE/USD": 0.002173, "LINK/USD": 0.002243,
    "DOT/USD": 0.002437, "AVAX/USD": 0.005929, "LTC/USD": 0.006096,
    "BCH/USD": 0.006167,
    # meme pairs - tradeable instruments, nothing allocated to them
    "PEPE/USD": 0.00293, "DOGE/USD": 0.00320, "TRUMP/USD": 0.00317,
    "WIF/USD": 0.00327, "SHIB/USD": 0.00382, "BONK/USD": 0.00727,
}

@dataclass
class SleeveConfig:
    symbol: str = "BTC/USD"
    # Fraction of TOTAL account equity, not of some separate pot. The sleeve is
    # sized against the whole account so it stays 5% as the account grows.
    fraction: float = 0.05
    trend_days: int = 100
    # Do not trade to correct a drift smaller than this. Without it the sleeve
    # would place a tiny order every cycle as equity moves by a few dollars,
    # paying spread each time for no change in exposure.
    rebalance_tolerance: float = 0.20
    minimum_order: float = 25.0

    def __post_init__(self) -> None:
        if not 0 < self.fraction <= 0.5:
            raise ValueError("fraction must be in (0, 0.5]; this is a sleeve, "
                             "not the account")
        if self.trend_days < 20:
            raise ValueError("trend_days must be at least 20")
        if not 0 < self.rebalance_tolerance < 1:
            raise ValueError("rebalance_tolerance must be a fraction in (0, 1)")


def risk_on(bars, config: SleeveConfig) -> Optional[bool]:
    """Is BTC above its own N-day average? None when there is not enough data.

    None is distinct from False on purpose. False means "measured, and the
    trend is down, so hold nothing". None means "cannot tell", and the caller
    must then do NOTHING rather than treat missing data as a sell signal - a
    failed data fetch should never liquidate a position.
    """
    if not bars or len(bars) < config.trend_days:
        return None
    closes = [b.close for b in bars]
    average = sma(closes, config.trend_days)
    if average is None or average <= 0 or closes[-1] <= 0:
        return None
    return closes[-1] > average


def plan(equity: float, held_value: float, on: Optional[bool],
         config: SleeveConfig,
         available_cash: Optional[float] = None) -> Dict[str, object]:
    """What the sleeve should do now: a target, a delta, and a reason.

    Pure, so the decision can be tested without a broker or a network.

    `available_cash` caps a BUY at what the account can actually pay. Without
    it the sleeve asks for its full 5% every cycle regardless of the balance -
    and on an account that is 99.3% invested in equities that is a $5,000
    order against $702 of cash, rejected by the broker every fifteen minutes
    for ever.

    Capping instead of refusing is what makes the sleeve work while the equity
    book is full: it takes the position it can afford now and tops up as
    equity trades close and free the cash, converging on the target instead of
    waiting for a day when the whole amount happens to be idle. The 20%
    tolerance then stops it churning once it arrives.

    A SELL is never capped - closing a position releases cash rather than
    needing it.
    """
    if on is None:
        return {"action": "hold", "target": held_value, "delta": 0.0,
                "reason": "not enough data to judge the trend; doing nothing"}
    target = equity * config.fraction if on else 0.0
    delta = target - held_value
    # Tolerance is measured against the TARGET when there is one, and against
    # the holding when the target is zero - otherwise an exit could never
    # clear a tolerance computed from a target of nothing.
    reference = target if target > 0 else held_value
    if reference > 0 and abs(delta) < reference * config.rebalance_tolerance:
        return {"action": "hold", "target": target, "delta": 0.0,
                "reason": "within {0:.0%} of target".format(
                    config.rebalance_tolerance)}
    if abs(delta) < config.minimum_order:
        return {"action": "hold", "target": target, "delta": 0.0,
                "reason": "order below ${0:.0f}".format(config.minimum_order)}
    action = "buy" if delta > 0 else "sell"
    reason = ("BTC above its {0}-day average".format(config.trend_days)
              if on else
              "BTC below its {0}-day average".format(config.trend_days))

    if action == "buy" and available_cash is not None:
        affordable = min(delta, max(0.0, float(available_cash)))
        if affordable < config.minimum_order:
            return {
                "action": "hold", "target": target, "delta": 0.0,
                "reason": ("wants ${0:,.0f} but only ${1:,.0f} is available, "
                           "below the ${2:.0f} minimum - waiting for equity "
                           "trades to free cash".format(
                               delta, max(0.0, float(available_cash)),
                               config.minimum_order)),
            }
        if affordable < delta:
            reason += ("; capped at ${0:,.0f} of available cash, topping up "
                       "as equity positions close".format(affordable))
            delta = affordable

    return {"action": action, "target": target, "delta": delta,
            "reason": reason}
