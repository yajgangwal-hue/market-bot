# Benchmark units, and the mistake this document exists to prevent

*2026-09-17. Written after I reported a "−224.6 point" gap to SPY without
saying what a point was.*

That figure is a difference of **cumulative** returns. It is not a CAGR
difference, not an annualised anything, and not comparable to the
"+13.7 points" used for exit hypotheses, which is a difference of
cumulative returns **against the frozen baseline** rather than against
SPY. Both are percentage points of cumulative return, but they have
different reference assets, and nothing downstream may add or compare
them without saying so.

---

## The five quantities, defined once

Let `V0` and `V1` be the starting and ending value of a curve over the
same dates, and `Y` the span in years.

| name | definition | unit | example |
|---|---|---|---|
| cumulative return | `V1/V0 − 1` | fraction, quoted as % | baseline +58.59% |
| wealth multiple | `V1/V0` | ratio | baseline 1.5859× |
| CAGR | `(V1/V0)^(1/Y) − 1` | fraction per year | baseline +4.42% |
| annualised volatility | stdev of daily returns × √252 | fraction per year | baseline 9.3% |
| maximum drawdown | `min(V_t / max(V_≤t) − 1)` | fraction, negative | baseline −12.98% |

And the two differences, which must always name their reference:

| name | definition | reads as |
|---|---|---|
| **cumulative-return gap vs X** | `cum_candidate − cum_X` | "percentage points of cumulative return against X" |
| **excess CAGR vs X** | `CAGR_candidate − CAGR_X` | "CAGR points per year against X" |

**Never write "points" unmodified.** Write "points of cumulative return
vs SPY" or "CAGR points vs baseline".

## Worked example, decade window 2016-01-04 to 2026-09-04, 10.6639 years

| | cumulative | wealth multiple | CAGR | max DD |
|---|---|---|---|---|
| SPY, price only | +283.14% | 3.8314× | +13.42% | — |
| frozen baseline | +58.59% | 1.5859× | +4.42% | −12.98% |

- cumulative-return gap vs SPY: 58.59 − 283.14 = **−224.55 points of cumulative return**
- excess CAGR vs SPY: 4.42 − 13.42 = **−9.00 CAGR points per year**

Those two describe the same fact. The first is the one I quoted; the
second is the one most people mean by "how far behind". Quote both.

## SPY benchmark assumptions, verified

| assumption | what it is | verified how |
|---|---|---|
| **price or total return** | **PRICE ONLY** | `fetch_alpaca_equity_bars(adjustment="split")` is the default and the source comments say split and deliberately not "all". A total-return series would show ~14.8-15.0% CAGR against the 13.42% observed. |
| dividends | **excluded** | follows from the above; **the benchmark is understated by roughly 1.3-1.5 CAGR points per year** |
| splits | adjusted | required, or a 10-for-1 reads as a 90% crash |
| trading calendar | SPY's own printed sessions, 2,684 bars | the strategy is evaluated on the same merged calendar |
| starting capital | $100,000 for the strategy; the benchmark is a ratio and is capital-independent | |
| cash treatment | the simulator holds idle cash at **0%**; `with_parked_cash` adds the bill rate as a separate overlay | both bases are reported where relevant |
| transaction costs | strategy pays 2 bps half-spread + 4 bps slippage each way; **SPY buy-and-hold pays nothing in this comparison** | favours the benchmark, stated rather than corrected |
| rebalancing | SPY buy-and-hold: none. The "SPY at 44.3% weight" comparator is **daily rebalanced and frictionless**, which is an idealisation and not achievable | flagged wherever that figure appears |

**The direction of every known bias in this comparison favours SPY.** The
real gap is wider than reported, not narrower. That is the right way for
the error to point, and it must not be "corrected" in a later experiment
to make a candidate look better.

## Rules

1. Every benchmark comparison names its reference asset and its unit.
2. The comparison period is the strategy's own evaluation window, fixed
   before results are seen, and never re-chosen afterwards.
3. The benchmark definition does not change because a change would move
   the gap. If a better SPY series is obtained, the switch is registered
   as its own change with the old numbers preserved.
4. SPY is a benchmark, not an optimisation target. No parameter may be
   chosen to improve a comparison against it.
