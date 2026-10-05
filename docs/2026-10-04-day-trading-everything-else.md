# Day trading: everything else, and the whole record in one table

*2026-10-04, third round. Research only. Nothing implemented, no live change,
nothing committed.*

This continues `2026-10-04-what-else-day-traders-do.md`. It adds:

- the one test that covers what most day traders actually do, chart rules
  (H-0036);
- a descriptive check of "fade the open" on SPY;
- about twenty more practices checked against primary sources;
- section 4, one table of every day-trading strategy and practice this
  project has examined, so nothing is left out.

## The answer

**Still no.** Nothing day traders do makes money consistently *and* is
reachable from this bot.

- **The chart rules almost passed.** The largest test of chart rules there
  is — all 7,846 rules from the standard study, run on SPY 5-minute bars as
  day trades — produced the closest call of the whole program:
  - its best rule earned money from 2018 to 2023, and kept earning when picked
    on 2016–2020 and judged on 2021–2026;
  - but it **failed the correction for trying 7,846 rules** (SPA p = 0.16);
  - and it **has earned nothing since 2024**.
- **India's regulator measured almost every trader in its market.** 7 in 10
  intraday traders lost money in a year, and 93% of 10 million options and
  futures traders lost over three years. The profits went to proprietary
  firms and foreign funds trading by algorithm.
- **The pattern-day-trader rule is gone.** The SEC approved its removal in
  April 2026, which corrects the September study.

## 1. H-0036: every standard chart rule, as SPY day trades

**What was tested.** Sullivan, Timmermann & White (1999) built the standard
universe of technical rules and the test that corrects for searching through
them. The universe has 7,846 rules:

- 497 filter rules;
- 2,049 moving-average rules;
- 1,220 support-and-resistance rules;
- 2,040 channel break-outs;
- 2,040 on-balance-volume rules.

Marshall, Cahan & Cahan (2008) ran it on SPY 5-minute bars for 2002–2003, and
no rule was profitable after the correction. H-0036 asks the same of
2016–2026, with every position closed at 16:00, a $0.0045-a-share cost on
every change, and an out-of-sample test.

- **Sealed** before any result (seal `4811522a…`). The rules are the paper's
  Appendix A exactly.
- **Bootstrap** as the paper: q = 0.1, 1,000 draws.

| | Result |
|---|---|
| Best rule over 2016–2026 | a 0.5% filter: long after SPY rises 0.5% from a recent low, short after it falls 0.5% from a recent high |
| Its return | +5.9 bps a day, +14.8% a year on the money traded (naive t 3.9) |
| Corrected for 7,846 tries | Reality Check p = **0.021**; **SPA p = 0.159** |
| Before costs | Reality Check p = 0.009; SPA p = 0.048 |
| Picked on 2016–2020, judged on 2021–2026 | **+10.8% a year**, t 2.12, Sharpe 0.90, against SPY's 13.8% and Sharpe 0.84 |
| Rules with a positive mean after costs | 49% |

**Verdict: REJECTED.** The sealed criteria needed both corrected tests below
0.05. The SPA test, the more powerful of the two, says p = 0.16: across 7,846
rules, a best rule this good turns up by chance about one time in six. The
out-of-sample criteria (R2, R3) did pass.

**What it actually found.** Checked after the run (exploratory; the verdict
stands):

| Year | Best rule | Year | Best rule |
|---|---:|---|---:|
| 2016 | +0.3% | 2022 | +27.4% |
| 2017 | −7.4% | 2023 | +11.6% |
| 2018 | +25.6% | **2024** | **−0.2%** |
| 2019 | +23.9% | **2025** | **+3.8%** |
| 2020 | +54.9% | **2026, to Sep 10** | **−1.3%** |
| 2021 | +19.6% | **since 2024-05-10** | **−0.1% a year** |

- **Same effect as H-0033.** It is the intraday trend effect "Beat the Market"
  caught, strong from 2018 to 2023, and gone since 2024.
- **A few big days carry it.** Without its best 1% of days, the 10-year total
  falls from +156% to +63%. Without the best 5%, it is −108%.
- **It is not an artefact:**
  - filled one bar later, it earns the same (+5.86 bps a day);
  - at doubled costs it still earns +5.43 bps a day;
  - it trades about 3.5 times a session and is always in the market.

**Engine checks.**

- **Every rule family against hand-worked cases.** Several of my own
  expected answers were wrong; the engine was right each time.
- **Pure noise:** nothing significant on two random walks (Reality Check p
  1.0 and 0.88; SPA p 0.29 and 0.55).
- **Built-in intraday trends:** the trend rule found at p = 0.000, and still
  working out of sample (t 44).

## 2. "Fade the open" on SPY, described

Descriptive only, with no strategy. SPY, 2,644 sessions, 2016–2026:

| | 2016–2020 | 2021–2023 | 2024–2026 | All |
|---|---:|---:|---:|---:|
| Correlation, overnight gap with open-to-close | −0.06 | −0.01 | −0.11 | −0.05 |
| Correlation, first 30 minutes with the rest of the day | −0.08 | +0.00 | +0.10 | −0.01 |
| After the biggest 10% of gaps, the rest of the day in the gap's direction | −0.03% (t −0.3) | −0.02% (t −0.1) | −0.17% (t −1.1) | −0.07% (t −0.9) |
| After the biggest 10% of first-30-minute moves, the same | −0.08% (t −0.6) | +0.06% (t +0.4) | +0.18% (t +1.1) | +0.04% (t +0.5) |

**Neither fading the open nor going with it is reliable on SPY.** Grant, Wolf
& Yu (2005) found S&P 500 futures reversed after large opening moves over
1987–2002, but the reversals were "sharply reduced" by a bid-ask cost. Their
exact rule is not published anywhere reachable, so it was not replicated.

## 3. Everything else day traders do, checked

### 3.1 The best whole-market evidence: India's regulator

SEBI studied nearly every individual trader in India:

- **Intraday stock trading, 2022–23** (released July 2024; individual clients
  of the 10 largest brokers, about 86% of all individual clients):
  - **7 in 10** intraday traders lost money;
  - **8 in 10** of those making more than 500 trades a year;
  - **76%** of traders under 30;
  - on top of their losses, loss-makers paid **another 57%** of those losses
    in trading costs.
- **Options and futures, 2021–22 to 2023–24** (September 2024):
  - **93% of over 10 million individual traders lost money**, about ₹2 lakh
    each on average, ₹1.8 lakh crore in total, costs included;
  - **1%** made more than ₹1 lakh after costs;
  - the money went to proprietary traders (₹33,000 crore of gross profit in
    2023–24) and foreign funds (₹28,000 crore). **96–97% of their profits
    came from algorithmic trading.**

This is the clearest answer yet to "who makes the money every day": firms
trading by algorithm, from individuals.

### 3.2 Chart patterns and indicators

- **7,846 intraday rules on SPY 5-minute bars, 2002–2003** (Marshall, Cahan &
  Cahan, 2008): "none … are profitable after data snooping bias is taken into
  account". H-0036 above repeats it for 2016–2026.
- **Candlesticks.** No value found:
  - 28 candlestick signals on Dow stocks, 1992–2002 (Marshall, Young & Rose,
    2006);
  - 83 candlestick rules on 5-minute bars of Dow stocks, 2010–2011
    (Duvinage, Mazza & Petitjean, 2013): about a third beat buy-and-hold
    before costs, but after costs and the data-snooping correction, none.
- **The best old rules stopped working.** On the Dow, the best of 7,846 rules
  stopped outperforming in the decade after the original study; on S&P 500
  futures, none ever beat the benchmark (Sullivan, Timmermann & White, 1999).
- **Even the best rules can't be picked in advance.** Over 1897–2011, no
  investor could have chosen the future best rules ahead of time, and even
  in-sample, low costs wiped out their performance (Bajgrowicz & Scaillet,
  2012).
- **Round numbers.** Currency take-profits cluster at round numbers, where
  trends tend to stall, and stop-losses just beyond them, where trends speed
  up (Osler, 2003). This is a real order-flow effect, and the one way chart
  levels can matter.

### 3.3 Judging any strategy claim

- **Backtest overfitting.** Trying a modest number of variants makes a great
  backtest easy to produce (Bailey, Borwein, López de Prado & Zhu, 2014).
  Overfit strategies can lose money afterwards, not just earn nothing.
- **A t-statistic above 3.0** is the bar after decades of searching (Harvey,
  Liu & Zhu, 2016).
- **AI-read news has look-ahead traps.** In a backtest a language model can
  "know" what happened next, and knowing the company's name distorts its read
  of the headline. Removing the names helps (Glasserman & Lin, 2023).

### 3.4 Information day traders buy or follow

- **Social-media sentiment.** The first half hour's change in StockTwits
  sentiment predicted SPY's last half hour, driven by novice traders: "noise
  trading" (Renault, 2017). It has not been tested here; the data is not held.
- **Reddit research.** WallStreetBets due-diligence posts predicted returns
  before the GameStop squeeze, and not after it (Bradley, Hanousek, Jame &
  Xiao).
- **"Unusual options activity."** Stocks with low put-call ratios beat those
  with high ones by more than 40 bps the next day and more than 1% over the
  next week (Pan & Poteshman, 2006). But the ratios came from opening buys,
  which were **not public**. The authors trace the predictability to private
  information, not to anything a subscriber can buy.
- **Order-book AI.** Deep learning on billions of order-book events predicts
  the next price move with stable accuracy out of sample (Sirignano & Cont,
  2019). It needs the full order book and speed; neither is reachable.

### 3.5 Where retail traders lose to the other side

- **Options before earnings.** Retail buyers lose **5–9%** on average, and
  **10–14%** before the most volatile announcements. They overpay for
  volatility, pay wide spreads and react slowly; market makers collect it
  (de Silva, Smith & So).
- **The same "free" trade costs different amounts at different brokers.** In
  85,000 simultaneous orders, round-trip execution cost ranged from **0.07% to
  0.46%** depending on the broker, commissions excluded, and payment for order
  flow did not explain it. Each basis point costs retail traders about $2.8
  billion a year (Schwarz, Barber, Huang, Jorion & Odean, *Journal of
  Finance* 2025).
- **The close.**
  - The closing auction grew from 3.1% of daily volume in 2010 to 7.5% in
    2018, driven by index funds and ETFs.
  - Closing prices are pushed away from fair value, and the push reverses by
    half soon after the close and fully overnight (Bogousslavsky & Muravyev,
    2023).
  - Absorbing that push is an institutional liquidity trade.
- **Leveraged ETFs.** Their daily re-leveraging adds volatility near the
  close, and holding them loses value through path dependence (Cheng &
  Madhavan, 2009). This matters because the breakout and VWAP papers'
  headline returns came from TQQQ.
- **After hours.** Prices are less efficient after hours than during the day
  (Barclay & Hendershott, 2003).

### 3.6 Other markets and old favourites

- **Bitcoin.** The first half hour, by volume, predicts the last, especially
  in downturns, and the effect comes from liquidity provision (Shen, Urquhart
  & Wang, 2022). The project's crypto tests (EXP-0003, -0015, -0032 to -0035)
  were rejected on daily data.
- **Pairs trading.** It made up to 11% a year in excess returns over
  1962–2002 (Gatev, Goetzmann & Rouwenhorst, 2006). The top 20 pairs' monthly
  excess return then fell from 0.86% (1962–1988) to 0.37% (1989–2002) and
  0.24% (2003–2009), though it did well in turbulent markets (Do & Faff,
  2010).
- **Copy trading.** Seeing others' results raises risk-taking, and being able
  to copy them raises it more (Apesteguia, Oechssler & Weidenholzer, 2020).

### 3.7 Rules and enforcement

- **Correction: the pattern-day-trader rule is gone.**
  - The SEC approved FINRA's amendments to Rule 4210 on 14 April 2026,
    effective 4 June 2026, and brokers have until 20 October 2027 to
    implement them.
  - The PDT label and the $25,000 minimum no longer exist. Every margin
    account now follows an intraday margin standard that tracks actual
    exposure.
  - The September study's PDT points, including "futures avoid the PDT rule",
    are out of date.
- **Some of the "consistent daily money" is illegal:**
  - JPMorgan paid $920 million in 2020 for spoofing metals and Treasury
    futures over 2009–2016, admitting wrongdoing.
  - In 2022 eight social-media influencers (the "Atlas Trading" group) were
    charged with a $100 million-plus pump-and-dump. A court dismissed the
    criminal case; in 2025 the Fifth Circuit reinstated it. These are charges,
    not findings.
  - In July 2025 India's SEBI barred Jane Street in an interim order alleging
    expiry-day index manipulation, and impounded ₹4,843.57 crore. Jane Street
    deposited the sum and contests the findings. These are allegations.
- **Prop-firm "challenges."** The 2023 CFTC fraud case against My Forex Funds
  was dismissed with prejudice in 2025 after the court found the regulator had
  misled it. There is no court finding either way. Industry figures on pass
  and payout rates remain marketing-grade.

## 4. Every day-trading strategy and practice examined, in one table

**Tested here, on this project's data:**

| Strategy | Test | Result |
|---|---|---|
| Opening-range breakout, "stocks in play" | 167,594 trades, 230 large caps (2026-09-07) | −0.18% a trade before costs; REJECTED (the paper used 7,000+ stocks) |
| Intraday swing trading (RSI, 15-minute bars) | 192,000 trades (2026-09-09) | zero before costs; REJECTED |
| Shorting violent opens | 154,131 sessions (2026-09-10) | violent opens kept rising; REJECTED |
| Fading the worst gaps | 322 firings, day-collapsed (2026-09-19) | t −1.00; REJECTED |
| Harvesting the overnight move | SPY (2026-09-19) | the cost is 2.5× the premium; REJECTED |
| Trading the news, from headlines | 4,668 items (2026-09-18) | t ≈ 0 once days are collapsed; the archive has no article text |
| +0.5% target / −0.2% stop | H-0030 | −0.02% a trade against +0.57%; REJECTED |
| Shorting | H-0027–H-0029 | every sleeve lost; REJECTED |
| One all-in position | H-0031 | 2.56% a year, −38.7% drawdown; REJECTED |
| First half hour predicts the last (Gao et al.) | H-0032 | reversed after 2020; REJECTED |
| "Beat the Market" noise area | H-0033 | about +0.2% to +1.3% a year after publication; REJECTED |
| 5-minute opening-range breakout | H-0034 | −4.7% a year after publication; REJECTED |
| VWAP trend | H-0035 | +0.9% a year after publication; REJECTED |
| **Every standard chart rule (7,846)** | **H-0036** | **closest call; failed the search correction; zero since 2024; REJECTED** |
| Fade or follow the open | descriptive, this document | nothing |

**From the literature, not testable here:**

| Practice | Evidence | Reachable? |
|---|---|---|
| Market making, high-frequency trading | the most consistent daily profits (Virtu: 1 losing day in 1,238) | no: speed, scale, rebates |
| Latency arbitrage | races of 5–10 microseconds; 6 firms win more than 80% | no |
| Speed on news | priced within a minute | no |
| AI-read headlines | works in small stocks; fading as adoption rises | no feed |
| Earnings plays | top traders earn more; the drift is gone outside microcaps | no |
| Pre-Fed-announcement drift | gone since 2015 | n/a |
| Pairs trading | decayed; turbulent-period profits | daily-data question, not day trading |
| Chasing hot or attention stocks | loses (Robinhood herding −4.7% over 20 days) | not worth it |
| Candlesticks and chart patterns | no value after costs and data snooping | tested, H-0036 |
| Options before earnings | retail loses 5–9% | no |
| Same-day (0DTE) options | contested | no options path |
| Social-media sentiment | intraday noise trading | no data |
| Options-flow services | the predictive part was private | no |
| Closing-auction pressure | institutional liquidity provision | no |
| Following gurus and finfluencers | 56% have negative skill; FTC: most Warrior Trading customers lost | avoid |
| Copy trading | raises risk-taking | avoid |
| Prop-firm challenges | most fail on drawdown; marketing-grade data | n/a |
| Manipulation | prosecuted (spoofing, pump-and-dump, alleged index manipulation) | illegal |
| Discipline: loss limits, no revenge trading, cutting losers | rewarded in the studies | **already built in** |
| Broker execution quality | 0.07%–0.46% round trip between brokers | worth knowing |
| Being paid the spread (resting orders, not market orders) | the professionals' edge; for retail, aggressive orders and concentration predicted profit instead (Barber et al. 2014) | partly: exits now rest at the broker (EXP-0056) |
| Order-flow imbalance at the best bid and ask | the most reproducible short-horizon relation (Cont, Kukanov & Stoikov) | no order-book data |
| Trading more often to use the √N law | works only when the cost per trade is near zero; H-0007 measured the edge decaying 72% under forced frequency | no |
| Position sizing by Kelly | the bot bets about 1/16 of Kelly, correctly given how uncertain its edge is | already conservative |
| Staying small (capacity) | the one real structural advantage of a small account | about 51× headroom |
| Futures instead of stocks | 60/40 tax treatment (Section 1256); the PDT advantage is gone since 2026 | Alpaca has no futures |
| Trader tax status and the 475(f) election | facts-and-circumstances test; a sticky election | a tax adviser's question |

## Sources

Checked 2026-10-04:

- SEBI, [Updated study: 93% of individual traders incurred losses in equity F&O, FY22–FY24](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html); intraday cash study as reported by [Business Standard](https://www.business-standard.com/markets/news/7-in-10-intraday-traders-in-equity-cash-suffered-losses-in-fy23-sebi-study-124072400975_1.html).
- Sullivan, Timmermann & White (1999), "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap", *Journal of Finance* 54; Appendix A read from the [working paper](https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf).
- Marshall, Cahan & Cahan (2008), [Does intraday technical analysis in the U.S. equity market have value?](https://ideas.repec.org/a/eee/empfin/v15y2008i2p199-210.html), *Journal of Empirical Finance* 15; instrument and period per [CXO Advisory](https://cxoadvisory.com/?p=1253).
- White (2000), [A Reality Check for Data Snooping](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping), *Econometrica* 68; Hansen (2005), "A Test for Superior Predictive Ability", *JBES* 23.
- Marshall, Young & Rose (2006), [Candlestick technical trading strategies](https://ideas.repec.org:443/a/eee/jbfina/v30y2006i8p2303-2323.html), *Journal of Banking & Finance* 30 (summary per [CXO Advisory](https://www.cxoadvisory.com/technical-trading/candlesticks-fiddlesticks/)); Duvinage, Mazza & Petitjean (2013), *Quantitative Finance* (per [CXO Advisory](https://cxoadvisory.com/technical-trading/testing-japanese-candlesticks-intraday-on-liquid-stocks)).
- Bajgrowicz & Scaillet (2012), [Technical trading revisited](https://ideas.repec.org:443/a/eee/jfinec/v106y2012i3p473-491.html), *Journal of Financial Economics* 106.
- Osler (2003), [Currency orders and exchange rate dynamics](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.html), *Journal of Finance* 58.
- Bailey, Borwein, López de Prado & Zhu (2014), [Pseudo-Mathematics and Financial Charlatanism](https://scholarworks.wmich.edu/math_pubs/40/), *Notices of the AMS* 61(5); Harvey, Liu & Zhu (2016), [… and the Cross-Section of Expected Returns](https://www.nber.org/papers/w20592), *RFS* 29.
- Glasserman & Lin (2023), [Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis](https://arxiv.org/abs/2309.17322).
- Renault (2017), [Intraday online investor sentiment and return patterns in the U.S. stock market](https://ideas.repec.org/a/eee/jbfina/v84y2017icp25-40.html), *Journal of Banking & Finance* 84.
- Bradley, Hanousek, Jame & Xiao, "Place Your Bets? The Value of Investment Research on Reddit's Wallstreetbets" ([summary](https://academicnewsletter.sufe.edu.cn/info/351572)).
- Pan & Poteshman (2006), [The Information in Option Volume for Future Stock Prices](https://www.nber.org/papers/w10925), *RFS* 19.
- Sirignano & Cont (2019), [Universal features of price formation in financial markets](https://arxiv.org/abs/1803.06917v1), *Quantitative Finance*.
- de Silva, Smith & So, [Losing is Optional: Retail Option Trading and Expected Announcement Volatility](https://www.gsb.stanford.edu/faculty-research/publications/losing-optional-retail-option-trading-expected-announcement).
- Schwarz, Barber, Huang, Jorion & Odean (2025), [The "Actual Retail Price" of Equity Trades](https://ideas.repec.org/a/bla/jfinan/v80y2025i5p2507-2541.html), *Journal of Finance* 80.
- Bogousslavsky & Muravyev (2023), [Who trades at the close?](https://ideas.repec.org/a/eee/finmar/v66y2023ics1386418123000502.html), *Journal of Financial Markets* 66.
- Cheng & Madhavan (2009), [The Dynamics of Leveraged and Inverse Exchange-Traded Funds](https://www.joim.com/the-dynamics-of-leveraged-and-inverse-exchange-traded-funds/), *Journal of Investment Management* 7(4).
- Barclay & Hendershott (2003), [Price discovery and trading after hours](https://ideas.repec.org/a/oup/rfinst/v16y2003i4p1041-1073.html), *RFS* 16.
- Shen, Urquhart & Wang (2022), [Bitcoin intraday time series momentum](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/), *Financial Review* 57.
- Gatev, Goetzmann & Rouwenhorst (2006), "Pairs Trading", *RFS* 19 ([working paper](https://ideas.repec.org:443/p/nbr/nberwo/7032.html)); Do & Faff (2010), [Does simple pairs trading still work?](https://ideas.repec.org/a/taf/ufajxx/v66y2010i4p83-95.html), *FAJ* 66.
- Apesteguia, Oechssler & Weidenholzer (2020), "Copy Trading", *Management Science* 66(12) ([summary](https://bse.eu/node/9553)).
- Grant, Wolf & Yu (2005), [Intraday price reversals in the US stock index futures market](https://researchwith.montclair.edu/en/publications/intraday-price-reversals-in-the-us-stock-index-futures-market-a-1/), *Journal of Banking & Finance* 29.
- WilmerHale (2026), [SEC approves amendments to FINRA Rule 4210](https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard).
- CFTC (2020), [JPMorgan to pay $920 million for spoofing](https://cftc.gov/PressRoom/PressReleases/8260-20); US DOJ, [United States v. Constantinescu et al.](https://www.justice.gov/criminal/criminal-vns/case/united-states-v-constantinescu-et-al) and [Fifth Circuit reinstatement](https://clsbluesky.law.columbia.edu/2025/10/16/quinn-emanuel-discusses-fifth-circuit-decision-reinstating-securities-fraud-indictment); SEBI interim order against Jane Street as reported by [Oxford Business Law Blog](https://blogs.law.ox.ac.uk/oblb/blog-post/2025/07/jane-street-and-expiry-day-trap-unpacking-sebis-crackdown-algorithmic); My Forex Funds dismissal per [Finance Magnates](https://financemagnates.com/forex/mff-case-misconduct-embarrassment-for-the-cftc-but-not-yet-a-win-for-prop-trading).

Project records:

- H-0036: `scripts/h0036_ta_universe.py`, `h0036_spec.py`, `run_h0036.py`,
  `tests/test_h0036_ta_universe.py`, and `docs/phase5/h0036-results.json`.
- Earlier rounds: `docs/2026-09-19-day-trading-*.md`,
  `2026-10-03-day-trading-what-works.md` and
  `2026-10-04-what-else-day-traders-do.md`.
