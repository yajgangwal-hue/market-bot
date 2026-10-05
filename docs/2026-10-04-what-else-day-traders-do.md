# What else day traders do to make money every day

*2026-10-04. Research only. Nothing implemented, no live change, nothing
committed.*

This builds on `2026-09-19-day-trading-*.md` (three parts) and
`2026-10-03-day-trading-what-works.md`. Those covered:

- the loss statistics;
- high-frequency firms;
- costs, the overnight split and taxes;
- the project's seven earlier intraday tests;
- H-0032 and H-0033.

This round adds:

- two more sealed tests of published day-trading systems (H-0034, H-0035);
- eight practices the earlier studies did not cover.

## The answer

**Is there something day traders do that makes money consistently, day after
day, that this bot could copy? No.**

- **The people who make money nearly every day are market makers.** They are
  paid the bid-ask spread on enormous volume and control risk in real time.
  That is a different business from what day-trading courses teach.
- **The individuals who win consistently are a fraction of one percent.** They
  win with an information edge in a few stocks, not with a chart rule.
- **Every published "beats the market" index day-trading system tested here
  failed after its publication: four of four.**

| Who makes money day after day | How | Evidence | Could this bot do it? |
|---|---|---|---|
| High-frequency market makers | Quote both sides of more than 10,000 instruments, earn the spread, hedge in real time | Virtu Financial: **1 losing day in 1,238** (2009–2013); about **$1.6 million a day** of adjusted net trading income in 2013 | **No.** Needs exchange connections, speed and rebates |
| The best day traders, well under 1% | Trade a few stocks they know; trade around news and earnings | Taiwan's 500 best, ranked on the prior year: **+0.38% a day after fees** the next year | **No.** No information edge; the news archive has no article text |
| The fastest news traders | Act within seconds | Positive TV stock reports were fully priced **within a minute**; traders who acted **within 15 seconds** made small profits | **No.** No real-time news feed |
| Followers of published systems | Opening-range breakout, VWAP trend, noise-area bands, intraday momentum | **4 of 4 failed after publication** on SPY (section 1) | **Tested: no** |
| Everyone else | | **97%** of Taiwan day traders were likely to lose money in future day trading; **74%** of day-trading volume came from traders with a history of losses | |

## 1. Four published day-trading systems, tested on SPY

| System | Published claim | SPY after publication, realistic costs | SPY held, same days | Verdict |
|---|---|---|---|---|
| Intraday momentum (Gao et al., 2018), H-0032 | The first half hour predicts the last | The effect reversed after 2020; the account made **−1.5% a year**, 2016–2026 | +13.1% a year | REJECTED |
| "Beat the Market" noise area (Zarattini, Aziz & Barbon, 2024), H-0033 | 19.6% a year, Sharpe 1.33 | **+0.24% a year** unlevered; **+1.29%** volatility-targeted | +17.5% a year | REJECTED |
| 5-minute opening-range breakout (Zarattini & Aziz, 2023), H-0034 | On QQQ: 33% a year, Sharpe 1.13 | **−4.71% a year**, Sharpe −0.14 | +19.7% a year | REJECTED |
| VWAP trend (Zarattini & Aziz, 2023), H-0035 | On QQQ: 43% a year, Sharpe 2.1 | **+0.94% a year**, Sharpe 0.14 | +21.2% a year | REJECTED |

How to read the table:

- **"After publication"** runs from each paper's first version to 2026-09-10:
  - H-0033 from 2024-05-10;
  - H-0034 from 2023-04-24;
  - H-0035 from 2023-11-13.

  H-0032's paper predates the data, so its row covers 2016–2026.
- **SPY figures are price only.** Total return adds about 1.3–1.6 points a
  year.
- **The realistic cost** is $0.0045 a share each side. That is the same
  authors' own figure in their 2024 paper. Their 2023 papers assumed $0.0005
  and no slippage, which ignores SPY's one-cent spread.

### H-0034: the 5-minute opening-range breakout

**The rule, from the paper's text and its Table 1:**

- **Direction.** If the first 5-minute candle closes up, buy at the open of
  the second candle (09:35). If it closes down, short. If it closes where it
  opened, no trade.
- **Stop.** Long: the first candle's low. Short: its high. The distance from
  entry to stop is R.
- **Target.** 10R; otherwise exit at the 16:00 close.
- **Size.** Risk 1% of equity, capped at 4× leverage:
  `int(min(equity × 0.01 / R, 4 × equity / entry))`.

**It does not hold even on the paper's own terms.**

| | Paper: QQQ, Jan 2016 – Feb 2023 | SPY, same window, paper's costs | SPY after publication, realistic | SPY held, after publication |
|---|---:|---:|---:|---:|
| A year | 33% | 8.35% | **−4.71%** | 19.74% |
| Sharpe | 1.13 | 0.46 | **−0.14** | 1.31 |
| Worst drop | −22% | −26.3% | −32.7% | −19.0% |

Over the paper's window, SPY held made 10.43% a year (Sharpe 0.61; worst drop
−34.2%).

**The friendliest version still lost to SPY.** That version uses the paper's
window, its $0.0005 cost, and stops filled exactly at their level. It made
11.15% a year at a Sharpe of 0.57, against SPY's 0.61. The 4× leverage cap
was binding on 86% of trades.

**Per trade, before costs:**

| | R per trade | t | Winners |
|---|---:|---:|---:|
| Paper's figure, QQQ | +0.13R | — | 24% |
| SPY, paper's window | +0.085R | 1.39 | 20% |
| SPY, after publication | +0.009R | — | — |

An independent replication on index CFDs (Krueger, 2026, not peer-reviewed)
found the same pattern. The +0.12–0.13R before costs reproduced; after spreads
and slippage, no market was distinguishable from zero.

| Sealed criterion | Result |
|---|---|
| R1: in the paper's window at the paper's cost, return and Sharpe above SPY's | **fail** (8.35%, 0.46 against 10.43%, 0.61) |
| R2: after publication, return above 0 and Sharpe above SPY's 1.31 | **fail** (−4.71%, −0.14) |
| R3: positive in at least 8 of 11 years | **fail** (4: 2019, 2021, 2022, 2025) |
| R4: full-window Sharpe at least 0.7 at doubled costs | **fail** (0.05) |
| R5: worst drop no deeper than SPY's −34.2% | **fail** (−45.8%) |

**Verdict: REJECTED.** All five criteria fail.

### H-0035: VWAP trend trading

**The rule, from the paper's text:**

- **VWAP** is the session's volume-weighted average of the typical price,
  (high + low + close) / 3.
- **Entry.** After the first candle closes, go long if it closed above VWAP,
  short if below.
- **Reversals.** Reverse whenever a candle closes on the other side of VWAP.
  Always long or short; out at the close.
- **Size.** All equity, no leverage.

The paper used 1-minute candles and says the same rule can be run on 5-minute
candles, which is what the store holds.

| | Paper: QQQ 1-minute, 2018 – Sep 2023 | SPY 5-minute, same window, paper's costs | SPY after publication, realistic | SPY held, after publication |
|---|---:|---:|---:|---:|
| A year | 43% | 9.75% | **0.94%** | 21.16% |
| Sharpe | 2.1 | 0.73 | **0.14** | 1.36 |
| Worst drop | −9.4% | −15.0% | −13.2% | −19.0% |

Over the paper's window, SPY held made 8.61% a year (Sharpe 0.50).

- **Costs decide it.** The rule makes about 8 trades a session (21,389 in
  2,660 sessions). Over 2016–2026 it made 5.58% a year before costs and 0.24%
  at realistic costs.
- **It did beat SPY in the paper's own years, at the paper's costs** (R1
  passes). Most of that came from SPY's two down years, 2018 and 2022 (+20.6%
  and +23.6%).
- **Year by year,** it was positive in 6 of 11 years at realistic costs.

| Sealed criterion | Result |
|---|---|
| R1: paper's window, paper's cost, return and Sharpe above SPY's | pass (9.75%, 0.73 against 8.61%, 0.50) |
| R2: after publication, return above 0 and Sharpe above SPY's 1.36 | **fail** (0.94%, 0.14) |
| R3: positive in at least 8 of 11 years | **fail** (6) |
| R4: full-window Sharpe at least 0.7 at doubled costs | **fail** (−0.33) |
| R5: worst drop no deeper than SPY's −34.2% | pass (−29.5%) |

**Verdict: REJECTED** (R2 fails).

### Checks on these two tests

- **Sealed before any result was computed.** H-0034 seal `76e5ce78…`, H-0035
  seal `ab96ed75…`, both registered 2026-10-04 18:38 UTC. The chain is intact
  with 34 registrations, and the code is bound by SHA-256.
- **Same data handling as H-0033.** After-hours bars on the 21 early-close days
  are dropped, and duplicated quarter-boundary bars are merged.
- **The candle logic was checked against an exact simulation.** On a
  synthetic SPY that moves one cent at a time, the breakout engine matched a
  tick-by-tick simulation on **3,932 of 3,932 trades**.
  - Coarser synthetic data flattered stop fills by hiding the overshoot
    between steps. Finding and fixing that came before registration.
  - Real stop orders take the next available price. So stops are filled one
    cent beyond their level, a deliberately cautious allowance, and results
    with stops at their level are reported beside them.
- **Controls.**
  - On a driftless random walk, neither rule showed an edge before costs.
  - On a walk with built-in intraday trends, both earned large profits. The
    engine finds an edge when one exists.
- **Tests.** 13 unit tests, all passing.

## 2. Other things day traders do, and what the evidence says

### 2.1 Trading the news

- **Speed is everything.** Busse & Green (2002) studied stock reports on
  CNBC:
  - prices moved within seconds;
  - positive reports were fully priced within one minute;
  - traders who executed within 15 seconds made small but significant
    profits.
- **News moves drift; moves without news reverse.** Chan (2003) found:
  - after big moves *with* public news, prices kept drifting, especially after
    bad news;
  - after big moves *without* news, they reversed;
  - this is a monthly horizon, and mostly in small, illiquid stocks.
- **AI reading headlines works at first, then fades.** Lopez-Lira & Tang
  (2023, revised 2025) found that a language model's headline scores predict
  later drift, most in small stocks and after bad news. The instant reaction
  it caught (about 90% hit rate) is not tradable. In the authors' words,
  "strategy returns decline as LLM adoption rises".
- **For this bot.** The project's archive has headlines only (median 13
  words), with unverified timestamps; the 2026-09-18 study found nothing
  usable. A news edge would need a real-time feed with full article text.
  That is a data purchase, and Alpaca's news feed is blocked until the exposed
  key is rotated.

### 2.2 Chasing hot stocks and gappers

- **Herding into the most-bought stocks loses.** Barber, Huang, Odean &
  Schwarz (*Journal of Finance*, 2022) found that the stocks Robinhood users
  bought most each day had a **−4.7% abnormal return over the next 20 days**.
- **Buying attention stocks at the open is expensive.** Berkman, Koch, Tuttle
  & Zhang (2012) found these stocks rise overnight and give it back during the
  day. Retail buyers at the open pay hidden costs that often exceed the
  half-spread.
- **The project's own tests found no edge either way:**
  - on 230 large caps, violent opens kept *rising* (2026-09-10);
  - the stocks-in-play breakout lost money before costs (2026-09-07).

### 2.3 Earnings plays

- **Earnings are where the best traders earn.** Barber et al. (2014) found the
  top day traders earned more around earnings announcements (65.5 against
  58.9 bps).
- **But the slow drift afterwards is gone in liquid stocks.** Martineau
  (2022): prices have absorbed earnings surprises on the day itself since about
  2006 for non-microcaps.
- **A 2025 debate leaves it only in microcaps.** UCLA's Subrahmanyam
  reconciled newer papers: the drift shows up only when microcaps are included
  (t 2.18), and not without them (t 1.43).
- **What's left is speed, and microcaps.** Neither is reachable here.

### 2.4 Event days: Fed announcements

- **Before 2011 the effect was huge.** Lucca & Moench (2015): the S&P 500 rose
  49 bps on average in the 24 hours before Fed announcements. Over 1994–2011,
  that was more than 80% of the equity premium.
- **It is gone.** Kurov, Wolfe & Gilbert (2021): the drift essentially
  disappeared after 2015.

### 2.5 Tight stops and quick exits

- **Stops cost money unless prices trend.** Kaminski & Lo (2014): on a random
  walk, stop-loss rules always lower expected return. They add value only when
  returns have momentum.
- **That is why +0.5% / −0.2% failed here.** H-0030 measured −0.02% a trade
  against +0.57% with the bot's current exits. Its winners mostly keep rising:
  the project measured 81.2% continuing higher.
- **The breakout paper's best variant was picked after the fact.** Its stop at
  5% of the average daily range, worth +9,350% on the 3× leveraged TQQQ, was
  chosen after looking at a grid of stops and targets.

### 2.6 Discipline

- **Losing in the morning leads to bigger bets in the afternoon.** Coval &
  Shumway (*Journal of Finance*, 2005) found Chicago futures traders
  "regularly assuming above-average afternoon risk to recover from morning
  losses". The prices they set reversed faster.
- **Holding losers longer cost US proprietary day traders money** (Garvey &
  Murphy, 2004). They took winners faster than losers, and that lowered their
  profits.
- **Futures floor traders held losers longer too, with no measured cost**
  (Locke & Mann, 2005). Their relative discipline predicted later success.
- **Experience did not help.** Kuo & Lin (2013) studied 3,470 Taiwan futures
  day traders over October 2007 to September 2008:
  - they lost **NT$61,500** each on average after costs (NT$26,700 before);
  - more experienced traders traded more aggressively, but did not lose less.
- **Losers keep trading.** Barber et al. (2020): 74% of day-trading volume came
  from traders with a history of losses.
- **For this bot.** Its rules are fixed in code, so "revenge trading" and
  holding losers by hope cannot happen. It already has the discipline the
  literature rewards.

### 2.7 Being paid for liquidity

- **Buying what others are dumping pays, most of all in a panic.** Nagel
  (2012): short-term reversal returns are the reward for providing liquidity,
  and they rise sharply with the VIX.
- **Retail traders who buy after drops with limit orders benefit.** Kelley &
  Tetlock (2013): retail limit-order buying follows price drops and gains as
  prices recover. Retail market orders instead anticipate news.
- **Timing matters.** Heston, Korajczyk & Sadka (2010): returns repeat at the
  same half-hour across days for at least 40 days. "Timing trades can reduce
  execution costs by the equivalent of the effective spread."
- **For this bot.** Buying dips is liquidity provision at a daily horizon.
  - Nagel says it should pay most when fear is high. The project has only
    tested cutting exposure when volatility is high (EXP-0009, rejected),
    never adding to it.
  - But the bot's two worst years per trade, 2020 (−0.11R) and 2022 (−0.22R),
    were high-volatility years. The idea may not transfer.

### 2.8 Gurus and courses

- **A regulator found most customers of one large course lost money.** In
  2022 the FTC reached a $3 million settlement with Warrior Trading over
  misleading earnings claims. Most customer accounts lost money trading, on
  top of the course fees.
- **The most popular finfluencers are the worst.** Kakhbod, Kazempour, Livdan
  & Schürhoff studied stock pickers on StockTwits:

  | Skill | Share | Abnormal return a month |
  |---|---:|---:|
  | Skilled | 28% | +2.6% |
  | Unskilled | 16% | — |
  | Negative skill | 56% | −2.3% |

  The negative-skill group had more followers. Trading against them earned
  1.2% a month.

### 2.9 The +0.5%-a-day goal in perspective

- **It compounds to about +250% a year** (1.005^252 = 3.52).
- **The best group of day traders ever measured fell short of it.** Taiwan's
  top 500, ranked on the prior year from hundreds of thousands of traders,
  averaged **0.38% a day** after fees.
- **The four public systems tested here made between −4.7% and +1.3% a year**
  after publication.

## 3. What this means for the bot

**Nothing to implement.** No day-trading practice here beats what the bot
already does, and none of the four published systems survived publication.

**Already in place:**

- resting take-profit and stop orders at the broker (EXP-0056);
- fixed rules, so no emotional trading;
- small positions.

**Open leads** — the owner's call. Each would need its own sealed test, and
none has been started:

1. **Buy dips more when the market is fearful** (Nagel, 2012). It can be tested
   on existing daily data, but the bot's poor 2020 and 2022 make it doubtful.
2. **Separate dips with news from dips without news** (Chan, 2003). This
   needs a news feed with article text and reliable timestamps: a data
   purchase, blocked until the Alpaca key is rotated.

**Not worth more time:**

- index day-trading systems (four tested);
- chasing gappers and hot stocks;
- the pre-Fed-announcement drift;
- earnings drift in liquid stocks;
- tighter stops.

## Records

- `docs/phase5/h0034-h0035-results.json`, `scripts/run_h0034.py`,
  `scripts/h0034_index_day_rules.py`, `scripts/h0034_spec.py` and
  `tests/test_h0034_index_day_rules.py`.
- H-0034 and H-0035 are in `docs/preregistrations.jsonl`.
- Dataset `spy-5min-2016-2026-quarterly-43`, gate-verified, used as a
  rejection test only.

## Sources

Checked 2026-10-04:

- Zarattini & Aziz (2023), [Can Day Trading Really Be Profitable?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622). First version 2023-04-24; rules and Table 2 read from the [full text](https://concretumgroup.com/can-day-trading-really-be-profitable/).
- Zarattini & Aziz (2023), [Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading Systems](https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/). Dated 2023-11-13; rules and Tables 1–2 read from the full text.
- Krueger (2026), [The opening-range breakout paper, replicated on five indices](https://www.mql5.com/en/blogs/post/776235). Blog post, not peer-reviewed.
- Virtu Financial, [Form S-1 (2014)](https://www.sec.gov/Archives/edgar/data/0001592386/000104746914002070/a2218589zs-1.htm).
- Busse & Green (2002), [Market efficiency in real time](https://ideas.repec.org/r/eee/jfinec/v65y2002i3p415-437.html), *Journal of Financial Economics* 65.
- Chan (2003), "Stock price reaction to news and no-news: drift and reversal after headlines", *Journal of Financial Economics* 70.
- Lopez-Lira & Tang, [Can ChatGPT Forecast Stock Price Movements?](https://arxiv.org/abs/2304.07619v6), revised 2025-10-28.
- Barber, Huang, Odean & Schwarz (2022), [Attention-Induced Trading and Returns: Evidence from Robinhood Users](https://profiles.wustl.edu/en/publications/attention-induced-trading-and-returns-evidence-from-robinhood-use/), *Journal of Finance*.
- Berkman, Koch, Tuttle & Zhang (2012), [Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open](https://ideas.repec.org/a/cup/jfinqa/v47y2012i04p715-741_00.html), *JFQA* 47(4).
- Martineau (2022), [Rest in Peace Post-Earnings Announcement Drift](https://ideas.repec.org/a/now/jnlcfr/104.00000122.html), *Critical Finance Review* 11.
- Subrahmanyam, [Is post-earnings announcement drift a thing again?](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/), UCLA Anderson Review.
- Lucca & Moench (2015), [The Pre-FOMC Announcement Drift](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.html), *Journal of Finance* 70.
- Kurov, Wolfe & Gilbert (2021), [The disappearing pre-FOMC announcement drift](https://ideas.repec.org/a/eee/finlet/v40y2021ics1544612320315956.html), *Finance Research Letters* 40.
- Kaminski & Lo (2014), [When do stop-loss rules stop losses?](https://dspace.mit.edu/handle/1721.1/114876), *Journal of Financial Markets* 18.
- Coval & Shumway (2005), [Do Behavioral Biases Affect Prices?](https://ideas.repec.org/a/bla/jfinan/v60y2005i1p1-34.html), *Journal of Finance* 60(1).
- Garvey & Murphy (2004), [Are Professional Traders Too Slow to Realize Their Losses?](https://ideas.repec.org/a/taf/ufajxx/v60y2004i4p35-43.html), *Financial Analysts Journal* 60(4).
- Locke & Mann (2005), [Professional trader discipline and trade disposition](https://ideas.repec.org/a/eee/jfinec/v76y2005i2p401-444.html), *Journal of Financial Economics* 76(2).
- Kuo & Lin (2013), [Overconfident individual day traders: Evidence from the Taiwan futures market](https://ideas.repec.org/a/eee/jbfina/v37y2013i9p3548-3561.html), *Journal of Banking & Finance* 37.
- Barber, Lee, Liu, Odean & Zhang (2020), [Learning, Fast or Slow](https://ideas.repec.org/a/oup/rasset/v10y2020i1p61-93..html), *Review of Asset Pricing Studies* 10(1).
- Nagel (2012), [Evaporating Liquidity](https://www.nber.org/papers/w17653), *Review of Financial Studies* 25(7).
- Kelley & Tetlock (2013), [How Wise Are Crowds? Insights from Retail Orders and Stock Returns](https://business.columbia.edu/sites/default/files-efs/pubfiles/4471/Kelley_Tetlock_JF_12_How_Wise_Are_Crowds_with_Appendix.pdf), *Journal of Finance* 68.
- Heston, Korajczyk & Sadka (2010), [Intraday Patterns in the Cross-section of Stock Returns](https://ar5iv.arxiv.org/html/1005.3535), *Journal of Finance* 65(4).
- FTC (2022), [FTC bids good night to deceptive day trading earnings claims](https://www.ftc.gov/business-guidance/blog/2022/04/ftc-bids-good-night-deceptive-day-trading-earnings-claims).
- Kakhbod, Kazempour, Livdan & Schürhoff, [Finfluencers](https://www.sfi.ch/en/publications/n-23-30-finfluencers), Swiss Finance Institute.

From the earlier studies: Barber, Lee, Liu & Odean (2014); Gao, Han, Li & Zhou
(2018); Zarattini, Aziz & Barbon (2024); and the project's H-0030, H-0032 and
H-0033 records.
