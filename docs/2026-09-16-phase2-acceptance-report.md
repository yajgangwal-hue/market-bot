# Phase 2 acceptance report — P4, P6, P7, P8

*2026-09-16. Commits `dac3a1c` onward. The production path was not touched.
The question this phase answers: after correcting the benchmark and removing
research contamination, what performance remains on data that was not used
to construct the strategy?*

**The answer is: none, because no such data exists yet.** Clean evaluation
has not begun and needs 18 more sessions. Everything below is measured on
contaminated data and is labelled accordingly.

---

## 1. P4 — SCOPE STATEMENT

**What the backtest represents**

| | |
|---|---|
| **Capital included** | 100% of simulated capital ($100,000) allocated to the equity book |
| **Strategies included** | ONE: long-only mean reversion (RSI ≤ 35 above SMA200) |
| **Strategies EXCLUDED** | the 5% BTC sleeve; the 5% reserve that funds it |
| **Cash treatment** | idle cash earns the actual 3-month bill rate, applied as a post-hoc overlay (`with_parked_cash`), not as simulated SGOV trades |
| **Historical period** | 1996-01-01 → 2026-09-05 (229 symbols) and 2016-01-01 → 2026-09-05 (230 symbols) |
| **Universe** | today's liquid US equities and ETFs |
| **Survivorship bias** | **PRESENT.** The universe is names that exist now. A name delisted in 2003 is absent from the 1996 backtest |
| **Dividends** | **1996–2026: EXCLUDED** (unavailable). **2016–2026: credited as cash** on held positions, not reinvested |
| **Transaction costs** | 2 bps half-spread + 4 bps slippage = 6 bps one-way, both sides; $0 commission |
| **Execution** | market orders only; gapped stops fill at the open; rule exits carry the 0.652% timing haircut |

**Constraints modelled:** risk 0.5%/trade; 20% per name; 12 positions; one
per correlation bucket; 1.5% daily and 6% weekly loss guards; 2%
participation cap; whole shares; 3 entries/day; entries at the signal close.

**Constraints NOT modelled:** partial fills; latency; market impact;
volatility- or size-dependent slippage; the crypto sleeve; the 5% reserve's
competition for cash; SGOV as an actual instrument with its own spread.

**Does this represent the actual intended live portfolio? NO.** The live
account allocates ~95% to this book and ~5% to a BTC sleeve funded from a
reserve the simulator does not withhold. **Every historical figure in this
project describes an equity-only book that does not exist as configured.**
The sleeve's contribution is measured separately and must never be added to
these numbers without saying so.

**What this result can legitimately be used to conclude:**
- that the rule produced a positive return over this period on this universe
  under these assumptions — **in-sample**
- that its drawdown was far shallower than the index's over the same period
- that a change which loses money here will not win elsewhere (rejection)

**What it cannot be used to conclude:** that the strategy is profitable
forward; that it beats any benchmark; that its parameters are correct; that
the account will behave like this. It contains no out-of-sample evidence.

---

## 2. P6 — BENCHMARK METHODOLOGY

**The objective is stated in total-return terms, so total return is the
correct basis — where the data permits it. Where it does not, both legs are
put on price return rather than estimating one side.**

| decision | choice | why |
|---|---|---|
| dividend treatment, 1996–2026 | **both legs ex-dividend** | no dividend-adjusted series before 2016 is reachable from this machine (Alpaca starts 2016; the Yahoo path fails on a certificate error). Estimating one leg and measuring the other is not a comparison |
| dividend treatment, 2016–2026 | **both legs cum-dividend** | measured on both sides |
| strategy dividends | credited as **CASH** on held positions, on the ex-date, **not reinvested** | the account receives cash; it does not buy more of the stock. Crediting reinvestment it never performs would overstate it |
| SPY dividends | **reinvested** total-return series | that is what a buy-and-hold holder gets |
| signal basis | **split-adjusted (as-traded) prices, always** | see the leakage note below |
| cash | strategy's idle cash earns the actual bill rate; SPY is 100% invested | the comparison an owner actually faces |
| compounding | geometric on both legs | |
| annualisation | 365.25 calendar days on both legs | |
| calendar | both legs on their own trading days over the identical span | |
| risk-free rate | 2.30% (measured mean 3-month bill over the window), never 0 | rf = 0 flatters a book that is ~74% cash |
| transaction costs | strategy pays 6 bps/side on ~1,500 round trips; **SPY pays nothing** | a buy-and-hold leg incurs one entry. Charging it 6 bps once would change its CAGR by under 0.01 pts. **The comparison is therefore mildly unfavourable to the strategy, and deliberately left that way** |

**A leakage finding that determined the design.** `adjustment="all"`
back-adjusts *historical* closes using dividends paid *afterwards* — verified
directly: the last close is identical between the two series while every
earlier one differs. Running the strategy on that data would let RSI and SMA
see the future. **Signals therefore stay on as-traded prices, and only the
per-day dividend yield is extracted from the adjusted series.** That yield is
a contemporaneous cash event, not future information.

**Extraction and its validation.** Per-day yield = the gap between the
adjusted and split-only daily returns. The first attempt used a 1e-6
threshold and produced **225,929 payment days across 178 symbols** — about
one per trading day, i.e. floating-point rounding noise, not dividends.
Raised to 5e-4 (above the ~1e-4 noise floor of 2-decimal prices, below any
real payment): **8,453 payments, median 43 per symbol over ten years** ≈
quarterly, which is correct. Reconciled against each symbol's own CAGR gap:
detected yields recover 80–85% (XLU 2.75 of 3.28 pts/yr; VNQ 3.30 of 4.04;
SPY 1.40 of 1.72; COST 1.53 of 1.96). **That shortfall is the reinvestment
the bot does not perform, plus any payment under the threshold** — both
biases run against the strategy, so the figure is conservative.

---

## 3–5. STRATEGY vs BENCHMARK ON THE IDENTICAL BASIS

### 1996–2026 · price vs price · MEASURED

| | CAGR | vol | Sharpe | Sortino | maxDD |
|---|---|---|---|---|---|
| strategy + parked cash | **3.18%** | 6.1% | 0.17 | 0.23 | **−11.0%** |
| SPY price return | **8.55%** | 19.2% | **0.40** | **0.57** | −56.5% |
| **difference** | **−5.37 pts/yr** | −13.1 | −0.23 | −0.34 | +45.5 |

### 2016–2026 · total vs total · MEASURED

| | CAGR | vol | Sharpe | Sortino | maxDD |
|---|---|---|---|---|---|
| strategy, ex-dividend | 5.13% | 9.1% | 0.34 | 0.48 | −12.5% |
| **strategy + dividends as cash** | **5.71%** | 8.8% | 0.42 | 0.59 | **−11.9%** |
| SPY price return | 13.42% | 17.6% | 0.68 | 0.94 | −34.2% |
| **SPY total return** | **15.00%** | | | | |
| **difference, total vs total** | **−9.29 pts/yr** | | | | |

Dividend income on held positions over the decade: **$10,352**, worth
**+0.58 CAGR points** (5.13% → 5.71%).

**Per the brief: this increase is not evidence the strategy improved.** It
is a measurement correction. The strategy did exactly what it always did;
the simulator was failing to credit cash the account actually received.

---

## 6. COMPARABLE SHARPE AND SORTINO METHODOLOGY

Both legs, identically: daily returns from the equity curve; arithmetic mean
annualised ×252; standard deviation annualised ×√252; **excess over the
measured 2.30% bill rate**, never over zero. Sortino uses the same excess
numerator with downside deviation computed against the daily bill rate,
annualised the same way. Both legs use the same `metrics()` function in the
same run, so no methodological difference can exist between them.

**On this basis SPY wins both** over thirty years (0.40 vs 0.17 Sharpe;
0.57 vs 0.23 Sortino). The earlier claim that the bot led on risk-adjusted
return rested on an rf = 0 convention that flattered a three-quarters-cash
book, and on a headline since corrected downward by 2.57 points.

---

## 7. P7 — PURGE METHODOLOGY AND DATES

**Rule:** the evaluation boundary is the date of the last experiment whose
decision *changed the shipped configuration* (`accepted` or `reverted`).
Experiments that merely `measured` or `rejected` consumed data but altered no
parameter, so they do not move it — otherwise running more experiments would
buy a longer clean period.

**Derived from the registry (53 experiments), not chosen:**

| id | date | decision | what changed |
|---|---|---|---|
| EXP-0004 | 2026-09-09 | reverted | 200-day trend filter |
| EXP-0014 | 2026-09-10 | accepted | cash parking |
| EXP-0015 | 2026-09-10 | accepted | 5% BTC sleeve |
| EXP-0016 | 2026-09-11 | accepted | entry at the signal close |
| **EXP-0017** | **2026-09-11** | **reverted** | **entry window 30 → 20 min** |

**FREEZE DATE = 2026-09-11.** Independently equal to
`research.FORWARD_START`, which was set months earlier by a different route.
That agreement is a consistency check and it passes.

**What must be excluded from acceptance:** all 1996-01-01 → 2026-09-11.
Every parameter was selected using data spanning that whole range (37
recorded touches on the decade, 30 on the thirty-year window), so no part of
it can accept anything. It can still reject.

**Straddling trades:** any position opened before 2026-09-11 and closed
after it is purged — its entry used a rule chosen with knowledge of the
data, its outcome lands in the evaluation window.

Nothing is deleted. Every trade is placed in exactly one of
`clean` / `straddling` / `embargoed` / `pre_freeze` and the counts are
reported, because a purge that silently drops observations cannot be
distinguished from one that drops the inconvenient ones.

---

## 8. P8 — EMBARGO METHODOLOGY AND DATES

**Length = `MeanReversionConfig.max_holding_bars` = 20 sessions.** This is
the strategy's own information horizon: the point by which the rule has
closed every position. `embargo_sessions()` reads the config rather than
taking an argument, **so it cannot be lengthened or shortened because of the
result it produces.** A test asserts it tracks the config rather than a
literal.

**Rationale:** conditions the researcher observed up to the freeze persist
into the following sessions. The persistence horizon for a strategy that
holds 14 days on average and 20 at most is 20 sessions.

| | |
|---|---|
| freeze | 2026-09-11 |
| embargo | 20 sessions |
| sessions elapsed since freeze | **2** |
| sessions embargoed so far | 2 |
| **clean evaluation begins** | **NOT YET REACHED — 18 more sessions required** |

---

## 9. CLEAN vs CONTAMINATED SAMPLE SIZES

| bucket | trades |
|---|---|
| pre-freeze (contaminated by selection) | **1,501** |
| straddling the freeze | 0 |
| embargoed | 0 |
| **clean** | **0** |

**There is at present zero uncontaminated evidence about this strategy.**
Two forward sessions exist and both are inside the embargo.

---

## 10. CHANGES FROM THE 3.18% PHASE 1 HEADLINE

| | Phase 1 | Phase 2 | why |
|---|---|---|---|
| 30-yr headline (price basis) | 3.18% | **3.18%** | unchanged — no dividend data exists pre-2016, so nothing moved |
| decade, ex-dividend | — | 5.13% | newly reported on a stated basis |
| decade, with dividends | — | **5.71%** | +0.58 pts from crediting cash the account receives |
| 30-yr gap to SPY | "≈ −4.5 est." | **−5.37 measured** | the estimate is replaced by a measurement on one basis |
| decade gap to SPY | not stated same-basis | **−9.29 measured** | |

No parameter was tuned. No configuration was selected after seeing a result.
The haircut was not revisited. The benchmark basis was fixed before the
comparison was run.

---

## 11. ASSUMPTIONS THAT REMAIN UNRESOLVED

1. **The 0.652% haircut is a conservative BOUND, not a measurement.** The
   live trigger-time distribution is **UNVERIFIED** — three rule exits have
   ever been logged, all pre-instrumentation. True drag lies between the
   0.120% case and this.
2. **Dividends before 2016: UNAVAILABLE.** The thirty-year comparison is
   therefore ex-dividend on both sides. The strategy's true thirty-year
   total return is higher than 3.18% by an unmeasured amount, and so is
   SPY's by roughly 1.7 points.
3. **Dividend extraction recovers 80–85%** of the reinvested gap. Part is
   correctly excluded (no reinvestment); part is payments below the 5e-4
   threshold. The split between those two is **UNVERIFIED**.
4. **Survivorship remains** and is unquantified under the corrected basis —
   the 2.24% ETF-control floor predates P2/P3 and has **not been
   re-measured**.
5. **The backtest is still equity-only.** No sleeve, no reserve.
6. **No partial fills, latency, or market impact** are modelled.
7. **SGOV is an overlay, not an instrument.** Its spread and the cash it
   consumes are not simulated.
8. **The benchmark pays no transaction costs.** Immaterial (<0.01 pts) but
   unmodelled, and it favours SPY.

---

## 12. WHAT IS MEASURED, WHAT IS BOUNDED, WHAT IS NOT EVIDENCE

**MEASURED HISTORICAL PERFORMANCE** (in-sample, contaminated by selection):
30 yrs price-basis 3.18% vs SPY 8.55%; decade total-basis 5.71% vs SPY
15.00%; maxDD −11.0% vs −56.5%; Sharpe 0.17 vs 0.40; Sortino 0.23 vs 0.57;
$10,352 dividend income; 8,453 dividend payments extracted and reconciled.

**METHODOLOGICAL ESTIMATES AND BOUNDS:** the 0.652% haircut (upper bound on
the exit-timing gap, so 3.18% is a lower bound on that axis); the 80–85%
dividend recovery (lower bound on dividend income); survivorship inflation
(direction known, magnitude not re-measured).

**OUT-OF-SAMPLE EVIDENCE: NONE.** Zero clean trades. Two forward sessions,
both embargoed. First clean session in 18 trading days.

**CONCLUSIONS THAT CANNOT YET BE SUPPORTED:** that the strategy is
profitable; that it outperforms the S&P 500 on any basis; that it
outperforms on a risk-adjusted basis (on the corrected basis it now trails
SPY on Sharpe and Sortino as well as return); that its parameters are
correct; that the drawdown advantage will persist out of sample.

**The one thing the corrected measurement does support** is narrow and worth
stating precisely: over 1996–2026, on a consistent ex-dividend basis, this
rule produced a far shallower drawdown than the index — **−11.0% against
−56.5%** — while returning 5.37 points a year less. That is a measured
in-sample fact about a strategy whose parameters were chosen on the same
data, and it is not a prediction.

---

### The question asked

> After correcting the benchmark and removing research contamination, what
> performance remains on data that was not used to construct the strategy?

**Nothing remains, because no such data exists yet.** The purge removes all
1,501 trades; the embargo removes both forward sessions; the clean sample is
empty and will stay empty for 18 more sessions. Phase 2 did not measure
out-of-sample performance — it established, reproducibly, that there is none
to measure, and built the machinery that will recognise it when it arrives.
