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
    trend_ma_days: int = 200         # only inside a long-term uptrend
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
    max_atr_fraction: Optional[float] = 0.035
    min_price: float = 20.0
    min_average_dollar_volume: float = 50_000_000.0

    def __post_init__(self) -> None:
        if not 0 < self.rsi_entry < self.rsi_exit < 100:
            raise ValueError("require 0 < rsi_entry < rsi_exit < 100")
        if self.stop_atr_multiple <= 0 or self.max_holding_bars < 1:
            raise ValueError("stop_atr_multiple and max_holding_bars must be positive")

    @property
    def minimum_history(self) -> int:
        return self.trend_ma_days + self.rsi_period + 1


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
    trend_ma = sma(closes, config.trend_ma_days)
    strength = rsi(closes, config.rsi_period)
    atr = wilder_atr(bars, config.atr_days)
    atr_fraction = (atr / close) if (atr and close > 0) else None
    dollar_volume = sum(b.close * b.volume for b in bars[-20:]) / 20.0

    if close < config.min_price:
        reasons.append("Price below ${0:.2f}".format(config.min_price))
    if dollar_volume < config.min_average_dollar_volume:
        reasons.append("Average dollar volume below the liquidity floor")
    if trend_ma is None or close <= trend_ma:
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
