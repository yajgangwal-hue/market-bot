# Re-tuning after the trend filter came off — 26 variants, nothing shipped

**9 September 2026.** Every parameter in `MeanReversionConfig` was chosen by
sweeps run with the 200-day trend filter in place. When that filter was
switched off, those numbers were optimising a strategy that no longer existed:
the filter had been doing a large part of the selection, and the other dials
were compensating for a population of trades that had changed.

So all five were re-swept. Nothing survived.

## What passed the usual bar, and why that meant nothing

Three of about twenty-six variants beat the shipped configuration on **both**
halves of the decade — the bar this project has used all week to reject
changes.

| variant | decade | maxDD | 1st half | 2nd half |
|---|---|---|---|---|
| baseline (shipped) | 157.4% | −22.4% | 59.9% | 69.9% |
| rsi_entry 45 | 187.6% | −23.0% | 82.4% | 93.3% |
| stop 1.5 ATR | 275.6% | −20.9% | 77.5% | 114.1% |
| atr ceiling none | 188.3% | −22.1% | 65.5% | 85.1% |

**Three passes is exactly what chance predicts.** A pure-noise variant has
roughly a one-in-four chance of beating a baseline on both halves. Of the ~10
variants that are plausible neighbours of the shipped config, chance alone
produces about 2–3 passes. The both-halves rule was designed to test one
hypothesis; run twenty-six hypotheses past it and it stops being evidence.

Two were rejected immediately on the shape of their own sweeps:

- **rsi_entry 45.** First-half column: 18.7, 44.2, 59.9, **49.0**, 82.4. It is
  non-monotone, and 40 is *worse* than the shipped 35 before 45 leaps. One
  lucky cell.
- **atr ceiling none.** Decade column across the top of the range: 186.2,
  **127.7**, 188.3. It dips hard at 8% and jumps back. Same shape, same
  verdict.

## The one that looked real, and how it died

The stop was different in kind. On the coarse grid, tighter was better at
every step — 275.6, 235.5, 157.4, 153.9, 77.3 — the drawdown improved as well
as the return, and the mechanism had been written down before the numbers
arrived: with the trend filter off the rule buys stocks in genuine downtrends,
where a tight stop cuts a falling knife and a wide one rides it down.

A finer grid weakened it. Every value from 0.75 to 2.0 beat the shipped 2.5,
which is a real level shift, but *within* that range it zigzagged — 260.5,
310.7, 236.2, 275.6, 227.6, 235.5 — so "1.5 is the optimum" was never the
finding and neither was 1.0.

The thirty-year test killed it outright:

| stop | CAGR | maxDD | 2000-02 | 2008 | 2022 |
|---|---|---|---|---|---|
| 1.0 ATR | 7.86% | −32.6% | −16.4% | −7.8% | +4.9% |
| 1.5 ATR | **6.05%** | **−43.0%** | −26.7% | **−27.6%** | −3.5% |
| 2.0 ATR | 8.42% | −27.6% | −9.4% | −15.1% | +3.4% |
| 2.5 ATR (shipped) | 6.76% | −36.7% | −17.3% | −25.8% | −5.3% |

No ordering in any column. CAGR: 7.86, 6.05, 8.42, 6.76. Drawdown: −32.6,
−43.0, −27.6, −36.7. And **1.5 ATR — the coarse grid's winner — is the worst
configuration in the table**, with a −43.0% drawdown and −27.6% in 2008, both
worse than what is shipped.

The decade's clean result was a decade-specific artefact. Six values beating
the shipped one looked like a level shift; over thirty years it is
indistinguishable from noise.

## A fragility worth recording separately

Even taking the decade at face value, the tight-stop advantage is almost
entirely a function of execution quality:

| one-way cost | stop 2.5 | stop 1.5 | advantage |
|---|---|---|---|
| 6 bps | 157.4% | 275.6% | +118.2 |
| 9 bps | 165.5% | 197.0% | +31.5 |
| 12 bps | 129.9% | 163.3% | +33.4 |
| 18 bps | 81.7% | 89.2% | +7.5 |

A tighter stop buys return with trading activity, so the gain evaporates as
fills get worse. Any future version of this idea has to clear the crash test
*and* survive pessimistic costs.

## The general lesson, which is the actual output

This is the third time this project has measured the same thing: **return
differences at this scale are noise and risk differences are real.** The
mechanism is that changing any sizing or exit parameter changes *which trades
get taken*, and the sequence then diverges chaotically. It showed up in the
`risk_per_trade` sweep (85, 112, 90, 110, 90 with drawdown perfectly ordered),
in the position-size sweep (103, 69, 165, 34), and now here.

The practical consequence: a decade is not enough data to tune a parameter on,
and the both-halves rule is not enough protection when many parameters are
tried. The thirty-year window is now the deciding test, and it should be run
before anything is believed rather than after it is nearly shipped.

Nothing changed. `scripts/trend_filter_test.py` and the stop-check script are
kept so the next person can re-run rather than re-derive.
