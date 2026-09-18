# Entry-signal breadth — read-only forensic pass

*2026-09-17. **FORENSIC_NON_PROMOTIONAL.** No experiment registered. No
threshold moved. No file in `src/` touched. No promotion candidate.*

## Classification: **B — INCONCLUSIVE**, and the closest any pass has come to C

There is a real, non-monotone **hump at RSI 35–40**: those names carry
*higher* excess return than both the names the strategy already buys
(RSI ≤ 35) and everything above 40. It survives a chronological split
in absolute terms. It does **not** survive the paired test — "are they
better than what we already take?" — once day-level clustering is
handled honestly. Every paired confidence interval includes zero, and
the sign flips in the middle third at two of three horizons.

**A correction to the brief's framing first:** `conviction()` is *not* a
qualification threshold. It is a sizing multiplier in [0.5, 1.5] driven
by drawdown from the 20-day high, applied *after* a name qualifies.
There is no conviction gate to sit below. The qualification boundary is
`rsi_entry = 35.0`, so "just below threshold" means **RSI just above
35**, and that is what everything here measures.

---

## 1. Opportunity funnel

582,324 symbol-sessions, `evaluate` called on every one with the
production 400-bar window. Stages in the exact order the code tests
them.

| stage | killed here | of total | surviving | survive % |
|---|---|---|---|---|
| history (<215 bars) | 49,220 | 8.45% | 533,104 | 91.55% |
| price (< $20) | 37,473 | 6.44% | 495,631 | 85.11% |
| liquidity (< $50M ADV) | 7,709 | 1.32% | 487,922 | 83.79% |
| **trend (≤ 200-day SMA)** | **161,389** | **27.71%** | 326,533 | 56.07% |
| **RSI > 35** | **320,170** | **54.98%** | **6,363** | **1.09%** |
| ATR > 3.5% | 1,276 | 0.22% | 5,087 | 0.87% |
| stop ≤ 0 | 0 | 0.00% | 5,087 | 0.87% |

**Final candidates: 5,087 — 0.874% of symbol-sessions. Entries taken:
698.**

Per session: mean 1.90 candidates, **median 0**, and 1,398 sessions
(52.1%) with zero.

**The RSI gate is the funnel.** It removes 55% of everything — more than
every other filter combined, and 25× more than the ATR ceiling.

### Where the portfolio, not the signal, was the constraint

| | sessions | share |
|---|---|---|
| at least one entry | 507 | 18.9% |
| **no entry** | **2,177** | **81.1%** |
| …signal produced nothing | 1,398 | **52.1%** |
| …**candidates existed, portfolio rules blocked them all** | **779** | **29.0%** |

On those 779 sessions the mean candidate count was 3.54 and the maximum
was **49**. So the earlier "half of sessions have nothing to buy" is
right, but it is only 52% of the story — on another 29% of sessions the
signal *did* fire and portfolio construction refused every name. (The
prior bucket pass established that those refusals are sound: blocked
candidates are ~78% duplicates of what was held and beat their occupant
only 29.5% of the time.)

## 2. No-trade candidate distribution

On the 1,398 signal-empty sessions, the **nearest miss** — the lowest
RSI among names that passed price, liquidity, trend and ATR and failed
*only* RSI ≤ 35:

| | |
|---|---|
| sessions with any near miss | 1,184 of 1,398 (84.7%) |
| nearest-miss RSI | mean 38.84, median 37.87 |
| p5 / p25 / p75 / p95 | 35.23 / 36.29 / 40.42 / 45.52 |

| nearest miss within… | sessions | share of signal-empty |
|---|---|---|
| RSI 36.0 | 222 | 15.9% |
| RSI 37.5 | 530 | 37.9% |
| RSI 40.0 | 849 | **60.7%** |
| RSI 45.0 | 1,108 | 79.3% |

So structurally, **yes**: on most "empty" sessions a name is sitting
just outside the gate. Whether that matters depends entirely on section
3.

Band populations (all passing every filter except possibly RSI):

| band | observations |
|---|---|
| ≤35 **(qualifies)** | 5,072 |
| (35, 37.5] | 5,408 |
| (37.5, 40] | 7,807 |
| (40, 45] | 26,306 |
| (45, 50] | 40,125 |
| (50, 60] | 107,674 |

## 3. Forward outcome of missed candidates

Bands and horizons were declared in the script docstring before any
outcome was examined.

**Excess vs SPY, naive (every symbol-session as one observation):**

| band | 5 sessions | 10 sessions | 20 sessions | win @10 |
|---|---|---|---|---|
| ≤35 **(qualifies)** | +0.143% | **+0.095%** | +0.186% | 50.1% |
| **(35, 37.5]** | +0.242% | **+0.422%** | +0.663% | 51.3% |
| **(37.5, 40]** | +0.213% | **+0.406%** | +0.732% | 51.5% |
| (40, 45] | +0.035% | +0.079% | +0.257% | 48.4% |
| (45, 50] | +0.021% | +0.055% | +0.243% | 48.2% |
| (50, 60] | +0.087% | +0.140% | +0.254% | 48.5% |

**The shape is an inverted U.** The 35–40 bands beat *both* the
qualifying band below them and everything above. If "deeper oversold is
better" were true, ≤35 would lead. It does not — it is the weakest of
the three near bands at every horizon.

That is consistent with something already in the codebase: the
`conviction()` docstring records that RSI *depth* was tested as a
sizing signal and found to be **noise**, with its two sample halves
disagreeing. This funnel says the same thing from a different angle.

### Counterfactual (item 6) — descriptive only

Taking the single nearest miss on each signal-empty session, 1,175
usable sessions, mean RSI of the pick 38.85:

| horizon | raw | excess | win |
|---|---|---|---|
| 5 | +0.684% | **+0.387%** | 51.7% |
| 10 | +1.086% | **+0.472%** | 50.1% |
| 20 | +1.990% | **+0.804%** | 47.8% |

Against all qualifying signals (RSI ≤ 35): +0.143% / +0.095% / +0.186%.
The nearest misses look *better* than the names actually bought.

### A control the brief did not ask for, and it matters

SPY here is **price-only** (`adjustment="split"`, dividends excluded),
which understates the benchmark by ~1.3–1.5 CAGR points a year. That is
a **mechanical positive bias in every excess figure above**:

| horizon | artefact |
|---|---|
| 5 sessions | +0.026% to +0.030% |
| 10 sessions | +0.052% to +0.060% |
| 20 sessions | +0.103% to +0.119% |

The (50,60] band — a group nobody would call a dip signal — shows
+0.140% at 10 sessions, which is roughly two to three times the
artefact and no more. **And the qualifying ≤35 band's +0.095% at 10
sessions is almost entirely the artefact.** The 35–40 hump at ~+0.41%
sits well clear of it, but the baseline it is being compared against is
essentially zero, not positive.

## 4. Where opportunity disappears

Against the brief's three failure modes, the evidence is **mixed, and I
will not force one label**:

- **A. Early-funnel scarcity — partly true.** The trend filter alone
  removes 27.7% of symbol-sessions, and price/liquidity/history remove
  another 16.2%. Only 56% of the universe reaches the RSI test.
- **B. Threshold scarcity — structurally true, economically unproven.**
  60.7% of signal-empty sessions have a name within RSI 40, and those
  names show higher excess than the ones bought. But see section 6.
- **C. Quality scarcity — true above RSI 40.** The (40,45], (45,50] and
  (50,60] bands all sit at or below the dividend artefact with win rates
  of 48%. There is genuinely nothing there.

The honest summary is **B bounded by C**: opportunity exists in a
narrow strip from 35 to 40 and vanishes above it. It is not a broad
scarcity of eligible names.

## 5. Time-split stability

Chronological thirds, boundaries 2019-07-24 and 2023-02-09, declared
before results.

**Absolute excess vs SPY, 10 sessions:**

| band | early | middle | late |
|---|---|---|---|
| ≤35 (qualifies) | +0.057% | +0.236% | +0.015% |
| (35, 37.5] | +0.214% | +0.111% | +0.762% |
| **(37.5, 40]** | **+0.312%** | **+0.325%** | **+0.512%** |
| (40, 45] | +0.080% | −0.085% | +0.204% |
| (45, 50] | +0.178% | +0.028% | +0.009% |

**(37.5,40] is positive in all three thirds and is the most stable cell
in the table.** The qualifying band is the least stable of the three
near bands.

Signal scarcity is itself **not** stable — it has been easing:

| period | signal-empty rate | mean candidates |
|---|---|---|
| early | 62.9% | 1.44 |
| middle | 55.8% | 1.78 |
| late | **37.6%** | **2.46** |

Using only the already-defined market states (no new regime introduced):

| state | signal-empty | mean candidates | (35,40] excess @10 |
|---|---|---|---|
| favourable | 47.3% | 1.53 | +0.270% |
| neutral | 45.8% | 4.24 | +0.718% |
| unfavourable | 57.1% | 1.56 | +0.254% |

## 6. Evidence for and against threshold scarcity

### The clustering problem

192,392 observations come from only 2,450 sessions and 230 symbols. On
any day most names move together, and the same name recurs on
consecutive days with overlapping forward windows. Treating those as
independent manufactures significance. Two honest restatements:

**(a) One observation per session** — average within a day, day as the
unit, then a monthly block bootstrap:

| band | horizon | days | mean | t | 95% CI | excludes 0 |
|---|---|---|---|---|---|---|
| ≤35 | 10 | 1,275 | +0.059% | 0.60 | [−0.234%, +0.368%] | no |
| (35,37.5] | 10 | 1,564 | +0.232% | 1.99 | [−0.132%, +0.602%] | no |
| **(37.5,40]** | 5 | 1,863 | +0.223% | 2.91 | **[+0.017%, +0.440%]** | **yes** |
| **(37.5,40]** | 10 | 1,863 | +0.374% | 3.45 | **[+0.013%, +0.732%]** | **yes** |
| (37.5,40] | 20 | 1,863 | +0.541% | 3.78 | [−0.003%, +1.098%] | no (just) |

**(b) The paired test — the one that decides this.** "Is the near-miss
band better than the band we already take?" is a paired question, asked
within each session so the day's market move cancels exactly.
(35,40] minus ≤35, on the 1,222 sessions where both exist:

| horizon | mean difference | t | 95% CI (monthly) | excludes 0 | near-miss wins |
|---|---|---|---|---|---|
| 5 | +0.098% | 1.05 | [−0.110%, +0.317%] | **no** | 51.1% |
| 10 | +0.315% | 2.56 | **[−0.0002%, +0.638%]** | **no** | 53.5% |
| 20 | +0.413% | 2.32 | [−0.140%, +0.944%] | **no** | 55.2% |

The 10-session lower bound lands at **−0.0002%** — as close to the
boundary as a result can sit without crossing it.

**Paired difference by chronological third:**

| horizon | early | middle | late |
|---|---|---|---|
| 5 | +0.089% | **−0.350%** | +0.417% |
| 10 | +0.251% | **−0.096%** | +0.650% |
| 20 | +0.504% | +0.166% | +0.515% |

**The sign flips in the middle third at 5 and 10 sessions.**

### For

1. The hump is real, large-sample (5,408 and 7,807), and non-monotone —
   higher than both neighbours, which no simple bias explains.
2. (37.5,40] absolute excess is positive in all three thirds and its CI
   excludes zero at 5 and 10 sessions.
3. It holds across all three horizons.
4. The mechanism is coherent and already half-documented: RSI *depth* is
   recorded in the codebase as noise, so a gate placed on depth may be
   cutting in the wrong place rather than too tight.

### Against

1. **Every paired CI includes zero.** The question that matters
   operationally is not "do these names beat SPY" but "are they better
   than what we buy instead", and that is unresolved.
2. **The paired sign flips in the middle third** at 5 and 10 sessions,
   failing the brief's own consistency requirement.
3. **The comparison baseline is ~zero.** After the dividend artefact,
   the qualifying band's excess is approximately nil — so the hump is
   partly "≤35 is bad" rather than "35–40 is good".
4. **The pool would grow 3.61×** (5,072 → 18,287). With 59.5% of today's
   candidates already refused as correlated duplicates, and the bucket
   relaxation test costing 27.8 points of return and breaching the
   drawdown ceiling, extra candidates mostly mean more competition for
   the same slots — not more trades. Whether that improves *selection
   within slots* is a genuinely different question this pass did not
   test.
5. Seven bands were examined. Declared in advance, but still seven.

## 7. Potential hypothesis, if justified

**Not justified yet — nothing proposed, nothing registered.**

Recording the shape a future H-0009 would have to take, so that it
cannot be assembled later from a flattering subset:

- It would **not** be "lower the RSI gate to 40". The evidence does not
  support more trades; it weakly suggests a *differently placed* gate,
  and the ≤35 band's weakness is as much of the finding as the 35–40
  band's strength.
- The operative mechanism is **selection within existing slots**, not
  breadth. The right experiment enlarges the candidate pool while
  holding every capacity rule fixed, and asks whether the portfolio
  improves at equal or lower drawdown.
- Direction and cutoffs must be declared before outcome testing, and the
  **multiple-comparison cost recorded**: the 35–40 region was chosen
  after looking at a seven-band table on this same decade. That is a
  real search cost and it must be stated in the seal, exactly as H-0007
  disclosed its six-dimension provenance.
- The 110% ceiling (14.2806%) applies unchanged and is not negotiable.

## 8. Reasons not to register

1. The paired test — the operative one — is inconclusive at every
   horizon.
2. It fails the brief's own consistency criterion: the paired difference
   changes sign in the middle third.
3. A 3.61× pool interacts with a capacity system that has just been
   shown to punish extra correlated positions severely. The likely
   portfolio effect is not knowable from name-level returns, and
   pretending otherwise would be the "more activity = more edge" trap
   the brief names explicitly.
4. Registering now would spend a slot on the weakest defensible version
   of the idea. The stronger version — pool enlargement tested against
   portfolio outcomes at fixed capacity — needs its acceptance criteria
   written first.

## 9. Governance / fingerprint status

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` working tree clean |
| `rsi_entry` / `trend_ma_days` | **35.0 / 200 — unchanged** |
| bucket cap / max positions | **1 / 12 — unchanged** |
| learned ranker / veto | `False` / `False` |
| exit haircut | **0.652% unchanged**, default still `0.0` |
| 110% drawdown ceiling | **unchanged** |
| clean OOS | **untouched**, frozen to 2026-10-12 |
| registrations | 8, chain intact — **none added** |
| promotion candidates | **none** |
| research ledger | 30 experiments, 91 configurations — unchanged |
| thirty-year access count | **13 — not read** |
| decade reads | 80 (this pass added 3 diagnostic reads, each recorded) |
| artefacts | every JSON carries `FORENSIC_NON_PROMOTIONAL: true` |
| tests | **1,191 passing** |

## 10. Recommended next investigation

The central question answered plainly: **the strategy holds ~52% cash
mostly because its signal genuinely finds little — but the boundary is
placed on a variable the codebase already knows is noisy, and the strip
just outside it is the one place in the funnel with measurable value.**

Two candidates, in order:

1. **Pool enlargement at fixed capacity** — the strong form of this
   finding. Enlarge the candidate pool to RSI ≤ 40 while holding the
   bucket cap, position cap, per-day cap, sizing and stops *exactly* as
   they are, and measure the portfolio, not the names. This tests
   selection-within-slots rather than breadth, which is where the
   previous three passes say the real constraint lives. It needs a
   pre-registered direction, the search-cost disclosure, and the 110%
   ceiling as a hard clause. **A descriptive pass should come first**:
   of the 13,215 extra name-days, how many would actually win a slot
   under today's rules?
2. **Why the ≤35 band is weak.** The deepest-oversold names carry
   essentially zero excess after the dividend artefact, which is a
   finding in its own right and may be more useful than the hump. If
   RSI ≤ 35 selects distress rather than dislocation, that is an entry
   *quality* question and it is upstream of every capacity question
   asked so far.

I would do the descriptive half of (1) next, and register nothing until
it lands.

## Artefacts

- `scripts/forensics_breadth.py`, `scripts/forensics_breadth_significance.py`
- `docs/phase5/breadth-forensics.json`, `docs/phase5/breadth-significance.json`
- `docs/phase5/breadth-observations.json` (192,392 rows; not committed — 51 MB, regenerable)
