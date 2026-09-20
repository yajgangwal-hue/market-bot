# Day trading, part II — the full mechanics, and four new tests on this repo's data

*Read-only. Nothing registered, nothing implemented, no configuration touched.
Companion to `2026-09-19-day-trading-research.md`, which covered the survey
level. This one goes to the mechanism, and adds original measurement.*

---

## 0. What changed

Part I argued from the literature plus a single SPY decomposition. This round I
tested four things directly on the 230-symbol equity universe in `data/`
(126,227 symbol-sessions). **One of them looked like the best intraday edge
in the whole program and then died under the program's own methodology.** That
failure is the most useful thing in this document, so it is §1.3.

---

## 1. Four tests on this repo's own data

### 1.1 The overnight effect is universal, not a SPY artefact

Part I showed SPY's return is 82% overnight. Running the same decomposition
across every symbol with ≥250 bars:

| universe | n | mean overnight | mean intraday | overnight wins |
|---|---|---|---|---|
| equity / ETF | 230 | **+88.30%** | **+15.60%** | **164/230 = 71%** |
| crypto | 10 | +15.73% | −21.80% | 8/10 |

**The crypto row is withdrawn.** A 24/7 tape has no overnight session; I checked
whether `close[t−1] == open[t]` and the median absolute gap is 0.0216% (BTC) and
0.0507% (ETH), with essentially zero exact-zero-gap sessions. That is a
bar-boundary artefact of how Alpaca stamps daily crypto bars, not a tradable
session break. **Do not read a crypto overnight premium into this table** — I
generated the number, checked it, and it does not mean what it appears to.

The equity result stands and is stronger than SPY alone suggested: in 71% of
230 names, the overnight leg beat the intraday leg, and the mean overnight
total is **5.7× the mean intraday total**.

### 1.2 The intraday pool is too shallow to fish, before any skill is applied

On SPY, per session:

| | bps/session | net of 12 bps round trip | annualised |
|---|---|---|---|
| overnight leg | **+4.90** | −7.10 | −16.40% |
| intraday leg | **+1.29** | **−10.71** | **−23.67%** |

**A day trader's raw material yields 1.29 bps a session and costs 12 bps to
touch.** Before selecting a single trade, before any skill at all, the pool is
negative by 10.7 bps a session. Every basis point of alpha a day trader
generates is spent climbing out of that hole, and they need 10.7 of them just
to reach zero — while a buy-and-hold investor sits in a stream yielding 4.90
bps a session and pays the 12 bps **once, ever**.

This is the arithmetic behind the −23.9 bps/day that the Taiwan population
actually realised. The population number is not a mystery; it is what this
table predicts.

### 1.3 The one intraday pattern that looked real — and why it is not

Pooling all 126,227 sessions, the correlation between a session's overnight
move and its own intraday move is **−0.0250, t = −8.9**. Significant reversal.
Sliced by gap size, it looked spectacular:

| slice | count | mean gap | gross intraday | **net of 12 bps** | annualised @1/day |
|---|---|---|---|---|---|
| all sessions | 126,227 | +0.090% | +0.0357% | −0.0843% | −19.1% |
| worst 20% gaps | 25,245 | −1.868% | +0.1402% | +0.0202% | +5.2% |
| worst 10% | 12,622 | −2.850% | +0.2235% | +0.1035% | +29.8% |
| worst 5% | 6,311 | −4.065% | +0.2744% | +0.1544% | +47.5% |
| worst 2% | 2,524 | −5.994% | +0.3212% | +0.2012% | +66.0% |
| **worst 1%** | 1,262 | −7.703% | **+0.5568%** | **+0.4368%** | **+199.9%** |
| worst 0.5% | 631 | −9.718% | +0.6575% | +0.5375% | +286.1% |
| best 5% (gap UP) | 6,311 | +4.464% | −0.1486% | −0.2686% | −49.2% |
| best 1% (gap UP) | 1,262 | +8.713% | −0.2701% | −0.3901% | −62.7% |

Monotone in gap size, symmetric in both tails, net of costs, naive **t = +2.50**.
Buy the worst gap-downs at the open, sell at the close. On its face this is the
single best thing measured anywhere in this program.

**It is not real.** The observations cluster — a market-wide gap morning
produces dozens of correlated "independent" observations, and equal-weighting
126,227 of them is exactly the error this program built day-collapsing to
prevent. Collapsing to one equal-weight basket return per session:

| | pooled (naive) | **day-collapsed (honest)** |
|---|---|---|
| observations | 126,227 | **322 firings** |
| mean net | **+0.4368%** | **−0.2997%** |
| t | **+2.50** | **−1.00** |
| win rate | — | 47.2% |
| median | — | −0.2002% |
| ex- best day | — | **−0.4247%, t = −1.55** |

**The sign flips.** Total summed net across 322 firings is **−96.50%**, and a
single session (2024-10-21, +39.84%) accounts for more than the entire deficit.
Remove it and the strategy gets *worse*, not better — the opposite of what a
real effect does.

This is candidate number twelve to fail in this program, and it failed for the
same reason several others did. Worth stating plainly: **had I reported the
pooled table and stopped, I would have handed you a fictional 200%/yr
strategy.** The gap between those two tables is the entire value of the
methodology.

### 1.4 You cannot trade the overnight premium either

The obvious inversion — if overnight is where the return is, buy at the close
and sell at the open every day — fails on the same arithmetic:

| | value |
|---|---|
| mean overnight premium | **4.90 bps/session** |
| round-trip cost to capture it | **12.00 bps** |
| net | **−7.10 bps/session → −16.40%/yr**, t = −2.51 |
| break-even one-way cost required | **≤ 2.45 bps** (model assumes 6.00) |
| buy-and-hold over the same window | **+16.68%/yr, zero round trips** |

**The cost of harvesting the overnight premium is 2.5× the premium.** You would
need fills 2.5× better than this bot assumes before the trade exists at all.
Buy-and-hold captures the identical premium and pays the toll once.

So the honest conclusion from §1.1–§1.4 is not "day trade the other side." It
is that **the overnight premium is real, large, and only available to someone
who does not trade.**

---

## 2. What a professional's P&L actually decomposes into

Part I established that the top of the intraday distribution provides liquidity.
Here is what that job actually is, because "be a market maker" is not a
strategy, it is three simultaneous risk problems.

A market maker's per-trade P&L is:

```
P&L  =  (+) captured spread
        (+) exchange rebate / PFOF
        (−) adverse selection
        (−) inventory (directional) risk
        (−) fees, technology, capital cost
```

**The spread and rebate are the only positive terms, and they are known in
advance.** Everything that determines whether the business works is on the
negative side.

- **Adverse selection** is the dominant cost. Your resting quote is an option
  you have written to the rest of the market, exercised against you precisely
  when someone knows something you do not. This is why "passive HFT is
  profitable even without rebates" is a strong result — it says the spread
  capture exceeds adverse selection on its own.

- **Inventory risk** is what the Avellaneda–Stoikov framework (2008) formalises.
  The maker quotes not around the mid but around a **reservation price** that
  skews away from the mid as inventory builds: long inventory means you value
  the asset below the market because you are carrying the risk, so you shade
  both quotes down to attract sells and discourage buys. The **optimal spread**
  widens with volatility, with risk aversion, and with time remaining. This is
  the actual content of "position sizing" at this end of the business — it is
  continuous, inventory-dependent quote placement, not a fixed fractional bet.

- **Queue position** is the hidden variable. At the same price, being 5th in
  the queue rather than 500th changes fill probability and changes *which*
  fills you get — you are more likely to be filled when the queue ahead of you
  cancels, which is when informed flow is arriving. Queue position is a latency
  and technology problem, which is why this tier of the business is capital
  intensive.

**Why this matters to you specifically:** the H-0010 finding — $58,857 of
avoided haircut across 987 trades because take-profit exits were resting limits
— is the *first* line of that decomposition, captured accidentally. The bot
already demonstrated it can earn the spread term. What it has never modelled is
the adverse-selection term that comes with it: a resting limit exit fills when
price reaches your level, and sometimes it reaches your level because it is
about to keep going. **Any registration of the limit-exit finding must model
non-fills and adverse fills, or it will overstate the gain.** That is the single
most important methodological warning in this document.

---

## 3. Sizing and survival — why the top under-bet

Measured on this bot's own 698 trades:

| | value |
|---|---|
| win rate | 51.15% |
| average win | +0.9781 R |
| average loss | −0.8592 R |
| payoff ratio *b* | 1.1384 |
| **full Kelly** | **8.2320% of equity per bet** |
| half Kelly | 4.1160% |
| **what the bot actually risks** | **0.50% base (0.75% ceiling)** |
| **fraction of Kelly** | **0.06×** |
| expectancy | +0.0805 R |
| **noise / edge** | **12.9×** |

The bot bets **one-sixteenth of Kelly**. That is not timidity, it is correct:
Kelly is optimal only if your estimated edge is the true edge, and with
noise 12.9× the edge — measured in-sample — the true edge could plausibly be
zero. Betting Kelly on a mis-estimated edge is the standard route to ruin.

Monte Carlo on the same R distribution, 3,000 paths, ruin = a 50% drawdown:

| risk/trade | trades/yr | P(ruin) 1yr | median 1yr | P(beat SPY) |
|---|---|---|---|---|
| 0.5% | 65 | 0.0% | +2.50% | 1.0% |
| 0.5% | 252 | 0.0% | +9.90% | 36.7% |
| 0.5% | 756 | 0.0% | +34.07% | 88.3% |
| 2.0% | 252 | 0.2% | +42.96% | 75.9% |
| 5.0% | 252 | **15.1%** | +90.44% | 71.5% |
| 10.0% | 252 | **52.7%** | **−100.00%** | 43.7% |
| 10.0% | 756 | **62.0%** | **−100.00%** | 37.2% |

Two readings, and the second is the one that matters.

**Naive reading:** frequency is a free multiplier — at 0.5% risk and 756
trades/yr you beat SPY 88.3% of the time with zero ruin risk. This is the
arithmetic every day-trading course is implicitly selling.

**Correct reading:** this simulation assumes **the per-trade edge survives a
12× increase in trade count**, and this program has already measured that it
does not. H-0007 forced the bot to take more trades and selection-per-dollar
collapsed from **0.2068% to 0.0575%** — a 72% decay. The 88.3% figure is what
you get if you can find 756 trades a year as good as your best 65. You cannot;
that was tested and rejected.

What the table *does* show honestly is the ruin side: **at 10% risk per trade
the median outcome is total loss**, and going faster makes it worse (52.7% →
62.0%). This is the quantitative form of "60–70% of prop-firm failures are
drawdown breaches." The top survive by under-betting a measured edge, and the
bottom die by over-betting an imagined one.

### A correction to how Part I's cost table should be read

Part I's frequency table assumed **100% deployment**, which was right for the
question asked ("100% in for 5 minutes"). At this bot's actual sizing the
numbers are much smaller:

| | value |
|---|---|
| cost per round trip | $19.87 |
| average equity | $123,088 |
| **cost per trade as % of equity** | **1.61 bps** |
| average position notional | $16,516 = **13.4% of equity** |
| 12 bps on that notional | 1.61 bps ✓ |

So at 13.4% deployment, friction at 3 trades/day is −11.46%/yr, not −59.66%.
**But this changes nothing about whether a strategy works**, because reducing
deployment scales the edge down by the identical factor. The invariant is
**edge-per-trade ÷ cost-per-trade, both measured in bps of notional** — and
that denominator is the 12 bps. Deployment sets your volatility, not your
Sharpe.

---

## 4. The behavioural layer — what reliably destroys the other 99%

These are documented on administrative data, not surveys.

- **The disposition effect.** Linnainmaa, on the complete record of every
  individual day trader in Finland, documents a strong disposition effect
  *specific to day traders* — selling winners and holding losers. This is the
  precise inverse of the payoff profile any positive-expectancy short-horizon
  system needs, and it is the mechanism by which a trader with a real edge
  still loses.
- **"Learning" is mostly attrition.** The same literature finds that aggregate
  improvement among day traders comes substantially from bad traders *quitting*,
  not from traders getting better. Chague et al. found **no evidence of
  learning** at all among Brazilian persisters. The surviving-cohort statistics
  you see advertised are the selection effect, not a skill curve.
- **Overconfidence and turnover.** The Barber–Odean line of work ties excess
  turnover directly to underperformance; the more you trade, the worse you do,
  which §1.2 explains mechanically.
- **The demographic is stable.** Typically male, late 30s, metropolitan,
  trading larger size than matched controls. The same profile appears in the
  BIS crypto data: ~40% of new users are men under 35, the most risk-seeking
  segment, and 75% entered after the price cleared $20,000.

**The operational answer the top use is not willpower, it is a pre-committed
hard daily loss limit** — a rule that fires without discretion. It exists
specifically because the disposition effect is not something you can decide not
to have.

---

## 5. The infrastructure layer — and the market's own price on retail skill

This is the part that settles the question, and it is not a matter of opinion.

**Payment for order flow is a market price for uninformed order flow.**
Wholesalers pay brokers to route retail marketable orders to them rather than
to an exchange. The economic logic, stated plainly in the literature: retail
marketable flow is *overwhelmingly uninformed*, so a wholesaler facing it
carries far less adverse selection than it would on a lit venue, and can
therefore quote inside the NBBO and still profit. Robinhood's transaction-based
revenue was **over 77% of net revenue** in 2021 — $1.4bn, split options 49%,
crypto 30%, equities 21%.

Read that carefully. **There is a liquid, competitive market in which
professionals pay real money for the right to take the other side of retail
day-trading orders, and they do it because that flow does not predict price.**
That is not an anecdote or a loss statistic — it is a revealed price, set by
the best-informed participants in the market, on exactly the activity being
proposed. It is the strongest single piece of evidence in either document.

The corollary for the E-mini data in Part I is direct: small traders lose
**$50,328/day** to HFT firms in that market, and "uninformed flow" is precisely
what makes that transfer reliable.

**The rest of the stack**, briefly, because it defines the moat: colocated
servers at the matching engine, direct exchange feeds rather than the SIP
(the consolidated tape is slower by construction), kernel-bypass networking,
often FPGA order handling, and rebate-tier relationships that turn the
−12 bps taker cost into a positive number. None of this is reachable from a
Python process on daily bars, and none of it is a tuning gap.

---

## 6. The tax and entity layer — the most reliable "edge" available

This requires no forecasting skill, which makes it the highest-confidence item
in either document. **I am not a tax advisor and this is not tax advice; verify
with a professional before acting.**

- **Section 1256 (futures, broad-based index options).** Marked to market, and
  gains split **60% long-term / 40% short-term regardless of holding period** —
  roughly **26.8% blended top federal rate vs 37% ordinary**. Exempt from wash
  sales. Losses carry back up to three years. **On a high-turnover book this is
  ~10 points of after-tax return, free.**
- **Trader Tax Status (TTS).** Not elected — a facts-and-circumstances test
  (IRS Topic 429): profit sought from daily market movements, substantial
  activity, continuity and regularity. Practitioners commonly cite **720+
  trades/yr, ~4+/day on most trading days**, short holding periods. It permits
  deducting ordinary and necessary business expenses (software, data, home
  office, equipment) on Schedule C or through an entity. **Commissions are not
  deductible as expenses** — they adjust basis.
- **Section 475(f) mark-to-market election.** Available *if* you have TTS.
  Eliminates wash-sale tracking and converts trading losses to ordinary
  business losses, escaping the $3,000 capital-loss cap. **Costs:** all open
  positions are deemed sold at year-end FMV, and gains become **ordinary income**
  — you give up preferential long-term rates. **Deadline is the prior year's
  return due date without extensions**, and revoking within five years requires
  non-automatic IRS consent with a user fee around **$13,000**. This is a
  serious, sticky election.

**Constraint unchanged: Alpaca offers no futures**, so the Section 1256 route —
the single best-evidenced item here — is unreachable from this brokerage.

---

## 7. Documented intraday anomalies — the complete list, with verdicts

| effect | source | status | usable here? |
|---|---|---|---|
| **Overnight > intraday** | Cooper/Cliff/Gulen (2008); **confirmed here, 230 names, 71%** | Robust, decades | **Only by holding, not trading** (§1.4) |
| **Order flow imbalance** | Cont/Kukanov/Stoikov, JFE 2014 | Most reproducible in microstructure; linear in OFI, slope ∝ 1/depth | **No — needs level-2 book** |
| **Market intraday momentum** | Gao/Han/Li/Zhou, JFE 2018 | First half-hour return predicts last half-hour on SPY, 1993–2013; stronger on volatile, high-volume, recession and macro-news days; CE gain **6.02%/yr** at risk aversion 5 | **No — needs intraday bars** |
| **Overnight/intraday tug of war** | Lou/Polk/Skouras, JFE 2019 | 14 strategies earn profits *entirely* overnight or *entirely* intraday, typically opposite signs; firm-level continuation within period, reversal across | **Partially — tested in §1.3, failed** |
| **Gap fade** | folklore; tested here | **REJECTED** — pooled t = +2.50 → day-collapsed t = **−1.00** | **No** |
| Relative volume, float rotation, VWAP reversion, opening range, prior-day levels | retail literature | No credible public evidence | Treat as unproven |

Note the pattern in the "usable" column. **Every intraday effect with real
academic standing requires intraday or order-book data.** This repository has
daily OHLCV, 550 bars per symbol. The two effects testable on daily bars were
tested above, and both fail after costs.

---

## 8. So what is "everything they do"?

Assembled from all of the above, the complete profile of the persistent
outperformer:

1. **Earns the spread rather than paying it** — the single largest
   discriminator, a 16.5 bps swing per round trip against this bot's own cost
   model, and the difference between the taker needing +1,961% gross to break
   even and the maker's friction term being positive.
2. **Manages inventory continuously**, quoting around a reservation price that
   skews with position and widens with volatility — not fixed-fraction betting.
3. **Treats adverse selection as the main cost**, and measures it. Most retail
   systems do not model it at all, which is how backtests of limit-order
   strategies overstate returns.
4. **Competes on queue position, latency and routing** — colocation, direct
   feeds, rebate tiers. Capital-intensive, and the actual moat.
5. **Accepts a tiny per-trade edge and enormous count**, viable only because
   step 1 made fills nearly free.
6. **Concentrates on one or two instruments**, learned exhaustively.
7. **Under-bets a measured edge** — the bot's own numbers say full Kelly is
   8.23% and prudence says 0.5%; over-betting is the documented route to the
   52.7%-ruin row.
8. **Enforces pre-committed, non-discretionary loss limits**, because the
   disposition effect is structural, not a character flaw.
9. **Is capacity-aware** — these edges work at $100k and vanish at $100m,
   which is the one genuine structural advantage a small account holds.
10. **Optimises the tax and entity layer** — Section 1256, TTS, 475(f) — worth
    ~10 points of after-tax return with no forecasting skill required.
11. **Increasingly is a firm, not a person.** The E-mini audit trail shows HFT
    firms extracting ~$146,005/day from fundamental investors, ~$89,874/day
    from non-HFT market makers, and ~$50,328/day from small traders.

Items 1–4 and 11 are not reachable from this project's data or brokerage. Items
7–9 this bot already does. Item 10 is blocked by Alpaca. **What is left is the
part you already found.**

---

## 9. Where this leaves the recommendation

Unchanged in direction, and now considerably better evidenced.

**The lead is still execution, not frequency.** The $58,857 of avoided haircut
that H-0010 measured is the same spread-capture term that defines the top of
the professional distribution, and this round's literature review says it is
*the* discriminator rather than one factor among many.

**But this round added a hard condition on how to register it.** §2 says a
resting limit earns the spread *and* writes an option to the market. The
H-0010 number counted only the first half. A registration of the limit-exit
finding must model:

- **non-fills** — the limit that never trades, and what the position does after
- **adverse fills** — filling because price is about to continue through you
- **queue position** — you are not first in line at your price

Without those three, the $58,857 is an upper bound, not an estimate. Given the
gap-fade in §1.3 turned from +200%/yr to negative under one methodological
correction, I would not register the execution finding until its adverse-
selection model is specified in the seal.

**The day-trading branch itself should be closed**, on the following record:

| test | result |
|---|---|
| intraday pool depth (SPY) | **1.29 bps/session, −23.67%/yr after cost** |
| overnight harvest by trading | **−16.40%/yr; cost is 2.5× the premium** |
| gap fade, worst 1% | **day-collapsed −0.2997%, t = −1.00** |
| gap fade ex-best-day | **−0.4247%, t = −1.55** |
| every effect with academic standing | **requires data this project does not have** |
| Section 1256 tax route | **blocked — Alpaca has no futures** |
| the market's own price on retail day-trade flow | **wholesalers pay for it** |

Seven independent lines, no survivors. That is a closure on evidence, not on
preference — and if new permissible intraday or order-book data becomes
available, §7 lists exactly which three effects would be worth re-opening it
for.

---

## Sources

New in this round:
- Gao, Han, Li, Zhou — *Market Intraday Momentum*, JFE 129(2), 2018 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866
- Lou, Polk, Skouras — *A Tug of War: Overnight Versus Intraday Expected Returns*, JFE 134(1), 2019 — https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Linnainmaa — *The Individual Day Trader* / *Learning from Experience* — https://www.anderson.ucla.edu/documents/areas/fac/finance/28-05.pdf
- Avellaneda & Stoikov — high-frequency market making, reservation price and optimal spread (2008) — https://www.math.nyu.edu/~avellane/HighFrequencyTrading.pdf
- Ernst — *Payment for Order Flow and Asset Choice*, NBER w29883 — https://www.nber.org/system/files/working_papers/w29883/revisions/w29883.rev0.pdf
- CRS — *Payment for Order Flow and Broker-Dealer Regulation* — https://www.congress.gov/crs-product/IF12594
- IRS Topic 429, Traders in Securities — https://www.irs.gov/taxtopics/tc429
- Schwab — Trader status and 475 mark-to-market — https://www.schwab.com/learn/story/mark-to-market-trader-taxes

Carried from Part I: Barber/Lee/Liu/Odean; Chague/De-Losso/Giovannetti;
Jordan & Diltz; Cooper/Cliff/Gulen; Cont/Kukanov/Stoikov;
Baron/Brogaard/Kirilenko; BIS Bulletin 69; SEC HFT literature review.

Computed here, on this repo's data:
- 230-symbol overnight/intraday decomposition, 126,227 symbol-sessions
- Crypto bar-boundary check (BTC/ETH gap distribution)
- Gap-fade pooled vs day-collapsed adjudication, 322 firings
- Overnight-harvest cost arithmetic on `data/SPY.csv`
- Kelly fraction and risk-of-ruin Monte Carlo from `docs/phase5/h0010-cache.json`
- Cost-per-trade as a fraction of equity at realised deployment
