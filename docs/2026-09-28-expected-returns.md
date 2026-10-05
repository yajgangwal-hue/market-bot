# Expected returns with the bot's stop losses and take profits

*Measured 2026-09-28 and written up 2026-10-03. The TradingView indicator cites
this page (`scripts/tradingview_levels.py`). Purpose: `diagnostic`. There is
no accept/reject decision here; this describes what the bot runs.*

## The short answer

Expect **about 3–5½% a year**, against SPY's 15% a year over the same
2016–2026 years. **The average trade is close to break-even**: a typical
position makes or loses roughly the same amount at its take profit as at its
stop, and the edge left after costs is small enough that it might not be
there at all.

Every figure below comes from simulating 2016–2026 on data the strategy was
built on, using today's surviving stocks. **Both of those make it look better
than it will be.** The forward record is the only clean evidence, and it
starts 2026-10-27.

## What the bot does now

Since 2026-09-29 (EXP-0055) each position has four exits:

- a stop 2.5 × ATR below entry, resting at the broker;
- a take profit 2.5 × ATR above entry, checked by the bot every 15 minutes
  and sold at market;
- daily RSI ≥ 60;
- 20 sessions held.

The stop and take profit are the same distance from the entry, so a target
hit makes about what a stop-out loses.

## One trade

754 simulated trades, 2016-01-04 to 2026-09-04.

| How the trade ends | How often | Average result | Average days held |
|---|---:|---:|---:|
| Take profit hit | 43% | +5.6% (+4.9% conservative) | 9 |
| Stop hit | 32% | −5.7% | 8 |
| 20-day limit | 24% | −0.3% | 20 |
| RSI bounce exit | 1% | +3.4% | 17 |

- **Average trade as simulated:** +$84 on an average position of $16,703,
  with $865 at risk. That is +0.08 of the risk, about 2.3 standard errors from
  zero.
- **Average trade, conservative:** +$35, or +0.01 of the risk, 0.4 standard
  errors from zero. In plain terms, it cannot be told apart from break-even.
- **Win rate:** 55%.

"Conservative" charges every take-profit sale the same 0.652% execution cost
as every other rule exit. The live take profit is a market order placed
within 15 minutes of the level being reached; it is not a resting order, so
it does not always get the level's price.

Two splits that are worse than the average:

- **ETFs:** 157 trades averaged +0.001 of the risk as simulated and −0.11
  conservative. Their stops are narrow, so the execution cost takes a larger
  share.
- **2016–2020:** −0.02 of the risk conservative, against +0.04 in 2021–2026.

## The account, per year

Idle cash earns the 3-month T-bill rate, as the bot's parked cash does in
SGOV.

| | Return a year | On $100,000 | Worst drop from a peak | Worst year | Years with a gain |
|---|---:|---:|---:|---:|---:|
| **Conservative** | **+3.2%** | **≈ $3,200** | −15.7% | −4.4% (2024) | 6 of 11 |
| As simulated | +5.5% | ≈ $5,500 | −11.8% | −1.3% (2022) | 8 of 11 |
| Before the take profit (old exits) | +5.1% | ≈ $5,100 | −12.5% | −9.9% (2022) | 10 of 11 |
| SPY, total return | +15.0% | ≈ $15,000 | −33.8% | — | — |

The take profit's effect is unclear. As simulated it adds about 0.4 points a
year. Conservatively it costs about 2 points, because it cuts off the RSI
bounce exits that used to average +7.3%. H-0026 had already found that the
best take-profit level for this strategy was "none".

## The positions open at the 2026-10-02 close

Levels are the bot's own, from its state file. Entry is the broker's average
fill.

| | Entry | Stop | Take profit | Lose at stop | Make at target | Expected as simulated | Expected, conservative |
|---|---:|---:|---:|---:|---:|---:|---:|
| CVS | 87.45 | 81.71 (−6.6%) | 93.19 (+6.6%) | −$711 | +$711 | +$56 | +$23 |
| IWM | 282.10 | 273.20 (−3.2%) | 291.01 (+3.2%) | −$312 | +$312 | +$24 | −$4 |
| MDY | 664.57 | 647.13 (−2.6%) | 682.01 (+2.6%) | −$453 | +$453 | +$36 | −$14 |
| SCHD | 33.32 | 32.49 (−2.5%) | 34.15 (+2.5%) | −$320 | +$320 | +$25 | −$12 |
| SCHW | 98.36 | 92.84 (−5.6%) | 103.85 (+5.6%) | −$784 | +$780 | +$62 | +$20 |
| UNP | 269.87 | 254.77 (−5.6%) | 284.97 (+5.6%) | −$725 | +$725 | +$57 | +$19 |
| VZ | 46.34 | 43.61 (−5.9%) | 49.07 (+5.9%) | −$475 | +$475 | +$37 | +$13 |
| **All seven** | | | | **−$3,781** | **+$3,777** | **+$297** | **+$45** |

How the two expected columns are worked out:

- **As simulated:** the average trade's +0.0786 of risk, times this
  position's risk.
- **Conservative:** the same, less the execution cost on the take-profit sale.
  That is 0.652% of the sale, times the 43% chance the take profit is hit. A
  narrow stop (IWM, MDY, SCHD) pays the most of its risk this way.

These are averages over many trades. Any one position will end near its stop,
near its target, or near flat. It will not end at the expected value.

## The live record so far

At the 2026-10-02 close, from `data/reports/2026-10-02.json`:

- account equity $97,310;
- realized −$2,839, of which −$2,335 came from 11 positions closed outside
  the bot's rules;
- 3 trades closed by the bot's own rules, too few to mean anything;
- over the same span, SPY returned +0.44%.

## Sources

- Simulation runs:
  - `docs/phase5/expected-returns-2026-09-28.json`, the record the chart
    reads;
  - the scripts `expected_returns.py` and `expected_returns_conservative.py`;
  - two `diagnostic` reads of the decade, logged in
    `docs/dataset-uses.jsonl`.
- Reproduction checks:
  - the frozen baseline reproduced +58.5889% over 698 trades;
  - the EXP-0055 disclosure reproduced +67.2147% over 756 trades.
- SPY: EXP-0037 (`knowledge/01-frozen/Benchmark.md`).
