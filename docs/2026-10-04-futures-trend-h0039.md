# A futures strategy: trend following across 19 markets (H-0039)

*2026-10-04. The owner asked:*

> "ok the trading view should be connected to my account now, should i give
> you my trading view account information so the bot has access to it, then i
> want you to build a smart futuers trading strategy"

*Nothing is live, nothing was committed, and no broker was called. The test
was registered before any result existed.*

## The answers

| Question | Answer |
|---|---|
| Should I give you my TradingView login? | **No.** The bot doesn't use TradingView; it trades through the broker. With TradingView connected to the account, the charts show the bot's positions and orders directly. Never paste a password or key into a chat. |
| Is there a futures strategy worth pursuing? | **Yes, on paper first.** Diversified trend following passed all four of its sealed tests: verdict NOT REJECTED. |
| Does it beat SPY? | **On its own, no:** +5.7% a year against SPY's +11.8%. **Added to an account holding SPY, yes:** +14.8% a year against +11.8%, with a worst fall of −33% against −51%. That is May 2008 to September 2026, after costs. |
| Can it run now? | **No.** It needs a futures broker connection (Interactive Brokers) and about $1,000,000 to hold every market in whole contracts. IBKR's paper account comes with $1,000,000 of paper money, so a proper paper test is possible there. |

## What the strategy does

This is the futures strategy with the longest published record:
- Moskowitz, Ooi & Pedersen (2012) measured it on 58 markets over 1985–2009.
- Hurst, Ooi & Pedersen (2017) measured it back to 1880.

The rule:

- **Markets.** 19 futures markets:
  - stock indexes: S&P 500, Nasdaq-100, Russell 2000, Dow;
  - Treasuries: 2-year, 10-year, 30-year;
  - metals: gold, silver, copper;
  - energy: crude oil, natural gas;
  - grains;
  - six currencies: euro, yen, pound, Australian dollar, Canadian dollar,
    Swiss franc.
- **Direction.** Once a month, for each market: is it up or down over the
  last 1, 3 and 12 months, against Treasury bills? All three up is a full
  long, all three down a full short, and a mix is a third of a position.
- **Size.** Each market gets the same risk, so a quiet market gets a bigger
  position than a wild one. The whole book is sized for about 10% volatility
  a year.
- **Trading.** Trades go in at the next day's close and stay until the next
  month. That is 12 decisions a year, with rolls to the next contract in
  between.

Nothing was tuned. Every number comes from the papers, and all of them were
sealed in the registration before any result was computed.

### How it was measured

Free futures history is spliced at every roll, and the splices are not real
returns. So each market was measured through a fund that tracks it (SPY, TLT,
GLD, USO, FXE and the others), minus the Treasury-bill return. The funds'
fees stay in, which makes the result slightly worse than real futures.

Costs were set high on purpose:
- 0.5–6 basis points a side, plus every roll;
- this totals about 1% of the account a year.

## Results: May 2008 to September 2026, after costs

| | Trend alone | 80% SPY + trend | SPY |
|---|---:|---:|---:|
| Return a year (CAGR) | **+5.70%** | **+14.80%** | +11.76% |
| Sharpe ratio | 0.42 | **0.76** | 0.59 |
| Volatility | 11.5% | 18.6% | 19.7% |
| Worst fall | −21.8% | **−33.0%** | −51.5% |
| 2008–2016, a year | +6.02% | +13.23% | +7.98% |
| 2017–2026, a year | +5.41% | +16.22% | +15.25% |
| Total | +177% | +1,166% | +673% |

"80% SPY + trend" means an account holding 80% SPY and 20% Treasury bills,
with the bills posting margin for the futures.

Verdict: NOT REJECTED - nominated for a forward paper test.

| Sealed test | Needed | Result | Pass? |
|---|---|---|---|
| G1 An edge | Sharpe ≥ 0.30 and bootstrap p ≤ 0.05 | 0.42, p = 0.033 | ✅ |
| G2 It lasted after the papers | Positive in both halves | +6.29% and +3.50% a year over bills | ✅ |
| G3 It helps beat SPY | 80% SPY + trend beats SPY in the full window and in both halves, with a shallower worst fall | +14.80% vs +11.76%; +13.23% vs +7.98%; +16.22% vs +15.25%; −33.0% vs −51.5% | ✅ |
| G4 It survives double costs | Sharpe ≥ 0.30, still positive | 0.335, +3.84% a year over bills | ✅ |

### Year by year

| Year | Trend alone | 80% SPY + trend | SPY |
|---|---:|---:|---:|
| 2008 (May–Dec) | +14.9% | −14.2% | −33.5% |
| 2009 | −2.2% | +19.3% | +26.4% |
| 2010 | +7.6% | +20.0% | +15.1% |
| 2011 | +11.1% | +13.4% | +1.9% |
| 2012 | −1.4% | +11.1% | +16.0% |
| 2013 | +21.8% | +51.8% | +32.3% |
| 2014 | +6.6% | +17.4% | +13.5% |
| 2015 | −3.6% | −2.7% | +1.2% |
| 2016 | +0.1% | +9.4% | +12.0% |
| 2017 | +2.2% | +18.4% | +21.7% |
| 2018 | −1.4% | −7.1% | −4.6% |
| 2019 | +2.4% | +25.5% | +31.2% |
| 2020 | +17.8% | +38.2% | +18.3% |
| 2021 | −1.7% | +19.7% | +28.7% |
| 2022 | +20.9% | +3.1% | −18.2% |
| 2023 | −10.9% | +3.4% | +26.2% |
| 2024 | +5.2% | +20.3% | +24.9% |
| 2025 | +14.5% | +27.1% | +17.7% |
| 2026 (Jan–Sep) | +7.7% | +15.8% | +12.7% |

**It earns most when stocks fall.** In 2008 it made +14.9% while SPY lost
33.5%, and in 2022 it made +20.9% while SPY lost 18.2%. Its daily returns had
almost no relation to SPY's (correlation −0.09).

### Where the return came from

Average a year, % of the account, before costs:

| Treasuries | Stock indexes | Energy | Metals | Currencies | Grains | Costs |
|---:|---:|---:|---:|---:|---:|---:|
| +1.68% | +1.63% | +1.07% | +0.52% | +0.45% | +0.44% | −0.97% |

No single market type carried it. The source changed from year to year:

| Year | What drove it |
|---|---|
| 2013, 2017 | stock indexes (+14.5% and +13.3%) |
| 2022 | Treasuries (+11.3%) |
| 2025 | metals (+11.4%) |
| 2008, 2014 | currencies |

(`docs/phase5/h0039-diagnostics.json`)

### Other versions, for information only

These cannot change the verdict. Picking the best of them after seeing the
results is exactly the curve-fitting the sealed test exists to prevent.

| Version | Return a year | Sharpe | Worst fall |
|---|---:|---:|---:|
| The sealed rule | +5.70% | 0.42 | −21.8% |
| 12-month signal only | +8.22% | 0.63 | −16.8% |
| Rebalanced weekly | +4.83% | 0.35 | −25.3% |
| Double costs | +4.68% | 0.33 | −23.2% |
| 100% SPY + trend, margin borrowed | +16.75% | 0.75 | −42.4% |

## What could make this wrong

- **The edge weakened after the papers were published:**

  | | Sharpe | Over bills, a year |
  |---|---:|---:|
  | 2008–2016 | 0.57 | +6.3% |
  | 2017–2026 | 0.30 | +3.5% |
  | 2017–2026, double costs | 0.21 | — |

  This project has watched published rules fade before. This one has faded
  but not disappeared.
- **Its lead over SPY in the second half is thin:** +16.22% against +15.25%
  a year. The big wins came in crashes, and a calm bull market leaves it
  trailing. 2023 lost 10.9% while SPY made 26.2%.
- **The statistics are modest.** p = 0.033 is just inside the line, and 18
  years at a Sharpe of 0.42 is not overwhelming. The strongest support is
  the published record, not this test.
- **Funds stand in for futures.** Fees, roll methods and bond durations
  differ from the real contracts
  (`docs/datasets/futures-proxies-yahoo-2006-2026-20.md`).
- **Account size.** The registration requires a whole-contract check before
  anything trades. Most positions are smaller than one contract at
  $100,000:

  | Account | Markets whose usual position is at least half a contract |
  |---|---:|
  | $100,000 | 9 of 19 |
  | $250,000 | 14 of 19 |
  | $1,000,000 | 19 of 19 |

  - At $100,000 the stock-index, gold, silver, 10-year and 30-year positions
    round to zero most months. The book would become mostly currencies and
    small commodities: a different strategy.
  - A cut-down version for a small account would need its own test.
  - Contract sizes in the diagnostics are approximate, within about ±15%.
- **Historical data can only reject.** These data could have rejected the
  idea, and they didn't. They cannot prove it will work. A forward paper
  record is the real test.

## What happens next

Nothing below has been done.

1. **The owner opens a full Interactive Brokers account.** IBKR says new
   account holders "automatically receive a paper trading account" with
   $1,000,000. The free trial gives platform access, but whether it allows
   the programming interface a bot needs is unconfirmed.
2. **Then the bot gets a futures side.** That means:
   - IBKR's interface, through its IB Gateway program running on this PC;
   - whole-contract sizing;
   - contract rolls;
   - the same safety checks as the Alpaca side: a paper-only guard, resting
     stops and outside-close detection.

   The stock bot stays on Alpaca, unchanged.
3. **Keys go through the secure setup, never through chat.**
4. **Months of forward paper trading decide it.** With one decision a month,
   evidence builds slowly.

## Governance

- **Dataset:** `futures-proxies-yahoo-2006-2026-20`, SHA-256
  `dc1d1049c62f4cf0f86b2e31eb359b1f1f9c73f7be1727aa886f8ea473958042`, 20 raw
  files. It was acquired by `scripts/h0039_acquire.py` before registration,
  is registered in `docs/datasets/registry.json` and is described in its
  datasheet.
- **Registration:** H-0039, sealed 2026-10-05 05:01 UTC, seal
  `70e8fe4190c7d33f9be23a2990a5f1e231e49695c11ab1b13e100950b9355e20`,
  before any outcome was computed. The seal pins the SHA-256 of the
  acquisition script, engine, runner and tests. The registration chain is
  intact (38 registrations).
- **Prior related trials, all rejected:** H-0036 (7,846 single-market rules
  on SPY), EXP-0003, EXP-0033 and EXP-0034 (crypto trend). This test differs
  in its premise: the edge comes from many markets at once.
- **Results:**
  - `docs/phase5/h0039-results.json`, the sealed run;
  - `docs/phase5/h0039-diagnostics.json`, descriptive and written after the
    sealed run: P&L by market type and the whole-contract check.
- **Files:**
  - `scripts/h0039_acquire.py`, `scripts/h0039_trend.py`,
    `scripts/h0039_spec.py`, `scripts/run_h0039.py`,
    `scripts/h0039_diagnostics.py`;
  - `tests/test_h0039_trend.py`: 31 tests, including the verdict step, run
    end to end before the sealed run.

## Sources

- Moskowitz, Ooi & Pedersen (2012), "Time series momentum", *Journal of
  Financial Economics* 104(2).
- Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following
  Investing", *Journal of Portfolio Management* 44(1).
- Interactive Brokers: [Free Trial](https://www.interactivebrokers.com/en/trading/free-trial.php),
  [About Paper Trading Accounts](https://www.ibkrguides.com/clientportal/aboutpapertradingaccounts.htm).
