# H-0021 — give-back anatomy against an executable peak

*Sealed `563d778a…` at commit `beaefbfd`, before any give-back was computed.
Read-only over the frozen baseline's 698 decade trades. No rule simulated, no
exit altered, no trade excluded, nothing promoted.*

---

## Classification: **A — A MATERIAL, EXECUTABLE GIVE-BACK POPULATION EXISTS**

…and it is **not** where the directive's section 1 expected it. The RSI exit
gives back nothing. The leakage is entirely in the **20-bar time exit**.

Outcome A licenses the **design** of one separately sealed exit candidate,
which must carry **54 prior exit configurations** into its DSR. It authorises
nothing else, and it is not evidence that the leakage is recoverable.

---

## A. The three peaks — rule exits only (459 trades)

The bot decides on closes and transacts at the next open, so `PEAK_NEXTOPEN`
is the only peak against which a give-back is a forgone price.

| peak definition | mean peak | median peak | mean give-back | median give-back | capture (aggregate) | capture (median trade) |
|---|---:|---:|---:|---:|---:|---:|
| HIGH — **NOT EXECUTABLE** | +6.674% | +6.294% | +2.826% | +1.893% | 57.7% | 72.0% |
| CLOSE — observable | +5.934% | +5.518% | +2.086% | +0.806% | 65.5% | 84.2% |
| **NEXTOPEN — executable** | **+5.281%** | **+4.944%** | **+1.433%** | **+0.919%** | **73.6%** | **87.3%** |

**Half the apparent leakage vanishes the moment you require an executable
price.** Give-back falls from +2.826% against the intraday high to +1.433%
against the next open — the intraday high is exactly what EXP-0048 established
is unknowable in advance, and it is reported here only as that bound.

*Capture is computed in aggregate (Σ realised / Σ peak), not as a mean of
per-trade ratios. The mean-of-ratios version is meaningless — a trade whose
peak is 0.01% above entry yields a ratio in the hundreds — and my first pass
printed exactly that artefact before it was corrected.*

**The bot already keeps about three-quarters of the executable peak**, and the
median trade keeps 87% of it.

## B. Where the leakage actually is — by exit reason

| exit reason | trades | mean realised | mean give-back (executable) | one-sided pool |
|---|---:|---:|---:|---:|
| **reverted** (RSI exit) | 221 | **+7.261%** | **−0.618%** | $11,765 |
| **time_exit** (20-bar cap) | 238 | **+0.680%** | **+3.337%** | **$122,444** |
| stop | 239 | −5.629% | +6.723% | $256,108 — *not a choice* |

**The RSI exit has negative give-back.** On average it exits *above* the best
price the bot could have transacted at during the hold. Family A of the
directive — "test whether different RSI exit regions improve realized
returns" — is answered on measurement grounds, not just by EXP-0023's prior
rejection: there is nothing there to recover.

**The time exit realises +0.68% while having passed through an executable
price +3.34% higher.** That single population is 91% of the recoverable pool.

Stops are reported separately and excluded from the pool, per the seal: a stop
fills when hit and the price was not a decision.

## C. Size — and why the headline number is an upper bound

| | |
|---|---|
| one-sided recoverable pool (rule exits) | **$134,209 = 134.2 pts of starting equity** |
| net, two-sided (counting trades that exited above their peak) | **$104,468 = 104.5 pts** |

Both are **hindsight bounds, not gains.** Identifying the peak requires knowing
it in advance. EXP-0048 already measured what happens when you approximate it:
a pullback rule gives back its own threshold by construction, which "eats a
third to a half before anything is captured."

## D. Give-back is largest on the *small* winners, not the fat tail

Rule exits whose executable peak reached at least N × the trade's own risk:

| band | trades | share | mean give-back | mean realised |
|---|---:|---:|---:|---:|
| ≥ 0.5R | 386 | 84.1% | +0.266R | +0.831R |
| ≥ 1.0R | 205 | 44.7% | +0.155R | +1.237R |
| ≥ 2.0R | 11 | 2.4% | **+0.009R** | +2.388R |

**The biggest winners give back essentially nothing.** This matters because the
standing mechanism behind every rejected exit experiment is that the top 50
trades carry 67% of all profit. The leakage is *not* in the fat tail — it is in
the mass of small and flat trades, which is the same population as the time
exit. A rule targeting it would not truncate the winners that carry the book.

## E. Stability and concentration

| third | rule exits | mean give-back | pool |
|---|---:|---:|---:|
| 2016-2019 | 148 | +1.069% | $30,893 |
| 2020-2023 | 177 | +1.916% | $64,755 |
| 2024-2026 | 134 | +1.196% | $38,561 |

**3 of 3 thirds positive.** Regime (existing `trend_dual_ma`, not refitted):
+1.495% favourable / +1.369% neutral / +1.175% unfavourable — spread, not
concentrated in one environment.

Concentration: **top 5 symbols 13.3%** of the pool (AMGN, AAPL, HD, ADI, CVS),
**top 5 trades 6.1%**. This is a broad, repeatable pattern — unlike P3, which
H-0020 killed partly because 5 of 242 trades carried 32% of its profit.

## F. What this does **not** license

1. **It is not a candidate, and it is not evidence of recoverability.** No rule
   was simulated. A trailing mechanism gives back its own width; that cost is
   not in any number above.
2. **The obvious responses are already rejected.** Holding cap: EXP-0019 (3
   cfg) and EXP-0024 (5 cfg), both rejected — "monotone in holding period; the
   edge is overnight." Trailing stops, partial profits, momentum and regime
   exits: EXP-0036 (11 cfg), rejected. A new candidate must be materially
   different from those, not a re-run.
3. **54 prior exit configurations come forward** into any candidate's DSR, plus
   H-0011. The exit family is the most-explored area of this project.
4. **Stage 4 is unavailable.** The clean forward record holds **0 sessions** and
   is frozen until **2026-10-12**. READY FOR CLEAN OOS is the best attainable
   classification for anything in this programme before that date.

## G. Production status

ATR ceiling 0.035 · RSI 35.0 / exit 60 · 20-bar cap · stop 2.5× · sizing,
buckets, cash, guards — **all unchanged**. Fingerprint `da22011e…c237b`
unchanged. Baseline re-verified at **+58.5889000000% / 698**. No learned model.
Clean OOS untouched. No live brokerage action. **Nothing promoted.**
21 registrations, chain intact, thirty-year reads 13.
