# H-0025 — gain-to-loss forensics under the canonical execution boundary

*Sealed `165fccd4…` at commit `bbd1885c`, **before** any give-back or
gain-to-loss number was computed. Read-only over the frozen baseline's 698
decade trades. No rule simulated, no exit altered, no trade excluded, no band
nominated as best, nothing promoted.*

---

## Verdict — §9

**Evidence is weak / inconclusive.** The owner's question is a conjunction, and
it splits:

| clause | answer |
|---|---|
| Does a meaningful class of trades transition from a significant, **executable** unrealised gain into a realised loss? | **YES — established, and genuinely new.** 87 trades crossed +2% executable and realised a loss, −$57,208, 21.0% of crossings, 23.3% of the book's total losses, present in all three chronological thirds. H-0021 never measured this population. |
| Does that transition contain a repeatable information pattern actionable **without sacrificing larger winners**? | **NO — not supported.** 81.2% of +2% crossers go on to a *higher* executable gain. Every crossing-time feature that is stable across thirds has a **positive** IC with the realised return: strength predicts strength. No feature says "this winner is about to fail" without also saying "sell the winners." |

The conjunction fails on the second clause, so the answer is not "evidence
exists." And on the give-back axis specifically the answer is **D — already
answered by H-0021**: correcting the execution boundary moved the number by
0.044 percentage points.

**My own registered rationale was wrong, and this is the headline correction.**
H-0025 was sealed on the argument that H-0021 had used the wrong execution
boundary and had therefore *understated* the give-back. The boundary claim is
correct — H-0021's `execution_assumptions` say next-open fills are "exactly
what the frozen entry mechanism already assumes," and they are not;
`research.PRODUCTION_CANDIDATE` fixes `entry_fill="signal_close"` and
`portfolio.py:653` books rule exits at `bar.close × (1 − 0.00652)`. But the
*consequence* I predicted did not occur. The 0.652% haircut almost exactly
cancels the close-versus-open gap, and the corrected number is **smaller**, not
larger. H-0021's conclusion survives its own broken premise.

---

## A. Data availability

| quantity the directive asks for | reconstructable? | from what |
|---|---|---|
| entry timestamp and executable entry price | **yes** | `ClosedTrade.entry_time` / `.entry_price` |
| every observed position state after entry | **yes, at daily resolution** | daily bars, entry session → exit session |
| unrealised P&L through time | **yes** | `close(t)×(1−h)/entry − 1` per bar |
| maximum unrealised gain | **yes, three boundaries** | see §B |
| maximum adverse excursion | **yes** | `min(low)` — executable downward, see §B |
| highest *executable* exit price after entry | **yes** | `max close(t)×(1−h)` over the decision set |
| actual exit timestamp and price | **yes** | `ClosedTrade.exit_time` / `.exit_price` |
| realised P&L | **yes** | `.net_pnl`, `.r_multiple` |
| time spent profitable | **yes** | per-bar marks |
| max gain before return to breakeven | **yes** | per-bar marks |
| max gain before eventual loss | **yes** | per-bar marks |
| gain retained at exit | **yes** | realised ÷ executable peak |

**All 698 trades reconstructed, 0 skipped.** Baseline re-verified at
**+58.5889000000% / 698** before anything was computed.

**What cannot be reconstructed, and was not invented:** intraday path. Daily
bars give open/high/low/close/volume and nothing between. The *order* in which
the high and the low occurred within a session is unknowable, so no
intraday-sequence claim appears anywhere in this report.

**The live record cannot support this analysis, on two independent grounds.**
`data/autotrade-audit.jsonl` holds 2,294 rows and — structurally — exactly the
right shape: 1,060 `hold` rows each carrying `symbol`, `last` and `unrealized`,
which is a per-observation position state. But it contains **22 entries and 3
exits**, which is not a population; and it is the **embargoed forward period**,
which research code is type-refused from reading (`reject_forward_data`). It is
reported here as a capability that will exist later, and was used as evidence
for nothing.

---

## B. Methodology — definitions fixed before calculation

**The decision set.** A position filled at the close of bar `i0` has its exit
first evaluated at bar `i0+1` — `portfolio.py:415` increments `bars_held` at the
top of the bar loop, and `signal_close` entries fill *after* exit management.
So every statistic below runs over bars `[i0+1, i1]`. The entry bar is excluded
because its close *is* the fill and cannot also be an exit.

**Maximum Unrealized Gain** — `max over t in [i0+1, i1] of x(t)`, where `x(t)`
is defined per boundary below. Uses only information available at each bar's own
close.

**Maximum Giveback** — `peak_after(t*) − realised`, where `peak_after` is the
running executable peak observed at or after the threshold crossing `t*`. A
negative value means the trade exited *above* every mark it showed.

**Gain Retention** — `realised ÷ peak_after`, computed only where
`peak_after > 0`. Aggregated as `Σrealised ÷ Σpeak`, never as a mean of
per-trade ratios — that artefact produced a meaningless 98.8% in an earlier
pass of H-0021 and is not repeated.

**Gain-to-Loss Transition** — crossed the band, and `realised ≤ 0`. Both
conditions on the same trade, forward-looking from `t*`.

### The four price boundaries, never merged

| boundary | price | class |
|---|---|---|
| `high(t)` | intraday high | **HINDSIGHT ONLY** — never counted as an opportunity |
| `close(t)` | raw close | MODEL-AVAILABLE — observable, but the frozen strategy does not get it |
| `open(t+1)` | next open | MODEL-AVAILABLE — H-0021's headline |
| **`close(t) × (1 − 0.652%)`** | close less haircut | **EXECUTABLE — canonical SPEC-0001 C-1** |

**The adverse side is asymmetric and this is stated wherever MAE appears.**
`low(t)` *is* executable downward, because the protective stop is a resting
broker order that fills when touched. The upside has no resting order, so
`high(t)` is not executable. Give-back and MAE are therefore not symmetric
measurements and are never differenced against each other.

---

## C. Give-back by predeclared executable gain band

Conditioned on the **first** bar whose executable unrealised return crossed the
band; every column looks **forward only** from that bar.

| band | n | % profitable | % losing | med give-back | p75 | p90 | p95 | med final | med bars to exit | continued higher |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| +0.5% | 513 | 69.4% | 30.6% | **+0.44%** | +4.35% | +8.35% | +10.03% | +2.92% | 13.0 | 86.0% |
| +1% | 481 | 72.8% | 27.2% | **+0.14%** | +4.10% | +8.48% | +10.50% | +3.38% | 11.0 | 83.6% |
| +2% | 414 | 79.0% | 21.0% | **+0.07%** | +3.10% | +8.39% | +10.76% | +4.21% | 9.0 | 81.2% |
| +3% | 343 | 84.5% | 15.5% | **+0.07%** | +2.25% | +7.33% | +10.81% | +5.11% | 7.0 | 77.8% |
| +5% | 229 | 89.5% | 10.5% | **+0.07%** | +0.85% | +5.87% | +10.80% | +6.87% | 4.0 | 63.3% |
| +10% | 39 | **100.0%** | **0.0%** | +0.07% | +0.07% | +0.07% | +0.11% | +11.76% | 0.0 | 23.1% |

Worst subsequent executable mark after any crossing: **−15.54%**. Worst realised
outcome after any crossing: **−10.88%**.

**Three things this table says, none of them the owner's hypothesis:**

1. **The median trade gives back nothing.** +0.07% is the haircut itself — the
   median crosser exits *at* its executable peak. The give-back is entirely a
   tail phenomenon: median +0.07%, p90 +8.39%.
2. **Every band is a bad place to sell.** 81.2% of +2% crossers go on to a
   higher executable gain, and the median crosser's final return (+4.21%) is
   more than double the band. This is EXP-0049/0050's monotone take-profit
   result re-derived from the opposite direction — and, unlike those, without
   simulating anything.
3. **The big winners are clean.** At +10%: zero losses, median 0 bars from
   crossing to exit — the RSI exit fires the same session. This confirms
   H-0021 §D on an independent construction.

---

## D. Gain-to-loss analysis

| band | A normal | B excessive | C gain-to-loss | C dollars | C med return | C med bars | C % stop |
|---|---:|---:|---:|---:|---:|---:|---:|
| +0.5% | 313 | 43 | 157 | −$104,675 | −4.34% | 13.0 | 54.8% |
| +1% | 308 | 42 | 131 | −$86,605 | −4.65% | 13.0 | 55.0% |
| +2% | 293 | 34 | **87** | **−$57,208** | −4.75% | 13.0 | 49.4% |
| +3% | 267 | 23 | 53 | −$32,253 | −3.87% | 12.0 | 41.5% |
| +5% | 193 | 12 | 24 | −$16,175 | −5.50% | 9.5 | 50.0% |
| +10% | 39 | 0 | **0** | $0 | — | — | — |

*A = profitable, kept ≥50% of the executable peak. B = profitable, kept <50%.
C = realised a loss. The 50% cut is a **reporting convention declared in the
seal**, not a tuned parameter; the band table above gives the full retention
distribution so it can be re-cut.*

**Economic scale.** The book's gross loss across all 341 losing trades is
−$245,637 against +$303,197 of gross winner profit, netting +$57,560. The +2%
gain-to-loss pool of −$57,208 is therefore **23.3% of all losses** — material,
and not previously measured.

**Composition at +2%, by exit reason:**

| exit reason | crossings | % realising a loss | med give-back | med realised |
|---|---:|---:|---:|---:|
| `reverted` (RSI) | 213 | **0.0%** | +0.06% | +6.93% |
| `time_exit` (20-bar) | 158 | 27.8% | +2.25% | +1.92% |
| `stop` | 43 | 100.0% *(by construction)* | +10.50% | −6.70% |

**The RSI exit has a zero percent gain-to-loss rate.** Not one of its 213
crossings of +2% ended in a loss. The transition lives in the other two
populations, and about half of it is the stop.

**Stability.** Gain-to-loss share by chronological third at +2%: **14.3% /
23.2% / 24.4%** (n = 119 / 168 / 127). Positive in 3 of 3, so the population is
not an artefact of one regime — but it is **rising, not stable**, and that is
the one result in this report that does not settle. It is flagged in §I as a
monitoring item.

**Concentration** at +2%: top 5 symbols 18.2% of the loss pool (COST, BSX, NKE,
QQQM, ADI), top 5 trades 11.8%. Broad, not carried by a handful of names.

---

## E. Predictive-feature analysis

Spearman rank IC of each **fixed** crossing-time feature against the realised
return, computed from information at or before `t*` only, **day-collapsed** to
one observation per calendar day so clustered positions cannot vote repeatedly
for the same market move. **No model was fitted. No feature was added, dropped
or transformed after results were seen.**

| feature | IC +1% | IC +2% | IC +3% | thirds agreeing (at +2%) |
|---|---:|---:|---:|---|
| executable return at `t*` | +0.181 | +0.163 | +0.247 | 3/3 |
| **ATR(14)/close at `t*`** | **+0.128** | **+0.199** | **+0.266** | **3/3** |
| SPY-relative return, entry→`t*` | +0.162 | +0.166 | +0.229 | 3/3 |
| close/SMA200 at `t*` | +0.131 | +0.149 | +0.166 | 3/3 |
| volume ratio vs prior 20 bars | +0.081 | +0.106 | +0.076 | 3/3 |
| `bars_held` at `t*` | −0.029 | −0.094 | −0.163 | 2/3 |
| RSI(14) at `t*` | +0.053 | −0.018 | −0.067 | 2/3 |
| SPY RSI(14) at `t*` | −0.044 | −0.037 | −0.097 | 2/3 |
| drawdown from running peak at `t*` | **degenerate** | **degenerate** | **degenerate** | — |

**Every stable feature has the wrong sign for a protective exit.**

- **ATR/price is the decisive one.** It is the natural input to a
  volatility-based exit, it is the most stable feature in the table (3/3 at all
  three bands, IC rising to +0.266), and it points **positive**: *higher*
  volatility at the crossing predicts a *better* outcome. A volatility-triggered
  protective exit would be backwards.
- **SPY-relative strength, distance above SMA200, and the size of the gain
  itself** all point the same way: the trades that look strong at the crossing
  are the trades that finish strong. There is no feature whose sign isolates the
  deteriorating 21% without also selling the 79% that continue higher.
- **RSI — the strategy's own exit input — carries no information at the
  crossing moment.** IC ≈ 0 and unstable (2/3). Consistent with H-0021's
  finding that the RSI exit has negative give-back: it is already positioned
  correctly.
- **`bars_held` is the only feature pointing the "right" way** (older positions
  at the crossing do worse) and it is **2/3 unstable**, with the whole effect
  in the 2024-2026 third (−0.425 at +3%, against +0.025 in 2020-2023). This is
  H-0021's time-exit finding again, not new information.

**Interpretive caveat, stated rather than buried:** "executable return at `t*`"
is close to tautological — a trade already up more tends to finish up more —
and it is reported for completeness, not as a signal. Its positive sign is
nonetheless informative in one direction: it is further evidence that a fixed
gain band is the wrong place to act.

**`drawdown from running peak at t*` is degenerate by construction**, not
dropped after inspection: `t*` is the *first* bar to reach the band, so every
earlier bar was below it and the running peak at `t*` is `x(t*)` itself. The
value is identically zero for every observation. This was provable a priori and
is reported rather than silently removed.

---

## F. What this adds beyond H-0021 — and what it does not

### What it does **not** add

**The boundary correction is null.** Same 459 rule-exit trades, four boundaries:

| boundary | mean peak | mean give-back | capture (aggregate) | capture (median) |
|---|---:|---:|---:|---:|
| HIGH — **HINDSIGHT ONLY** | +6.621% | +2.773% | 58.1% | 67.7% |
| CLOSE — model-available | +5.928% | +2.080% | 64.9% | 79.5% |
| NEXT OPEN — H-0021's headline | +5.281% | +1.433% | 72.9% | 82.7% |
| **CLOSE−h — EXECUTABLE, canonical** | **+5.238%** | **+1.389%** | **73.5%** | **97.9%** |

My reconstruction reproduces H-0021's next-open figures **exactly** (+5.281%
peak, +1.433% give-back) — an independent confirmation of that work. The small
deltas on HIGH and CLOSE (0.053 and 0.006 pp) are explained: H-0021 scanned
`bars[i0:i1+1]`, including the entry bar, whose high and close cannot be exits.

Correcting to the canonical boundary moves the give-back from **+1.433% to
+1.389%** and raises aggregate capture from 72.9% to **73.5%**. The haircut
offsets the close-versus-open gap almost exactly. **H-0021's conclusion stands,
and the premise I sealed H-0025 on was wrong.** The one thing the correction
does change is the *median*: 82.7% → **97.9%**, i.e. the median trade keeps
essentially all of its executable peak, which makes H-0021's case *stronger*
than H-0021 stated it.

### What it genuinely adds

1. **The gain-to-loss population, measured for the first time.** H-0021's seal
   excluded all 239 stop exits — "a stop fills when hit and the price was not a
   choice." That is right about the *price* and silent about the *position*:
   remaining in a trade at an observed executable +2% is a decision the frozen
   rule took at that close. 87 trades, −$57,208, 23.3% of all book losses,
   about half of it stops.
2. **Crossing-conditioned rather than peak-conditioned statistics.** H-0021's R
   bands select trades whose *peak* reached N×R — a retrospective filter.
   Conditioning on the first crossing and looking only forward is a different
   population and the only one that corresponds to a decision the bot could
   have taken.
3. **The first crossing-time feature scan on this strategy**, with the ATR sign
   as its substantive result.
4. **A documented defect in H-0021's stated execution assumption**, now
   corrected on the record — with the finding that correcting it changes
   nothing material.

---

## G. Hindsight vs executable — explicit classification

| claimed opportunity | class | used as evidence? |
|---|---|---|
| `close(t) × (1 − 0.652%)` at any held bar | **EXECUTABLE** | **yes — every headline figure** |
| `low(t)` reaching the protective stop | **EXECUTABLE** (resting order) | yes, for MAE only, asymmetry stated |
| `open(t+1)` after an observed close | MODEL-AVAILABLE | comparison only (§F) |
| raw `close(t)` without the haircut | MODEL-AVAILABLE | comparison only (§F) |
| `high(t)` intraday high | **HINDSIGHT ONLY** | **no — bound only, never an opportunity** |
| any intraday path or sequence | **HINDSIGHT ONLY / unrecorded** | **no — not reconstructed, not claimed** |

No figure in §C, §D or §E uses a hindsight price. The peak used throughout is a
price the frozen strategy could have transacted at, under its own execution
model, on a bar it could observe.

---

## H. Research conclusion

**Weak / inconclusive — with one clause established and one refuted.**

The gain-to-loss transition is **real, material and newly measured**: 87 trades,
−$57,208, 23.3% of the book's losses, present in all three thirds, not
concentrated in a few symbols. The owner's instinct that something is happening
there is correct, and H-0021 did not measure it.

But the transition is **not separable at decision time from the winners it
shares a population with**. 81.2% of +2% crossers continue to a higher
executable gain. Every crossing-time feature stable across thirds has a positive
IC with the outcome, including — decisively — the ATR fraction that a
volatility exit would key on. The RSI has no information at that moment. The
only feature pointing toward deterioration is `bars_held`, it is 2/3 unstable,
and it restates H-0021's time-exit finding rather than adding to it.

On the give-back axis specifically, the answer is **already answered by
H-0021**, and the boundary correction that motivated this hypothesis made its
case stronger rather than weaker.

---

## I. Future research candidate

**None is justified. No proposal is made.**

Producing one would require re-opening ground this programme has already
closed. The mechanism the §D composition points at — a stop that never moves
after entry, so a trade that showed +2% and reversed runs the full 2.5×ATR from
its *entry* — is a trailing or breakeven stop. That is `mr_trail`, rejected in
EXP-0036, and it is explicitly forbidden by §1 of this directive. The feature
that looked most promising, ATR fraction, has the wrong sign and belongs to the
ATR-ceiling lead that H-0020 already closed. The remaining 54 exit
configurations across 12 registered exit experiments bound the rest.

**Two things are recorded for the future without proposing any rule:**

1. **The rising gain-to-loss share (14.3% → 23.2% → 24.4% across thirds) is the
   one unsettled result here.** It is a monitoring item for the Clean OOS
   period, not a hypothesis. If the forward record shows it continuing to rise,
   that is a *different* question — about regime drift in the entry population,
   not about exit timing — and would need its own registration.
2. **The live telemetry already records what this analysis needed.** `hold` rows
   carry per-observation `unrealized` and `last`. Once Clean OOS accumulates
   sessions, this exact forensic pass runs on live data with no new
   instrumentation. No code change is required or proposed to enable that.

---

## J. Governance confirmation

| | |
|---|---|
| Frozen strategy | **unchanged** — no entry rule, RSI threshold, ATR, stop distance, time exit, sizing, portfolio limit, cash/risk limit, liquidity rule or execution timing touched |
| Exits added | **none** — no take-profit, trailing stop, profit lock, dynamic stop, volatility exit, momentum exit, new RSI exit or give-back exit |
| Emulator, SPEC-0001, benchmark, news, regime, ML/ranker, crypto | **unchanged** |
| Fingerprint | **`da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b`** — unchanged |
| Baseline | **+58.5889000000% / 698** — re-verified before computation |
| Clean OOS | **0 sessions**, embargo 7 of 20 elapsed, opens **2026-10-12** — untouched, not read |
| Thirty-year dataset | **13 reads** — unchanged, not accessed |
| Registrations | 24, chain **intact**, 64 declared trials — H-0025 added as a formally required audit artefact, sealed before results |
| New exit candidate in production | **none** |
| Current open trades used to justify anything | **none** — the live record was examined for *capability* only and used as evidence for nothing |
| Live brokerage action | **none** |
| Promoted | **nothing** |

Files added: [`scripts/register_h0025.py`](scripts/register_h0025.py),
[`scripts/run_h0025.py`](scripts/run_h0025.py),
[`docs/phase5/h0025-gain-to-loss.json`](docs/phase5/h0025-gain-to-loss.json),
this report. No file under `src/` was modified.
