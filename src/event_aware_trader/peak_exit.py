"""Sell a position into intraday strength rather than at whatever price is on
the screen when someone decides to exit.

WHAT THIS IS FOR. On 2026-09-14 the account owner asked for three losing
positions to be closed - but not dumped at an arbitrary moment: "when the bot
thinks that it is at its daily peak then sell the losing stocks". This module
is that judgement, separated from the plumbing so it can be tested without a
broker.

THE HONEST LIMIT, STATED UP FRONT. A day's peak is only knowable after the
day is over. Nothing here can identify the high in advance; a rule that sells
"at the peak" can only mean "sell while price is at the top of the range so
far", and on a day that keeps climbing it will sell at 10am and leave money on
the table. What it reliably avoids is the opposite and more common mistake -
selling into an intraday trough because that happened to be when the decision
was made. Half the day's range is the rough size of what is at stake either
way.

WHAT THIS IS NOT. It is not a standing strategy rule, and deliberately so.
Exiting losers early is the single most destructive change measured on this
project: the rescue-exit test (09-11) moved win rate 53% -> 67% while CAGR
fell 7.83% -> 6.41%, because a mean-reversion book earns its living from
positions that are underwater in the middle of their life. This module is a
directed liquidation tool - it acts on the symbols it is handed, and nothing
else decides to call it.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

# Within this fraction of the session high counts as "at the peak". 0.15% is
# wide enough that a normal bid-ask bounce does not hide the top from us, and
# tight enough that it is genuinely the top of the range rather than "near".
DEFAULT_TOLERANCE = 0.0015

# Bars required before the session high means anything. At 5-minute bars this
# is the first half hour, which is also the noisiest part of the day - the
# opening print is frequently the high or the low and neither tells you much.
DEFAULT_MIN_BARS = 6

# Minutes before the close at which we stop waiting for a better price and
# take what is there. Without a deadline a position on a day that never
# revisits its high is simply never sold, and the instruction quietly fails.
DEFAULT_DEADLINE_MINUTES = 12.0

WAIT = "wait"
SELL = "sell"


@dataclass
class PeakDecision:
    action: str                 # WAIT or SELL
    reason: str
    session_high: Optional[float] = None
    last: Optional[float] = None
    gap_pct: Optional[float] = None      # how far below the high, in percent
    bars_seen: int = 0

    @property
    def should_sell(self) -> bool:
        return self.action == SELL


def session_bars(bars: Sequence, session_date: date) -> List:
    """Just today's bars. Anything earlier is a different day's range."""
    return [b for b in bars if b.timestamp.date() == session_date]


def decide(bars: Sequence, session_date: date,
           minutes_to_close: Optional[float] = None,
           tolerance: float = DEFAULT_TOLERANCE,
           min_bars: int = DEFAULT_MIN_BARS,
           deadline_minutes: float = DEFAULT_DEADLINE_MINUTES) -> PeakDecision:
    """Sell if price is at the top of today's range, or if time has run out.

    `minutes_to_close` comes from the BROKER's clock, not this machine's - it
    knows half-days and holidays, and a deadline measured against the wrong
    close is not a deadline. None means the clock could not be read, in which
    case the deadline simply never fires and only the peak rule can sell:
    waiting is the safe failure here, since the position keeps its stop.
    """
    today = session_bars(bars, session_date)
    if not today:
        return PeakDecision(WAIT, "no bars for today yet", bars_seen=0)

    high = max(b.high for b in today)
    last = today[-1].close
    gap_pct = ((high - last) / high * 100.0) if high > 0 else 0.0

    deadline_hit = (minutes_to_close is not None
                    and minutes_to_close <= deadline_minutes)

    if len(today) < min_bars and not deadline_hit:
        return PeakDecision(
            WAIT, "only {0} bars so far; the day's high is not meaningful "
                  "before {1}".format(len(today), min_bars),
            high, last, gap_pct, len(today))

    if high > 0 and last >= high * (1.0 - tolerance):
        return PeakDecision(
            SELL, "at the session high ({0:.2f}), {1:.2f}% off the top"
                  .format(high, gap_pct),
            high, last, gap_pct, len(today))

    if deadline_hit:
        return PeakDecision(
            SELL, "{0:.0f} min to the close and the high ({1:.2f}) did not "
                  "come back; taking {2:.2f}".format(
                      minutes_to_close, high, last),
            high, last, gap_pct, len(today))

    return PeakDecision(
        WAIT, "{0:.2f}% below the session high ({1:.2f}); waiting"
              .format(gap_pct, high),
        high, last, gap_pct, len(today))
