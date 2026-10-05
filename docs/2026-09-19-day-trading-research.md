# Day trading to beat SPY — what the persistent minority actually does

*Read-only research. Nothing registered, nothing implemented, no configuration
touched. Commissioned 2026-09-19 to answer: can this bot be made a day trader
that outperforms SPY, and what do the people who genuinely manage it do?*

---

## 0. The answer in one paragraph

A persistently profitable day-trading minority **does exist and is
statistically real** — it is not survivorship illusion, and the best-measured
cohort beat SPY by a wide margin. But it is roughly **0.1–1% of participants**,
it is concentrated in **liquidity provision rather than liquidity taking**, and
the specific shape proposed — *100% of capital in for five minutes, then out* —
is the single worst configuration in the whole design space, because it
maximises the one term that destroys day traders (cost × frequency) while
discarding the one term that makes SPY hard to beat (the overnight drift).
Below: the three structural facts, who the top actually are, what they trade,
what they look for, and the four leads that survive contact with this bot.

---

## 1. Three structural facts that decide the question before strategy enters

### 1.1 At high frequency, transaction cost *is* the strategy

This bot's shipped `CostModel` assumes 6 bps one-way (2 bps half-spread +
4 bps slippage), so **12 bps per round trip**. Holding that fixed and varying
turnover at full deployment:

| trades/day | trades/yr | friction alone | gross needed to break even | gross needed to beat SPY |
|---|---|---|---|---|
| 0.25 (the bot today) | 63 | −7.29% | +7.9% | +22.3% |
| 1 | 252 | −26.11% | +35.3% | +53.5% |
| 3 | 756 | −59.66% | +147.9% | +181.1% |
| 5 | 1,260 | −77.97% | +354.0% | +414.9% |
| 10 | 2,520 | −95.15% | +1,961.1% | +2,237.7% |
| 20 | 5,040 | −99.76% | +42,380.6% | +48,081.5% |

Now the same thing expressed as edge per trade:

| trades/day | net bps needed per trade | **gross bps needed** | of which is pure friction |
|---|---|---|---|
| 0.25 | 20.01 | 32.01 | 37% |
| 1 | 5.00 | 17.00 | 71% |
| 3 | 1.67 | 13.67 | 88% |
| 10 | 0.50 | 12.50 | **96%** |
| 20 | 0.25 | 12.25 | **98%** |

**This is the whole game.** As frequency rises the required gross edge converges
to the round-trip cost. At ten trades a day, 96% of every basis point you
extract goes to the spread and slippage, and your entire economic return is the
4% sliver on top. You are not competing against the market; you are competing
against your own fill quality, and the market is merely the noise you have to
see through to do it.

This also explains the direction of the whole program's findings so far: the
existing sensitivity table in `risk.py` says **about four points of decade
return per basis point** of one-way cost, measured on 698 trades. Multiply the
trade count by 40× and that sensitivity multiplies with it.

### 1.2 SPY's return is an overnight phenomenon — verified on this repo's own data

Decomposing `data/SPY.csv`, 549 sessions, 2024-07-10 → 2026-09-17, into the
overnight leg (close → next open) and the intraday leg (open → close):

| leg | total | annualised | share |
|---|---|---|---|
| buy and hold (close → close) | **+35.86%** | **+15.10%** | 100% |
| **overnight only** | **+29.25%** | **+12.50%** | **82%** |
| **intraday only** | **+5.11%** | **+2.31%** | **18%** |

(The two legs multiply back to the total exactly, so this is an identity, not a
fit.) This is not a local quirk — Cooper, Cliff and Gulen documented it on
1993–2003 S&P 500 data and found the equity premium accrues *entirely*
overnight, holding for individual stocks, indices and index futures alike, and
it has persisted since.

**The consequence is severe and is usually missed.** A day trader who is flat
every night has voluntarily left the pool where 82% of the benchmark's return
lives. They are fishing in a puddle that drifts up +2.31%/yr while being
measured against a benchmark earning +15.10%/yr. Before costs, before strategy,
before anything, **a flat-overnight trader starts roughly 12.8 points per year
behind SPY** and must manufacture all of it from intraday skill.

Stack that on §1.1 and the bar for "100% in for 5 minutes" becomes: generate
~12.8 points/yr of genuine intraday alpha *and* out-earn a friction drag that
runs from −26% to −95% per year depending on how often you do it.

### 1.3 In aggregate, day trading is negative-sum, and the average is badly negative

- **Taiwan, 1992–2006, effectively the entire population** (Barber, Lee, Liu,
  Odean — 3.7bn transactions): day traders lost an average of **−23.9 bps per
  day net of fees**. Less than **1%** were able to predictably and reliably earn
  positive abnormal returns net of fees.
- **Brazil, 2013–2015, equity index futures, every new entrant tracked**
  (Chague, De-Losso, Giovannetti): of those who persisted **more than 300
  days**, **97% lost money**. Only **1.1%** earned more than the Brazilian
  minimum wage; only **0.5%** earned more than a bank teller's starting salary.
  The single best individual earned **US$310/day with a standard deviation of
  US$2,560**. The authors found **no evidence of learning**.
- **US, 324 traders, 1998–1999** (Jordan & Diltz): ~**20%** were more than
  marginally profitable — and that window was the internet bubble, i.e. about
  as favourable as the sample gets.
- **Crypto retail** (BIS Bulletin 69, 200+ exchange apps, 95 countries,
  2015–2022): under a constant-buying assumption **81% would have lost money**;
  75% of users entered *after* the price cleared $20,000. Large holders sell
  into retail entry.

Two of those four are whole-population administrative datasets, which is as
good as evidence gets in this field. The honest summary: the base rate is
brutal, and it gets worse the longer people persist, not better.

---

## 2. So who *are* the top 1%?

This is the part the loss statistics obscure, and it is the part worth taking
seriously. **Skill in this domain is real, cross-sectionally large, and it
persists.** Barber, Lee, Liu and Odean sorted Taiwanese day traders on past
performance and then measured what the sorted groups earned *going forward*:

| cohort | before fees | **after fees** |
|---|---|---|
| top 500 ranked day traders | 61.3 bps/day | **+37.9 bps/day** |
| bottom-ranked day traders | −11.5 bps/day | **−28.9 bps/day** |

That spread is enormous and it is out-of-sample by construction. For scale,
this bot's frozen baseline earns **1.72 bps/day** and SPY price-only earns
**5.00 bps/day**. The top Taiwanese cohort cleared roughly **seven times SPY's
daily rate, after fees**.

> *Caveat I will not paper over:* compounding an arithmetic daily mean to
> "+159%/yr" overstates realised growth — it ignores variance drag and assumes
> they trade every session. Treat 37.9 bps/day as the finding and any
> annualisation as illustrative only. Also, 500 of ~360,000 is **0.14%**.

The second cohort worth studying is the one that actually dominates intraday
markets. Baron, Brogaard and Kirilenko, on E-mini S&P 500 futures audit-trail
data, found HFT firms take money from **every** other category: roughly
**$146,005/day from fundamental investors, $89,874/day from non-HFT market
makers, and $50,328/day from small traders**. Within HFT, passive strategies
lose to mixed, and mixed lose to aggressive — but the critical finding for our
purposes is that **passive HFT is profitable even without liquidity rebates**,
while aggressive HFT is not, in at least one study of the same market.

**Read those two results together and the picture is unambiguous: the top of
the intraday distribution is populated by participants who are paid the spread
rather than paying it.** The retail day trader sending market orders is, in the
E-mini data, literally an identified revenue line item for the other side.

### The funded-account industry is not the exception

Industry-published figures (weaker sourcing — these are marketing-adjacent, so
treat as indicative, not measured): challenge pass rates **5–14%**; about
**45%** of *funded* traders receive at least one payout, but only about **7% of
all challenge buyers** ever receive any payout; an estimated **1–3%** become
consistently paid long-term. **60–70% of failures are drawdown breaches, not
missed profit targets.** Note what that last number means: the binding
constraint is risk control, not signal — the same conclusion this program
reached independently when every H-0010 configuration breached the drawdown
ceiling.

---

## 3. What the persistent winners actually do differently

Synthesising across the microstructure literature and the cohort studies, the
profitable minority is characterised by a consistent set of choices — and
almost none of them are "a better entry signal."

1. **They provide liquidity instead of consuming it.** This is the single
   largest discriminator, and it is an arithmetic sign flip, not a preference.
   Against this bot's own cost model:

   | | half-spread | slippage | rebate | per side | round trip |
   |---|---|---|---|---|---|
   | taker (market order) | −2.00 | −4.00 | 0 | −6.00 bps | **−12.00 bps** |
   | maker (resting limit) | +2.00 | 0 | +0.25 | +2.25 bps | **+4.50 bps** |

   A **16.5 bps swing per round trip.** The taker at 10 trades/day needs
   +1,961% gross to reach flat; the maker's friction term is *positive* before
   any directional view at all. The real cost of being a maker is **adverse
   selection** — you get filled precisely when you are wrong — and that is what
   the "passive HFT profitable without rebates" result is measuring net of. But
   the sign of the friction term genuinely flips, and that is why the top of
   the distribution lives there.

   *This is the same mechanism this program already found independently:* the
   H-0010 adjudication measured **$58,857 of avoided haircut across 987 trades**
   purely because take-profit exits are resting limits rather than market
   orders. That was flagged as the largest single effect in the whole research
   program, larger than any strategy effect. It is the identical finding
   arriving from a different direction.

2. **Tiny per-trade edge, enormous trade count, ruthless cost discipline.**
   Nobody in this cohort is looking for 5% moves. They are looking for 1–3 bps
   of expectancy repeated tens of thousands of times, which only works if
   fills are near-costless.

3. **Extreme instrument concentration.** One or two products, learned to
   exhaustion — ES/NQ, or a handful of names. Breadth is a retail habit.

4. **Hard, pre-committed loss limits.** Consistent with drawdown breaches being
   60–70% of prop-firm failures, survival is governed by the loss cap, not the
   win rate.

5. **Capacity self-awareness.** The Taiwan top-cohort edge is measured on small
   accounts. Most intraday edges are capacity-constrained: they work at $50k
   and evaporate at $50m. This cuts *for* a small account — it is the one
   genuine structural advantage a retail-scale operator has.

6. **They do not hold overnight risk they are not paid for** — but note they
   also do not pretend the intraday pool is as rich as the overnight one. They
   are explicitly playing a different, smaller game and sizing accordingly.

---

## 4. What they trade, and why

> **Correction, 2026-10-04.** The PDT points below are out of date.
>
> - The SEC approved FINRA's amendments to Rule 4210 on 2026-04-14, effective
>   2026-06-04; brokers have until 2027-10-20 to implement them.
> - The pattern-day-trader designation and the $25,000 minimum no longer
>   exist. Every margin account now follows an intraday margin standard that
>   tracks actual exposure.
> - "No PDT rule" is therefore no longer an advantage of futures.
>
> Source and details: `2026-10-04-day-trading-everything-else.md` §3.7.

### Futures (ES/MES, NQ/MNQ, CL, GC) — the standard professional venue

**Why it is chosen:**
- **No PDT rule.** FINRA Rule 4210's $25,000 pattern-day-trader minimum applies
  to margin accounts at FINRA-regulated broker-dealers. Futures are CFTC/NFA
  regulated and fall outside it entirely.
- **Section 1256 tax treatment.** Futures gains are marked to market and split
  **60% long-term / 40% short-term regardless of holding period** — a blended
  top federal rate around **26.8%** versus **37%** ordinary on an equivalent
  equity day trade. **On a day-trading strategy this is ~10 points of after-tax
  return handed over for free**, and it is the most reliable "edge" in this
  entire document because it requires no forecasting skill whatsoever.
- **Exempt from wash-sale rules**; Section 1256 losses can be carried back up
  to three years.
- Micro contracts carry **$50–$200** day margin, deep books on ES, nearly 23/5
  hours, and no short-locate requirement.

**Why it kills people:** that same margin means a micro-contract account can
lose multiples of deposit on a normal day. Leverage is the mechanism through
which the 97% figure is realised.

### Crypto — 24/7, structurally worse

Advantages are real: no PDT, no market-hours constraint, genuine volatility,
and perpetual-swap funding rates create a *carry* term that has nothing to do
with price forecasting. Disadvantages dominate for a cost-sensitive strategy:
wider spreads, thinner books outside majors, exchange/counterparty risk, and
a retail-loss profile (BIS: 81%) at least as bad as equities. **Note also that
§1.2 does not apply — crypto has no overnight session to forgo, so the
"day trader forfeits the drift" objection is weaker here.** That is the one
genuine structural argument for crypto over equities in this context.

### Equities — best data and tooling, worst rules

PDT $25,000 minimum in margin accounts (a cash account escapes PDT but is
bounded by T+1 settlement), full borrow/locate friction on shorts, and short-
term gains taxed as ordinary income. Best-in-class data and infrastructure.

**Hard constraint on this bot:** *Alpaca does not offer futures.* Stocks, ETFs,
options and crypto only. The instrument class with the strongest structural
case — futures, for the tax treatment and PDT exemption alone — **is not
reachable from the current brokerage at all.**

---

## 5. What they specifically look for

Separated honestly by evidence quality, because most published day-trading
"setups" have none.

**Documented in peer-reviewed microstructure literature:**
- **Order flow imbalance (OFI).** Cont, Kukanov and Stoikov: short-horizon
  price changes are approximately a **linear function of order flow imbalance
  at the best bid and ask**, with slope **inversely proportional to market
  depth** — the same imbalance moves a thin book much further than a deep one.
  Stable across a large cross-section of US stocks and across intraday sampling
  scales. This is the most reproducible relationship in the field and is a
  standard input at trading firms. **It requires level-2 / full order book
  data, which this project does not have in any form.**
- **The overnight/intraday split** (§1.2) — tradeable as a systematic tilt,
  and notably *not* a day-trading strategy.
- **Adverse selection / queue position** — the actual economics of passive
  fills.

**Widely used, weakly evidenced in public literature** (relative volume, gap
percentage, float rotation, VWAP reversion, opening-range breakout, prior-day
high/low, session levels): these are the standard retail vocabulary. Some
almost certainly encode real microstructure, but public evidence is thin and
heavily contaminated by publication and survivorship bias. **I would treat
every one of them as unproven until measured here — which is exactly how this
program has treated every other candidate, and eleven of eleven have failed.**

**What the top cohort looks for that retail does not:** queue position, fill
probability, adverse-selection cost, rebate tier, latency to venue, and
*capacity* — i.e. execution quality variables, not chart patterns.

---

## 6. The specific proposal: "100% in for 5 minutes, then out"

Taken literally, this configuration is dominated on every axis:

- **Cost.** At even 3 round trips/day it needs **+181% gross annually** to beat
  SPY. At 10, **+2,238%**.
- **Overnight.** It discards 82% of the benchmark's return stream by design.
- **Concentration.** 100% of capital in one name at a time removes
  diversification entirely; the current bucket cap of 1 and 12-position limit
  exist precisely to bound this, and every drawdown clause in the program keys
  off it. A single 2% adverse gap on full deployment is a 2% account loss, and
  gaps are not bounded by your stop.
- **Drawdown governance.** The 110% ceiling of **14.2806%** is already the
  binding constraint that rejected every H-0010 configuration. A fully
  deployed, high-frequency, flat-overnight strategy would breach it in normal
  conditions, let alone stressed ones.
- **It is the taker side of §3.1.** Five-minute holds with hard exits are
  market orders by necessity — you are paying the 12 bps, not earning the
  4.5 bps, on every one of thousands of round trips.

The direction that the evidence actually supports is the **inverse**: fewer
trades, not more; resting limits, not market orders; overnight exposure kept
rather than discarded; and position sizing bounded well below 100%.

---

## 7. What survives contact with this bot — four leads, ranked

Ranked by expected value per unit of work, all read-only, none registered.

**1. Execution — make exits resting limits (already measured, already the
program's largest finding).** H-0010 quantified **$58,857 avoided haircut
across 987 trades**, larger than any strategy effect found in 39 experiments.
§3.1 says the top of the day-trading distribution is defined by exactly this
sign flip. This needs its own registration and it is the highest-value open
item in the project. **It is an execution change, not a day-trading change.**

**2. Overnight/intraday tilt — the opposite of day trading.** §1.2 shows the
overnight leg earns +12.50%/yr against intraday's +2.31%/yr on this repo's own
SPY data, and it is computable from the daily bars already on disk with no new
data feed. If any part of the day-trading question deserves a registered
experiment, it is this one — and it argues for holding *more* overnight, not
less.

**3. Section 1256 tax treatment — real, large, and requires no skill.** ~10
points of after-tax return on a day-trading book. **Blocked: Alpaca offers no
futures.** Worth knowing; not actionable here.

**4. Crypto's 24/7 structure.** The one venue where the §1.2 objection does not
bite, and 10 pairs are already in `data/`. Costs are worse, which per §1.1 is
the term that matters most. Low priority.

**Not worth pursuing:** OFI and any genuine microstructure edge. They need
level-2 order book data, sub-second execution, colocation and maker rebates.
This project has **daily OHLCV bars only** — 550 rows per symbol — and a
brokerage with no futures. The gap between that and the venue where intraday
edges live is not a tuning gap; it is a different business.

---

## 8. The honest bottom line

The top 1% is real, it persists, and it beats SPY decisively. It gets there by
**being paid the spread, on one or two instruments, with tiny per-trade edge
repeated enormously often, under hard loss limits, at small capacity** — and
increasingly it is a firm with colocated servers, not a person. The retail
day trader sending market orders appears in the best intraday dataset we have
as a **$50,328/day revenue line for the other side.**

For this bot specifically: the research says the profitable direction is
**better fills on the trades it already takes**, not more trades. That finding
was already sitting in the H-0010 report, and this survey's main contribution
is independent confirmation, from an entirely separate literature, that it is
the right lead — and that the day-trading framing points the other way.

---

## Sources

Peer-reviewed / primary:
- Barber, Lee, Liu, Odean — *The Cross-Section of Speculator Skill: Evidence from Day Trading*, J. Financial Markets (2014) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=529063
- Barber, Lee, Liu, Odean, Zhang — *Do Day Traders Rationally Learn About Their Ability?* — https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf
- Chague, De-Losso, Giovannetti — *Day Trading for a Living?* (2020) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101
- Jordan & Diltz — *The Profitability of Day Traders*, Financial Analysts Journal 59(6), 2003 — https://www.tandfonline.com/doi/abs/10.2469/faj.v59.n6.2578
- Cooper, Cliff, Gulen — *Return Differences between Trading and Non-Trading Hours* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Cont, Kukanov, Stoikov — *The Price Impact of Order Book Events*, J. Financial Econometrics (2014) — https://arxiv.org/pdf/1011.6402
- Baron, Brogaard, Kirilenko — *The Trading Profits of High Frequency Traders* — https://conference.nber.org/confer/2012/MMf12/Baron_Brogaard_Kirilenko.pdf
- BIS Bulletin 69 — *Crypto shocks and retail losses* (2023) — https://www.bis.org/publ/bisbull69.htm
- SEC — *Equity Market Structure Literature Review Part II: High Frequency Trading* (2014) — https://www.sec.gov/marketstructure/research/hft_lit_review_march_2014.pdf

Regulatory / tax:
- FINRA pattern day trader rule — https://en.wikipedia.org/wiki/Pattern_day_trader
- Section 1256 contracts and 60/40 — https://greentradertax.com/trader-tax-center/tax-treatment/section-1256-contracts/
- Alpaca asset classes — https://alpaca.markets/

Industry-published (weaker sourcing, treat as indicative):
- Prop firm pass/payout statistics — https://track360.io/blog/prop-trading-industry-statistics-2026

Computed here, on this repo's data:
- Cost/turnover arithmetic against the shipped `CostModel` (6 bps one-way)
- SPY overnight/intraday decomposition, `data/SPY.csv`, 549 sessions
- H-0010 haircut figures, `docs/phase5/h0010-adjudication.json`
