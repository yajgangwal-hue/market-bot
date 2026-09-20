# Forensic capability audit — is the architecture too weak for the question being asked?

*2026-09-20. Read-only. No registration, no seal, no economic experiment, no
parameter changed, no production file modified. H-0011 remains frozen at
B — REPRODUCIBLE BUT FRAGILE.*

**The central question, answered first: yes, partially — and the binding
constraint is not information in general, it is temporal resolution, which
shows up first as a measurement problem before it shows up as a decision
problem.**

---

## 1. The current information set at the decision point

Inventoried from `strategy.py`, `mean_reversion.py`, `risk.py`, `portfolio.py`
and the contents of `data/`.

### A — Price/volume

| input | status |
|---|---|
| daily OHLC | **available, used** |
| daily volume, ADV ($50M floor) | **available, used** |
| RSI(14) on closes | **available, used** — the entry and exit trigger |
| Wilder ATR(14) | **available, used** — stop distance and sizing |
| SMA(200) trend filter | **available, used** |
| 21d momentum, 252d drawdown, distance to 200d SMA, trend R², breakout distance, relative volume, ATR fraction | **available, computed, NOT used in production** — these exist only inside the disabled learned model |

### B — Market/context

| input | status |
|---|---|
| SPY | **available, used** as benchmark and as `market_gate_symbol` default |
| market-below-MA flag | **available, not used** (`mr_take_profit_up_r`/`down_r` are None) |
| regime classifier (`regime.py`) | **available, not used** (`mr_regime_exit=False`) |
| TLT / HYG / LQD credit or rates context | **unavailable** — not in the 241-file universe as inputs |
| market breadth | **unavailable** — never computed |

### C — Event/information

| input | status |
|---|---|
| news headlines | **partially available, unusable.** 11,852 archive items, **headline-only, zero content/summary fields**. Classified `A_NO_EVIDENCE`. Forward collection began 2026-09-15 — **6 days of history** |
| SEC Form 4 | **available retrospectively, resolved — see §8** |
| earnings dates / guidance / analyst actions | **unavailable** |
| corporate actions | **unavailable** as a feature |

### D — Intraday

| input | status |
|---|---|
| intraday bars at any frequency | **UNAVAILABLE — zero files on disk** |
| opening behaviour, opening range | **unavailable** |
| volume curve, time-of-day | **unavailable** |
| VWAP | **unavailable** |
| relative volume (intraday) | **unavailable** |
| gap structure | **partially available** — the overnight gap is derivable as `open/prev_close`, and is **not used** |
| intraday volatility | **unavailable** (only the daily H−L proxy) |

### E — Execution

| input | status |
|---|---|
| trigger price | available — always the session close |
| **trigger time** | **UNAVAILABLE.** Daily bars have no intraday clock |
| close price | available, used |
| spread | **assumed, not observed** — flat 2 bps half-spread |
| slippage | **assumed, not observed** — flat 4 bps |
| **fill delay / trigger-to-fill** | **assumed, not observed** — the flat 0.652% haircut |
| order queue position | **unavailable** — and H-0011 showed this is load-bearing |
| liquidity at execution | **unavailable** — only the daily 2% ADV cap |

---

## 2. Capability matrix

Column 2 describes the actual implementation, verified in code.

| Capability | Current bot | Generic day-trading research capability | Missing? | Research value |
|---|---|---|---|---|
| Daily OHLCV | 241 symbols, ~550 bars each, used | table stakes | no | — |
| Intraday bars | **none on disk** | 1-min/5-min standard | **YES** | **highest** |
| Real-time price change | none; one decision per session | continuous | **YES** | high |
| Relative volume | daily ADV ratio only, unused | intraday RVOL vs time-of-day curve | **YES** | medium |
| VWAP | none | session/anchored VWAP | **YES** | medium |
| Opening range | none | ORB 5/15/30 min | **YES** | medium |
| Gap structure | derivable, **unused** | gap %, fill rate, continuation | **partial** | medium |
| Market breadth | none | adv/decl, % above MA, TICK | **YES** | medium |
| Cross-sectional momentum | computed, **only in disabled model** | standard | **partial** | low-medium |
| News | headline-only archive, 6 days forward | timestamped full text | **YES** | low — tested `A` |
| SEC events | Form 4 parsed, **resolved as redundant** | timestamped filings | **partial** | low — see §8 |
| Earnings/events | none | dated calendar | **YES** | medium |
| Insider activity | Form 4, resolved | Form 4 + 13D/G | **partial** | low |
| Catalyst timing | none | event clock | **YES** | medium |
| Volatility regime | classifier exists, **off** | standard | **partial** | low — forensics `B` |
| Liquidity / spread | flat assumption | quoted spread, depth | **YES** | high |
| **Trigger-to-fill measurement** | **flat 0.652% assumption, 0 live exits logged** | measured per fill | **YES** | **highest** |
| Intraday exit timing | none — exits price at the close | continuous | **YES** | high |

---

## 3. Does daily data itself create a structural ceiling? — **Yes, measured**

Three measurements on 582,324 symbol-sessions.

**3A — how much path a daily bar discards**

| | value |
|---|---|
| mean intraday range (H−L)/C | **2.394%** |
| mean net move \|C−O\|/C | **1.189%** |
| **ratio** | **2.01×** |
| mean upper wick above O/C | 0.585% |
| mean lower wick below O/C | 0.620% |

On an average session price traverses **twice** the distance the bar records
as its net move. Everything about the *order* of that traverse is
unrepresentable. **Two sessions with identical O, H, L, C are literally the
same object to this system** whether the high printed at 09:31 or 15:59,
whether volume arrived on the open or the close, whether the gap filled, and
whether a catalyst landed mid-session.

**3B — the exit blind spot**

For the 221 `reverted` exits, the distance from the session high to the close
the bot actually priced at:

| | value |
|---|---|
| mean (High − Close)/Close | **0.526%** |
| median | 0.295% |
| p75 / p90 | 0.655% / 1.226% |
| *for scale: the charged haircut* | *0.652%* |

This is not a claim the bot could have captured it — it had no way to know the
high was in. It is the **size of the blind spot**, and it is the same order of
magnitude as the single largest cost line in the model.

**3C — entry signals invisible to a close-only RSI**

RSI(14) reads closes. A stock that dips and recovers intraday never generates a
signal. Substituting the session low for its close in the final RSI term bounds
how many signals that hides:

| | sessions |
|---|---|
| close RSI ≤ 35 | **41,619** |
| low-substituted RSI ≤ 35 | **60,317** |
| **hidden** | **18,698 — 45% more than the visible set** |

This is a bound, not a tradable count: it assumes the low is knowable, which it
is not at decision time. But it establishes the **information-capacity** point
the section asks for — the close-only rule cannot see roughly a third of the
sessions where its own condition was true at some point in the day.

---

## 4. Candidate-generation audit

Funnel over 582,324 symbol-sessions, 2,684 trading sessions:

| stage | killed | surviving | % of universe |
|---|---|---|---|
| history | 49,220 | 533,104 | 91.5% |
| price | 37,473 | 495,631 | 85.1% |
| liquidity | 7,709 | 487,922 | 83.8% |
| trend_200d | 161,389 | 326,533 | 56.1% |
| **rsi_35** | **320,170** | **6,363** | **1.1%** |
| atr_ceiling | 1,276 | 5,087 | 0.9% |
| stop_positive | 0 | 5,087 | 0.9% |

- **2,177 of 2,684 sessions (81.1%) produce no entry at all.** 1,398 because the
  signal set was empty; **779 because the portfolio blocked it.**
- 5,087 candidates survive; 698 trades were taken over the decade.
- Nearest-miss RSI: median 37.87, p25 36.29, p75 40.42.

**Classification, with evidence:**

| candidate | supported? | evidence |
|---|---|---|
| signal-limited | **partially** | one filter kills 98% of survivors; 52% of sessions have no signal |
| selection-limited | **tested and rejected** | the (35,40] near-miss bands show *higher* forward excess (5d +0.242%/+0.213% vs qualifying +0.143%). H-0009 acted on exactly this and was **rejected** — Spearman −1.0000, only 425/273/201 of 698 baseline trades survived. Widening was tried; it churned |
| capacity-limited | **weakly** | 779 blocked sessions, but the **12-position cap never binds** — max concurrent is 9, zero sessions at ≥11. The binder is the bucket cap (29 buckets, top carries 67 trades) |
| **timing-limited** | **strongly** | MFE capture is **11.25%** — see §5 |
| **execution-limited** | **strongly** | the exit gap is 96% of realised profit — see §5–6 |

---

## 5. Opportunity ceiling — where the money goes

The project's existing decomposition reconciles **exactly** (identity, not a
fit): `realised = buy-and-hold + entry gap + exit gap`.

| term | dollars |
|---|---|
| buy-and-hold the same names over the same windows | **+119,330** |
| entry gap (signal close → actual fill) | **−6,913** |
| **exit gap (rule close → actual fill)** | **−54,858** |
| **realised** | **+57,560** |

Check: +119,330 − 6,913 − 54,858 = **+57,559.93**, exact.

| | value |
|---|---|
| GROSS opportunity — mean MFE per trade | **5.363%** |
| EXECUTABLE — mean realised per trade | **0.603%** |
| **MFE capture** | **11.25%** |
| notional traded | $11,527,911 |
| modelled friction both ways | $13,833 |

By exit reason:

| reason | n | realised | buy&hold | exit gap | mean off-close |
|---|---|---|---|---|---|
| reverted | 221 | +248,916 | +279,403 | **−28,272** | **−0.7116%** |
| stop | 239 | −213,599 | −211,706 | +547 | +0.0450% |
| time_exit | 238 | +22,243 | +51,633 | **−27,133** | **−0.7116%** |

**Keep the three layers separate, as instructed:**
- **Gross opportunity:** 5.363% MFE per trade. The signal does find real
  movement.
- **Executable opportunity:** 0.603% realised. **88.75% of the identified
  excursion is not captured** — because the system has no mechanism to observe
  the excursion while it happens. It can only act at the next close.
- **Assumed-cost opportunity:** −$54,858 of the gap, on 459 rule exits, at
  exactly −0.7116% each.

---

## 6. Execution-model audit — **the largest single line in the P&L is an assumption**

0.652% + 0.06% one-way slippage = **0.712%**. The measured
`mean_exit_off_close` on reverted and time_exit is **−0.7116%**. They match to
four decimals. **The exit gap on rule exits is the modelled charge, not
observed market movement.**

| | value |
|---|---|
| exit gap on rule exits | **−$55,405** |
| exit gap on stops (a real fill, no haircut) | +$547 |
| realised total profit | +$57,560 |
| **assumption as a share of realised profit** | **96%** |

Provenance of the constant, from `portfolio.py:238–251`: measured on **155 real
exits against 5-minute bars**, taking the **worst** of three trigger times
(10:00 ET 0.652%, 12:30 ET 0.289%, 15:00 ET 0.120%) because "overstating risk
was the safer error." The comment states the live trigger-time distribution is
**UNVERIFIED**, with "only three rule exits" ever logged. **The current session
log contains zero.**

Historical intraday execution data: **none on disk.**

**Is better execution measurement merely measurement, or does it unlock a
different decision? Both — and they are separable:**

- **As measurement:** the constant is 96% the size of realised profit. Moving
  it from 0.652% to the 15:00 ET value of 0.120% would change every historical
  result this project has produced. That is not a refinement; it re-prices the
  whole record.
- **As decision:** H-0011 demonstrated it empirically. Changing only *how the
  same exits fill* moved decade return by **+27.76 points** and Sharpe by
  **+0.15** — a larger effect than any signal change in 40 experiments. But
  **78–85% of that gain was the avoided haircut itself**, i.e. the experiment
  was substantially measuring the assumption rather than the market.

**These two are currently inseparable, and that is precisely the defect.**

---

## 7. New-information inventory

Descriptive scoring. **Not ranked by expected profitability.**

| source | historical availability | timestamp quality | survivorship risk | coverage | point-in-time validity | independence from OHLCV | implementation difficulty | supports a clean experiment? |
|---|---|---|---|---|---|---|---|---|
| **Intraday bars (1–5 min)** | good — standard vendor/Alpaca history | **excellent, exchange clock** | low if universe fixed | full for liquid names | **high** — bars are immutable | **partial by construction** (same prices, finer grid) but reveals *path*, which is genuinely new | medium — volume, storage, loaders | **yes — strongest** |
| Quote/spread data | moderate | excellent | low | good for liquid names | high | high | high | yes, but heavy |
| Earnings / event calendar | good | **variable** — announce vs effective dates | **moderate — restatement risk** | good | **needs care** | high | medium | yes, with a point-in-time source |
| Market breadth | derivable from existing OHLCV | inherits daily | none | full | high | **low — built from the same prices** | low | weak — not new information |
| Relative volume / VWAP / opening range | **requires intraday** | inherits intraday | low | — | high | medium | — | only after intraday exists |
| SEC Form 4 | done — 130,069 filings | **excellent** (`acceptanceDateTime`) | low | 161 symbols | high | **measured LOW — see §8** | already built | **no — resolved negative** |
| News | **archive headline-only** | poor | high | 40–53%/yr | **unverified** | unknown | medium | **no — classified `A_NO_EVIDENCE`** |

**Strongest research justification: intraday bars.** Not because they are
likely profitable — that is untested — but because they are the only source
that simultaneously (a) makes the largest P&L line measurable instead of
assumed, (b) has excellent point-in-time timestamps, (c) carries near-zero
survivorship risk on a fixed universe, and (d) is a precondition for testing
*any* of the other intraday capabilities in §2.

---

## 8. Form 4 status — **completed, and the result is negative**

From `docs/phase5/form4-feasibility.json`, not assumption:

| | value |
|---|---|
| filings parsed | **130,069**, 0 unparseable |
| events mapped | 46,847 across **161 symbols** |
| filing lag (days) | median 2.0; 93.4% within 4; 1.1% over 30 |
| time of day | after close 108,120 (83%); intraday 16,668; pre-market 4,042 |
| **usable same session** | **15.92%** |
| usable next session | 84.08% |
| **features separating with Cohen's d ≥ 0.2** | **NONE — empty list** |

Maximum redundancy |d| across all tested features is **0.1866** (distance to
200d SMA); RSI 0.1531, momentum 0.1324, drawdown 0.1369, relative volume
−0.0219, ATR fraction 0.0272. Being an RSI ≤ 35 candidate: **−0.0490**.

**Conclusion: Form 4 presence is not meaningfully distinguishable from what the
price features already encode, and 84% of it is not actionable until the next
session.** It is not the missing capability. No Form 4 strategy is proposed,
and none was backtested.

---

## 9. Architectural bottleneck — **F: multiple, with one shared root**

Materially supported: **B (temporal resolution)** and **E (execution
measurement)**. They are not independent — both are the same absence.

| candidate | verdict | decisive evidence |
|---|---|---|
| A — information | **partially, and the tested parts came back negative** | Form 4 all \|d\| < 0.2; news headline-only `A_NO_EVIDENCE` |
| **B — temporal resolution** | **SUPPORTED** | path 2.01× net move; 45% more RSI-35 sessions hidden intraday; exit blind spot 0.526% vs a 0.652% haircut; **MFE capture 11.25%** |
| C — candidate generation | **tested and rejected** | near-miss bands do show more excess, but H-0009 acted on it and failed on churn |
| D — portfolio selection | **weak** | 12-position cap never binds (max 9); bucket cap is the only real binder |
| **E — execution measurement** | **SUPPORTED, strongest single number** | exit gap = **96% of realised profit**, matches the modelled charge to 4 dp, validated against **0 logged live rule exits**; H-0011 moved return +27.76 pts by changing only this assumption |

**Answer to the central question: we are not primarily starved of *information*
— we are starved of *resolution*, and the first thing that costs us is not
better decisions but the ability to know whether our current decisions are
being measured correctly at all.**

The order matters. Today it is impossible to tell whether any intraday decision
rule works, because the yardstick — the 0.652% haircut — is 96% the size of the
thing being measured and rests on 155 five-minute observations and zero live
exits. **Any intraday strategy built before that is fixed would be graded by an
instrument it also depends on.**

---

## 10. Highest-value next direction — one only

**Acquire historical intraday bars for the research universe, and spend them
FIRST on replacing the execution assumption with a measured trigger-to-fill
distribution — before any decision rule is changed.**

This is chosen because it is the only direction that addresses **E** (the
largest demonstrated limitation) and is simultaneously the precondition for
testing **B**, while remaining fully point-in-time testable.

| requirement | specification |
|---|---|
| **information required** | Intraday OHLCV bars, 5-minute or finer, for the 230-name equity research universe plus SPY, covering the full decade window |
| **historical coverage** | The complete decade already used, on the **same fixed symbol list**, so survivorship is inherited from the existing universe and introduces no new bias |
| **timestamp requirement** | Exchange-clock, timezone-explicit, with regular-hours flagged separately from extended hours. Session boundaries must reconcile to the existing daily bars |
| **minimum data quality** | Each intraday session must aggregate to the daily bar already on disk within a stated tolerance on O, H, L, C and volume. **Symbols failing reconciliation are excluded, not repaired.** Gaps and halts recorded, not interpolated |
| **exact information boundary** | The rule fires on a **completed** intraday bar. Fill measurement may read only bars **strictly after** the trigger bar. No bar may be used before its own close. Trigger time is derived from the bar clock, never from the daily record |
| **what is genuinely new** | **Intra-session ordering.** Same prices, but the sequence — when in the session the trigger occurred, and what the tape did between trigger and fill. §3A shows this is 2.01× the information the daily bar carries, and it is not derivable from OHLCV at any aggregation |
| **what must be audited before any economic test** | (1) reconciliation to daily bars; (2) the realised trigger-time distribution for the 459 historical rule exits, replacing the assumed worst case; (3) the measured trigger-to-fill drift distribution, replacing 0.652%; (4) whether intraday adds any information at all beyond the daily bar — the §8 Form 4 redundancy test, re-run; (5) a queue/fill-probability model, since H-0011 showed the touch-equals-fill assumption carries the result |

**Critically: steps (1)–(4) are a measurement audit, not an economic
experiment, and must complete and be reported before any hypothesis is
registered.** If the measured haircut differs materially from 0.652%, every
historical result in this project changes, including H-0011's — and that
re-pricing must happen before, not after, a new strategy is evaluated against
it.

---

## Future hypothesis sketch — **NOT registered, NOT sealed**

Only if the §10 audit passes:

> **Sketch (H-0012 candidate).** Replacing the assumed 0.652% flat rule-exit
> haircut with the *measured* trigger-to-fill drift distribution, derived from
> intraday bars at the actual trigger times, changes the frozen baseline's
> decade return by a material amount — and the direction and size of that
> change, not any strategy modification, is the finding.
>
> Falsification: the measured distribution is statistically indistinguishable
> from the 0.652% assumption, in which case the assumption is vindicated and
> the execution-measurement bottleneck is closed.
>
> This is a **measurement** hypothesis with no parameter to optimize and no
> promotion path. It changes the yardstick, not the strategy. A decision-rule
> hypothesis using intraday information would be a **separate, later**
> registration that cannot honestly be evaluated until this one resolves.

---

## 11. Research directions explicitly rejected as the next step

| rejected class | why it is lower-value **given evidence already in hand** |
|---|---|
| another RSI threshold sweep | Swept **three times** — twice before H-0009, then H-0009 itself, rejected on churn (Spearman −1.0000). The breadth bands are already measured; the answer is known and negative |
| another stop / target sweep | H-0010 swept three stop widths with a 2.5R target: every configuration breached the 14.2806% ceiling, and clause E showed the gain was 3.06× explained by avoided haircut |
| another ATR floor | H-0010's family covered this; no configuration passed |
| another holding-period sweep | The 2-session cap was measured at −77.52% standalone; the 20-bar cap probe is on file |
| another ranker model | The weekly retrain now reports **OOS AUC 0.4857 on 26,425 examples**, below chance, worse than the 0.542 it showed at 10,647. More data made it worse |
| any parameter optimization on the same daily OHLCV | **This is the core finding.** 40 experiments, 119 configurations, 0 promotion candidates. The information set has been searched hard. §5 says 88.75% of identified opportunity is lost to timing and execution, neither of which any daily-bar parameter can reach |
| another post-hoc regime split | Regime forensics classified **B — dependence runs backwards**; the classifier exists and is off for cause |
| stacking several untested ideas | H-0011 already showed that one mechanism produces −$19,062 of knock-on through the portfolio path. Stacking would make attribution impossible |

---

# REQUIRED FINAL REPORT

**CURRENT CAPABILITY.** One decision per symbol per session, taken at the
close, from daily OHLCV: RSI(14), ATR(14), SMA(200), ADV. It knows SPY as a
benchmark. It has no intraday data of any kind, no trigger clock, no observed
spread, no queue, no usable news, and no event calendar. Form 4 is parsed but
measured as redundant. Regime, breadth-style features and the learned model
exist and are off.

**DEMONSTRATED LIMITATIONS.** (1) The exit gap is **−$54,858 = 96% of realised
profit** and matches the modelled charge to four decimals — the largest line in
the P&L is an assumption validated against **zero logged live rule exits**.
(2) **MFE capture is 11.25%** — the signal finds 5.363% of favourable
excursion per trade and realises 0.603%. (3) Widening candidate generation was
tested (H-0009) and failed on churn. (4) 40 experiments on this information set
have produced 0 promotion candidates.

**INFORMATION LOST.** Price traverses **2.01×** the net daily move, and the
order of that traverse is unrepresentable — identical O/H/L/C are the same
object whether the high printed at 09:31 or 15:59. The close-only RSI cannot
see **45% more** sessions where its own condition held intraday. At the 221
reverted exits the mean high-to-close distance is **0.526%**, the same order as
the entire modelled haircut.

**OPPORTUNITY DECOMPOSITION.** Exact identity: buy-and-hold +$119,330, entry
gap −$6,913, **exit gap −$54,858**, realised +$57,560. Gross 5.363%/trade;
executable 0.603%/trade; assumed cost −0.7116% on each of 459 rule exits.

**BOTTLENECK: F — multiple, specifically B and E, with one shared root.**
Temporal resolution and execution measurement are the same absence. E is the
more urgent because it is currently unfalsifiable: the yardstick is 96% the
size of the measurement.

**HIGHEST-VALUE NEXT DIRECTION.** Acquire decade-length intraday bars for the
existing fixed universe and spend them first on measuring the real
trigger-to-fill distribution — a measurement audit, reported before any
hypothesis is registered.

**FUTURE HYPOTHESIS SKETCH.** As above — a measurement hypothesis about the
haircut, with no parameter to optimize and no promotion path. **Not
registered.**

**GOVERNANCE.**

| check | state |
|---|---|
| H-0011 | **frozen** — spec, parameters and B verdict unchanged |
| production fingerprint | `da22011e…c237b` — **unchanged** |
| `rsi_entry` | **35.0** |
| ranker / veto | **OFF / OFF** |
| clean OOS | **untouched** |
| forward evaluation | frozen to 2026-10-12, untouched |
| new economic registration | **none created** |
| production files modified | **none** |
| promotion candidate | **none created** |
| live brokerage / live trading | **none — no connection attempted** |
| profitability experiment | **none performed** — every number here is read from an existing artifact or a read-only measurement |
| registrations / chain | 11 / intact |
| thirty-year reads | **13** |
