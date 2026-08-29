# Unleashing it on the week of 2026-08-24

## What it does at each level of freedom

Daily bars, week of 2026-08-24, $1,000:

| Setting | Trades closed | Still open | Return |
|---------|--------------|-----------|--------|
| default (score 70) | 0 | 0 | 0.00% |
| score 60 | 0 | 0 | 0.00% |
| score 50 | 0 | 3 | −0.23% |
| score 0 (blockers only) | 0 | 3 | −0.16% |

Even with the score gate removed entirely, **no trade opens and closes inside
one week** — the trailing exit holds positions longer than five sessions. To
see completed trades in a week the bar interval has to change, not the gate.

## Intraday, 15-minute bars

The same week, unleashed on 15-minute bars, is where it actually trades.

**First run — six trades, one win, −$9.16.** And one of them was impossible.

| Symbol | Bars held | Net | Exit |
|--------|----------|-----|------|
| GLD | 9 | −$2.74 | trailing_stop |
| **XLP** | **1** | **+$2.61** | **stop** ← incoherent |
| TLT | 1 | −$0.83 | trailing_stop |
| EEM | 3 | −$3.82 | stop |
| XLK | 1 | −$2.25 | trailing_stop |
| SLV | 2 | −$2.13 | trailing_stop |

A *profitable stop-out* is not a thing. That was a real bug.

## Bug: entering a position already through its stop

The stop is derived from the signal bar's close, but the fill happens at the
next bar's open. XLP's signal came from the 08-24 15:45 close at $87.43 with a
stop at $87.15. Overnight it gapped down 0.66%, so the fill landed at **$86.89
— below its own stop**. The position was entered already stopped out, and
closing it "at the stop" booked a phantom $2.61 profit.

A second failure hides in the same place. Position size is risk budget divided
by risk-per-share, so a fill that lands *just above* the stop leaves a tiny
denominator and silently produces a **maximum-sized position on the setup whose
premise just broke**.

This affected live trading too, not only the simulator: `autotrade` was
computing the stop the same way and would have submitted a buy with a stop
above the fill, which a broker rejects or triggers instantly.

**Fix.** Both `portfolio.py` and `autotrade.py` now re-validate against the
actual fill: skip the entry if the fill is at or below the stop, or if the gap
has eaten more than half the planned risk. Skipped entries are counted
(`gapped_through_stop`), not silently dropped. `ClosedTrade` also gained
`initial_stop` and `exit_stop` so this class of error is visible in the record.

**After the fix**, same week: 3 entries skipped, 0 incoherent exits.

| Symbol | Entry | Bars | Net | Exit |
|--------|-------|------|-----|------|
| GLD | 08-24 09:45 | 9 | −$2.74 | trailing_stop |
| EEM | 08-26 09:30 | 3 | −$1.49 | trailing_stop |
| SLV | 08-28 09:45 | 2 | −$2.14 | trailing_stop |

**3 trades, 0 wins, −$6.37, ending $993.63 (−0.64%).** An improvement of $2.79
purely from removing trades that should never have existed.

## Why the survivors lost

All three entered at 09:30 or 09:45 and were stopped out within 30 minutes to
two hours. Measuring the range of every 15-minute bar across 20 ETFs:

| Time | Mean range | vs midday |
|------|-----------|-----------|
| **09:30** | 0.5864% | **3.02x** |
| 09:45 | 0.3996% | 2.05x |
| 10:00 | 0.3716% | 1.91x |
| 10:45 | 0.2706% | 1.39x |
| 12:00 | 0.1945% | 1.00x |

The opening bar carries three times the range of a midday bar. The stop is
sized from an ATR that averages in quiet midday bars, so at 09:30 it sits well
inside ordinary opening noise. Those trades were not stopped out because the
idea was wrong; they were stopped out because the stop was too tight for the
time of day.

## The fix that did not survive validation

An opening blackout is the obvious response, and on the target week it worked:

| Blackout | Trades | Return |
|----------|-------|--------|
| none | 3 | −0.64% |
| 30 min | 1 | **−0.15%** |

Then the same setting over the full month:

| Blackout | Trades | Win rate | Return |
|----------|-------|---------|--------|
| **none** | 22 | 40.9% | **+1.89%** |
| 15 min | 16 | 31.2% | −0.69% |
| 30 min | 12 | 41.7% | −0.43% |
| 60 min | 10 | 50.0% | +0.95% |
| 120 min | 9 | 44.4% | +1.09% |

**No blackout is the best setting over the month.** The week where it looked
like a half-point improvement was a three-trade sample.

So the feature ships **disabled by default**, with the volatility measurement
and the contradicting trading result recorded next to it. The hypothesis is
well-motivated and the sample — 9 to 22 trades — cannot resolve it either way.
Shipping a default the evidence contradicts would be worse than leaving a good
idea untested.

## Result

| | |
|---|---|
| Trades taken | 3 |
| Won / lost | 0 / 3 |
| **Profit** | **−$6.37 (−0.64%)** |
| Bugs found and fixed | 1 (affecting live trading) |
| Phantom entries removed | 3 |

Unleashing it produced losing trades, and analysing them produced one genuine
correctness fix. It did not produce a profitable week, and the honest summary
of the intraday experiments across this month is that 22 trades returning
+1.89% is not distinguishable from noise.

Tests 113 → 118.
