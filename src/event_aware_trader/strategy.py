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
    volatility_multiplier_for,
    wilder_atr,
)
from .regime import MarketRegime, RegimeConfig, classify_regime
from .smc import smc_features
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
# Full fund names. A ticker is fine inside the code, but a report a human
# reads should say what the instrument actually is - "SLV" and "iShares Silver
# Trust" are not equally clear when you are deciding whether a trade made
# sense.
INSTRUMENT_NAMES: Dict[str, str] = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "DIA": "SPDR Dow Jones Industrial Average ETF Trust",
    "IWM": "iShares Russell 2000 ETF",
    "QQQ": "Invesco QQQ Trust",
    "XLK": "Technology Select Sector SPDR Fund",
    "XLE": "Energy Select Sector SPDR Fund",
    "USO": "United States Oil Fund",
    "XLF": "Financial Select Sector SPDR Fund",
    "XLV": "Health Care Select Sector SPDR Fund",
    "XLP": "Consumer Staples Select Sector SPDR Fund",
    "XLU": "Utilities Select Sector SPDR Fund",
    "XLI": "Industrial Select Sector SPDR Fund",
    "XLB": "Materials Select Sector SPDR Fund",
    "XLY": "Consumer Discretionary Select Sector SPDR Fund",
    "VNQ": "Vanguard Real Estate ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "GLD": "SPDR Gold Shares",
    "SLV": "iShares Silver Trust",
    "EFA": "iShares MSCI EAFE ETF",
    "EEM": "iShares MSCI Emerging Markets ETF",
}


INSTRUMENT_NAMES.update({
    # single names
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com Inc.", "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms Inc.", "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla Inc.", "BRK-B": "Berkshire Hathaway Inc.",
    "JPM": "JPMorgan Chase & Co.", "V": "Visa Inc.", "MA": "Mastercard Inc.",
    "JNJ": "Johnson & Johnson", "WMT": "Walmart Inc.",
    "PG": "Procter & Gamble Co.", "HD": "The Home Depot Inc.",
    "CVX": "Chevron Corporation", "ABBV": "AbbVie Inc.",
    "MRK": "Merck & Co. Inc.", "KO": "The Coca-Cola Company",
    "PEP": "PepsiCo Inc.", "BAC": "Bank of America Corp.",
    "PFE": "Pfizer Inc.", "TMO": "Thermo Fisher Scientific Inc.",
    "COST": "Costco Wholesale Corporation", "AVGO": "Broadcom Inc.",
    "CSCO": "Cisco Systems Inc.", "ACN": "Accenture plc",
    "MCD": "McDonald's Corporation", "ABT": "Abbott Laboratories",
    "CRM": "Salesforce Inc.", "NKE": "NIKE Inc.", "LIN": "Linde plc",
    "DHR": "Danaher Corporation", "TXN": "Texas Instruments Inc.",
    "NEE": "NextEra Energy Inc.", "VZ": "Verizon Communications Inc.",
    "ADBE": "Adobe Inc.", "PM": "Philip Morris International Inc.",
    "RTX": "RTX Corporation", "UNP": "Union Pacific Corporation",
    "QCOM": "QUALCOMM Inc.", "HON": "Honeywell International Inc.",
    "LOW": "Lowe's Companies Inc.", "UPS": "United Parcel Service Inc.",
    "INTC": "Intel Corporation", "IBM": "International Business Machines Corp.",
    "CAT": "Caterpillar Inc.", "GS": "The Goldman Sachs Group Inc.",
    "AMGN": "Amgen Inc.", "SBUX": "Starbucks Corporation",
    "BLK": "BlackRock Inc.", "DE": "Deere & Company",
    "LMT": "Lockheed Martin Corporation", "AXP": "American Express Company",
    "BKNG": "Booking Holdings Inc.", "MDLZ": "Mondelez International Inc.",
    "GILD": "Gilead Sciences Inc.", "ADI": "Analog Devices Inc.",
    "SYK": "Stryker Corporation", "TJX": "The TJX Companies Inc.",
    # additional funds
    "VTI": "Vanguard Total Stock Market ETF", "VOO": "Vanguard S&P 500 ETF",
    "IVV": "iShares Core S&P 500 ETF", "RSP": "Invesco S&P 500 Equal Weight ETF",
    "MDY": "SPDR S&P MidCap 400 ETF Trust",
    "XLRE": "Real Estate Select Sector SPDR Fund",
    "XLC": "Communication Services Select Sector SPDR Fund",
    "IYR": "iShares U.S. Real Estate ETF", "KRE": "SPDR S&P Regional Banking ETF",
    "SMH": "VanEck Semiconductor ETF", "SOXX": "iShares Semiconductor ETF",
    "XBI": "SPDR S&P Biotech ETF", "IBB": "iShares Biotechnology ETF",
    "ITB": "iShares U.S. Home Construction ETF", "XHB": "SPDR S&P Homebuilders ETF",
    "XRT": "SPDR S&P Retail ETF", "XOP": "SPDR S&P Oil & Gas Exploration ETF",
    "OIH": "VanEck Oil Services ETF", "UNG": "United States Natural Gas Fund",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
    "LQD": "iShares iBoxx Investment Grade Corporate Bond ETF",
    "HYG": "iShares iBoxx High Yield Corporate Bond ETF",
    "TIP": "iShares TIPS Bond ETF", "AGG": "iShares Core U.S. Aggregate Bond ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "GDX": "VanEck Gold Miners ETF", "GDXJ": "VanEck Junior Gold Miners ETF",
    "DBC": "Invesco DB Commodity Index Tracking Fund",
    "PDBC": "Invesco Optimum Yield Diversified Commodity Strategy ETF",
    "VEA": "Vanguard FTSE Developed Markets ETF",
    "VWO": "Vanguard FTSE Emerging Markets ETF",
    "EWJ": "iShares MSCI Japan ETF", "EWZ": "iShares MSCI Brazil ETF",
    "EWG": "iShares MSCI Germany ETF", "EWU": "iShares MSCI United Kingdom ETF",
    "EWY": "iShares MSCI South Korea ETF", "EWT": "iShares MSCI Taiwan ETF",
    "FXI": "iShares China Large-Cap ETF", "INDA": "iShares MSCI India ETF",
})


def instrument_name(symbol: str) -> str:
    """Full fund name, falling back to the ticker for anything unlisted."""
    return INSTRUMENT_NAMES.get(symbol.upper(), symbol.upper())


# Single names, bucketed by sector so the correlation cap still means
# something across a wider universe. Two megacap semis are close to one trade
# twice; the cap counts the bucket, not the ticker.
SINGLE_NAME_BUCKETS: Dict[str, str] = {
    # technology
    "AAPL": "technology", "MSFT": "technology", "NVDA": "semis", "AVGO": "semis",
    "QCOM": "semis", "TXN": "semis", "ADI": "semis", "INTC": "semis",
    "CSCO": "technology", "IBM": "technology", "ACN": "technology",
    "ADBE": "software", "CRM": "software",
    # internet and media
    "GOOGL": "internet", "META": "internet", "AMZN": "internet", "BKNG": "internet",
    # consumer
    "TSLA": "discretionary", "HD": "discretionary", "LOW": "discretionary",
    "MCD": "discretionary", "NKE": "discretionary", "SBUX": "discretionary",
    "TJX": "discretionary", "COST": "staples", "WMT": "staples", "PG": "staples",
    "KO": "staples", "PEP": "staples", "PM": "staples", "MDLZ": "staples",
    # financials
    "BRK-B": "financials", "JPM": "financials", "BAC": "financials",
    "GS": "financials", "BLK": "financials", "AXP": "financials",
    "V": "payments", "MA": "payments",
    # healthcare
    "JNJ": "healthcare", "ABBV": "pharma", "MRK": "pharma", "PFE": "pharma",
    "AMGN": "pharma", "GILD": "pharma", "TMO": "medtech", "ABT": "medtech",
    "DHR": "medtech", "SYK": "medtech",
    # industrials, energy, materials
    "CVX": "energy", "RTX": "industrials", "HON": "industrials", "UPS": "industrials",
    "CAT": "industrials", "DE": "industrials", "LMT": "industrials", "UNP": "industrials",
    "LIN": "materials", "NEE": "utilities", "VZ": "telecom",
}
CORRELATION_BUCKETS.update(SINGLE_NAME_BUCKETS)

# Extra sector and thematic ETFs, kept in their sector's bucket.
CORRELATION_BUCKETS.update({
    "VTI": "broad_equity", "VOO": "broad_equity", "IVV": "broad_equity",
    "RSP": "broad_equity", "MDY": "mid_cap", "XLRE": "real_estate",
    "XLC": "communications", "IYR": "real_estate", "KRE": "financials",
    "SMH": "semis", "SOXX": "semis", "XBI": "biotech", "IBB": "biotech",
    "ITB": "homebuilders", "XHB": "homebuilders", "XRT": "discretionary",
    "XOP": "energy", "OIH": "energy", "UNG": "energy",
    "IEF": "duration", "SHY": "duration", "LQD": "credit", "HYG": "credit",
    "TIP": "duration", "AGG": "credit", "BND": "credit",
    "GDX": "precious_metals", "GDXJ": "precious_metals",
    "DBC": "commodities", "PDBC": "commodities",
    "VEA": "developed_intl", "VWO": "emerging", "EWJ": "developed_intl",
    "EWZ": "emerging", "EWG": "developed_intl", "EWU": "developed_intl",
    "EWY": "emerging", "EWT": "emerging", "FXI": "emerging", "INDA": "emerging",
})

# Crypto, all in ONE bucket on purpose. These pairs move together closely
# enough that holding three of them is one position taken three times, and the
# correlation cap counts buckets rather than tickers precisely to stop that.
#
# Slashed symbols because that is the form Alpaca uses everywhere - orders,
# fills and activities - so a symbol from the broker classifies without a
# lookup table that would drift as pairs are listed.
CRYPTO_UNIVERSE = (
    "BTC/USD", "ETH/USD", "SOL/USD", "LTC/USD", "LINK/USD",
    "AAVE/USD", "AVAX/USD", "DOT/USD", "UNI/USD", "BCH/USD",
)
CORRELATION_BUCKETS.update({symbol: "crypto" for symbol in CRYPTO_UNIVERSE})
INSTRUMENT_NAMES.update({
    "BTC/USD": "Bitcoin", "ETH/USD": "Ethereum", "SOL/USD": "Solana",
    "LTC/USD": "Litecoin", "LINK/USD": "Chainlink", "AAVE/USD": "Aave",
    "AVAX/USD": "Avalanche", "DOT/USD": "Polkadot", "UNI/USD": "Uniswap",
    "BCH/USD": "Bitcoin Cash",
})

DEFAULT_UNIVERSE = tuple(CORRELATION_BUCKETS.keys())


def is_crypto(symbol: str) -> bool:
    """Alpaca names crypto pairs with a slash; equities never contain one."""
    return "/" in str(symbol)


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
    # Separate floors for crypto. The equity numbers are not a near miss there:
    # Alpaca prints about $103,000 a day on BTC against SPY's $35bn, and
    # several pairs trade under $20. Applying the equity floors rejected all
    # 2,363 crypto bars tested without ever scoring one.
    #
    # These are deliberately paired with RiskPolicy.max_volume_participation.
    # Lowering a liquidity floor without capping participation would remove the
    # protection the floor existed to provide.
    crypto_min_price: float = 0.50
    crypto_min_average_dollar_volume: float = 1_000.0
    min_relative_volume: float = 1.20
    min_atr_fraction: float = 0.003
    max_atr_fraction: float = 0.10
    min_adx: float = 18.0
    min_trend_r_squared: float = 0.40
    max_atr_extension: float = 4.0
    stop_atr_multiple: float = 2.0
    # Chosen for MONEY PER TRADE, not for win rate. Walk-forward across six
    # years, filtered to the model's top third of candidates:
    #
    #     exit rule              win %   mean R   years positive
    #     1.0R / 2.0 / 10 bar    52.9%  +0.0249
    #     2.0R / 3.0 / 15 bar    47.5%  +0.0983        4 of 6
    #     5.0R / 2.0 / 20 bar    33.4%  +0.1393        5 of 6   <- this
    #
    # The 5R target earns 42% more per trade than the 2R one AND was positive
    # in more years, so it is better on both counts. The price is that it wins
    # only a third of the time: two trades in three are losers, and the profit
    # comes from the third one running much further than the losers fall.
    #
    # That will look and feel like losing. It is the same arithmetic as riding
    # a bus to the end of the line - you miss your stop more often, and you
    # travel much further when you do not.
    #
    # NOTE: this is INERT under exit_mode="trailing", the shipped default,
    # which drops the fixed target so an advance is not truncated. It governs
    # "fixed_time" and the cost/reward gates only. Sweeping what trailing
    # actually uses - trail_atr_multiple and trail_activate_r - confirmed the
    # existing 2.5 ATR / 0.5R was already the optimum, and identically so
    # across all eight tested regimes. There was no improvement to make there.
    reward_to_risk: float = 5.0
    minimum_score: float = 70.0
    # How long a simulated position may stay open before it is closed at the
    # market.  This was a literal 5 buried in the backtest loop while it
    # decided roughly seven out of ten exits: with a 2-ATR stop and a 2R
    # target, a 5-bar window is usually too short for the target to be
    # reached, so most trades ended at whatever the clock happened to show.
    # Naming it makes that trade-off visible and testable.
    max_holding_bars: int = 20
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
    # Skip the first N bars of an intraday session.  The motivating measurement
    # is solid: across 20 ETFs the 09:30 bar carries 3.02x the range of the
    # midday bar and 09:45 carries 2.05x, settling by about 11:45.  Entering
    # into 3x volatility with a stop sized from an ATR that averages in quiet
    # midday bars is structurally wrong, and in one week all three losing
    # trades opened at 09:30 or 09:45.
    #
    # It is nevertheless DISABLED by default, because the trading result does
    # not support it.  Over a full month a 30-minute blackout returned -0.43%
    # against +1.89% for no blackout at all; the week where it looked like a
    # +0.49pp improvement was a three-trade sample.  Nine to twenty-two trades
    # cannot resolve this either way, and shipping a default that the evidence
    # contradicts would be worse than leaving a good hypothesis untested.
    intraday_open_blackout_bars: int = 0

    # Widen the stop by how volatile the coming time-of-day slot usually is.
    # A US session is not homogeneous: on 15-minute bars the 09:30 slot runs
    # about 1.8x the session average range and 13:45 about 0.6x, but ATR
    # averages them together. That is why three consecutive weeks of intraday
    # losers all opened at 09:30 or 09:45 and died inside half an hour - the
    # stop was sized for a calm bar and placed in a violent one.
    #
    # Scaling the stop instead of skipping the open keeps the trade available
    # and makes the position smaller for the same dollar risk, which is the
    # correct adjustment rather than a refusal to participate. No effect on
    # daily bars, where every bar is the same slot.
    use_intraday_volatility_scaling: bool = True

    # Smart-Money-Concepts confluence, from the Boot Camp material: require
    # this many of {price inside a bullish fair value gap, price inside a
    # bullish order block, a recent bullish liquidity sweep} before a long.
    # Measured out of sample on 3,624 candidates over ten years, each of the
    # three individually lifts the winner rate by about four percentage
    # points, from roughly 18% to 22%, with AUCs near 0.53 - real but weak.
    # 0 disables the requirement; see the regime table in the docs before
    # raising it, because filtering also removes winners.
    required_smc_confluence: int = 0
    smc_swing_lookback: int = 2
    smc_range_window: int = 40

    # "quick_target" takes a small profit fast instead of riding a move. It is
    # the only setting that produces a high per-trade win rate, and the win
    # rate is a property of the EXIT, not of the entry - measured on 24,581
    # trades across 120 instruments:
    #
    #     target    win rate    mean R
    #     0.10R       89.9%    -0.0132     <- costs eat it
    #     0.15R       89.2%    +0.0090
    #     0.25R       84.9%    +0.0371     <- the default here
    #     0.50R       71.8%    +0.0565
    #     3.00R       43.9%    +0.0773     <- most profit, fewest wins
    #
    # 0.25R held 84.3% on average and never fell below 75.6% in any of eight
    # years, with positive expectancy in seven of them. Below 0.15R the win
    # rate keeps climbing and the expectancy goes negative, which is the whole
    # trap: a win rate can always be raised by taking profits sooner, right up
    # to the point where the wins no longer cover the losses.
    #
    # Read the table honestly. A higher win rate here means LESS money per
    # trade, not more. 0.25R wins twice as often as a 3R target and earns half
    # as much per trade.
    quick_target_r: float = 0.25

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
        if self.exit_mode not in ("fixed_time", "trailing", "quick_target"):
            raise ValueError(
                "exit_mode must be 'fixed_time', 'trailing', or 'quick_target'")
        if self.quick_target_r <= 0:
            raise ValueError("quick_target_r must be positive")
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

    volatility_scale = (
        volatility_multiplier_for(bars) if config.use_intraday_volatility_scaling else 1.0
    )
    features["intraday_volatility_scale"] = volatility_scale

    # ---- Blockers -----------------------------------------------------------
    floor_price = config.crypto_min_price if is_crypto(symbol) else config.min_price
    floor_volume = (config.crypto_min_average_dollar_volume if is_crypto(symbol)
                    else config.min_average_dollar_volume)
    if close < floor_price:
        blockers.append("Price below ${0:.2f} minimum".format(floor_price))
    if average_dollar_volume < floor_volume:
        blockers.append("Average dollar volume below ${0:,.0f} liquidity floor".format(floor_volume))
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
    if config.required_smc_confluence > 0:
        smc = smc_features(bars, config.smc_swing_lookback, config.smc_range_window)
        confluence = int(
            smc["smc_in_bullish_fvg"]
            + smc["smc_in_bullish_order_block"]
            + smc["smc_recent_bullish_sweep"]
        )
        features.update(smc)
        if confluence < config.required_smc_confluence:
            blockers.append(
                "Smart-money confluence {0} of 3 is below the required {1}".format(
                    confluence, config.required_smc_confluence
                )
            )

    if event_impact < -0.10:
        blockers.append("Reviewed event scenario conflicts with a new long candidate")
    if config.use_regime_filter:
        blockers.extend(regime.blockers)

    # ---- Position plan ------------------------------------------------------
    entry = close
    stop = entry - config.stop_atr_multiple * volatility_scale * atr
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
