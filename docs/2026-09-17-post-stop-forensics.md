# Post-stop behaviour — read-only forensic pass

*2026-09-17. No experiment registered. No file in `src/` touched. No
parameter tuned.*

## Classification: **B — INCONCLUSIVE**

The +0.339% reproduces exactly. It does not survive contact with the
robustness checks: the 95% confidence interval spans zero, the effect
exists at one horizon and reverses by 20 sessions, and removing 5 of 128
symbols flips its sign. **It does not meet the bar for registering
H-0009, and I am not proposing one.**

Not classification A, because three pre-declared chronological thirds
are all positive and one conditional split has a coherent shape. Those
are weak indications, not evidence.

---

## What was declared before any number was computed

**The time split.** Chronological thirds of the eligible events ordered
by exit date, equal count (79 / 79 / 81). Calendar years reported
separately as a finer view. No other split computed, and this one was
not revisited.

**The regime definition — one, not a sweep.** SPY's close over its own
200-day SMA, minus 1, read from the **prior** close t−1, ranked by
expanding percentile through t−1. Bottom/middle/top third =
unfavourable/neutral/favourable. A volatility tercile on the same
construction is reported alongside.

**Two reference points, never conflated.** From the exit session's
**close** — "did the name go up?", which is what the original
observation measured. From the **stop fill** — "what would holding have
been worth?", which is the actual counterfactual, because the fill is
where the money left.

## Data quality

| | |
|---|---|
| total stop events | 239 |
| eligible | **239 — none dropped** |
| symbols contributing | 128 of 230 |
| exit dates | 2016-11-09 → 2026-06-30 |
| calendar alignment, symbol vs SPY | max **0 days**, mean 0.000 |
| missing conviction / ATR | 0 / 0 |
| regime label unavailable (pre-252 expanding history) | 19 |

Nothing was discarded. Every stop event had 20 forward sessions
available and a matching SPY window on the identical calendar.

**Benchmark basis**, per `docs/benchmark-units.md`: SPY **price return**,
`adjustment="split"`, **dividends excluded**, matched session-for-session
over the exact forward window from the same starting session. Dividend
exclusion understates SPY by roughly 1.3–1.5 CAGR points per year, so
every excess figure below is **flattering to the stopped names**. All
figures are cumulative returns over the stated window; no CAGR is
quoted, because 1–20 session windows do not annualise meaningfully.

## The observation, reproduced and extended

### From the exit session's close, excess vs SPY

| horizon | n | mean | median | p25 | p75 | stdev | win |
|---|---|---|---|---|---|---|---|
| 1 session | 239 | +0.033% | −0.004% | −0.665% | +0.714% | 1.416% | 49.8% |
| 3 | 239 | +0.116% | −0.028% | −1.381% | +1.527% | 2.527% | 49.0% |
| 5 | 239 | +0.078% | +0.146% | −1.666% | +2.061% | 3.394% | 52.3% |
| **10** | 239 | **+0.339%** | +0.287% | −2.719% | +3.189% | 4.837% | **52.7%** |
| 20 | 239 | **−0.024%** | −0.602% | −3.707% | +2.961% | 6.474% | **46.0%** |

Percentiles of the 10-session excess: p5 −7.839%, p25 −2.719%, p50
+0.287%, p75 +3.189%, p95 +7.472%.

**The first finding is the shape.** A genuine post-stop rebound should
build and persist, or decay smoothly. This one is flat through 5
sessions, appears at 10, and is **gone and slightly negative at 20**,
with the win rate falling to 46.0%. The effect exists at exactly the
horizon it was first noticed at.

### From the stop fill — the real counterfactual

| horizon | mean excess | win |
|---|---|---|
| 1 | +0.018% | 51.9% |
| 3 | +0.097% | 48.5% |
| 5 | +0.062% | 49.8% |
| 10 | +0.325% | 54.0% |
| 20 | −0.053% | 48.1% |

Same shape. The fill sits close enough to the close that the choice of
reference does not change the story.

### What holding would also have meant

Worst close within the window, measured from the fill:

| horizon | mean | median | p25 |
|---|---|---|---|
| 3 | −1.197% | −0.693% | −3.001% |
| 5 | −1.975% | −1.176% | −3.826% |
| 10 | −3.131% | −1.770% | −4.724% |
| 20 | −4.927% | −3.193% | −6.904% |

**22.2% of positions traded at least 5% below the fill within 10
sessions; 36.4% within 20.** Where a rebound happens it frequently
happens *after a further fall*. That is the distinction the brief asked
for: this is consistent with legitimate risk protection, not only with
premature exit.

## Time stability — the one favourable result

| period | n | dates | mean excess | median | win |
|---|---|---|---|---|---|
| early | 79 | 2016-11-09 → 2020-02-25 | +0.091% | −0.190% | 46.8% |
| middle | 79 | 2020-02-25 → 2023-10-11 | +0.285% | +0.655% | 53.2% |
| late | 81 | 2023-10-19 → 2026-06-30 | +0.633% | +0.561% | 58.0% |

All three positive. But the early third's mean is +0.091% against a
~4.8% dispersion — indistinguishable from zero — and its **median is
negative with a 46.8% win rate**. The apparent trend is upward, and the
years driving the late third are the same ones the concentration
analysis flags below. This is the strongest evidence in favour and it is
not strong.

## Year concentration — fails

| year | n | mean | sum excess | share of aggregate |
|---|---|---|---|---|
| 2016 | 5 | +1.752% | +8.761% | 10.8% |
| 2017 | 19 | +0.340% | +6.458% | 8.0% |
| 2018 | 30 | +0.985% | +29.561% | 36.5% |
| 2019 | 18 | −0.281% | −5.061% | −6.2% |
| 2020 | 22 | −1.169% | −25.729% | −31.8% |
| 2021 | 22 | +0.443% | +9.747% | 12.0% |
| 2022 | 24 | −0.659% | −15.805% | −19.5% |
| **2023** | 23 | **+2.168%** | **+49.865%** | **61.6%** |
| 2024 | 32 | −0.254% | −8.120% | −10.0% |
| 2025 | 29 | +0.504% | +14.624% | 18.1% |
| 2026 | 15 | +1.113% | +16.694% | 20.6% |

**2023 alone is 61.6% of the aggregate.** Removing it: mean falls from
+0.3389% to **+0.1441%**, less than half. Four of eleven years are
negative.

The shares exceed 100% because the aggregate (+80.99 percentage-points
summed) is a small residual of much larger offsetting contributions —
+49.9 from 2023 against −25.7 from 2020. That is the fragility in one
line.

## Symbol concentration — fails decisively

128 symbols, at most 6 events each.

| symbol | n | sum excess | share |
|---|---|---|---|
| AAPL | 4 | +28.852% | 35.6% |
| FIX | **1** | +19.099% | 23.6% |
| NFLX | **1** | +16.710% | 20.6% |
| TIP | 3 | +14.304% | 17.7% |
| MPC | 3 | +12.758% | 15.8% |

**Two single-event symbols supply 44% of the aggregate between them.**

| removed | n | mean excess |
|---|---|---|
| none | 239 | +0.3389% |
| top 1 | 235 | +0.2219% |
| top 3 | 233 | +0.0701% |
| **top 5** | 227 | **−0.0473%** |
| top 10 | 216 | **−0.3159%** |

**Removing 5 of 128 symbols flips the sign.** Leave-one-symbol-out
across all 128 refits stays positive (+0.2219% dropping AAPL to +0.4309%
dropping XHB), but that test cannot fail when one name of 128 is removed
— the top-k removal is the informative one, and it fails.

## Market regime — no coherent story

SPY vs its own 200-day SMA, expanding-percentile terciles, prior close:

| regime | n | mean | median | win |
|---|---|---|---|---|
| unfavourable | 100 | +0.395% | −0.003% | 50.0% |
| neutral | 56 | +0.103% | +0.144% | 51.8% |
| favourable | 64 | +0.190% | +0.325% | 54.7% |
| unlabelled (pre-252) | 19 | +1.238% | +1.451% | 63.2% |

SPY 20-day realised-volatility terciles, same construction:

| regime | n | mean | median | win |
|---|---|---|---|---|
| calm | 42 | +0.643% | +0.805% | 59.5% |
| middling | 95 | +0.826% | +0.408% | 52.6% |
| turbulent | 96 | **−0.295%** | −0.021% | 49.0% |

Neither is monotone, and in both the largest bucket is the weakest. The
19 unlabelled events — those before 252 expanding readings exist —
average +1.238%, the highest of any bucket, which is a reminder that
small buckets here produce large numbers for no reason.

## Trade characteristics — attribution only, nothing optimised

| split | low | mid | high |
|---|---|---|---|
| stop distance (% of entry) | +0.010% | −0.452% | **+1.449%** |
| stop distance in ATRs | +0.423% | +0.197% | +0.395% |
| sessions held before the stop | +0.746% | −0.030% | +0.386% |
| entry conviction | +0.136% | −0.373% | +0.490% |
| peak unrealised gain (MFE) | **−0.599%** | +0.875% | +0.747% |

Had the position ever been in profit before stopping? **Every one had** —
the "never above entry" bucket is empty.

| | n | mean | win |
|---|---|---|---|
| was up < 2% | 93 | −0.183% | 46.2% |
| was up ≥ 2% | 146 | +0.671% | 56.8% |

The MFE split is the only one with a shape that suggests a mechanism: a
position that had run up meaningfully before reversing rebounds; one
that never did, does not. But the **ATR-relative** stop distance — the
variable the rule actually sets — is flat across all three terciles
(+0.423% / +0.197% / +0.395%), while raw stop distance is non-monotone.
If the stop were systematically too tight, ATR-relative distance is
where that would show, and it does not.

These are subgroups of an aggregate that is not distinguishable from
zero. They are recorded as leads, not findings.

## Overlapping windows — why the naive statistics are wrong

| | 10 sessions | 20 sessions |
|---|---|---|
| event-sessions | 2,629 | 5,019 |
| distinct calendar sessions covered | 1,148 | 1,677 |
| **overlap ratio** | **2.29×** | **2.99×** |
| busiest session carries | 12 open windows | 15 open windows |
| events sharing an exit date | 71 of 239 | 71 of 239 |

Windows overlap more than twofold and 12 can be open simultaneously, so
these observations are not independent and a common market move is
counted many times. Excess-vs-SPY removes the index component but not
sector or beta co-movement.

| | value |
|---|---|
| mean 10-session excess | +0.3389% |
| naive SE / t | 0.3129% / **1.08** |
| overlap-adjusted n_eff | 104 |
| adjusted SE / t | 0.4735% / **0.72** |
| **monthly block bootstrap, 76 months, 4,000 iterations** | |
| **95% CI on the mean** | **[−0.2180%, +0.9466%]** |
| share of resamples above zero | 87.9% |
| **CI excludes zero** | **No** |

**The effect is not significant even under the naive assumption**
(t = 1.08), and the assumption is wrong in the direction that inflates
it. The honest interval includes zero.

To resolve a +0.339% mean against a 4.84% dispersion at t = 2 would take
roughly **815 independent events** — about **1,866 raw stop events** at
this overlap. We have 239 raw, ~104 effective: a **7.8× shortfall**.

## Portfolio-level bounding

| horizon | hold instead | same $ in SPY | difference |
|---|---|---|---|
| 1 | −$2,983 | −$4,459 | +$1,476 |
| 3 | +$8,823 | +$5,045 | +$3,778 |
| 5 | +$11,138 | +$10,313 | +$826 |
| **10** | +$33,283 | +$24,643 | **+$8,641** |
| 20 | +$34,232 | +$39,632 | **−$5,401** |

**+$8,641 is an upper bound**, and at 20 sessions it is negative. Set
against $213,599 of realised stop losses it is about 4%. It ignores two
real costs: the freed capital returned to cash at 0% under 44% average
exposure, and holding would have occupied a 20%-per-name slot another
entry might have used.

So on the dimensions that matter:

- **CAGR / total return**: the upper bound closes roughly 3% of the
  224.55-point cumulative gap to SPY. It does not change the answer to
  "can this beat SPY".
- **Maximum drawdown**: would very likely **worsen**. 22.2% of positions
  went ≥5% further below the fill within 10 sessions. The ceiling is
  −14.2806% against a −12.9824% baseline, and H-0007 showed two of three
  configurations breaching it on a far gentler change.
- **Volatility and exposure**: both rise, because positions are held
  longer.
- **Turnover and costs**: fall slightly.
- **Risk-adjusted return**: the numerator gain is bounded at ~4% of stop
  losses while the denominator and the drawdown both move against it.

The binding constraint is drawdown, not return — and the change pushes
on exactly the constrained dimension.

## Which explanation fits

Ranked against the candidate explanations in the brief:

1. **Noise, amplified by concentration** — best fit. CI spans zero,
   sign flips on 5 of 128 symbols, one year is 62% of the total, and the
   effect appears at one horizon and reverses at the next.
2. **Small number of symbols** — directly demonstrated. Two single-event
   names are 44% of the aggregate.
3. **Small number of years** — directly demonstrated. 2023 is 61.6%.
4. **Overlapping windows** — demonstrated at 2.29×, which inflates any
   naive significance.
5. **Genuine premature exits** — not supported. The ATR-relative stop
   distance, the variable the rule sets, is flat across terciles.
6. **Market beta** — partly controlled by excess-vs-SPY, but raw returns
   (+0.842% at 10 sessions) are more than twice the excess, so most of
   the visible move is market.
7. **Volatility clustering** — some sign: the turbulent tercile is
   negative while calm and middling are positive, but non-monotone.
8. **Survivorship / data availability** — not a factor here; all 239
   events were eligible and the universe is today's constituents, which
   affects entry selection rather than post-stop drift.

## Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| `src/` working tree | **clean, untouched** |
| learned ranker | `LEARNED_RANKING_ENABLED = False` |
| learned veto | `LEARNED_VETO_ENABLED = False` |
| model `.usable` / `is_promoted` | `False` / `False` |
| 0.652% haircut | **unchanged**, default still `0.0` |
| 110% drawdown ceiling | **unchanged** |
| clean OOS forward record | **untouched**, frozen to 2026-10-12 |
| thirty-year access count | **13 — not read** |
| registrations | 8, chain intact — **H-0009 NOT registered** |
| research ledger | 30 experiments, 91 configurations |
| promotion candidates | **none** |

## What would change the classification

Not a different analysis of this data — a different quantity of it.

1. **Roughly 8× the effective sample.** The forward record accrues stop
   events at a few dozen a year; this is not reachable soon.
2. **A conditional subgroup named in advance.** The MFE ≥ 2% split
   (+0.671%, n=146) is the only one with a plausible mechanism, but it
   was found by looking, and testing it now would be exactly the
   post-hoc move the governance forbids. It would need to come from a
   mechanical prior stated before the data was examined.
3. **A restatement of what the experiment is for.** If the question
   became "does the stop protect drawdown adequately" rather than "does
   the stop exit too early", the evidence above is relevant and points
   the other way — 22.2% of positions fell a further 5%.

## Artefacts

- `scripts/forensics_post_stop.py` — read-only, seeded, reproducible
- `docs/phase5/post-stop-forensics.json`
