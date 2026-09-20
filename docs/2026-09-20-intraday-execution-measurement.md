# Intraday acquisition and execution measurement — Phases 0–12

*2026-09-20. Read-only market data. No order, no account call, no brokerage
activity. No registration, no seal, no production change, no strategy
backtest. The 0.652% haircut has **not** been changed.*

## GO/NO-GO: **A — INTRADAY DATA SUFFICIENT; EXECUTION MODEL MEASURABLE**

With one bounded exception recorded in Phase 8: **market-order execution is
now measurable; limit-order queue position is not, and cannot be from OHLCV.**

---

## PHASE 0 — audit preserved

Commit **`17cf245f895495cf897c451c86bb4d2cae74b517`** — both audit documents
committed verbatim, conclusions unaltered, plus the `dataset-uses.jsonl` entry.

---

## DATA

| | |
|---|---|
| source | Alpaca `data.alpaca.markets/v2/stocks/bars`, `adjustment=split` (identical to the daily set) |
| interval | **5Min** |
| historical span probed | 2016-01-04 → 2026-09-05 |
| universe | **the existing fixed 230-symbol decade set. No symbol added, none removed, no substitution of today's survivors** |
| provenance | raw vendor payloads in the session scratchpad under `raw/intraday-probe/` and `raw/intraday-exits/`; **only derived summaries written to `docs/phase5/`** |
| timestamp quality | RFC3339, `Z`-suffixed UTC, modal spacing exactly **300s**, **zero duplicates** in every probe |

**Probe (early / middle / recent × 3 high-ADV × 3 low-ADV):** SPY, QQQ, NVDA
($48,065M / $33,235M / $32,401M ADV) and EWU, EWG, DBC ($86M / $80M / $26M).
All 18 symbol-windows returned data in all three periods, including 2016.

**Two acquisition limitations found, both real:**

1. **Extended hours are included by default.** SPY returns **186 bars/session**
   where a regular session is 78. Every apparent reconciliation failure in the
   first pass (up to 2.26% on NVDA 2016) was this and only this.
2. **Symbol identity diverges between endpoints.** The universe spells
   `BRK-B`; the intraday endpoint rejects it with `invalid symbol` and requires
   **`BRK.B`**. `BRKB` returns nothing. Re-acquired under the vendor spelling
   and stored under the universe spelling, with the mapping recorded in the
   payload.

**Environment finding:** `tzdata` is **not installed** — `ZoneInfo("America/
New_York")` raises. For a timestamp-critical dataset that is a genuine hazard,
so the post-2007 US Eastern rule (DST from 2nd Sunday March 02:00 to 1st Sunday
November 02:00) is implemented explicitly in code rather than assumed.

**Scale of a full acquisition**, measured not guessed: 230 symbols × 2,684
sessions × 78 RTH bars = **48,150,960 bars ≈ 2.9 GB, ≥4,815 requests.**
Targeted acquisition of only the sessions needed took **459 requests**.

---

## RECONCILIATION (Phase 6)

RTH filter `09:30 ≤ bar start < 16:00 ET`, 84 session-symbol reconciliations:

| field | mean abs diff | median | max | within 0.01% |
|---|---|---|---|---|
| open | 0.00344% | 0.00000% | 0.1043% | **94.0%** |
| **high** | **0.00003%** | 0.00000% | 0.0024% | **100.0%** |
| **low** | **0.00000%** | 0.00000% | 0.0000% | **100.0%** |
| close | 0.02328% | 0.01088% | 0.1041% | 47.6% |

**RTH bars/session: mean exactly 78.0.** Volume ratio (RTH intraday ÷ daily):
mean 0.891, median 0.902.

**Mismatch classification — zero unexplained:**

| mismatch | classification |
|---|---|
| close, ~2 bp | **expected vendor/session convention.** The daily close is the 16:00 closing-auction print; the last RTH 5-min bar (15:55–16:00) closes on the last continuous trade before it. Two different prices by construction |
| volume ratio 0.891 | **expected convention.** Daily volume includes the closing auction and extended hours; the RTH sum excludes both |
| open, 94% exact | **expected** — opening-auction print vs first continuous bar |
| high / low | **none — they match** |
| pre-fix high diffs up to 2.26% | **resolved:** extended-hours inclusion, not a data defect |

Nothing was silently patched.

---

## 459 EXIT RECONSTRUCTION (Phase 4)

| | |
|---|---|
| rule exits in the frozen baseline | **459** (221 `reverted`, 238 `time_exit`) |
| **reconstructed** | **459 — 100.0% coverage** |
| missing / too few bars / no intraday trigger | **0 / 0 / 0** |

**Trigger definition, kept separate from executability as required:**
- `reverted` — RSI(14) recomputed on each RTH 5-min bar with the *current*
  price standing in for today's close, exactly as the live bot does on its
  15-minute cycle. Prior closes taken **strictly before** the exit session.
  Trigger = first bar reaching `rsi_exit` 60.0.
- `time_exit` — `bars_held ≥ 20` is already true at the bell, so the trigger is
  the first RTH bar.

**Trigger-time distribution:**

| window | n | share | trigger→close mean | median |
|---|---|---|---|---|
| **09:30–10:59** | **398** | **86.7%** | +0.1755% | +0.2382% |
| 11:00–12:59 | 31 | 6.8% | +1.1255% | +0.7497% |
| 13:00–14:59 | 19 | 4.1% | +0.3579% | +0.6536% |
| 15:00–16:00 | 11 | 2.4% | −0.2558% | −0.1264% |

---

## EXECUTION — observed, modelled, assumed (Phases 5, 7, 8)

Sign convention: **A = (close − trigger)/trigger. A > 0 means the close sits
above the trigger, so selling at the trigger yields less, so a simulator
pricing at the close must deduct — A > 0 justifies the haircut.**

*(I mis-stated this sign in an interim printout during the run and corrected it
before drawing any conclusion; the corrected reading is used throughout.)*

### OBSERVED

| measure | n | mean | median | p10 | p90 | sd |
|---|---|---|---|---|---|---|
| **A trigger → session close, all** | 459 | **+0.2368%** | +0.2621% | −1.8415% | +2.1351% | 2.0179% |
| A — `reverted` | 221 | **+0.6113%** | +0.4560% | −1.3759% | +2.1490% | 1.8112% |
| A — `time_exit` | 238 | **−0.1109%** | +0.0967% | −2.3997% | +2.0023% | 2.1344% |
| **B trigger → next bar open** | 459 | **−0.0013%** | +0.0000% | −0.0544% | +0.0476% | **0.0688%** |
| C trigger → next bar **low** (conservative) | 459 | −0.1870% | −0.1222% | −0.4325% | −0.0026% | 0.2601% |
| max adverse after trigger | 459 | −1.1582% | −0.6882% | −2.7370% | −0.1390% | 1.4126% |
| max favourable after trigger | 459 | +1.4546% | +1.0259% | +0.2798% | +3.1080% | 1.4891% |

### The central finding: the haircut welds two unrelated things together

1. **Execution drift — trigger to the next realistically tradable print — is
   essentially zero.** Mean **−0.0013%**, median exactly 0, sd 0.0688%. Acting
   on a trigger costs approximately nothing.
2. **The 0.652% is not execution slippage at all. It is the price difference
   between acting at the trigger and waiting for the close** — a *policy*
   difference about when you act, not a cost of acting.

### Is 0.652% supported? — **split verdict, and it was not knowable before**

| bucket | n | measured | charged | verdict |
|---|---|---|---|---|
| **`reverted`** | 221 | **+0.6113%** | 0.652% | **approximately supported** — charged is 106.7% of measured, conservative by 6.7% |
| **`time_exit`** | 238 | **−0.1109%** | 0.652% | **materially too high** — the measured mean has the *opposite sign* |

Dollar implication **if** the measured means replaced the constant — **this has
NOT been applied; the haircut is unchanged**:

| bucket | notional | charged | measured | difference |
|---|---|---|---|---|
| `reverted` | $3,944,675 | $25,719 | $24,113 | **−$1,606** |
| `time_exit` | $3,785,753 | $24,683 | −$4,197 | **−$28,880** |

**The `time_exit` over-charge alone is ~$28,880 against a realised decade
profit of $57,560.** The `reverted` charge is very nearly right.

**An unexpected vindication:** the constant was taken from the 10:00 ET
measurement and chosen as the *worst* of three "because overstating risk was
the safer error." It turns out **86.7% of triggers actually land between 09:30
and 10:59.** Conservative by intent, representative by accident — for
`reverted`. It was simply never true for `time_exit`, which fires at the bell
by construction and was charged a 10:00-ET number.

### MODELLED

A research-only execution model can now be stated with each step separated:
**(A) signal trigger** — first RTH bar meeting the condition, observed;
**(B) order submission** — the following bar, observed;
**(C) queue/latency** — see below; **(D) executable price** — next bar open
(observed, drift ≈ 0) or next bar low (conservative, −0.187%);
**(E) position update** — the emulator records that fill. None of
`trigger = fill`, `next bar = fill`, `close = fill`, or `worst price = fill` is
assumed; each is a stated, separately measured option.

### ASSUMED — and the limit of what this data can support (Phase 8)

**OHLCV cannot reconstruct an order queue, and I will not pretend otherwise.**
What can be defensibly modelled from 5-minute bars: bar range, traded volume in
the fill window, participation against ADV, and a high-low proxy for
within-bar dispersion. What cannot: queue position, depth, quoted spread, or
fill probability for a resting order.

**This bounds what is now answerable and what is not:**

- **Market-order exits (all 459 rule exits): fully measurable.** A market order
  crosses the spread and fills; queue position is irrelevant. Drift is measured
  at −0.0013% ± 0.0688%.
- **Limit-order exits (H-0011): still not measurable.** H-0011's touch-equals-
  fill assumption carried its whole result, and 5-minute OHLCV cannot resolve
  it. **The H-0011 fragility finding stands unchanged and is not improved by
  this acquisition.** Resolving it needs quote or order-book data, not finer
  bars.

---

## INFORMATION GAIN (Phase 9)

Asked as the phase requires — can the daily bar reconstruct the intraday fact?
**No future returns used.** Target: minutes from the open at which the rule
first fired (n = 459).

| daily-bar feature | correlation | \|r\| |
|---|---|---|
| daily return (C/O−1) | +0.4203 | 0.4203 |
| close position in range | +0.4114 | 0.4114 |
| daily range (H−L)/C | +0.1976 | 0.1976 |
| overnight gap | −0.0458 | 0.0458 |
| volume vs 20d mean | +0.0279 | 0.0279 |

**Strongest daily predictor explains R² = 17.7% of trigger timing.** Over 82%
of *when* the rule fired is information the daily representation does not
carry. Trigger timing is a genuinely new dimension, not a re-encoding — which
is exactly the claim the capability audit made from the 2.01× path ratio, now
confirmed on a specific, decision-relevant variable.

---

## MFE / TIMING (Phase 10) — decomposition only

| layer | value |
|---|---|
| daily mean MFE per trade | 5.363% |
| daily mean realised per trade | 0.603% |
| **daily capture** | **11.25%** |
| intraday favourable still available *after* the trigger | **+1.4546%** |
| intraday adverse still to come after the trigger | −1.1582% |
| actually realised, trigger → close | +0.2368% |
| **capture of the post-trigger excursion** | **16.3%** |

So of the 88.75% of excursion the daily system does not capture, a measurable
slice — **1.455% per exit session** — was still on the table at the moment the
rule fired, and 16.3% of it was realised by holding to the close. The remainder
is split between genuinely unobservable path and the −1.1582% adverse
excursion that a close-only exit also absorbs.

**No exit rule was changed, tested, or proposed.**

---

## BOTTLENECK — updated

**E (execution measurement) is substantially resolved for market orders and
now has a number instead of an assumption.** Execution drift is −0.0013% ±
0.0688%; the `reverted` haircut is approximately right; the `time_exit`
haircut is materially wrong by ~$28,880.

**B (temporal resolution) is confirmed and stands.** The daily bar explains
only 17.7% of trigger timing.

**A new, narrower bottleneck is now the binding one for H-0011's direction:
quote/order-book data.** Limit-fill probability is not derivable from 5-minute
OHLCV, so the single largest open question from H-0011 remains unanswerable
with what has been acquired.

---

## FUTURE HYPOTHESIS — one candidate, **NOT registered, NOT sealed**

> **H-0012 candidate (measurement).** Replacing the flat 0.652% rule-exit
> haircut with the *measured* per-exit-reason trigger-to-close drift —
> +0.6113% for `reverted`, −0.1109% for `time_exit`, both from the 100%-covered
> 459-exit reconstruction — changes the frozen baseline's decade return, and
> the size and direction of that change is the finding.
>
> Falsification: the re-priced baseline is statistically indistinguishable from
> +58.5889%, in which case the flat constant is vindicated in aggregate and the
> execution-measurement bottleneck closes.
>
> It has **no parameter to optimize**, changes **no trading decision**, and has
> **no promotion path** — it re-prices the yardstick, not the strategy. Every
> prior result, H-0011 included, would need restating against it.

**What must still be audited before it is registered:** whether per-reason
means or the full measured distributions should be used; whether drift is
stable across the three chronological thirds; and whether re-pricing changes
the *ranking* of any past experiment or merely its level.

---

## GOVERNANCE

| check | state |
|---|---|
| H-0011 | **frozen** — not altered, not re-run under a new execution model |
| production fingerprint | `da22011e…c237b` — **unchanged** |
| `rsi_entry` | **35.0** |
| ranker / veto | **OFF / OFF** |
| clean OOS | **untouched** |
| forward evaluation | frozen to 2026-10-12, untouched |
| economic registration | **none created** |
| production files modified | **none** — all new code is in `scripts/` |
| promotion candidate | **none** |
| live trading / brokerage | **none.** Historical market-data reads only; no order, no account endpoint |
| new strategy backtest | **none performed** |
| **0.652% haircut** | **UNCHANGED — measured, not recalibrated** |
| data provenance | recorded: source, endpoint, adjustment, acquisition time, vendor-vs-universe symbol mapping |
| raw vs derived separation | **raw payloads in the scratchpad only; `docs/phase5/` holds derived summaries** |
| credentials | read by environment-variable name only; never printed, logged or persisted |
| registrations / chain | 11 / intact |
| thirty-year reads | **13** |

## Artefacts

- `scripts/intraday_probe.py` → `docs/phase5/intraday-probe.json`
- `docs/phase5/intraday-reconciliation.json`
- `scripts/intraday_exits_acquire.py` (459 sessions, raw store in scratchpad)
- `scripts/intraday_exit_measure.py` → `docs/phase5/intraday-exit-measurement.json`
