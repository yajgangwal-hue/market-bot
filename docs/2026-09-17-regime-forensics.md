# Market-regime conditioning — read-only forensic pass

*2026-09-17. No experiment registered. No file in `src/` touched. No
parameter tuned. Nothing promoted.*

## Classification: **B — INCONCLUSIVE**

Regime dependence is real and large. **It runs opposite to the
hypothesis.** In all six regime definitions the state a long-only
investor would call *favourable* is the state where this strategy
performs **worst** — four of the six annualise **negative** there.

The architecture proposed (more risk when favourable, defensive when
unfavourable) would deploy capital into the strategy's weakest
environment and withdraw it from its strongest. And the one stable
version of the inverse finding maps onto **H-0007, which was already
tested and rejected**.

I am not proposing H-0009.

---

## 1. Is a leakage-free regime signal feasible? **Yes.**

Every label for session *t* is built from closes through *t−1* and then
used to bucket what happened on *t*. All six are computable live from
data the bot already holds.

| # | signal | formula | available | coverage | missing | leakage | live? | stability (mean run) | economic reading |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **trend_dual_ma** *(primary)* | SPY close vs its own 200-day **and** 50-day SMA at t−1; above both / one / neither | t−1 close | 2,484 / 2,684 | 200 warm-up | none | yes | 12.2 sessions | trend participation; **no fitted parameter** |
| 2 | spy_drawdown | SPY close / expanding peak − 1; >−2% / >−10% / else | t−1 close | 2,683 | 1 | none | yes | 13.4 | textbook pullback vs correction |
| 3 | spy_volatility | 20-day realised vol, **expanding** percentile terciles | t−1 close | 2,412 | 272 warm-up | none | yes | 17.4 | risk environment |
| 4 | breadth | share of universe above own 200-day SMA, expanding terciles | t−1 close | 2,232 | 452 | **survivorship** | yes | 9.6 | participation |
| 5 | credit_hyg_lqd | HYG/LQD vs its own 50- and 20-day SMA | t−1 close | 2,634 | 50 | none | yes | **4.9** | credit risk appetite |
| 6 | risk_spy_tlt | SPY/TLT vs its own 50- and 20-day SMA | t−1 close | 2,634 | 50 | none | yes | **5.5** | risk-on vs risk-off |

**Rejected or down-weighted:**

- **VIX/VXX** — not attempted; the required history is absent and
  approximating it was forbidden.
- **breadth (4)** — computed and reported, but it uses **today's
  constituents projected backwards**. Median 216 names per session. It
  is survivorship-biased and cannot be read as clean historical
  evidence. Kept only as a cross-check.
- **credit (5) and risk_spy_tlt (6)** — economically the most
  interesting, but they flip **538 and 477 times** over the decade
  (mean runs of 4.9 and 5.5 sessions). Too unstable to drive a risk
  thermostat without hysteresis, and adding hysteresis is a parameter
  search this pass refuses.
- **cross-sectional dispersion / correlation** — not computed. They
  carry the same survivorship problem as breadth with none of its
  interpretability, and the brief asked for the smallest sufficient set.

The primary signal was chosen because it has **no fitted threshold at
all** — two textbook lookbacks and a count.

## 2. Does the frozen strategy behave differently across regimes? **Yes, materially — and inverted.**

Primary signal, `trend_dual_ma`:

| state | days | ann return | ann vol | Sharpe | Sortino | cash | positions |
|---|---|---|---|---|---|---|---|
| favourable | 1,693 | **+3.72%** | 7.98% | 0.467 | 0.587 | 51.8% | 3.86 |
| neutral | 474 | +4.85% | 12.57% | 0.386 | 0.462 | 49.9% | 4.17 |
| unfavourable | 317 | **+13.23%** | 12.71% | **1.041** | 1.418 | 57.4% | 3.90 |

Trades, by the regime in force at entry:

| state | trades | win | profit factor | avg $ | median R | held | stop rate |
|---|---|---|---|---|---|---|---|
| favourable | 466 | 49.1% | 1.170 | $59 | **−0.036** | 14.1 | 33.9% |
| neutral | 151 | 57.0% | 1.395 | $136 | +0.303 | 14.0 | 32.5% |
| unfavourable | 81 | 51.9% | 1.305 | $116 | +0.190 | 13.3 | 39.5% |

**The median trade entered in a favourable market loses money.**

### The same ordering under every definition

Strategy annualised return by state:

| signal | favourable | neutral | unfavourable |
|---|---|---|---|
| trend_dual_ma | +3.72% | +4.85% | **+13.23%** |
| spy_drawdown | +2.23% | **+9.10%** | +4.36% |
| spy_volatility | **−1.17%** | +5.63% | +7.82% |
| breadth | **−1.09%** | +7.92% | +7.33% |
| credit_hyg_lqd | **−0.73%** | +14.39% | +7.07% |
| risk_spy_tlt | **−1.44%** | +13.76% | +14.03% |

Six for six, "favourable" is the worst column. This is economically
coherent for a mean-reversion rule: a calm, trending market produces few
genuine dislocations, so the RSI ≤ 35 signals that do fire are weak,
while the account sits half in cash and the index compounds without it.

## 3. Is it beta? **Mostly, but not entirely.**

| signal | state | strategy | SPY | beta | beta×SPY | **residual** |
|---|---|---|---|---|---|---|
| trend_dual_ma | favourable | +3.72% | +12.03% | 0.380 | +4.58% | −0.85% |
| | neutral | +4.85% | +12.21% | 0.483 | +5.90% | −1.05% |
| | unfavourable | +13.23% | **+32.36%** | 0.215 | +6.96% | **+6.27%** |
| spy_volatility | favourable | −1.17% | +0.44% | 0.456 | +0.20% | −1.37% |
| | neutral | +5.63% | +20.34% | 0.499 | +10.14% | −4.51% |
| | unfavourable | +7.82% | +15.10% | 0.265 | +4.00% | +3.83% |
| risk_spy_tlt | favourable | −1.44% | +1.96% | 0.289 | +0.56% | −2.01% |
| | neutral | +13.76% | +32.58% | 0.340 | +11.08% | +2.68% |
| | unfavourable | +14.03% | +31.73% | 0.319 | +10.12% | +3.91% |

Residual spread across states: 7.32 / 8.34 / 5.92 percentage points. So
there **is** a non-beta component that varies by state — but note the
first line of the story: **SPY itself annualises +32.36% in the
trend-unfavourable state.** Being below both moving averages is not a
description of a falling market; it is largely a description of the
violent recoveries that follow one. Most of the strategy's advantage
there is the index, harvested at a beta of 0.215.

**Do not call this alpha.** Four of the nine residuals above are
negative, and the neutral residual is +2.68% under one signal and
−4.51% under another.

## 4. Is the timing drag regime-dependent? **No. It is a constant tax.**

Timing per dollar of notional, across every signal and state:

| signal | favourable | neutral | unfavourable |
|---|---|---|---|
| trend_dual_ma | −0.5053% | −0.6791% | −0.4494% |
| spy_drawdown | −0.4501% | −0.7131% | −0.4469% |
| spy_volatility | −0.4344% | −0.5803% | −0.5934% |
| breadth | −0.5167% | −0.5350% | −0.5411% |
| credit_hyg_lqd | −0.5564% | −0.5306% | −0.5084% |
| risk_spy_tlt | −0.5373% | −0.5681% | −0.5163% |

Every cell lies between −0.43% and −0.72%. There is no state in which
the drag is absent or materially smaller, and no consistent ordering.
**Regime conditioning cannot address the largest identified drag** —
which H-0008 established is 82% the deliberately conservative exit
haircut, not a market effect.

Selection per dollar, by contrast, has **no consistent ordering at
all**: trend and risk_spy_tlt say selection is best in favourable
(+0.2393%, +0.3953%); volatility says it is best in unfavourable
(+0.4479%); credit and risk_spy_tlt make it **negative** in
unfavourable (−0.0482%, −0.3052%). Four different signals, four
different stories.

## 5. Do capacity constraints bind differently? **Two of the three stated premises are wrong.**

| state | days | candidates | taken | conversion | **position cap** | **bucket** | **cash** | other |
|---|---|---|---|---|---|---|---|---|
| favourable | 1,693 | 2,583 | 466 | 18.0% | **0** | 1,623 | 43 | 451 |
| neutral | 474 | 2,009 | 151 | **7.5%** | **0** | 1,100 | 96 | 662 |
| unfavourable | 317 | 495 | 81 | 16.4% | **0** | 302 | 24 | 88 |
| **total** | | **5,087** | **698** | **13.7%** | **0** | **3,025 (59.5%)** | **163 (3.2%)** | **1,201** |

Reasons are attributed in the simulator's own order: position cap, then
correlation bucket, then cash. "Other" is the 3-per-day cap, sizing, or
ADV.

- **The 12-position cap never binds. Not once, in any regime.** Mean
  positions held is 3.86–4.17 against a cap of 12.
- **Cash blocks 3.2% of candidates.** Mean cash share is 49.9–57.4%;
  the account is not capital-constrained.
- **The correlation bucket is the constraint** — 59.5% of all
  candidates, and it bites hardest in the neutral state, where
  candidates cluster at 7.82 per day and conversion falls to 7.5%.

The brief carried forward that "cash, the 12-position cap, and
one-per-correlation-bucket are major portfolio constraints." On this
data only the third is. That correction matters more than anything else
in this report for where capacity work should point.

## 6. Cash drag — the mechanism, and it points the wrong way

| state | days | cash share | SPY annualised | **foregone annually** |
|---|---|---|---|---|
| favourable | 1,693 | 51.8% | +12.03% | 6.23% |
| neutral | 474 | 49.9% | +12.21% | 6.09% |
| unfavourable | 317 | **57.4%** | **+32.36%** | **18.57%** |

The largest cash drag by far is in the state the hypothesis wants to
hold *more* cash in. But that same state carries SPY's worst single day
(−10.78%) and its highest volatility (35.17% annualised). Deploying
there captures the rebound at exactly the drawdown the 110% ceiling
exists to constrain. It is a risk transfer, not a free lunch.

## 7. Is the finding stable in time? **Half of it is not.**

Chronological thirds of the sessions, declared in the script before any
number was computed. Which state was *worst* in each third:

| signal | early | middle | late | consistent? |
|---|---|---|---|---|
| trend_dual_ma *(primary)* | neutral | unfavourable | neutral | **no** |
| spy_drawdown | favourable | favourable | favourable | yes |
| spy_volatility | favourable | favourable | favourable | yes |
| breadth | neutral | unfavourable | favourable | **no** |
| credit_hyg_lqd | favourable | unfavourable | favourable | **no** |
| risk_spy_tlt | favourable | favourable | favourable | yes |

"Favourable is worst" holds in 12 of 18 signal×period cells (67%) and in
**3 of 6 signals across all three thirds**. The parameter-free primary
signal is **not** one of them.

Primary signal, annualised return by third:

| period | favourable | neutral | unfavourable |
|---|---|---|---|
| early | +3.23% | +1.24% | **+40.43%** |
| middle | +4.03% | +8.84% | **+0.85%** |
| late | +3.85% | +3.06% | **+22.91%** |

The favourable column is remarkably steady (3.23 / 4.03 / 3.85). The
unfavourable column swings from +40.43% to +0.85% to +22.91% — 317 days
split three ways is ~105 sessions per cell, and the estimate is not
stable enough to size a risk budget against.

## 8. Can transitions be detected early enough? **No.**

The first measurement of direct favourable→unfavourable flips returned
**n = 2**, because almost every transition passes through neutral. Re-
measured as entry into a state from any other state:

| entering | events | SPY after 5 | after 10 | after 20 | after 40 | after>0 @20 |
|---|---|---|---|---|---|---|
| favourable | 72 | +0.36% | +0.31% | +0.82% | +2.05% | 69.4% |
| neutral | 99 | +0.05% | −0.08% | +0.43% | +1.37% | 65.7% |
| unfavourable | **32** | −0.40% | −1.41% | −1.43% | **+0.77%** | 46.9% |

Entering *unfavourable* does weakly precede SPY weakness — about −1.4%
over 10–20 sessions — and reverses to **+0.77% by 40**. So the
defensive signal has roughly a 20-session useful life, a near-coin-flip
hit rate (46.9% positive at 20 sessions), and **32 observations**.

Against that:

| | |
|---|---|
| regime changes | 203 over 2,484 sessions = **20.6 per year** |
| runs under 10 sessions | **141 of 204 (69%)** |
| sessions inside those short runs | 370 of 2,484 (14.9%) |
| neutral runs | median **3** sessions; 85% under 10 |

A thermostat that flips twenty times a year, with two thirds of its
states lasting under two weeks, is not a thermostat. Making it usable
means adding hysteresis — a threshold, a confirmation delay, a buffer —
and every one of those is a fitted parameter this pass was told not to
search for.

## 9. Does the evidence support a regime-conditioned risk hypothesis?

**Not the one proposed, and not yet in any form.**

Against:

1. **The direction is inverted.** All six signals put the strategy's
   worst performance in the favourable state. Raising utilisation there
   and cutting it in unfavourable conditions would move capital the
   wrong way on this evidence.
2. **The primary, parameter-free signal fails the time split.**
3. **The strongest state's estimate is unstable** — +40.43% / +0.85% /
   +22.91% across thirds on ~105 sessions each.
4. **Most of the state difference is beta.** SPY annualises +32.36% in
   trend-unfavourable; the strategy captures it at beta 0.215.
5. **Selection edge has no consistent regime ordering.** Four signals,
   four different answers, two of them negative.
6. **The timing drag is regime-invariant**, so regime conditioning
   cannot touch the largest problem.
7. **Transitions whipsaw**: 20.6 changes a year, 69% of runs under 10
   sessions, 32 defensive events total.
8. **The stable inverse finding has already been tested.** The three
   signals that do survive time-splitting all say the calm / low-
   drawdown / risk-on state is worst. Acting on that means doing less
   when calm — which is **H-0007**, rejected at Spearman(cutoff,
   Sharpe) = −1.0000 because abstention removed net winners and market
   exposure. Re-running it under a trend label would be rediscovering a
   known failure.

For:

1. Regime dependence in the *outcome* distribution is real and large
   (−1.44% to +14.03% annualised across states).
2. Residual, non-beta return varies by 5.9–8.3 points across states.
3. Cash drag varies three-fold (6.09% to 18.57% foregone).

That is enough to say the environment matters. It is **not** enough to
say a regime layer would improve the portfolio, and it actively
contradicts the proposed direction.

## 10–12. Next experiment, configurations, criteria

**None proposed.** Classification B does not warrant a registration, and
the brief is explicit that I should stop here.

## 13. What would distinguish genuine regime adaptation from overfitting

Recorded now, before anyone is tempted:

1. **A mechanical prior stated before the tables.** "Mean reversion
   needs dislocations, dislocations need stress" predicts the inverted
   result *in advance*. Any future registration should declare that
   direction and be rejected if the data agrees only after the fact.
2. **Agreement across independent signal families**, not just across
   thresholds of one. Trend, volatility, credit and breadth are
   partially independent; a real effect should appear in most. Selection
   edge currently appears in none consistently.
3. **Survival of the chronological thirds**, applied to the exact signal
   being registered — not to the best of six.
4. **A residual that survives the beta subtraction**, since the beta
   term is where most of the state difference lives.
5. **Actionability under whipsaw**, costed explicitly: the number of
   switches per year and the turnover they imply, charged at the real
   cost model before any return is quoted.
6. **A drawdown test at the 110% ceiling**, because the only states
   worth deploying into on this evidence are also the states carrying
   SPY's worst days.

## 14. What remains completely untouched

| | |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production strategy | **unchanged**; `src/` working tree clean |
| learned ranker | `LEARNED_RANKING_ENABLED = False` |
| learned veto | `LEARNED_VETO_ENABLED = False` |
| rule-exit haircut | **0.652% unchanged**, default still `0.0` |
| 110% drawdown ceiling | **unchanged** |
| clean OOS forward record | **untouched**, frozen to 2026-10-12 |
| thirty-year dataset | **13 reads — not read by this pass** |
| registrations | 8, chain intact — **nothing registered** |
| research ledger | 30 experiments, 91 configurations |
| promotion candidates | **none** |
| tests | 1,191 passing |

## Artefacts

- `scripts/forensics_regime.py`, `scripts/forensics_regime_stability.py`
- `docs/phase5/regime-forensics.json`, `docs/phase5/regime-stability.json`
