# Day trading, part III — the mechanism, the moat, and the ladder

*Read-only. Nothing registered, nothing implemented, no configuration touched.
Third and final instalment. Parts I and II established that the top 1% is real
and that it earns the spread rather than paying it. This one answers the
harder question: by what **mechanism** does a tiny per-trade edge become a
return that beats SPY — and what stops anyone else from copying it.*

---

## 1. The √N law — this is the actual answer

Everything else in these three documents is commentary on one equation.

For independent bets with a fixed edge-to-noise ratio per bet, the Sharpe
ratio of the *strategy* scales with the square root of the number of bets:

```
Sharpe_annual  =  (edge per bet / sd per bet)  ×  √N
```

**The best day traders do not have bigger edges than you. They have the same
tiny edge, applied more times.** Measured on this bot's own 698 trades, the
per-trade edge-to-noise ratio is **0.07760**. Holding that constant and varying
only N:

| trades/yr | implied Sharpe | comparable |
|---|---|---|
| 65 *(the bot today)* | **0.63** | matches the bot's realised 0.5107 |
| 252 | 1.23 | a good systematic equity fund |
| 756 | 2.13 | an excellent fund |
| 2,520 | 3.90 | approaching HFT territory |
| 10,000 | **7.76** | top-tier HFT |
| 50,000 | 17.35 | the very top |

This is the whole game, stated in one table. A Sharpe-8 high-frequency firm
is **not** finding trades eight times better than this bot's. It is finding
trades of *roughly the same quality* and taking 150× as many of them.

**And this is the only honest argument for high frequency that exists.** It is
also strictly conditional, on a condition this program has already tested and
failed:

> **√N only helps if the per-trade edge-to-noise ratio survives the increase
> in N.** H-0007 forced this bot to trade more and selection-per-dollar
> collapsed from **0.2068% to 0.0575%** — a 72% decay. If edge/sd falls faster
> than √N rises, frequency makes things worse, not better.

That is precisely why the profitable minority does not simply "trade more."
They first do the thing that makes the edge survivable at scale — drive the
cost per trade to zero or below by earning the spread — and *then* scale N.
The order is not optional. Scaling N first is what the −23.9 bps/day Taiwan
population did.

---

## 2. The Sharpe ladder, with real numbers

| | Sharpe | source |
|---|---|---|
| **this bot, frozen decade** | **0.5107** | measured, rf = 0 |
| SPY buy-and-hold | ~0.65–0.75 | same window |
| good discretionary macro | 0.5–1.0 | industry |
| good systematic equity | 1.0–2.0 | industry |
| Medallion, net, 1988–2018 | ~2.5+ | reported **66.1% gross / 39.1% net** avg annual |
| **median HFT firm, E-mini audit trail** | **4.5** | Baron/Brogaard/Kirilenko, Aug 2010 |
| persistent HFT risk-adjusted performance | **4.3 annualised** | same authors |
| **top HFT firms** | far higher | fastest firms occupy the upper tail |

Two things to notice.

**First, the ladder is a ladder of N, not of insight.** Medallion's reported
edge is famously described as being right barely more than half the time —
the return comes from doing it constantly across thousands of positions. The
distance from 0.51 to 4.5 is almost entirely the √N term.

**Second, the return decomposition inside HFT is striking:** the average
*aggressive* HFT earns an annualised alpha of **90.67%**, the average *passive*
HFT **23.22%**. Aggressive is more profitable — but aggressive is also the
latency-dependent, arms-race-exposed half of the business, and it is where
the capital and speed requirements live. Passive earns a quarter as much and
requires no race wins. **For anyone without colocation, passive is the only
reachable half**, which is the same conclusion Part II reached from the cost
model.

For scale on the pool being fished: **31 HFT firms earned over $33 million in
trading profits in a single month in one contract** — the E-mini S&P 500.

---

## 3. The moat, quantified

This is the part that answers "why can't I just do what they do."

**Latency arbitrage races** (Aquilina, Budish & O'Neill, QJE 2022 — measured on
exchange *message* data, so both winners and losers of each race are visible,
which order-book data cannot show):

| | value |
|---|---|
| race frequency | **~one per minute per symbol** (FTSE 100) |
| modal race duration | **5–10 millionths of a second** |
| share of all trading volume in races | **~20%** |
| **top six firms' share of race wins** | **>80%** |
| latency arbitrage "tax" on trading | **~0.5 bps** |
| reduction in cost of liquidity if eliminated | **17%** |
| total annual prize, global equities | **~$5 billion** |

Read the second and fourth rows together. **The contest is decided in five
microseconds, and six firms win more than eighty percent of it.** Light travels
about 1.5 km in 5 µs. This is not a skill gap that study closes; it is a
physics-and-capital gap.

The earlier Budish–Cramton–Shim result adds the crucial dynamic: between 2005
and 2011 the median duration of an arbitrage opportunity fell from **97
milliseconds to 7 milliseconds** — a 14× speed improvement — and **the
profitability stayed constant.** The arms race consumed the entire speed gain.
It is a rent that gets competed over, not a service whose price falls.

**Barriers to entry are empirically confirmed, not just theorised.** The same
audit-trail research finds that HFT profits are *persistent*, that **new
entrants have a higher propensity to underperform and exit**, and that firms
which improve their latency *rank* through colocation upgrades see their
trading performance improve. Speed is causal, relative, and purchasable — which
means it is an auction, and the auction has already been won.

---

## 4. Who is actually on the other side of your trades

The firms at the top of this distribution are not obscure:

| firm | 2025 net trading revenue | notes |
|---|---|---|
| **Jane Street** | **$39.6bn** | nearly 2× the $20.5bn of 2024; >10% of North American equity trading; #1 in ETFs. Q1 2026 alone: $16.1bn revenue, $10.3bn net income |
| **Citadel Securities** | **$12.2bn** | up 25% from $9.7bn; ~$6.5bn EBITDA; $21bn trading capital |

Non-bank trading firms now take roughly **a fifth of global trading revenue**,
projected toward **30% by the end of the decade**.

Put Part I's PFOF finding next to this. Wholesalers pay brokers for retail
marketable order flow *because it is uninformed*, and the firms doing that
paying are booking tens of billions a year. **When you send a market order as
a retail day trader, one of these firms has bid for the right to take the other
side, and their published results are what that decision is worth to them.**

---

## 5. Capacity — the one axis where a small account genuinely wins

Every edge above is capacity-constrained. Medallion's defence is to stay
small and closed. This is the single structural advantage available to a
$99,000 account, so it is worth knowing exactly how much of it this bot has.

The binding rule is the **2% ADV participation cap** against the **$50M minimum
ADV** liquidity floor:

| equity | 20% position size | % of a $50M-ADV name | cap breached? |
|---|---|---|---|
| $100,000 | $20,000 | 0.04% | no |
| $1,000,000 | $200,000 | 0.40% | no |
| **$5,000,000** | **$1,000,000** | **2.00%** | **at the limit** |
| $10,000,000 | $2,000,000 | 4.00% | **YES** |
| $50,000,000 | $10,000,000 | 20.00% | **YES** |

**Capacity binds at roughly $5,000,000 of equity.** The current paper account
is ~$99,000 with an average position of $16,516 (13.4% of equity) — that is
**0.040% of a minimum-liquidity name, 51× below the cap.**

**The bot has about 51× of headroom before capacity is the constraint.** That
is real and it is worth stating plainly: whatever else is wrong with this
strategy, size is not currently one of the problems, and won't be for a long
way. It is also the reason not to chase the strategies in §3 — those are
capacity-rich businesses that exist *because* they can absorb billions, and
they have competed the returns down accordingly.

---

## 6. Alpha decay — and an honest test of this bot

**McLean & Pontiff** studied 97 published cross-sectional return predictors:
portfolio returns are **26% lower out-of-sample** and **58% lower
post-publication**. The out-of-sample decline bounds data-mining effects; the
extra ~32% is attributable to informed traders acting on the publication.

Applied inward, year by year on this bot's realised R-multiples:

| year | trades | mean R | win rate |
|---|---|---|---|
| 2016 | 14 | +0.2239 | 64.3% |
| 2017 | 72 | +0.1092 | 56.9% |
| 2018 | 72 | +0.0553 | 51.4% |
| 2019 | 62 | +0.1812 | 53.2% |
| 2020 | 56 | −0.1141 | 44.6% |
| 2021 | 87 | +0.2664 | 58.6% |
| 2022 | 52 | −0.2192 | 36.5% |
| 2023 | 73 | +0.1260 | 50.7% |
| 2024 | 88 | +0.0203 | 50.0% |
| 2025 | 71 | +0.0168 | 47.9% |
| 2026 | 51 | +0.2437 | 52.9% |

Split-half test:

| | mean R | n |
|---|---|---|
| first half | **+0.1215** | 349 |
| second half | **+0.0395** | 349 |
| difference | **+0.0820**, **t = +1.04** | — |

**Verdict: no statistically detectable decay.** But I will not oversell that.
The *point estimate* is a **67% decline**, which is the same order as McLean &
Pontiff's 58% post-publication figure. The test simply cannot separate that
from noise at n = 349 per half — with noise 12.9× the edge, this test is badly
underpowered. **The correct statement is "underpowered, not clean," not "no
decay."** Treating t = 1.04 as evidence of stability would be the same error
as treating the gap-fade's t = +2.50 as evidence of an edge.

---

## 7. Execution science — the part that is actually transferable

This is the one professional discipline that applies directly to this bot at
its current size, so it gets detail.

**Almgren–Chriss (2000), *Optimal Execution of Portfolio Transactions*.** Market
impact splits into two components:

- **Permanent impact** — the price level you move by trading, which does not
  come back
- **Temporary impact** — the concession you pay for demanding immediacy, which
  decays after you stop

The optimal execution trajectory balances **trading slowly to minimise impact**
against **trading quickly to reduce volatility risk versus the arrival price**.
The objective is **implementation shortfall**: the gap between the decision
price and the realised average fill, which is the only cost measure that
captures both what you paid and what you missed. A risk-averse trader executes
faster; a risk-neutral one executes slower. This framework is the basis of the
IS algorithms every institution uses, and the standard family — VWAP, TWAP,
POV, IS — are all points on this trade-off.

**Why this matters here, concretely.** This bot's `CostModel` charges a flat
6 bps one-way with `commission_per_share = 0.0`, and the 0.652% rule-exit
haircut is a separate flat charge. **Neither is a function of order size,
volatility, or urgency.** That is fine at 0.04% of ADV — impact is genuinely
negligible at this size, and the flat model is conservative. But it means:

1. The cost model **cannot express** the benefit of better execution, only its
   absence. Any execution improvement has to be modelled explicitly, as H-0010
   did for the limit-exit haircut.
2. If equity ever approaches the §5 capacity ceiling, the flat model stops
   being conservative and starts being *wrong*, because impact grows
   super-linearly with participation rate (the well-known square-root-of-
   participation shape).
3. The single actionable item stands: **the resting-limit exit is an
   implementation-shortfall improvement**, and Almgren–Chriss is the correct
   framework for pricing it — including the part H-0010 omitted, which is the
   cost of *not* being filled.

---

## 8. What the professional strategy families actually are

For completeness, the recognised revenue lines at the top tier:

| family | what it is | reachable here? |
|---|---|---|
| **ETF creation/redemption arbitrage** | Keep an ETF's price tied to its basket via the create/redeem mechanism. Jane Street's core franchise; #1 ETF share | No — needs AP status, basket execution, inventory |
| **Electronic market making** | Quote two-sided, earn spread, manage inventory (Avellaneda–Stoikov) | Partially — the passive-exit idea is a shadow of it |
| **Latency arbitrage** | Win the 5–10 µs race on correlated instruments | No — top 6 firms take >80% |
| **Index rebalance / flow anticipation** | Trade ahead of mechanical index demand | Marginally — but crowded and well documented |
| **Statistical arbitrage** | Thousands of weak signals, short horizons, market-neutral (Medallion) | This is the nearest neighbour to what the bot does |
| **Options market making / dispersion** | Quote vol, hedge delta, trade index-vs-single-name correlation | No — no options infrastructure |
| **Cash-futures basis** | Arbitrage the spread between spot and futures | No — no futures at Alpaca |
| **Crypto funding-rate / cross-exchange** | Harvest perpetual funding; arb venue price differences | Technically nearest, but costs are worse |

Note where the bot sits: **statistical arbitrage, at very low N.** That is the
correct family. The gap between this bot and Medallion is not the family and
not the idea — **it is N, and it is the cost per trade that caps N.**

---

## 9. Synthesis — the four things that actually separate the best

Stripped to essentials, and in dependency order:

1. **They made the cost per trade ≈ 0 or negative**, by earning the spread
   instead of paying it. Nothing else is possible until this is true. Against
   this bot's own cost model that is a 16.5 bps swing per round trip.
2. **Having done (1), they scaled N**, and √N did the rest: the same 0.078
   edge-to-noise ratio that gives this bot Sharpe 0.63 at 65 trades/yr gives
   Sharpe 7.76 at 10,000. This is the mechanism. There is no second mechanism.
3. **They defended the edge with a moat that is bought, not learned** —
   colocation, direct feeds, queue position, rebate tiers. Six firms win >80%
   of races; new entrants underperform and exit.
4. **They under-bet, capped size, and stayed inside capacity** — Medallion
   closed and returned capital; full Kelly on this bot's numbers is 8.23% and
   prudence says 0.50%; at 10% per trade the median Monte Carlo outcome is
   −100%.

**Items 1 and 3 are not available to this project.** Item 2 is arithmetically
unavailable without item 1. **Item 4 the bot already does correctly** — and
§5 shows it has 51× of capacity headroom, which is the one place it is
genuinely better positioned than the firms in §4.

---

## 10. What this changes

**Nothing in the recommendation, and that is now a well-tested conclusion
rather than an opinion.** Across three documents:

| line of evidence | result |
|---|---|
| intraday pool depth (SPY) | 1.29 bps/session → −23.67%/yr after cost |
| overnight harvest by trading | −16.40%/yr; cost is 2.5× the premium |
| gap fade, day-collapsed | −0.2997%, **t = −1.00** (pooled t was +2.50) |
| gap fade ex-best-day | −0.4247%, t = −1.55 |
| √N scaling | works — **but requires cost ≈ 0 first**, and H-0007 measured the edge decaying 72% under forced frequency |
| the moat | top 6 firms win >80% of races decided in 5–10 µs |
| capacity | **51× headroom — the one genuine advantage, and it argues for staying small** |
| alpha decay in the bot | point estimate −67%, t = +1.04 — **underpowered, not clean** |

**The single actionable item remains the resting-limit exit**, and Part III
sharpens what it needs. §1 explains *why* it is the highest-value lead: it is
step (1) of the dependency chain, the one that has to be true before anything
else can be. §7 names the framework it must be priced in — implementation
shortfall, Almgren–Chriss — and repeats Part II's condition: **the seal must
model non-fills and adverse fills**, or the $58,857 is an upper bound.

One thing Part III adds that the earlier documents did not: **§6 says this
bot's own edge may be decaying by ~67%, and the data cannot tell.** That is a
stronger argument for spending the next registration on execution — where the
gain is mechanical and measurable — than on any further search for signal,
where the program is 12 for 12 in rejections and the measurement apparatus is
underpowered to detect the decay it would need to detect.

---

## Sources

New in Part III:
- Aquilina, Budish, O'Neill — *Quantifying the High-Frequency Trading "Arms Race"*, QJE 137(1), 2022 — https://academic.oup.com/qje/article/137/1/493/6368348
- Budish, Cramton, Shim — *The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response*, QJE 130(4), 2015 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2388265
- Baron, Brogaard, Hagströmer, Kirilenko — *Risk and Return in High-Frequency Trading* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2433118
- McLean & Pontiff — *Does Academic Research Destroy Stock Return Predictability?*, Journal of Finance 71(1), 2016 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623
- Almgren & Chriss — *Optimal Execution of Portfolio Transactions* (2000) — https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf
- Jane Street Capital LLC, SEC Form X-17A-5 FY2024 — https://www.sec.gov/Archives/edgar/data/1103083/000110308325000002/jscpublic2024.pdf
- Industry revenue reporting (Bloomberg / Hedgeweek, 2025–2026) — https://www.hedgeweek.com/non-bank-trading-firms-surge-as-jane-street-and-citadel-securities-drive-record-114bn-revenue-pool/
- Medallion performance summary — https://www.cornell-capital.com/blog/2020/02/medallion-fund-the-ultimate-counterexample.html

Carried from Parts I–II: Barber/Lee/Liu/Odean; Chague/De-Losso/Giovannetti;
Jordan & Diltz; Cooper/Cliff/Gulen; Cont/Kukanov/Stoikov;
Baron/Brogaard/Kirilenko (2012); Lou/Polk/Skouras; Gao/Han/Li/Zhou;
Linnainmaa; Avellaneda/Stoikov; BIS Bulletin 69; SEC HFT review; IRS Topic 429.

Computed here, on this repo's data:
- √N Sharpe scaling from the measured per-trade edge/sd of 0.07760
- Capacity ceiling against the 2% ADV cap and $50M ADV floor
- Year-by-year and split-half alpha-decay test on 698 realised R-multiples
