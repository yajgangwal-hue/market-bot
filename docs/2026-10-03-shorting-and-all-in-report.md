# Shorting, the +0.5% / −0.2% target, and one all-in trade: sealed tests, all rejected

*2026-10-03. H-0027 to H-0031 were each registered and sealed before any
result was computed. Research only:*

- *no live behaviour, frozen parameter or fingerprint was changed;*
- *no broker was called;*
- *nothing was committed.*

## The answers

| Question | Answer | The number that decides it |
|---|---|---|
| Should the bot short? | **No: rejected.** All three short sleeves made the account worse. | Return a year fell from 5.13% to 4.17% (failed-rally shorts), 4.88% (bear-market only) and 2.34% (momentum shorts). Each also lowered the risk-adjusted return. |
| Can a trade make about +0.5% and lose only about −0.2%? | **No.** | On the bot's own buy signals that pair averages −0.02% a trade, against +0.57% with the current exits (paired t = −4.5). About half of the −0.2% stops are hit by the overnight gap; 1 in 5 loses more than 1%. |
| One big trade with all the money? | **No: rejected.** | 2.56% a year against 5.13%. Worst drop from a peak −38.7% against −12.5%. 2022 −25%. One trade lost $12,717. |
| Can the bot tell when stocks will fall? | **Not usefully.** | Failed-rally signals fell over the next 20 sessions 54% of the time, against 44% for comparable stocks. That is too little to pay for the stops. Momentum signals fell *less* often than average (41%). |
| Does any of this beat SPY? | **No.** | SPY total return was 15.0% a year over the same years. A SPY and T-bill mix with the bot's own volatility made about 9.5% a year. The bot makes 5.1%, and none of these tests raised it. |

**Classification: REJECTED for all five hypotheses.** No implementation plan
follows, because nothing reached a stage that would justify one.

## 1. What the current strategy exploits

| | |
|---|---|
| Rule | Buy RSI(14) ≤ 35 above the 200-day average, at the signal close |
| Exits | 2.5-ATR stop, RSI ≥ 60, 20 sessions; since 2026-09-29 also a 2.5-ATR take profit (EXP-0055) |
| Where the money comes from | A short-term bounce in uptrends: the overnight gap and the asymmetry between average win and average loss. Not from calling direction: the win rate is 51%. |
| Its weakness against SPY | Exposure. It is invested 44% of the time and its beta is 0.30. |
| When it does best | When SPY is *below* its 200-day average (EXP-0043) |

A short side would cut market exposure further. That is the opposite of
what the gap to SPY needs.

## 2. What was already answered, and was not re-run

| ID | What it tested | Result |
|---|---|---|
| EXP-0011 | Mirror short book, sized by stop distance | −0.88% a year (decade), −0.19% a year (thirty years) |
| EXP-0012 | Shorting the long rule's own signals | −0.501% a trade, no gradient |
| EXP-0013 | Shorting violent opens | Negative in every bucket, 154,131 sessions |
| EXP-0026 | Violent-gap shorts run as accounts | −49.8% to −64.2% a year |
| EXP-0011 | Overbought shorts *above* the 200-day | −0.454% a trade |
| EXP-0043 | Market regime | The long book is better when SPY is below its 200-day |
| EXP-0021 / EXP-0046 | Per-name cap ≠ 20%; a larger risk budget | 20% is best; every larger risk budget is worse. Neither ever put the whole account in one name. |
| H-0021 / H-0025 / H-0026, EXP-0049/0050 | Long-side band exits and take profits | All closed |

## 3. What is new, and how it was governed

| ID | Hypothesis | Configs | Seal |
|---|---|---:|---|
| H-0027 | Failed-rally shorts (RSI ≥ 70 below the 200-day) in a separate sleeve at equal 5% notional. This is EXP-0011's own open question. | 1 | `04edeb97…` |
| H-0028 | The same, new shorts only when SPY has been below its 200-day for 3 sessions | 1 | `717c6a2f…` |
| H-0029 | Momentum shorts: below the 200-day, a new 50-session low, ≥ 10 points behind SPY over 63 sessions | 1 | `59d99248…` |
| H-0030 | +0.5% target / −0.2% stop against the current exits, on long signals and on short signals | 2 | `66cb404b…` |
| H-0031 | One position at a time with 99% of the account | 1 | `78dbb636…` |

How they were governed:

- **The register:** all five are in `docs/preregistrations.jsonl`, and the
  chain is intact (30 registrations).
- **The code is fixed by hash, not by commit,** because no commit was
  authorised.
  - The usual `code_commit` field records the old HEAD (`d3a166a`).
  - Each registration seals the SHA-256 of every code file, and each runner
    refused to start if any hash differed.
  - H-0031, registered after the H-0027–H-0030 run, re-recorded the same
    hashes for the shared files. That confirms they did not change between
    registration and run.
- **Reproduction checks:** before anything ran, the frozen baseline
  reproduced +58.5889% over 698 trades.
- **Data reads:** every read of the decade is logged in
  `docs/dataset-uses.jsonl` as a `rejection_test`.
- **The criteria were fixed in advance.**
  - R1: the combined account's Sharpe beats the long book's, over the full
    window and in each half.
  - R2: the sleeve's expectancy is above zero with t ≥ 2.
  - R3: return a year is not lower.
  - R4: maximum drawdown no deeper than 1.10 × the control's.
  - R5: robustness at 12 bp costs, at 3% borrow plus 4% dividends, against
    the live long book, and on the ETF universe.
  - R6: tail limits.

## 4. Data and boundaries

- **Data:** the decade dataset (2016-01-04 to 2026-09-04, 230 names,
  hash-verified). The thirty-year window is lost.
- **Contamination:** this data was used to build the strategy and for the
  earlier shorting tests. Under the project's rule it **can reject but cannot
  accept**.
- **No clean out-of-sample test is possible.** The forward record contains
  no shorts and starts 2026-10-27.
- **Information:** every signal uses bars up to and including the signal
  close. Regime is measured at the same close.
- **Survivorship:** the universe is today's survivors.
  - For long trades this flatters results.
  - For short trades it cuts both ways: crashed-and-delisted names are
    missing, but so are takeover gap-ups.
- **ETF control:** 67 symbols by H-0019's keyword match, not the 46 quoted in
  older notes.

## 5. Execution, costs and borrow

| | Assumption |
|---|---|
| Entry | At the signal close, 6 bp worse |
| Short stop | A buy-stop 2.5 × ATR above. A session that opens above it covers **at the open** (gap-through). |
| Rule exits | Close + 6 bp + the 0.652% rule-exit haircut |
| Take-profit limits | Need price to trade 5 bp through the level |
| Same-day touch of stop and target | Given to the stop |
| Borrow | 0.5% a year (Alpaca charges $0 for easy-to-borrow names; this is conservative); stress test 3% |
| Dividends a short must pay | 2% a year; stress test 4% |
| SEC fee | 0.278 bp |
| Rule 201 | No new short after a 10% drop |
| Borrowability | Every name assumed borrowable; history is not available |
| Shares | Whole shares |
| Leverage | None: long value + short value ≤ equity, and the long book takes priority (youngest shorts are covered) |
| Collateral | Short notional earns no interest |

## 6. Results

### Long-only baseline (control A) and SPY

All from the decade, with idle cash at the bill rate.

| | Return a year | Total | Volatility | Sharpe (rf 2.3%) | Sortino | Max drawdown | Worst day | Beta to SPY |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A: frozen long book | 5.13% | +70.4% | 9.1% | 0.35 | 0.49 | −12.5% | −3.6% | 0.30 |
| A-live: with the EXP-0055 take profit | 5.53% | +77.6% | 8.6% | 0.40 | 0.58 | −11.8% | −4.0% | — |
| SPY, price | 13.42% | +283% | 17.6% | 0.68 | 0.95 | −34.2% | −10.8% | 1 |
| SPY, total return | 15.0% (documented) / 15.2% (approx.) | +353% | 17.6% | 0.77 | 1.07 | −34.1% | −10.8% | 1 |
| SPY/bills mix, same volatility as the bot | ≈ 9.3–9.7% | | ≈ 9.2–9.7% | 0.77 | | ≈ −19–20% | | |

### Short sleeves alone (B) and combined with the long book (C)

| | H-0027 failed rallies | H-0028 bear market only | H-0029 momentum |
|---|---:|---:|---:|
| Trades | 175 | 34 | 770 |
| **Average net per trade** | **−1.25% (t −3.1)** | **−1.76% (t −1.8)** | **−0.85% (t −3.9)** |
| Win rate | 36% | 29% | 39% |
| Profit factor | 0.56 | 0.49 | 0.64 |
| Mean / median winner | +4.42% / +3.21% | +5.67% / +4.54% | +3.80% / +2.24% |
| Mean / median loser | −4.44% / −4.29% | −4.86% / −5.39% | −3.86% / −3.40% |
| p05 / p25 / p50 / p75 / p90 / p95 | −8.5 / −5.5 / −1.4 / +2.2 / +6.5 / +8.7% | −8.6 / −6.4 / −2.5 / +2.0 / +6.5 / +8.3% | −8.2 / −4.2 / −1.1 / +1.3 / +4.5 / +6.5% |
| Average adverse move (MAE): mean / p90 / max | 3.8 / 7.4 / 20.9% | 4.1 / 8.0 / 8.6% | 3.2 / 7.1 / 17.0% |
| Average favourable move (MFE): mean | 4.2% | 3.9% | 3.6% |
| Sessions held: mean / median | 13.3 / 14 | 14.6 / 17.5 | 8.8 / 6 |
| Stops that gapped through | 23% (mean 1.9% beyond, max 12.4%) | 31% (1.0%, max 2.1%) | 20% (1.5%, max 9.0%) |
| Average net at 0 / 12 / 24 bp | −1.13 / −1.34 / −1.65% | −1.64 / −1.89 / −2.29% | −0.78 / −0.91 / −1.18% |
| Sleeve alone on $100,000, return a year | −1.1% | −0.3% | −5.0% (total −42%) |
| **Combined account, return a year** (A: 5.13%) | **4.17%** | **4.88%** | **2.34%** |
| Combined Sharpe (A: 0.35) | 0.24 | 0.32 | 0.05 |
| Combined max drawdown (A: −12.5%, limit −13.7%) | **−15.0%: over the limit** | −13.4% | **−19.1%: over the limit** |
| 2022 combined (A: −9.9%) | −10.9% | −10.4% | −10.4% |
| Correlation of the sleeve with A / with SPY | −0.06 / −0.24 | −0.03 / −0.15 | −0.36 / −0.53 |
| Sleeve while A was more than 5% below its peak | −2.0% a year | −0.8% a year | +1.5% a year |
| Combined, with the live long book as control (A-live: 5.53%) | 4.49% | 5.29% | 2.26% |
| ETF universe only: average per trade | −0.36% | −0.94% | −0.80% |
| Verdict | **REJECTED**: fails R1–R6 | **REJECTED**: fails R1–R3 and R5 | **REJECTED**: fails R1–R5 |

How they lose:

- **H-0027.**
  - Stops: 38% of exits, averaging −6.1%.
  - The few RSI covers: 13%, averaging +7.3%.
  - The rest: 18% forced covers to keep the account unlevered, near 0%.
  - Removing the execution haircut still leaves −0.90% a trade.
  - The earlier "+1.2% a trade" (EXP-0011) was measured over thirty years,
    data that no longer exists here. Its fills ignored gaps through the stop
    and it charged no dividends. On this decade, with realistic fills, the
    same signal makes −1.25%. EXP-0011's own decade account result was
    already negative (−0.88% a year).
- **H-0029.**
  - 56% of its exits were forced covers when the long book needed the cash.
  - Its trades that were not forced averaged about −2.1%, worse still.
  - It is the only sleeve that genuinely diversifies (correlation −0.36). It
    is a second way to lose money that happens to move differently.

### +0.5% / −0.2% (H-0030)

One trade per signal; a symbol is skipped until its trade under the current
exits would have closed.

| | Long signals (1,857) | Short signals (274) |
|---|---:|---:|
| Current exits: average per trade | **+0.57% (t 4.2)** | −0.34% |
| +0.5/−0.2: average per trade | **−0.02%** | −0.20% (t −2.8) |
| Paired difference | **−0.59% (t −4.5)**; halves −0.07% / −0.96% | +0.14% (t 0.4) |
| Win rate (needed to break even) | 39.6% (40.9%) | 36.9% (49.2%) |
| Average win / average loss | +1.04% / −0.72% | +0.84% / −0.81% |
| Stops that **gapped** at the open | 50% | 60% |
| Stops worse than −0.5% / −1.0% | 35% / 20% | 44% / 24% |
| Worst stop | −8.1% | −10.4% |
| Sessions held | 1.1 | 1.2 |
| Best case (target first on every two-sided day) | +0.12% | −0.12% |
| Verdict | **REJECTED** | **REJECTED** |

A −0.2% stop is not a −0.2% loss. With the spread, the smallest realised loss
is −0.26%. Half the time the next morning's open is already past the stop,
and then the loss is whatever the gap is.

### One all-in position (H-0031)

| | A: current, up to 12 positions | **H-0031: one position, 99% of the account** |
|---|---:|---:|
| Return a year | 5.13% | **2.56%** |
| Total, decade | +70.4% | +30.9% |
| Volatility | 9.1% | **22.1%**, more than SPY's 17.6% |
| Sharpe / Sortino | 0.35 / 0.49 | 0.12 / 0.18 |
| Max drawdown | −12.5% | **−38.7%** |
| Worst day | −3.6% | −12.4% |
| 2022 | −9.9% | −25.1% |
| Worst trade | −$1,794 | −$12,717 (TJX, 2018-11-16 to 11-20, −10.8% in 4 days) |
| Trades / win rate / time invested | 698 / 51% / 44% | 135 / 47% / 66% |
| Halves, return a year | 4.1% / 6.1% | 2.0% / 3.0% |
| At 12 bp costs | — | 1.0% |
| Alphabetical candidate order | — | −2.3% a year, −53% drawdown |
| ETF universe (A on ETFs: 3.2%) | — | 2.3%, −28% drawdown |
| Verdict | | **REJECTED**: fails R1–R4 |

Why one big trade is worse:

- **It takes far fewer trades.** With one slot the bot took 135 trades
  instead of 698, so it missed most of its signals.
- **One loss freezes it.** A stop on an all-in position is about −5.6% of the
  account, which trips the frozen daily (1.5%) and weekly (6%) loss limits.
  The bot then cannot enter anything for the rest of the week.
- **Concentration multiplies noise, not the edge.** Each trade's edge is
  about +0.57%, while a single stock's spread of outcomes per trade is about
  6%.

There is a literal "one big trade with all the money" that does work:
**buying SPY and holding it.** It made 15% a year. That is a decision about
owning the index, not a trading strategy.

## 7. Tail risk

The worst short trades:

| Trade | Dates | Loss on the position | Loss as share of the account |
|---|---|---:|---:|
| META short | 2023-01-27 to 02-02 | −21.0% (gapped through its stop) | −1.03% |
| AMZN short | 2026-07-29 to 07-31 | −17.1% (gapped) | −0.83% |
| FTNT short | 2024-08-02 to 08-07 | −16.4% (gapped) | −0.81% |
| SYK short | 2022-07-14 to 07-27 | −14.4% (gapped) | −0.72% |

- A 2.5-ATR stop meant to lose about 6% lost 14–21% when the stock gapped up
  overnight.
- At 5% of the account per short, that cost 0.7–1.0% of the whole account per
  trade. H-0027 breached its own 1.0% tail limit.
- The all-in book lost up to 12.7% of the account on one trade.
- Borrow recalls, buy-ins and hard-to-borrow fees are not in the data, so the
  real tail is worse than shown.

## 8. Does shorting solve a real weakness?

**No.**

- **The weakness is exposure.** The bot trails SPY because it holds too little
  stock. Shorting holds less.
- **It did not help in bad times.** In 2022, the long book's worst year, every
  sleeve made the account worse. During the long book's drawdowns, only the
  momentum sleeve helped (+1.5% a year), and it cost 2.8 points a year
  overall.
- **It did not help risk-adjusted return.** Every sleeve lowered the Sharpe
  ratio, in both halves.
- **It adds turnover, costs and tail risk,** and in two of three cases no
  diversification at all.

## 9. Out-of-sample status and next step

- **Out-of-sample:** none is possible. These are rejection tests on
  contaminated data, and a rejection there stands.
- **Next step for shorting:** nothing. It should not be raised again unless a
  *different* idea arrives with its own registration, for example diversified
  futures trend-following on futures data the bot does not have.

## 10. Problems found along the way

1. **The holding count starts a day early: a live non-conformance, not fixed
   here.**
   - What happens: since about 2026-09-22 the bot stamps each new position
     with the session *before* its entry. 5 of the 7 open positions (IWM, MDY,
     SCHD, SCHW, VZ) carry such a stamp.
   - Effect: the bot counts sessions from that stamp, so its 20-session time
     limit fires after 19 sessions. SPEC-0001 C-16 says it should fire on
     D+20.
   - Why it was left: changing it is a production change under the frozen
     evaluation, which is the owner's call.
   - The TradingView chart deliberately shows the bot's actual count.
2. **The old short simulator was optimistic** (`scripts/short_book_sim.py`,
   2026-09-10). It filled gapped stops at the stop and charged no dividends.
   EXP-0011's +1.2% a trade is overstated.
3. **The ETF control is 67 symbols, not the 46** quoted in older notes.
4. **Registration without commits** weakens the git binding. The SHA-256
   seals stand in for it.
5. **The emulator's `gapped_through_stop` counter reads 0** in runs with
   realistic fills. Do not rely on it.
6. **The thirty-year window is lost,** so the project's own bar (decade AND
   thirty years) cannot be met by anything.
7. **The exposed Alpaca credential is still not rotated.**

## Files

All uncommitted.

- Engine: `scripts/short_sleeve_research.py`; tests:
  `tests/test_short_sleeve_research.py` (18).
- Specs: `scripts/short_hypotheses_spec.py`, `scripts/h0031_spec.py`.
- Registration and runners: `scripts/register_short_hypotheses.py`,
  `scripts/run_short_hypotheses.py`, `scripts/run_h0031.py`.
- Results:
  - `docs/phase5/h0027-h0030-results.json` and `h0027-h0030-trades.json`;
  - `docs/phase5/h0031-results.json`.
- Full test suite: 1,378 OK with every network call blocked (0 attempts).
