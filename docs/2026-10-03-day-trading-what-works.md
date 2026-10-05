# What profitable day traders do, and whether day trading beats SPY

*2026-10-03, extended 2026-10-04 with H-0033. Research only.*

This builds on the project's three-part study of 2026-09-19 (`docs/2026-09-19-day-trading-*.md`).
It re-checks that study's key sources against the papers themselves, corrects
one of its claims, refreshes its SPY numbers, and runs the one documented
intraday effect the project had never tested (H-0032). On 2026-10-04 it also
replicates the strongest public claim that a day-trading rule beats SPY
(H-0033, section 4).

## The answer

| Question | Answer |
|---|---|
| Do some day traders consistently make money? | **Yes, but under 1% of them**, and it is measurable. In Taiwan, the 500 best day traders, chosen by the prior year's results, went on to make **+0.379% a day after fees** the following year. |
| Do most? | **No.** Of everyone who day traded futures in Brazil for more than 300 days, **97% lost money**. EU regulators found **74–89%** of retail CFD accounts lose. |
| What do the winners do? | Their own past results are the strongest predictor. Next comes **trading only a few stocks**. They earn more **around earnings announcements and in hard-to-value stocks**. Most of their orders are aggressive orders that cross the spread. Being *paid* the spread is how **high-frequency firms** win, using speed this bot cannot have. |
| Does the best-known "beats SPY" day-trading strategy still work? | **No.** "Beat the Market" (Zarattini, Aziz & Barbon, 2024) was replicated exactly as H-0033. It matched the paper on the paper's own years. **After publication** it made **+0.24% a year** unlevered and **+1.29% a year** at 2.7× average leverage. SPY made **+17.5% a year** over the same days. |
| Could this bot day trade its way past SPY? | **No evidence it could.** About three-quarters of SPY's return comes **overnight**, which a day trader never holds. Every daytime test in this project has failed, including H-0032 and H-0033. |

## 1. The evidence, checked against the sources

| Study | Who and when | Finding |
|---|---|---|
| Barber, Lee, Liu & Odean, *Journal of Financial Markets* 18 (2014) | All day traders in Taiwan, 1992–2006; about 450,000 a year | The top 500, ranked on the prior year, earned **61.3 bps a day before fees and 37.9 bps after**. The bottom earned −11.5 and −28.9. "Less than 1% … is able to predictably and reliably earn positive abnormal returns net of fees." About 20% of active day traders were positive in a given year, partly by luck. About 4,000 a year were predictably profitable. |
| Chague, De-Losso & Giovannetti, "Day Trading for a Living?" (2020) | Everyone who started day trading Brazilian equity futures, 2013–2015 | Of those who persisted more than 300 days, **97% lost money**. **1.1%** earned more than the minimum wage; **0.5%** more than a bank teller's starting salary. |
| Jordan & Diltz, *Financial Analysts Journal* (2003) | 324 US day traders, 1998–1999 | About twice as many lost as made money. **About 20%** were more than marginally profitable. Results tracked the Nasdaq, in the bubble years. |
| ESMA product intervention (2018) | Regulators' data across EU retail CFD accounts | **74–89%** of accounts lose money; average losses per client of €1,600–€29,000. |
| BIS Bulletin 69 (2023) | Crypto app users in 95 countries, 2015–2022 | **73–81%** of users had likely lost money on bitcoin. Large holders sold while small users bought. |
| Baron, Brogaard, Hagströmer & Kirilenko, *JFQA* 54(3) (2019) | High-frequency trading firms | Differences in **relative speed** explain large differences in performance. Firms whose colocation upgrades made them faster did better. |
| Beckmeyer, Branger & Gayda (2023) and Amaya, Garcia-Ares, Pearson & Vasquez (2025) | Same-day SPX options (0DTE) and retail options trades | **Contested.** Beckmeyer et al. estimate retail lost about $358,000 a day on 0DTE after May 2022. Amaya et al., using Cboe data and expiration values, find Cboe customer trades "on average profitable"; their study was funded by Cboe's education arm. |

## 2. What the profitable minority actually does

From Barber et al. (2014), the only whole-population study that ranks traders
and follows them forward:

1. **Their record persists.** Past performance is "by a large margin, the best
   predictor of future performance". Skill exists, but it shows up in a
   track record, not in a method anyone can copy.
2. **They concentrate.** After past performance, "the most important predictor
   of future performance is the concentration of trading in a few stocks". The
   authors read this as traders building an information advantage in those
   stocks.
3. **They trade when information is uneven.** The top group earned more on
   trades around **earnings announcements** (65.5 against 58.9 bps), and in
   **hard-to-value stocks**.
4. **They mostly take liquidity.** Day traders "tend to place aggressive
   orders", and aggressiveness is "an economically weak predictor" of profit.
   The authors conclude this is "not consistent with the hypothesis" that
   providing liquidity explains their returns.

**Correction to the 2026-09-19 study.** It said the top of the distribution
lives on liquidity provision, being paid the spread. That holds for
**high-frequency firms**, whose edge is speed: colocation and latency (Baron et
al.). It does **not** hold for the best retail day traders, by the most
complete evidence available. Those traders forecast short-term moves in a few
stocks they know well, around information events.

Two things the winners also have that matter as much as method:

- **Fees take a large share of what they make**: 61.3 bps before fees became
  37.9 after.
- **Survivorship works against outsiders.** By the Brazilian evidence, 97% of
  people still trading after a year are losing.

## 3. Why day trading is the wrong tool for beating SPY specifically

Using the bot's own SPY bars, 2024-07-24 to 2026-10-01 (549 sessions), split
into the overnight move and the daytime move:

| Part of the day | Total | A year | Average per session |
|---|---:|---:|---:|
| Buy and hold | +41.2% | +17.1% | |
| **Overnight (close to next open)** | +30.1% | **+12.8%** | 5.0 bps |
| **Daytime (open to close)** | +8.5% | **+3.8%** | **1.9 bps** |

Points to take from this:

- **About 76% of SPY's return came overnight.** The earlier window, to
  2026-09-17, gave 82%. Cliff, Cooper & Gulen (2008) found the same over
  1993–2003.
- **A day trader is flat every night, so starts about 13 points a year behind
  SPY.**
- **The daytime pool is shallow.** It averages about 1.9 bps a session, while
  this bot's cost model charges 12 bps for a round trip. Every point of
  daytime skill first has to pay that cost.

## 4. The project's daytime record

| Test | Size | Result |
|---|---|---|
| Opening-range breakout | 167,594 trades | −0.18% before costs; the volume effect runs backwards |
| Daytime swings | 192,000 trades | +0.009% gross: zero |
| Shorting violent opens (EXP-0013) | 154,131 sessions | Lost in every bucket |
| Shorter holding periods (EXP-0019) | decade | 1 day −39.3%; 20 days +123.1% |
| +0.5% / −0.2% exits (H-0030, today) | 1,857 trades, held 1.1 sessions on average | −0.02% a trade, against +0.57% with the current exits |
| **Intraday momentum on SPY (H-0032, today)** | 2,679 sessions | **REJECTED**; see below |
| **"Beat the Market" noise-area strategy (H-0033, 2026-10-04)** | 2,650 sessions, 2,360 trades | **REJECTED**: made nothing after publication; see below |
| **5-minute opening-range breakout on SPY (H-0034, 2026-10-04)** | 2,634 trades | **REJECTED**: −4.71% a year after publication; see `2026-10-04-what-else-day-traders-do.md` |
| **VWAP trend on SPY (H-0035, 2026-10-04)** | 21,389 trades | **REJECTED**: +0.94% a year after publication; same document |

### H-0032: the best-documented daytime effect, tested once

Gao, Han, Li & Zhou (*Journal of Financial Economics*, 2018) found that SPY's
first half hour predicts its last half hour, over 1993–2013. It needs 5-minute
bars, which the September study did not have. The project's preserved store of
SPY 5-minute bars (2016 to 2026-09-10) does.

**Rule, registered and sealed first** (seal `9323602e…`): if SPY rose from the
previous close to 10:00 ET, buy at 15:30 and sell at the 16:00 close.

**The effect existed, then turned around.**

| Period | Slope | t | R² |
|---|---:|---:|---:|
| 2016–2020 | +0.052 | 4.0 | 1.3% |
| 2021–2026 | **−0.022** | **−2.3** | 0.4% |
| Full window | +0.018 | 2.2 | 0.2% |

**It loses money even before costs.**

| Round-trip cost | Average per trade | t | Win rate |
|---|---:|---:|---:|
| 0 bps | −0.6 bps | −0.9 | 48% |
| **2 bps** (primary) | **−2.6 bps** | **−3.8** | 42% |
| 12 bps | −12.6 bps | −18.3 | 21% |

**Against SPY:**

- The account, with idle cash at the T-bill rate, made **−1.5% a year**
  against SPY's +13.1% (price only).
- It beat SPY in **2 of 11 years**, 2018 and 2022, which were years SPY fell.
- Trading both directions did no better: −2.2 bps a trade.

**Verdict: REJECTED** (R1, R2 and R4 fail; R3 passes on the full window only).
It follows the usual pattern for published anomalies: it worked in the years
before and around publication, then disappeared. McLean & Pontiff (*Journal of
Finance*, 2016) found published predictors' returns were 26% lower out of
sample and 58% lower after publication.

### H-0033: the strongest public claim that day trading beats SPY, replicated

Zarattini, Aziz & Barbon, "Beat the Market: An Effective Intraday Momentum
Strategy for S&P500 ETF (SPY)", was first posted on 2024-05-10. Over May 2007 to
April 2024, net of costs, it reported:

- **19.6% a year at a Sharpe of 1.33**;
- SPY over the same period: 7.2% a year, Sharpe 0.45.

It is the best-known public evidence that a day-trading rule beats SPY. It
uses only SPY prices, and every rule is written out, so it can be tested
without choosing anything. Everything after 2024-05-10 is out of sample for
its authors.

**The rule, from the paper, sealed before any result was computed** (seal
`e16bc81a…`, registered 2026-10-04 16:44 UTC):

- **Noise area.** For each time of day, sigma is the average absolute move
  from the 09:30 open over the previous 14 sessions.
- **Bands.** Upper = max(today's open, yesterday's close) × (1 + sigma).
  Lower = min(today's open, yesterday's close) × (1 − sigma).
- **Signal.** Checked at 10:00, 10:30, … 15:30. Long above the upper band and
  above VWAP; short below the lower band and below VWAP; otherwise flat. All
  positions close at 16:00.
- **Sizing (B).** 100% of equity, no leverage.
- **Sizing (C).** Targets 2% daily volatility using SPY's last 14 daily
  returns, capped at 4× leverage.
- **Costs.** The paper's $0.0035 commission plus $0.001 slippage per share,
  each side.

**Data, checked before registration.** Two problems were found and fixed:

- **Early closes.** The 5-minute store carries after-hours bars on the 21
  NYSE early-close days (13:00 closes). Those bars are now dropped. The
  calendar was confirmed against the data: those 21 days are exactly the 21
  with the lowest afternoon volume.
- **Duplicate days.** The first day of each quarter appears in two files. The
  bars are now merged by timestamp. The two copies were identical.

**No look-ahead.** On a synthetic random walk the engine's pre-cost Sharpe was
−0.43 (t −1.4), which is zero.

**It worked before publication. It did nothing after.**

| | Paper's own test, May 2007–Apr 2024 | Replication, Jan 2016–Apr 2024 | **After publication**, 2024-05-10 to 2026-09-10 |
|---|---|---|---|
| B: no leverage | 9.7%/yr, Sharpe 1.24 | 6.7%/yr, Sharpe 1.00, worst drop −11.7% | **+0.24%/yr, Sharpe 0.07**, worst drop −9.8% |
| C: volatility-targeted, up to 4× | 19.6%/yr, Sharpe 1.33 | 18.0%/yr, Sharpe 1.23, worst drop −25.1% | **+1.29%/yr, Sharpe 0.16**, worst drop −21.1% |
| SPY held, same days | 7.2%/yr, Sharpe 0.45 | 12.7%/yr, Sharpe 0.74, worst drop −34.2% | **+17.5%/yr, Sharpe 1.11**, worst drop −19.0% |

Notes on the table:

- **SPY figures are price only.** The store is unadjusted: SPY's 2017 here is
  +19.38%, its price return. Total return adds about 1.3–1.6 points a year.
- **Sharpe** uses the paper's convention: risk-free rate 0, daily mean ×
  √252.

**Over the whole window**, 2016-01-26 to 2026-09-10:

| | A year | Sharpe | Worst drop |
|---|---:|---:|---:|
| B | 5.11% | 0.80 | −11.7% |
| C | 13.69% | 0.97 | −25.1% |
| SPY, price only | 14.04% | 0.83 | −34.2% |

**Year by year after publication:**

| Period | C | SPY, price only |
|---|---:|---:|
| 2024, from 10 May | +17.2% | +12.7% |
| 2025 | −1.8% | +16.4% |
| 2026, to 10 September | −10.4% | +11.1% |

| Sealed criterion | B | C |
|---|---|---|
| R1: replication Sharpe ≥ 1.0, 2016 to Apr 2024 | pass (1.004) | pass (1.23) |
| **R2: after publication, return > 0 and Sharpe above SPY's 1.11** | **FAIL** (0.07) | **FAIL** (0.16) |
| R3: positive in at least 8 of 11 years | pass (8) | fail (7) |
| R4: full-window Sharpe ≥ 0.7 at doubled costs | pass (0.71) | pass (0.86) |
| R5: worst drop no deeper than SPY's −34.2% | pass (−11.7%) | pass (−25.1%) |

**Verdict: REJECTED, both versions** (R2 fails).

**Giving it every fair allowance:**

- **Idle cash.** An unlevered day trader's cash sits idle overnight. Credit it
  the T-bill rate, which averaged 4.1% over this window, and B makes about
  4.4% a year. That is still about 13 points a year behind SPY.
- **2.3 years is short.** If the pre-publication Sharpe were still true, a
  result this bad would happen about 1 time in 13 for B (p = 0.08) and 1 in 19
  for C (p = 0.05).
  - So it is **not proven** that the edge is gone.
  - What is proven is that it has **not beaten SPY since publication**, by
    about 16 points a year.
  - The drop matches the McLean–Pontiff pattern above.
- **The leverage did the work.** C's near-tie with SPY over the whole window
  (13.7% against 14.0% price, about 15.5% total return) needed:
  - **2.66× average exposure**, at the 4× cap on 21% of days;
  - mostly the years before publication.
- **What it does have is a hedge-like profile.** B's worst drop was −11.7%
  against SPY's −34.2%, and it made money when SPY fell:
  - 2018: +21%, against SPY's −6%;
  - 2022: +17%, against SPY's −19%.

  B beat SPY in only 2 of 11 years, and those were the two. That is
  diversification, not outperformance, and it is not the owner's goal.

**A check on the replication itself.** It made 2,360 entries, trading on
1,598 of 2,650 sessions (60%). The paper traded on 2,620 days of a roughly
4,250-day sample (62%). Its 7,964 "trades" are about 3 per traded day,
against 1.48 entries here. That is consistent with the paper counting entries
and exits separately, but this is not confirmed.

**Correction to H-0032.** The early-close problem also affected the H-0032
engine: 17 early-close sessions used after-hours prices. An exploratory
recheck without them:

- long-only at 2 bps: −2.64 → −2.75 bps (t −3.95);
- slope t: 2.17 → 2.08.

The verdict is unchanged: REJECTED.

## 5. What this means for the bot

- **Nothing in the evidence says a retail-scale bot can day trade its way past
  SPY.**
  - The rare winners have an information edge in a few stocks they know well,
    a track record that comes first, and high fees they still clear.
  - The firms with an edge built from structure, high-frequency traders, win on
    speed.
  - This bot has none of those.
  - Its own measured edge is the opposite of day trading. About 74% of its
    return comes overnight, and its best exits are the slow ones (H-0030).
- **Even the best-known published day-trading strategy did not survive its own
  publication** (H-0033). It also needed up to 4× leverage and daily shorting
  to look good. The project's rules allow neither, and the bot has no intraday
  order path.
- **The one transferable lesson has already been applied.** Exits work better
  as resting orders at the broker than as market orders. As of EXP-0056, the
  take profit rests at the broker.
- **Not recommended:** a day-trading mode. Nothing has been built.

## Sources

Checked 2026-10-03:

- Barber, Lee, Liu & Odean (2014), [The cross-section of speculator skill: Evidence from day trading](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf), *Journal of Financial Markets* 18, 1–24. The quotations above are from the paper's text.
- Chague, De-Losso & Giovannetti (2020), [Day Trading for a Living?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- Jordan & Diltz (2003), [The Profitability of Day Traders](https://www.semanticscholar.org/paper/The-Profitability-of-Day-Traders-Jordan-Diltz/c495c9e303835dc65d2af70d98dd545c75e092b7), *Financial Analysts Journal*.
- ESMA (2018), [product intervention on CFDs and binary options](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors).
- Cornelli, Doerr, Frost & Gambacorta (2023), [BIS Bulletin 69: Crypto shocks and retail losses](https://www.bis.org/publ/bisbull69.htm).
- Baron, Brogaard, Hagströmer & Kirilenko (2019), [Risk and Return in High-Frequency Trading](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/risk-and-return-in-highfrequency-trading/81F7800250E37410ADB20A989564814B), *JFQA* 54(3).
- Beckmeyer, Branger & Gayda (2023), [Retail Traders Love 0DTE Options… But Should They?](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf)
- Amaya, Garcia-Ares, Pearson & Vasquez (2025), [New Evidence on the Performance of Customer Options Trades](https://cdn.cboe.com/resources/education/research_publications/Retail_Profitability.pdf), Cboe-funded.
- Gao, Han, Li & Zhou (2018), [Market intraday momentum](https://www.researchwithrutgers.org/en/publications/market-intraday-momentum/), *Journal of Financial Economics* 129, 394–414.
- Zarattini, Aziz & Barbon (2024), [Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172), SSRN 4824172; first version 2024-05-10. The rules were read from the [full text](https://alexandria.unisg.ch/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/download).
- McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance* 71(1).
- Cliff, Cooper & Gulen (2008), [Return differences between trading and non-trading hours](https://www.researchgate.net/publication/233589349_Returns_in_Trading_versus_Non-Trading_Hours_The_Difference_is_Day_and_Night).

Project sources:

- `docs/2026-09-19-day-trading-research.md`, `-deep-dive.md` and `-part-iii.md`.
- `docs/phase5/h0032-results.json` and `scripts/run_h0032.py`; H-0032 in
  `docs/preregistrations.jsonl`.
- `docs/phase5/h0033-results.json`, `scripts/run_h0033.py`,
  `scripts/h0033_noise_area.py` and `scripts/h0033_spec.py`; H-0033 in
  `docs/preregistrations.jsonl`, with code bound by SHA-256.
- `docs/2026-10-03-shorting-and-all-in-report.md` (H-0030).
- The SPY split is computed from `data/SPY.csv`.
