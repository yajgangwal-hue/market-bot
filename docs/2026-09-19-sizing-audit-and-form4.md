# Sizing audit and Form 4 feasibility

*2026-09-19. **FORENSIC_NON_PROMOTIONAL.** No experiment registered. No
production file modified. H-0010 is **proposed, not sealed**.*

---

# SECTION 1 — H-0010 sizing audit

## Verdict: a defensible hypothesis exists, but it is weaker than it first looks

There is one stable, structural, leakage-free allocation inefficiency:
**the largest positions earn nothing, and the sizing formula creates
them mechanically.** It survives a chronological split 3 of 3.

But the honest reading is that acting on it is **exposure reduction,
not redistribution** — and that matters, because the governing
objective is excess return versus SPY. I set out the exact proposed
registration below and my recommendation, and I have not sealed it.

## The mechanism, traced not assumed

From `risk.position_size` and its single caller at `portfolio.py:840`:

```
loss_per_share = (entry - stop) + round_trip_cost_per_share(entry, stop)
risk_limited   = equity * 0.005 / loss_per_share
cash_limited   = equity * 0.20  / entry
quantity       = floor(min(risk_limited, cash_limited))
quantity      *= conviction(symbol, history)          # [0.5, 1.5]
quantity       = min(quantity, equity * 0.20 / entry) # cap survives conviction
quantity       = cap_by_participation(quantity, entry, adv, 0.02)
if quantity <= 0: the candidate is DROPPED
```

`stop = entry − 2.5 × ATR(14)`, so `loss_per_share ≈ 2.5 ATR + costs`.

**Classification: equal-risk, ATR-normalised, with a 20%-of-equity
concentration cap and a 2%-of-ADV participation cap, whole shares.**
It is not equal-dollar; it is not capital-constrained in the ordinary
case.

Four facts the trace turned up that documentation alone would not:

| | |
|---|---|
| **which constraint binds** | risk budget **91.3%**, notional cap 8.7%, participation **never** |
| **realised risk per trade** | mean **0.692%**, median 0.748% — not the stated 0.500% |
| **conviction is saturated** | 523 of 698 trades sit at mean multiplier **1.493**, i.e. pinned at the 1.5 ceiling |
| **candidate order in production** | `candidate_rank` is **not passed**, so scarce capital is allocated **alphabetically** |

The second and third are the same fact: conviction multiplies *after*
the 0.5% budget is applied, and because mean-reversion entries are deep
pullbacks by construction, most of them clear the 8%-drawdown threshold
for the full 1.5×. **The stated 0.5% risk budget actually delivers
~0.69%, and conviction is functioning as a near-constant 1.5× uplift
rather than as a discriminator.**

The fourth explains H-0009's churn finding exactly: the bucket cap is
resolved in candidate order, and that order is the alphabet.

## Does sizing couple to selection?

Yes, in two places, and both are small:

- `if quantity <= 0: continue` — sizing can drop a candidate outright.
- `if outlay > cash: rejected_for_capacity` — 3.2% of candidates.

So a sizing change is *mostly* pure redistribution, but the coupling is
real and any experiment must measure it rather than assume it away.

## Is the equal-risk assumption violated?

Equal-risk asserts expected R does not depend on stop distance. Testing
that is calibration of an **existing** input, not feature-fishing.

| ATR quartile | n | mean ATR | **mean size** | mean R | median R | win |
|---|---|---|---|---|---|---|
| **Q1 tightest** | 175 | 1.19% | **17.27%** | **−0.041** | **−0.289** | 45.7% |
| Q2 | 174 | 1.97% | 14.30% | +0.171 | +0.244 | 55.2% |
| Q3 | 174 | 2.45% | 11.84% | +0.105 | +0.131 | 54.0% |
| Q4 widest | 175 | 3.09% | 9.50% | +0.088 | −0.028 | 49.7% |

**Spearman(ATR, R) = +0.0596**, against a 2-SE noise band of 0.076. So
there is **no monotone relationship** — the formal answer is that
equal-risk is *not detectably miscalibrated*.

But the table is not flat. It is an inverted U with **Q1 as the
outlier**, and Q1 is precisely where the formula puts the most capital.
Sizing is inversely proportional to ATR, so the tightest-ATR names get
17.27% of equity each and return a median of **−0.289R**.

## Do large positions earn their capital?

| size quintile | n | mean size | notional | P&L | **per $1,000** |
|---|---|---|---|---|---|
| **Q1 largest** | 139 | 18.17% | **$3,050,759** | **−$306** | **−$0.10** |
| Q2 | 140 | 14.81% | $2,550,172 | $17,554 | +$6.88 |
| Q3 | 139 | 12.87% | $2,260,287 | $13,381 | +$5.92 |
| Q4 | 140 | 11.09% | $1,989,078 | $15,781 | **+$7.93** |
| Q5 smallest | 140 | 9.24% | $1,677,615 | $11,151 | +$6.65 |

**26% of all notional deployed earns zero.** The other four quintiles
cluster tightly at $5.92–$7.93 per $1,000.

## Is it stable? Yes — 3 of 3, both ways

Chronological thirds, declared before computing.

| period | largest-quintile $/1k | rest $/1k |
|---|---|---|
| early | 2.27 | 4.09 |
| middle | 2.98 | 7.82 |
| late | **0.57** | 6.38 |

| period | tightest-ATR $/1k | rest $/1k | Q1 mean R |
|---|---|---|---|
| early | 1.09 | 4.75 | +0.085 |
| middle | 0.52 | 9.34 | −0.161 |
| late | **−0.01** | 7.14 | −0.056 |

**Worse in 3 of 3 periods on both cuts.** After H-0007, H-0008, H-0009,
post-stop, regime, buckets, news and copy-trading, this is the first
structural effect to survive a time split cleanly.

## The problem with acting on it

Note the mean R for tight-ATR is not reliably negative (+0.085, −0.161,
−0.056). **These trades do not lose money — they earn very little while
consuming the most capital.** That is an allocation inefficiency, not a
selection problem, and it changes what a fix can achieve.

Shrinking those positions frees capital. **That capital has nowhere to
go.** The 12-position cap never binds, 52.1% of sessions produce no
candidate at all, and cash blocks only 3.2% of candidates. Freed
capital becomes idle cash at 0% — which is H-0006's lesson.

So an ATR floor in the sizing denominator is **case C, exposure
reduction**, not case A, redistribution. Expected consequences: total
return roughly flat (the block earns ~$0 anyway), drawdown and
volatility down, Sharpe and return-per-unit-exposure up, and **excess
return versus SPY slightly worse** because exposure falls.

Making it true redistribution requires a compensating uplift to
`risk_per_trade`, and choosing that uplift from this data is in-sample
fitting. The clean alternative — which your brief already mandates — is
to report raw *and* exposure-normalised performance and judge on
return per unit of exposure and risk.

## One further warning, stated before any registration

A **minimum-ATR entry filter** has already been tested and **rejected**:
floors of 0.800% / 1.000% / 1.250% / 1.500% gave +1.9 / +1.0 / **+7.5**
/ −2.2 points — explicitly recorded as *"NOT monotone, which is the
signature of noise rather than a mechanism."* My Q1 sits at 1.19% mean
ATR, inside that swept region.

Sizing is not removal, and there is a mechanistic reason to expect a
smoother surface: H-0009 established that removing candidates causes
churn through the alphabetical bucket resolution, whereas a sizing
change leaves selection almost untouched. That is a genuine prediction
and it is testable — **if the sizing surface is also non-monotone, the
region is noise and the whole direction closes.**

## Proposed H-0010 — exact registration, NOT sealed

> **Hypothesis.** Equal-risk sizing allocates capital inversely to ATR,
> which mechanically concentrates the book in the tightest-ATR names —
> 17.27% of equity each — and that quintile of notional returns
> approximately zero. Imposing a floor on the ATR used **for sizing
> only** improves return per unit of exposure and reduces drawdown,
> without changing which candidates are selected.
>
> **Exact parameter.** A floor `f` applied to the ATR term in the
> sizing denominator only: `loss_per_share = (entry − stop) + costs`
> becomes `(entry − stop_sizing) + costs` where
> `stop_sizing = entry − 2.5 × max(ATR, f × entry)`. **The real stop,
> the entry, the exit, the holding cap, the bucket cap, the position
> cap, the per-day cap, candidate ordering and `rsi_entry = 35.0` are
> all unchanged.** The traded stop is untouched — only the size is.
>
> **Family.** Three floors: `f ∈ {1.25%, 1.50%, 1.75%}`. Chosen as
> integer quarter-points spanning the Q1/Q2 ATR boundary (Q1 mean 1.19%,
> Q2 mean 1.97%). No fourth value may be added after the surface is
> visible.
>
> **Declared direction.** Exposure FALLS monotonically with `f`. Max
> drawdown SHALLOWS monotonically. Return per unit exposure RISES.
> Total return AMBIGUOUS and deliberately not predicted. Excess return
> versus SPY expected to WORSEN, because exposure falls and freed
> capital earns 0%.
>
> **Acceptance — ALL FIVE.**
> (A) **Return per unit of exposure** exceeds baseline's by more than
> 10% relative, for at least one floor.
> (B) `abs(max_drawdown) ≤ 14.2806%` — the ceiling is unchanged.
> (C) **Gradient, not spike:** the return-per-exposure improvements are
> monotone in `f`, and the largest ≤ 2.5× the second largest.
> (D) **Selection is not the cause:** at least 95% of baseline entries
> must also be taken by the configuration. A configuration that changes
> which trades happen is measuring something else and is rejected.
> (E) Survives leave-one-best-year-out and the early/middle/late thirds.
>
> **Rejection.** Any clause fails. Registered expectation: the family
> may fail (C) the way the min-ATR *filter* family did, and if it does,
> the ATR region is noise and the direction closes. Higher total return
> alone is insufficient; lower exposure alone is insufficient.
>
> **Exposure normalisation (mandatory, registered):** report gross
> exposure mean/median/max, average per-trade risk, aggregate portfolio
> risk, return per unit exposure and return per unit risk, for baseline
> and every floor.
>
> **Ceiling:** research_evidence. Changing sizing in production is a
> separate registration with a new fingerprint.

## My recommendation

**Run it, with expectations set low.** The effect is the first stable
structural finding in eight passes and the mechanism is understood, so
it is worth one registration. But I expect it to improve risk-adjusted
metrics and *not* excess return versus SPY, which is the stated primary
objective — and clause A is deliberately written on return-per-exposure
rather than total return so that outcome is recorded honestly rather
than dressed up.

If you would rather not spend a slot on a hypothesis whose best
realistic outcome is "better Sharpe, worse SPY gap," say so and I will
close the sizing branch on this audit alone. That is a defensible call.

**A separate, cheaper item worth doing either way:** the conviction
multiplier is saturated at 1.5 for 75% of trades, so the declared 0.5%
risk budget is really 0.69%. That is a documentation/correctness
discrepancy rather than an economic one, and it should be recorded
regardless of what happens to H-0010.

---

# SECTION 2 — Form 4 feasibility

**Not started. No data acquired. No experiment designed.** Per your
instruction this stays behind H-0010.

## What I can state, and what I have NOT verified

I have **not** made any network request to SEC EDGAR from this
environment. Everything below is either verifiable-in-principle
structure or an explicit unknown. The honest first step is an access
probe, not a design.

| requirement | status |
|---|---|
| legally accessible source | **Believed yes** — SEC EDGAR is public, free, no authentication, with a published fair-access policy (declared User-Agent, rate limit). **Must be verified from this machine**; I have not tried. |
| filing timestamp | **Believed yes** — EDGAR records an acceptance datetime, which is the genuine *availability* timestamp, distinct from the transaction date. This is the property the news archive lacked. |
| transaction timestamp | **Believed yes** — Form 4 carries a transaction date field separate from the filing date. |
| issuer/security identification | CIK is native. **Ticker mapping is the weak point** — requires SEC's CIK↔ticker mapping, which is maintained *as of today* and is therefore a survivorship hazard for delisted names. |
| historical coverage | Electronic Form 4 has been mandatory since 2003, so a decade of coverage is plausible. **Unverified.** |
| amendments | Form 4/A exists; a point-in-time reconstruction must use the original and treat the amendment as a later event, never retroactively. |
| missing filings | Unknown and **unmeasurable from the filings alone** — a late or absent filing leaves no trace. |
| survivorship | **Structurally good** — filings persist after delisting, unlike the trader feeds that don't exist. Offset by the ticker-mapping problem above. |
| acquisition reproducibility | Plausible (stable URLs, daily index files). **Unverified.** |

## The two questions that decide it, before any acquisition

**1. Does it arrive early enough to matter?** Sarbanes-Oxley §403
requires filing within 2 business days of the transaction. The
strategy's effective holding period is ~14 sessions, so a 2-day lag is
*not* structurally fatal the way 13F's 45-day lag is. This is the main
reason Form 4 is worth considering at all.

**2. Is it genuinely new information, or a price/volume proxy?** This
is the one that would kill it, and it is testable cheaply **before**
building anything: if insider-purchase dates cluster on days already
flagged by unusual volume or by the existing RSI/ATR features, then the
signal is already in the bars and adds nothing. The news branch failed
partly for the analogous reason — the earnings filter was
indistinguishable from an any-news control.

## Proposed order of work, if and when you open it

1. **Access probe only.** One request, confirm reachability, terms and
   rate limits. Report, stop.
2. **Coverage audit.** How many Form 4 filings map to the 230-name
   universe over the decade, with what filing-date distribution and
   what fraction of the universe covered per year.
3. **Redundancy test.** Do filing dates coincide with days the existing
   features already mark? If yes, stop — it is a proxy.
4. Only then design a hypothesis.

Steps 1–3 are cheap and each can close the branch. None of them
requires a registration.

## Governance

| check | result |
|---|---|
| frozen fingerprint | `da22011e…c237b` — **unchanged** |
| production source | **unchanged**; `src/` clean |
| `rsi_entry` / bucket cap / max positions | 35.0 / 1 / 12 — unchanged |
| learned ranker / veto | `False` / `False` |
| exit haircut / drawdown ceiling | 0.652% / 14.2806% — unchanged |
| clean OOS | **untouched** |
| registrations | 9, chain intact — **H-0010 NOT sealed** |
| promotion candidates | **none** |
| thirty-year reads | **13** |

## Artefacts

- `scripts/audit_sizing.py`
- `docs/phase5/sizing-audit.json`
