"""A mean-reversion entry rule, as an alternative to the trend gate.

The trend gate in `strategy.py` asks "is a move underway that I can join".
Tested across eight market regimes it loses money in seven of them, and no
amount of resizing, filtering, or re-exiting changed that - position size and
exit rules multiply an edge, they do not create one.

This module tests the opposite premise: on liquid index ETFs, short-horizon
weakness inside an intact long-term uptrend tends to be bought rather than
continued. Buy oversold above the 200-day average; exit when the oversold
condition has resolved.

Measured over 2017-2023, held out from every choice made here:

    trend gate         -3.46%
    mean reversion     +0.70%   (no crash filter)
    mean reversion     +2.28%   (ATR < 3.5% of price)

That is a genuine four-to-six point improvement over the existing rule, and
it is still only about a third of a percent a year against a buy-and-hold
that returned far more. It is offered as the better of two weak hypotheses,
not as a profitable system.

The known failure mode is buying into a crash: with no volatility ceiling,
2020 lost 8.36% with zero winners from five trades. `max_atr_fraction` is
the guard, and note it is not monotonic - 3.5% helped and 2.5% hurt - which
is itself a reason to treat the exact threshold as unreliable.


CAN A MODEL LEARN WHICH OF THESE SETUPS WIN? Tested 2026-09-06 on 1,872 real
entries this rule generated across 2016-2026, base win rate 53.4%, eleven
features known only at the signal bar, split chronologically:

    model                train AUC   test AUC   gap
    random forest           0.8959     0.5858  0.31
    gradient boosting       0.9289     0.5404  0.39
    neural net              0.9981     0.5386  0.46
    extra trees             0.7823     0.5241  0.26
    logistic                0.5984     0.4909  0.11

No usable model. The best grazed the 0.58 threshold while scoring 0.90 on the
data it was fitted to - a 0.31 gap, which is memorisation rather than skill,
and at 1,872 samples a test AUC of 0.586 is well inside what a lucky
memoriser produces.

This is NOT the same test as the one in ai_model.py, which ran on 3,624
candidates from the trend rule. These features carry marginally more signal
than those did (0.586 against 0.503) and still not enough to use. The
conclusion is the module's own: the limitation is the features, not the
learner, and a bigger model cannot extract information the inputs do not
contain.

The distinction that matters, because it is easy to conflate: fitting
PARAMETERS to history works and is how stop_atr_multiple, rsi_exit and
max_atr_fraction below were all chosen, on ten years including two crashes.
Training a MODEL to rank individual setups does not. The first has four
degrees of freedom checked against a decade; the second has hundreds and a
53% base rate to beat.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence

from .indicators import rsi, sma, wilder_atr
from .types import Bar


def _entry_date(value: str) -> Optional[date]:
    """The calendar date an entry timestamp falls on.

    Comparing the raw ISO strings does not work and is not a near miss. Bar
    timestamps are naive market-local ("2026-09-04T16:00:00"); entry
    timestamps are tz-aware UTC ("2026-09-04T19:00:24+00:00"). Lexically the
    bar sorts BEFORE the entry, while 16:00 ET is really 20:00 UTC - after it.
    A bar that closed after the entry was therefore judged to have closed
    before it, which suppresses a stop exit that should fire.

    Dates sidestep the timezone question, and dates are the right granularity
    anyway: this rule consumes daily bars.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


@dataclass(frozen=True)
class MeanReversionConfig:
    rsi_period: int = 14
    # RAISED FROM 30 TO 35 once the universe widened to 230 names. On the old
    # 120 this failed its holdout outright - +1.925% in the first half and
    # -0.027% in the second - and I rejected it for exactly that reason. With
    # 4.4x the sample it is the most significant setting tested anywhere in
    # this project:
    #
    #     rsi_entry   trades   mean/trade   p        1st half   2nd half
    #        30           43     +2.115%   0.0132    +1.006%    +2.914%
    #        35          189     +1.291%   0.0014    +1.382%    +1.200%
    #
    # Lower per trade, far more of them, and stable across halves rather than
    # carried by one. Total edge is 2.7x. What changed is not the market but
    # the evidence: 65 trades could not distinguish this from noise and 189
    # can, which is the same reason the universe was widened.
    # 35 re-checked on ten years, 2026-09-07. It had been swept on TWO years,
    # before the account simulator existed, and that sweep had 45 beating both
    # halves while 40 failed - dismissed as noise at the time. The decade says
    # the dismissal was right:
    #
    #     rsi_entry    whole    holdout    maxDD   trades
    #        30       + 26.2%    + 9.4%    - 9.4%     295
    #        35       +127.6%    +33.3%    -15.0%     708   <- live
    #        40       + 84.0%    +20.7%    -19.1%    1083
    #        45       + 53.5%    +10.2%    -23.7%    1414
    #
    # A clean peak with drawdown growing monotonically as it loosens. Tighter
    # starves the rule of trades (295 in a decade); looser admits setups that
    # are not oversold enough to revert, and pays for them in drawdown.
    rsi_entry: float = 35.0          # buy at or below this
    # 60, not 55. Re-validated 2026-09-06 on the ACCOUNT simulator - every
    # parameter in this class was originally chosen on per-symbol backtests
    # where each name had its own private cash balance, and the one figure
    # since re-measured that way moved by a factor of three.
    #
    # Holdout return by exit level, everything else held:
    #     50 -> +3.74%    55 -> +5.16%    60 -> +7.48%    65 -> +6.20%
    #
    # A coherent direction rather than an isolated peak: this rule buys a dip
    # and sells the recovery, and exiting at 55 was leaving part of the
    # recovery on the table.
    rsi_exit: float = 60.0           # sell once it has recovered to here
    # BACK ON (200), by the account owner's decision on 2026-09-10.
    #
    # It was switched OFF on 2026-09-09 for position count and return, with
    # the full trade shown and understood. One trading day later the first
    # broadly red session arrived - SPY -0.60%, small caps -1.07% - and the
    # account held six correlated longs with $703 of cash instead of about
    # 3.7 positions and a 19% buffer. Nothing malfunctioned; the bot beat the
    # market that day. But that is what the configuration feels like from the
    # inside, and on seeing it the owner chose the drawdown profile over the
    # return.
    #
    # The tables below are unchanged and still describe the trade exactly. 0
    # restores the higher-return, higher-drawdown behaviour.
    #
    # This is the single highest-stakes setting in the project, so the whole
    # trade is written down rather than summarised.
    #
    # WHY IT WAS REMOVED. It was the only thing limiting how many positions
    # the bot holds. Counted live on 2026-09-09: of 230 symbols exactly ONE
    # qualified, while 75 were oversold but below their 200-day average -
    # TJX at RSI 19.3, SYK at 24.7, RCL at 25.2. The 12-position cap was never
    # binding. Removing the filter is the only change that raises the count.
    #
    # WHAT IT BUYS, on the decade, and it clears the both-halves bar that
    # every other change this project rejected failed:
    #
    #     filter      decade    maxDD   1st half  2nd half  trades  avgPos
    #     200-day    +123.1%   -14.1%     +43.3%    +61.7%     710     3.7
    #     off        +157.4%   -22.4%     +59.9%    +69.9%    1117     6.0
    #
    # WHAT IT COSTS, over thirty years including two real bear markets. This
    # is the half that must not be forgotten:
    #
    #     filter       CAGR    maxDD   2000-02     2008     2022  avgPos
    #     200-day     4.61%   -16.3%     -2.4%    -8.7%    -8.9%     2.8
    #     off         6.61%   -37.9%    -16.4%   -25.8%    -5.3%     5.1
    #
    # Two percentage points a year, paid for with a maximum drawdown that
    # more than doubles and a 2008 that goes from -8.7% to -25.8%. The
    # mechanism is exactly the one the filter existed for: in a sustained
    # decline almost nothing is above its 200-day average, so with the filter
    # on the rule stops buying and sits in cash, and with it off the rule
    # keeps buying dips all the way down.
    #
    # RISK-ADJUSTED, THE FILTER STILL WINS: 4.61/16.3 = 0.28 against
    # 6.61/37.9 = 0.17. It was removed because the owner wants position count
    # and return and accepts the drawdown, not because the measurement
    # favours it. Anyone reading this later should know that.
    #
    # The middle ground is the worst of both and was tested: "above the
    # average OR within 5%" earns LESS than off (+78.8% decade) while drawing
    # down MORE than on (-23.7% over thirty years). There is nowhere
    # comfortable to stand between these two.
    #
    # WHAT THE RETURN TABLES ABOVE COULD NOT SEE, measured afterwards on
    # 2026-09-09 and confirmed by the owner's decision to keep the filter off
    # anyway. Per SESSION HELD, against the average session of the same
    # universe over the same decade:
    #
    #     config        overnight  intraday   overnight adv  intraday adv
    #     filter ON       0.0670%   0.0139%       +0.0121%      -0.0168%
    #     filter OFF      0.0440%   0.0157%       -0.0108%      -0.0150%
    #     the universe    0.0548%   0.0307%
    #
    # With the filter ON the rule had real selection skill and ALL of it was
    # in the overnight leg: the stocks it chose gapped up more than the
    # average stock. With it OFF that edge inverts - the stocks it picks now
    # gap up LESS than average. So the higher headline return is not better
    # picking, it is more capital exposed to the market's drift.
    #
    # Also measured: 73.6% of this strategy's entire return comes from the
    # overnight gap rather than the trading session, so holding overnight is
    # the business rather than a risk being tolerated. See
    # docs/2026-09-09-overnight-decomposition.md.
    #
    # 0 IS AN EXPLICIT OFF-SWITCH and 1 is not. sma(closes, 1) equals the
    # close, and the rule demands close > average, so a "1-day filter"
    # silently rejects every candidate forever. That cost a full test run.
    trend_ma_days: int = 200
    atr_days: int = 14
    # 2.5, not 3.0. Tighter is better across the whole tested range, which is
    # a direction and not a lucky point:
    #
    #     multiple   first half   holdout    whole   max DD
    #        2.0        +8.62%    +7.69%  +16.97%   -7.21%
    #        2.5        +8.07%    +6.68%  +15.29%   -6.19%
    #        3.0        +6.39%    +5.16%  +11.89%   -5.30%   <- was live
    #        4.0        +6.05%    +3.36%   +9.61%   -4.19%
    #
    # The mechanism fits what this rule is structurally exposed to. Buying
    # weakness has a fat LEFT tail - the trade where the fall was information
    # rather than noise - and a tighter stop truncates exactly that.
    #
    # 2.0 tested better and is deliberately not what shipped. Twenty-eight
    # variants were searched across this sweep and taking the argmax of a
    # search is the trap this project keeps finding elsewhere; 2.5 sits inside
    # the monotonic run rather than at its end, and holds drawdown at the old
    # level while 2.0 does not.
    #
    # CONFIRMED ON TEN YEARS. These settings, and the sizing that went with
    # them, were chosen on 2024-2026 - a window with no crash in it. Re-run
    # year by year from 2017, which includes the 2018 selloff, COVID and 2022:
    #
    #     year      SPY      OLD 3.0/55, 6/33%     NEW 2.5/60, 12/20%
    #     2017   +18.6%     +4.78%  (dd -2.12%)    +6.23%  (dd -2.42%)
    #     2018    -7.0%     +1.76%  (dd -4.87%)    +5.11%  (dd -9.49%)
    #     2019   +28.6%     +2.20%  (dd -4.38%)    +5.82%  (dd -5.26%)
    #     2020   +15.2%     -0.30%  (dd -8.67%)    +0.59%  (dd -11.91%)
    #     2021   +28.7%     +9.16%  (dd -3.25%)   +25.28%  (dd -4.73%)
    #     2022   -19.9%     -2.26%  (dd -3.72%)    -8.00%  (dd -10.76%)
    #     2023   +24.8%     +5.41%  (dd -3.29%)    +7.99%  (dd -7.41%)
    #     2024   +24.0%     -4.41%  (dd -7.00%)    +4.73%  (dd -6.89%)
    #     2025   +16.6%     +5.81%  (dd -6.18%)    +5.71%  (dd -10.35%)
    #     2026   +12.7%     +5.53%  (dd -3.82%)    +9.14%  (dd -5.38%)
    #     ----------------------------------------------------------------
    #     total +242.6%    +30.4%   CAGR +2.69%   +78.7%   CAGR +5.98%
    #
    # Better in 8 of 10 years, more than double the decade, and one down year
    # against three - on eight years that played no part in choosing it.
    #
    # THE COST, STATED PLAINLY. 2022 is worse: -8.00% against -2.26%, at
    # -10.76% drawdown against -3.72%. Roughly double the long-run return is
    # bought with materially worse behaviour in a sustained decline. It is
    # still the better trade on risk-adjusted terms (CAGR over worst drawdown,
    # 0.50 against 0.31), but anyone who cannot sit through -12% in a bad year
    # should revert to 3.0/55 with a cap of 6 at 33%.
    #
    # And the constant across all of it: SPY returned +242.6% over the same
    # decade. Both configurations lose to buying the index and doing nothing.
    # This is a low-return, low-risk product and ten years says so as clearly
    # as two did.
    stop_atr_multiple: float = 2.5   # wider than the trend rule; entries are into weakness
    # RAISED FROM 10 TO 20. The cap was binding, not backstopping: average
    # holding at 10 was 8.9 days, so most positions were being closed by an
    # arbitrary clock rather than by rsi_exit - the rule's own signal that the
    # move it entered on had finished. That is the "collect 0.4R" geometry the
    # 2026-08-28 review identified in the trend gate, arriving here by a
    # different route.
    #
    # Measured on the same 31 entries, so only the exit timing differs:
    #
    #     hold  mean/trade   95% CI            p       1st half  2nd half
    #      10     +1.571%   [+0.01%, +3.17%]  0.0364    +0.489%   +2.166%
    #      20     +1.991%   [+0.24%, +3.74%]  0.0210    +0.191%   +2.981%
    #
    # 20 is the only alternative positive in BOTH halves - 15, 30 and 60 all
    # have a negative first half - and it lifts the interval's lower bound off
    # zero.
    #
    # The honest caveat: the column zigzags. 15 is worse than both 10 and 20,
    # and 30 is worse than 20, which on 31 trades is what noise looks like. The
    # reason to take it is the mechanism - an 8.9-day average against a 10-day
    # cap means the limit is deciding most exits - not the ranking.
    max_holding_bars: int = 20
    # 0.035 is now EVIDENCED rather than reasoned. It was defended twice on
    # the argument that loosening a crash filter over a window containing no
    # crash will always look free. Alpaca's history reaches 2016, so 2020 and
    # 2022 are in the sample and the argument could finally be tested:
    #
    #     max_atr   10yr total    CAGR    2020 (DD)     2022 (DD)
    #      0.025        +56.9%   +4.61%  -0.6% (-11%)  -8.8% (-10%)
    #      0.035        +78.8%   +5.98%  +0.6% (-12%)  -8.0% (-11%)   <- live
    #      0.05         +72.6%   +5.61%  -1.0% (-13%)  -9.0% (-11%)
    #      0.10         +69.4%   +5.42%  -0.8% (-14%) -10.8% (-12%)
    #
    # It is the best value on the decade AND the best in both crash years, and
    # loosening it degrades 2020 and 2022 monotonically - which is exactly the
    # failure the reasoning predicted. Tightening to 0.025 is also worse, so
    # this is a real optimum rather than an arbitrary line.
    max_atr_fraction: Optional[float] = 0.035
    min_price: float = 20.0
    min_average_dollar_volume: float = 50_000_000.0
    # Warmup, held separately from the trend filter ON PURPOSE.
    #
    # `minimum_history` used to be trend_ma_days + rsi_period + 1, so turning
    # the trend filter off would have collapsed the warmup requirement from
    # 215 bars to 15 - and the rule would have started trading on an RSI
    # computed from fifteen prices and an ATR that needs about twice its
    # period to stabilise. That is not what was measured: the no-filter result
    # this configuration is based on was produced with 215 bars of warmup,
    # because the harness took `minimum_history` from a config that still had
    # the 200-day filter set.
    #
    # Shipping the collapse would have meant running a strategy nobody tested
    # while quoting numbers from one nobody shipped.
    warmup_days: int = 200

    def __post_init__(self) -> None:
        if not 0 < self.rsi_entry < self.rsi_exit < 100:
            raise ValueError("require 0 < rsi_entry < rsi_exit < 100")
        if self.stop_atr_multiple <= 0 or self.max_holding_bars < 1:
            raise ValueError("stop_atr_multiple and max_holding_bars must be positive")
        if self.trend_ma_days < 0:
            raise ValueError("trend_ma_days must be 0 (filter off) or positive")
        if self.warmup_days < 1:
            raise ValueError("warmup_days must be positive")

    @property
    def minimum_history(self) -> int:
        return max(self.trend_ma_days, self.warmup_days) + self.rsi_period + 1


@dataclass(frozen=True)
class MeanReversionSignal:
    symbol: str
    action: str                      # "BUY" or "STAND_ASIDE"
    close: float
    stop: Optional[float]
    rsi: Optional[float]
    trend_ma: Optional[float]
    atr_fraction: Optional[float]
    reasons: List[str]

    @property
    def is_buy(self) -> bool:
        return self.action == "BUY"



# Crypto needs its own floors or the rule cannot see the instruments at all.
#
# Measured 2026-09-08, and every number here is a fact about the asset class
# rather than a tuned parameter:
#
#   min_price 20        excludes DOT and UNI outright; SHIB trades near
#                       $0.00001, so any dollar floor is meaningless
#   min_adv 50m         Alpaca's own crypto book is far thinner than the
#                       consolidated equity tape
#   max_atr_fraction    3.5% rejects 95% of crypto days; the daily range is
#                       routinely 3-6% and that is normal, not a falling knife
#
# WHAT THIS PRESET DOES NOT DO IS MAKE CRYPTO PROFITABLE. With these floors
# the shipped rule fires 8 times in five years and none in the last two and a
# half, because oversold and above-the-200-day coincide on 1% of crypto days
# against 3.8% if they were independent. Every other rule family tested -
# RSI(2) mean reversion, 20/50/100/200-day trend, Donchian breakout - loses
# money in the account simulator. See docs/2026-09-08-crypto-rejected.md.
#
# It exists so that crypto CAN be run and observed on a bounded slice of
# capital, not because the evidence says it should be.
CRYPTO_MEAN_REVERSION = MeanReversionConfig(
    min_price=1e-9,
    min_average_dollar_volume=100_000.0,
    max_atr_fraction=None,
)


def evaluate(
    symbol: str, bars: Sequence[Bar], config: MeanReversionConfig = MeanReversionConfig()
) -> MeanReversionSignal:
    """Decide from bars up to and including the last one. No lookahead."""
    reasons: List[str] = []
    if len(bars) < config.minimum_history:
        return MeanReversionSignal(
            symbol.upper(), "STAND_ASIDE", bars[-1].close if bars else 0.0,
            None, None, None, None, ["Not enough history"],
        )

    closes = [b.close for b in bars]
    close = closes[-1]
    # trend_ma_days == 0 means the filter is off. There has to be an explicit
    # switch: setting it to 1 makes the average equal the close, and the test
    # below demands close > average, so a "1-day filter" silently rejects
    # every candidate forever. That mistake cost a whole test run.
    trend_ma = sma(closes, config.trend_ma_days) if config.trend_ma_days else None
    strength = rsi(closes, config.rsi_period)
    atr = wilder_atr(bars, config.atr_days)
    atr_fraction = (atr / close) if (atr and close > 0) else None
    dollar_volume = sum(b.close * b.volume for b in bars[-20:]) / 20.0

    if close < config.min_price:
        reasons.append("Price below ${0:.2f}".format(config.min_price))
    if dollar_volume < config.min_average_dollar_volume:
        reasons.append("Average dollar volume below the liquidity floor")
    if config.trend_ma_days and (trend_ma is None or close <= trend_ma):
        reasons.append(
            "Not above the {0}-day average; buying weakness only makes sense "
            "inside an intact uptrend".format(config.trend_ma_days)
        )
    if strength is None or strength > config.rsi_entry:
        reasons.append(
            "RSI {0} is not at or below {1}".format(
                "n/a" if strength is None else "{0:.1f}".format(strength), config.rsi_entry
            )
        )
    if atr is None:
        reasons.append("ATR unavailable")
    elif config.max_atr_fraction is not None and atr_fraction is not None:
        if atr_fraction > config.max_atr_fraction:
            reasons.append(
                "ATR is {0:.2%} of price, above the {1:.2%} ceiling; this is a "
                "falling knife rather than a dip".format(atr_fraction, config.max_atr_fraction)
            )

    stop = (close - config.stop_atr_multiple * atr) if atr else None
    if stop is not None and stop <= 0:
        reasons.append("Calculated stop is non-positive")
        stop = None

    action = "BUY" if not reasons and stop is not None else "STAND_ASIDE"
    return MeanReversionSignal(
        symbol.upper(), action, close, stop, strength, trend_ma, atr_fraction, reasons
    )


# Conviction weighting scale. A pullback of this depth from the 20-day high
# earns the full multiplier; flat earns the minimum, linear between.
CONVICTION_FULL_DRAWDOWN = 0.08
CONVICTION_MIN = 0.5
CONVICTION_MAX = 1.5


def conviction(bars: Sequence[Bar]) -> float:
    """How much of the risk budget this setup deserves, around 1.0.

    Same total appetite, concentrated where it measures better. Of six
    candidate signals tested on 1,872 entries across 2016-2026, split in half,
    the drawdown from the 20-day high was the only one monotonic on the
    holdout - deeper pullback, more to revert:

        quintile (deepest -> shallowest)   first half   holdout
              deepest                         +1.60%    +1.42%
                                              +1.73%    +1.51%
                                              +0.01%    +1.15%
                                              +0.54%    +0.96%
              shallowest                      +0.49%    +0.50%

    RSI depth - the obvious candidate, and the one predicted to work - is
    noise: its two halves disagree completely. 63-day momentum and SPY's RSI
    point in OPPOSITE directions across the halves.

    AND IT WAS CONTROLLED. Weighting improved the decade from +84.9% to
    +127.6%, which is not enough on its own: larger positions crowd others out
    of the cash, so the result was confounded with "fewer, bigger positions" -
    a variable that produced 85, 112, 90, 110, 90 with no ordering when swept
    directly. Random multipliers from the identical distribution:

        flat                        +84.9%   (818 trades)
        on the signal              +127.6%   (708 trades)
        random, four seeds    +73, +73, +77, +66%   (~825 trades each)

    Every random seed lands BELOW flat, and the signal lands far above. The
    random runs also kept MORE trades while doing worse, so trade count is not
    what is driving it. The signal is.
    """
    if len(bars) < 21:
        return 1.0
    high20 = max(bar.high for bar in bars[-20:])
    close = bars[-1].close
    if high20 <= 0 or close <= 0:
        return 1.0
    depth = max(0.0, min(1.0, -(close / high20 - 1.0) / CONVICTION_FULL_DRAWDOWN))
    return CONVICTION_MIN + (CONVICTION_MAX - CONVICTION_MIN) * depth


def should_exit(
    bars: Sequence[Bar],
    entry_price: float,
    stop: float,
    bars_held: int,
    config: MeanReversionConfig = MeanReversionConfig(),
    entry_time: Optional[str] = None,
) -> Optional[str]:
    """Why this position should close now, or None to keep holding.

    `entry_time` is the ISO timestamp the position was opened at. The stop is
    only checked against bars from a session strictly LATER than that date,
    because a daily bar can otherwise report a low from hours before the
    position existed.

    Measured live on 2026-09-06: EWY was entered at 15:00 ET on 09-04 behind a
    stop at 186.00. The most recent daily bar was 09-04's, whose low of 181.30
    came from the morning session - before the entry, and before the broker
    stop was placed. This function returned "stop" and the next cycle would
    have closed a position sitting on +$161, while the real broker-side stop
    had correctly never triggered because EWY never traded below 186 after the
    entry.

    Without `entry_time`, `bars_held` supplies the fallback. It counts
    COMPLETED daily bars since entry, and the entry day's own bar is excluded
    from the series while it is forming - so bars_held of 0 means the last bar
    predates the entry entirely, and 1 means it is the entry day's bar, which
    still contains pre-entry hours. Only from 2 is the final bar wholly after
    the position opened.
    """
    if not bars:
        return None
    bar = bars[-1]
    opened_on = _entry_date(entry_time) if entry_time else None
    if opened_on is not None:
        # Strictly later session. The entry day's own bar still contains the
        # hours before the position existed, so it does not qualify.
        stop_is_comparable = bar.timestamp.date() > opened_on
    else:
        stop_is_comparable = bars_held >= 2
    if stop_is_comparable and bar.low <= stop:
        return "stop"
    strength = rsi([b.close for b in bars], config.rsi_period)
    if strength is not None and strength >= config.rsi_exit:
        return "reverted"
    if bars_held >= config.max_holding_bars:
        return "time"
    return None
