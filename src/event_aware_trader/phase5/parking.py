"""H-0006. What idle capital does when the strategy has no signal.

THE FINDING THAT MOTIVATES THIS. Over the decade the frozen strategy
averages 44.3% invested and returns +58.59%. SPY held at that same
weight, with no selection and no timing, returns +88.79% with idle cash
at zero and +116.05% with idle cash at the bill rate. Every filter and
exit tested in Phases 5 and 6 failed at the portfolio level for the same
reason: capital freed by rejecting a trade earned nothing. The gap to the
benchmark is exposure, and no exit rule can close it.

This is an OVERLAY on the cash curve, exactly as `with_parked_cash` is.
The simulator's money path does not change. The strategy's own trades,
sizes, stops and exits are untouched; only what the parked balance earns
is different, and it is charged the full one-way cost on every dollar it
moves and on the whole balance whenever the trend state flips.

NO LOOK-AHEAD, and the point where it could creep in is named. The
decision to be in the index on day t uses the index's close against its
200-day average as of day t-1. Day t's return is then applied to the
balance that decision left in the index. A version that used day t's own
close to decide day t's exposure would know the answer before the bet.
"""

import copy
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

#: Same constants the SGOV overlay uses, so the two are comparable.
PARKING_FLOOR = 2_000.0
RESERVED_FRACTION = 0.05

#: Full one-way friction on the index leg: 2 bps half spread + 4 bps
#: slippage. SGOV is charged 2 bps because it barely moves; SPY is not.
INDEX_COST = 0.0006

#: The strategy's own trend constant, reused rather than chosen.
TREND_DAYS = 200


def index_state(bars) -> Dict[date, Tuple[float, Optional[bool]]]:
    """For each session: the close, and whether it sat above its 200-day.

    Both values are as of THAT session's close and are only ever applied
    to the following session's return.
    """
    out: Dict[date, Tuple[float, Optional[bool]]] = {}
    closes: List[float] = []
    for bar in bars:
        closes.append(bar.close)
        above = None
        if len(closes) >= TREND_DAYS:
            average = sum(closes[-TREND_DAYS:]) / TREND_DAYS
            above = bar.close > average
        out[bar.timestamp.date()] = (bar.close, above)
    return out


def _rate_on(rates: Dict[date, float], day: date, last: float) -> float:
    for back in range(8):
        probe = date.fromordinal(day.toordinal() - back)
        if probe in rates:
            return rates[probe]
    return last


def with_index_parking(report, index, mode: str,
                       cash_rates: Optional[Dict[date, float]] = None,
                       floor: float = PARKING_FLOOR,
                       reserved_fraction: float = RESERVED_FRACTION,
                       cost: float = INDEX_COST):
    """The candidate's curve with idle cash in the index, by rule.

    mode:
      "always"       idle cash in the index unconditionally (the CONTROL:
                     pure exposure with no trend filter)
      "trend_cash0"  in the index while it closed above its 200-day the
                     session before; otherwise idle at 0%
      "trend_bills"  as above, but idle earns `cash_rates` (the bill rate)
      "none"         identity - used only for the equivalence check
    """
    if mode not in ("always", "trend_cash0", "trend_bills", "none"):
        raise ValueError("unknown parking mode " + repr(mode))
    if len(report.cash_curve) != len(report.equity_curve):
        raise ValueError("cash_curve and equity_curve differ in length")
    state = index_state(index) if mode != "none" else {}
    rates = cash_rates or {}

    sleeve = 0.0
    lifted: List[Tuple[datetime, float]] = []
    previous_stamp: Optional[datetime] = None
    previous_parked = 0.0
    previous_close: Optional[float] = None
    in_index_yesterday = False
    bill_rate = 0.0
    switches = 0

    for (stamp, equity), (_, cash) in zip(report.equity_curve, report.cash_curve):
        day = stamp.date()
        parked = max(0.0, cash - floor - reserved_fraction * equity)
        close, above = state.get(day, (None, None))

        if previous_stamp is not None and mode != "none":
            balance = sleeve + previous_parked
            # 1. Yesterday's decision earns today's return.
            if in_index_yesterday and close is not None and previous_close:
                sleeve += balance * (close / previous_close - 1.0)
            elif mode == "trend_bills":
                bill_rate = _rate_on(rates, day, bill_rate)
                years = max(0.0, (stamp - previous_stamp).days / 365.25)
                sleeve += balance * ((1.0 + bill_rate) ** years - 1.0)
            # 2. Friction on what moved.
            moved = abs(parked - previous_parked)
            if moved > 1.0:
                sleeve -= moved * cost

        # 3. TODAY's close decides TOMORROW's exposure. Nothing here has
        # touched today's return with today's decision.
        if mode == "always":
            in_index_today = True
        elif mode == "none":
            in_index_today = False
        else:
            in_index_today = bool(above)
        if previous_stamp is not None and in_index_today != in_index_yesterday \
                and mode != "none":
            # The whole parked balance turns over on a regime flip.
            sleeve -= (sleeve + parked) * cost
            switches += 1

        lifted.append((stamp, equity + sleeve))
        previous_stamp, previous_parked = stamp, parked
        if close is not None:
            previous_close = close
        in_index_yesterday = in_index_today

    # A shallow copy rather than dataclasses.replace, so the overlay works
    # on any object carrying the two curves - the real PortfolioReport and
    # a test double alike. The strategy leg (trades, positions) is shared
    # by reference and deliberately not copied: it must not change.
    out = copy.copy(report)
    out.equity_curve = lifted
    out.equity = report.equity + sleeve
    out.parking_switches = switches
    return out
