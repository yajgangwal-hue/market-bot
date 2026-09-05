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
from typing import Dict, List, Optional, Sequence

from .indicators import rsi, sma, wilder_atr
from .types import Bar


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
    rsi_exit: float = 55.0           # sell once it has recovered to here
    trend_ma_days: int = 200         # only inside a long-term uptrend
    atr_days: int = 14
    stop_atr_multiple: float = 3.0   # wider than the trend rule; entries are into weakness
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
) -> Optional[str]:
    """Why this position should close now, or None to keep holding."""
    if not bars:
        return None
    bar = bars[-1]
    if bar.low <= stop:
        return "stop"
    strength = rsi([b.close for b in bars], config.rsi_period)
    if strength is not None and strength >= config.rsi_exit:
        return "reverted"
    if bars_held >= config.max_holding_bars:
        return "time"
    return None
