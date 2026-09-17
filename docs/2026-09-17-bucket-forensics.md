# The correlation-bucket constraint — read-only forensic pass

*2026-09-17. **FORENSIC, NON-PROMOTIONAL.** No experiment registered. No
file in `src/` touched. No rule relaxed. No promotion candidate created.*

## Classification: **A — NO EVIDENCE**

The bucket rule is not refusing valuable opportunities. It is refusing
duplicated risk, and it is doing so well.

---

## The five questions, answered from the reconstruction

**1. How much valuable opportunity is being rejected?**
**Essentially none.** Bucket-blocked candidates averaged **+0.063%**
excess vs SPY over 10 sessions (n=3,025). The candidates actually taken
averaged **+0.273%** (n=698) — four times better. At 20 sessions taken
is +0.475% against blocked +0.103%, and the blocked group's win rate
falls to 47.9%.

**2. Are the rejected candidates better than the positions they would
sit alongside?** **No.** Measured from the same day forward, the blocked
candidate beat the position occupying its bucket only **29.5%** of the
time at 10 sessions (blocked +0.957% vs occupant +1.097%). At the moment
of the decision, the blocked candidate's conviction exceeded the
occupant's-at-its-own-entry only **17.6%** of the time.

**3. How much of the ~52% cash is caused by correlation blocking?**
**Very little.** On **52.1%** of all sessions there is **no candidate at
all**, and mean cash on those days is **69.8%**. On the 39.8% of
sessions where the bucket does block something, cash is **36.9%** — far
*below* the 55.7% average, because positions are already on. The cash
comes from having nothing to buy, not from the bucket rule.

**4. Would allowing additional correlated positions improve portfolio
wealth after incremental risk?** **No — it is worse on every axis, with
no tradeoff to weigh.** Raising the cap to 2 costs **27.78 points** of
total return, **0.217** of Sharpe, and deepens maximum drawdown by
**7.30 points to −20.29%**, breaching the standing 14.2806% ceiling.

**5. Is there enough evidence for a preregistered capacity experiment?**
**No.** Classification A. Nothing proposed.

---

## What the bucket actually is (item 9)

This reframes the question, so it comes first.

| property | finding |
|---|---|
| construction | **static hand-written sector/theme map** in `strategy.py` — a literal dict |
| lookback window | **none** — no prices are read |
| data frequency | n/a |
| correlation calculation | **none** |
| threshold | n/a |
| update frequency | **never** |
| point-in-time | trivially yes; no market data is used, so no price look-ahead is possible |
| static or dynamic | **static**; an assignment never changes |
| historical info only | yes — no information of any kind is read at runtime |
| buckets | 30, covering all 230 symbols; 0 fall through to `other` |

It is **not** a measured correlation. The one real leakage concern is
that the *labels* encode today's understanding of each business and are
applied to all history.

**So: does a sector label actually track realised correlation?** Daily
returns, full decade, mean pairwise Pearson:

| | pairs | mean r | median r |
|---|---|---|---|
| **within** bucket | 1,397 | **+0.5191** | +0.5000 |
| **across** buckets | 981 | **+0.2954** | +0.2902 |
| separation | | **+0.2237** | |

The label does real work. Only **3 of 981** sampled cross-bucket pairs
exceed r = 0.75 (VEA/XLI 0.798, XHB/XLI 0.785, MS/XLI 0.752) — so
highly correlated names slipping into *different* buckets is rare.

Where it is weakest is inside the large heterogeneous buckets:

| least internally correlated | members | mean r | | most correlated | members | mean r |
|---|---|---|---|---|---|---|
| internet | 15 | 0.3764 | | homebuilders | 2 | 0.9525 |
| technology | 25 | 0.3806 | | broad_equity | 9 | 0.9171 |
| industrials | 15 | 0.4188 | | biotech | 2 | 0.9131 |
| pharma | 6 | 0.4209 | | developed_intl | 6 | 0.8893 |

## Reconstruction (items 1, 16)

All 5,087 candidates reconstructed; **none discarded**.

| status | n | share |
|---|---|---|
| bucket-blocked | 3,025 | 59.5% |
| other (3/day cap, sizing, ADV) | 1,201 | 23.6% |
| taken | 698 | 13.7% |
| cash-blocked | 163 | 3.2% |
| **position-cap-blocked** | **0** | **0.0%** |

5,081 of 5,087 have a full 10-session forward window (6 lost at the
series end). Universe: 230 non-crypto symbols, all mapped. The sample is
representative of the strategy's own candidate stream because it *is*
that stream.

**Survivorship limits, stated:** the universe is today's constituents,
and the bucket labels are today's classifications. Both affect which
names appear and how they are grouped, and neither can be corrected with
the data on hand.

**One imprecision, not hidden:** the simulator evaluates its guard
before the entry signal and processes candidates in an internal order
within a day. My reconstruction attributes reasons in the simulator's
documented order (position cap → bucket → cash) using open positions
plus same-day fills as occupants. Within-day ordering can therefore
shift a small number of candidates between the "bucket" and "other"
categories. It cannot move any candidate into or out of "taken".

## Taken vs blocked (items 3, 4, 14)

Excess vs SPY, by horizon:

| horizon | taken (698) | bucket (3,025) | cash (163) | other (1,195) |
|---|---|---|---|---|
| 1 session | +0.102% | +0.068% | +0.148% | +0.050% |
| 3 | +0.091% | +0.123% | +0.277% | +0.056% |
| 5 | +0.165% | +0.137% | +0.584% | +0.086% |
| **10** | **+0.273%** | **+0.063%** | +0.580% | +0.015% |
| 20 | +0.475% | +0.103% | +0.820% | +0.140% |

Win rate at 10 sessions: taken 50.7%, blocked 49.9%. At 20: taken 50.1%,
blocked **47.9%**.

Blocked candidates edge ahead at 1 and 3 sessions and fall behind from 5
onwards — over the horizon that matches the strategy's ~14-session
holding period, the taken candidates are clearly better.

**At the decision moment the two groups are indistinguishable:**

| status | n | conviction | ATR fraction | ADV |
|---|---|---|---|---|
| taken | 698 | 1.4036 | 2.1845% | $1,383m |
| bucket-blocked | 3,025 | 1.4191 | 2.1928% | $1,585m |

So the rule is not selecting on quality — it cannot see any — and the
group it happens to exclude did *worse* anyway.

*These are not investable portfolio returns.* A blocked candidate could
only have been taken by displacing or doubling something.

## The key counterfactual: blocked candidate vs its occupant (items 1, 2, 11)

3,025 reconstructable pairs.

| horizon | blocked | occupant | difference | blocked beat occupant |
|---|---|---|---|---|
| 1 | +0.204% | +0.215% | −0.011% | 28.1% |
| 3 | +0.427% | +0.389% | +0.039% | 29.8% |
| 5 | +0.617% | +0.573% | +0.044% | 30.5% |
| **10** | +0.957% | +1.097% | **−0.141%** | **29.5%** |
| 20 | +1.582% | +1.715% | −0.133% | 29.1% |

**In roughly 70% of cases the position already in the bucket did better
than the candidate it blocked.**

### How duplicated is the second position?

Correlation between the blocked candidate's forward return and its
occupant's, same window:

| horizon | r | n |
|---|---|---|
| 5 sessions | **+0.7342** | 3,025 |
| 10 sessions | **+0.7811** | 3,025 |
| 20 sessions | +0.7402 | 3,016 |

**The second position is ~78% the same trade.** It adds risk almost
one-for-one while adding return only where the two names diverge — which
is the minority of the variance.

### The occupant's state when it blocked something

| | |
|---|---|
| age | mean 7.2 calendar days, median 5 |
| unrealised | mean **−1.051%**, median −0.944% |
| under water | **79.2%** of the time |
| blocked conviction > occupant's at its entry | **17.6%** |

The occupant is usually a recently-opened, currently-losing position —
and it still outperformed the candidate it displaced 70% of the time.
For a mean-reversion rule that is coherent: the position further under
water has more to revert.

## Concentration (item 5)

28 buckets block something. Top 12 carry **82.0%**.

| bucket | blocked | share | taken | mean excess (10s) |
|---|---|---|---|---|
| financials | 407 | 13.5% | 67 | +0.109% |
| technology | 296 | 9.8% | 51 | +0.470% |
| discretionary | 266 | 8.8% | 57 | −0.622% |
| industrials | 257 | 8.5% | 45 | −0.026% |
| semis | 205 | 6.8% | 48 | +1.482% |
| software | 167 | 5.5% | 38 | +0.340% |
| staples | 155 | 5.1% | 36 | −0.573% |
| energy | 122 | 4.0% | 26 | −0.758% |

No single bucket dominates, and the sign of the blocked-candidate excess
is inconsistent across buckets — positive in semis and technology,
negative in discretionary, staples and energy.

## Time stability (item 6) — fails, and against the blocked candidates

Chronological thirds of the blocked events, declared in the script
before any number was computed:

| period | n | dates | mean excess | median | win |
|---|---|---|---|---|---|
| early | 1,008 | 2016-11-08 → 2020-10-09 | +0.073% | +0.040% | 50.8% |
| middle | 1,008 | 2020-10-21 → 2024-03-04 | +0.287% | +0.038% | 51.4% |
| late | 1,009 | 2024-03-05 → 2026-08-21 | **−0.171%** | −0.153% | 47.4% |

**Not the same sign.** By year, 2024 alone contributes −328.2 summed
excess points across 476 events (mean −0.689%), and 2022 contributes
+133.0 (mean +0.751%). Whatever small value the blocked group shows in
aggregate is neither stable nor recent.

## Regime interaction (item 7) — descriptive only

| state | candidates | blocked | blocking rate | mean excess | win |
|---|---|---|---|---|---|
| favourable | 2,583 | 1,623 | **62.8%** | **−0.220%** | 46.2% |
| neutral | 2,009 | 1,100 | 54.8% | +0.362% | 54.6% |
| unfavourable | 495 | 302 | 61.0% | +0.493% | 52.0% |

The rule blocks *hardest* in the favourable state, which is exactly
where the blocked candidates are *worst* (−0.220%, win 46.2%). That is
the constraint behaving well, not badly. No threshold was optimised and
the regime hypothesis is not revived.

## Portfolio counterfactual (items 8, 10, 15)

Three mechanical integer caps. **No threshold was chosen.** The standing
ceiling — 1.10 × 12.9824% = **14.2806%** — was not relaxed.

| | cap 1 (production) | cap 2 | cap 3 |
|---|---|---|---|
| total return | **+58.59%** | +30.80% | +44.50% |
| CAGR | +4.42% | +2.55% | +3.52% |
| annualised volatility | 9.34% | 10.45% | 10.73% |
| downside deviation | 7.85% | 9.02% | 9.13% |
| Sharpe | **0.5107** | 0.2937 | 0.3759 |
| Sortino | 0.7221 | 0.4036 | 0.5225 |
| **maximum drawdown** | **−12.98%** | **−20.29%** | **−20.28%** |
| Calmar | 0.3408 | 0.1259 | 0.1734 |
| worst day | −3.79% | −4.58% | −4.32% |
| trades | 698 | 785 | 805 |
| turnover | 21.70 | 22.50 | 22.82 |
| transaction costs | $13,868 | $14,381 | $14,580 |
| exposure | 44.28% | 49.68% | 50.60% |
| mean cash | 55.7% | 50.3% | 49.4% |
| mean positions | 3.63 | 4.16 | 4.28 |
| win rate | 51.15% | 49.30% | 50.19% |
| profit factor | 1.234 | 1.108 | 1.158 |
| sessions holding a doubled bucket | 0.0% | **52.3%** | **53.7%** |

Against the ceiling:

| cap | drawdown | ceiling | |
|---|---|---|---|
| 1 | 12.9824% | 14.2806% | **within** |
| 2 | 20.2868% | 14.2806% | **BREACH** |
| 3 | 20.2825% | 14.2806% | **BREACH** |

Costs are net in every column; no gross figure is compared to a net one.

**There is no tradeoff here to weigh.** Relaxing the cap loses return
*and* raises every risk measure. That is unusual and worth stating
plainly: more exposure on a decade when the index tripled would normally
raise return. It does not here, because the added positions are ~78%
duplicates that lose together, and the deeper drawdown damages
compounding. Note also that cap 2 is *worse* than cap 3 — these are
path-dependent runs with no clean gradient, which is one more reason not
to go looking for a best value.

## Cash (items 12, 13)

| | |
|---|---|
| sessions simulated | 2,684 |
| sessions with **no candidate at all** | **1,398 (52.1%)** |
| sessions with a bucket-blocked candidate | 1,068 (39.8%) |
| mean cash, all sessions | 55.7% |
| mean cash, no-candidate sessions | **69.8%** |
| mean cash, sessions with a block | **36.9%** |
| mean positions held | 3.63 of 12 |

Decomposing the idle balance: **the dominant cause is the absence of
candidates**, not any constraint. Raising the cap to 2 moved mean cash
only from 55.7% to 50.3% — 5.4 points — while costing 27.8 points of
return and 7.3 points of drawdown.

Against a fully-invested SPY, the gap attributable to correlation
blocking is therefore small and *negative in value*: removing the
constraint deploys more cash and ends up with less money and more risk.
Cash here is largely the absence of opportunity, and partly a risk
reduction that is being earned rather than wasted.

## Governance (item 17)

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production strategy | **unchanged**; `src/` working tree clean |
| `max_per_bucket` / `max_open_positions` in production | **1 / 12, unchanged** |
| learned ranker | `LEARNED_RANKING_ENABLED = False` |
| learned veto | `LEARNED_VETO_ENABLED = False` |
| model `.usable` / `is_promoted` | `False` / `False` |
| rule-exit haircut | **0.652% unchanged**, default still `0.0` |
| 110% drawdown ceiling | **unchanged**, and enforced against every counterfactual |
| clean OOS forward record | **untouched**, frozen to 2026-10-12 |
| experiments registered | **none** — chain intact at 8 |
| promotion candidates | **none** |
| research ledger | 30 experiments, 91 configurations — **unchanged** |
| thirty-year access count | **13 — not read** |
| decade reads | 77 (this pass added 4: 1 forensic baseline + 3 caps, each recorded) |
| artefacts marked | every JSON carries `FORENSIC_NON_PROMOTIONAL: true` |
| tests | **1,191 passing** |

## Conclusion

**A — NO EVIDENCE.** The 59.5% blocking rate is not opportunity loss. The
blocked candidates are indistinguishable from taken ones at the decision
point, slightly worse afterwards, worse than the positions they would
have joined 70% of the time, and ~78% correlated with them. Relaxing the
cap costs return and breaches the drawdown ceiling by six points.

The high blocking *rate* is a consequence of the candidate stream being
clustered by sector, not of the rule being tight. The strategy's idle
cash is caused by finding nothing to buy on half of all sessions.

### One observation, recorded and not proposed

The rule's weakest point is not its strictness but its **granularity**:
`technology` (25 members, mean internal r = 0.3806) and `internet` (15
members, r = 0.3764) group names the market prices quite differently,
while `homebuilders` (r = 0.9525) is tight. A *refinement* of the map —
splitting heterogeneous buckets — is a different question from relaxing
the cap, and nothing in this pass tests it. It would need its own
registration, its own mechanical prior, and it carries an obvious
overfitting hazard: re-drawing sector lines using decade returns is
curve-fitting with extra steps. **Not proposed.**

## Artefacts

- `scripts/forensics_buckets.py`, `scripts/forensics_bucket_capacity.py`
- `docs/phase5/bucket-forensics.json`, `docs/phase5/bucket-capacity.json`
