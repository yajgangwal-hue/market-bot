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
    rsi_entry: float = 30.0          # buy at or below this
    rsi_exit: float = 55.0           # sell once it has recovered to here
    trend_ma_days: int = 200         # only inside a long-term uptrend
    atr_days: int = 14
    stop_atr_multiple: float = 3.0   # wider than the trend rule; entries are into weakness
    max_holding_bars: int = 10
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
