# Boot Camp concepts, and where the money actually goes

## What was implemented, and what was not

I cannot watch video. `smc.py` implements the mechanical concepts the playlist
names, from their standard public definitions:

| Boot Camp day | Concept | Implemented |
|--------------|---------|-------------|
| 6 | Break of Structure / CHoCH | yes |
| 8, 10, 12 | Liquidity sweeps | yes |
| 14, 16, 18 | Fair Value Gaps | yes |
| 20, 22, 24 | Order Blocks | yes |
| 26, 28 | Equilibrium (premium/discount) | yes |
| 34–36 | Daily Bias | **no** |
| 19, 47 | Reading news / CPI | **no** |
| 1,3,5,7,9,11,15,17,21,23,25,27,31,40,41,44,45,46,51 | Psychology and discipline | **not codable** |

Roughly 25 of the 56 videos are mindset. Whatever TJR's specific variations are
on drawing these zones, they are not in here — these are the textbook versions.

## Confirmation lag

A swing high is only knowable once enough bars print after it. A detector that
scans the whole array marks swings it could not have seen, and every downstream
signal inherits the lookahead. Every `SwingPoint` carries `confirmed_at`,
consumers filter on it, and one test replaces a *future* bar with an extreme
value and asserts the earlier signal does not move.

## Do the concepts predict anything?

3,624 candidates over ten years, out of sample:

| Feature set | AUC | Brier | Base Brier |
|------------|-----|-------|-----------|
| existing indicators | 0.5169 | 0.1650 | 0.1611 |
| **SMC only** | **0.5351** | 0.1652 | 0.1611 |
| both | 0.5176 | 0.1653 | 0.1611 |

SMC features carry slightly more signal than the indicators already in the bot
— and both are near a coin flip.

Individually, as winner rates against an 18–20% base:

| Concept | Winner rate when true | Lift |
|---------|---------------------|------|
| liquidity sweep | 22.5% | **+4.2 pp** |
| order block | 22.7% | **+4.0 pp** |
| fair value gap | 22.1% | **+3.7 pp** |
| bullish BOS | 20.6% | +3.7 pp |
| CHoCH | 15.4% (n=26) | −4.9 pp |

A first pass reported AUCs up to 0.9931. That was a broken metric — the rank
statistic had no tie handling and these features are mostly binary. Corrected
before any conclusion was drawn.

## Used as an entry filter, it does not help

Requiring N of {fair value gap, order block, liquidity sweep} before a long:

| Period | none | ≥1 of 3 | ≥2 of 3 |
|--------|------|---------|---------|
| 2017 | −2.13% (6) | −0.73% (2) | −0.17% (1) |
| 2018 | **+1.65%** (7) | −1.28% (5) | −0.51% (2) |
| 2019 | −0.86% (6) | −0.18% (4) | −0.76% (2) |
| 2020 | −0.84% (7) | −0.83% (6) | −1.13% (2) |
| 2021 | −2.37% (13) | −1.84% (9) | −1.30% (3) |
| 2022 | **+0.27%** (5) | −0.91% (5) | −1.38% (5) |
| 2023 | +0.81% (8) | +1.15% (7) | +0.94% (6) |
| 2024–26 | **+4.83%** (17) | +2.60% (10) | +2.08% (3) |
| **Sum, all 8** | **+1.37%** | **−2.03%** | **−2.22%** |
| **Sum ex-2024–26** | **−3.46%** | **−4.62%** | **−4.31%** |

The filter is doing something — trade counts fall sharply, 17 to 10 to 3 in the
last window — but the total gets *worse* on the held-out years **and** on the
full record, which is unusual: most changes at least flatter the period they
were measured on. It also flips 2018 and 2022 from positive to negative. Those
are the two drawdown years where the strategy earned its keep, and this is now
the second unrelated change to break exactly those years.

So `required_smc_confluence` defaults to **0**. The detectors are in, tested,
and available; the evidence does not support switching them on.

## Performance

Screening with these features was not slow, it was unrunnable — the first
ten-year sweep was killed after 20 minutes with no output.

| Fix | Gain |
|-----|------|
| `detect_structure`: cursor instead of re-filtering the swing list per bar | **19×** |
| `SMC_MAX_LOOKBACK = 250` bars per evaluation | — |
| `find_liquidity_sweeps`: same cursor fix, plus `since_index` | **7.2×** |

53.86 ms → 7.52 ms per evaluation. Output verified byte-identical across five
symbols at four history cutoffs each, before and after.

## Where the money actually goes

The hypothesis was that low profits come from deploying only part of the
$1,000. Measured, one position in SPY:

| Profile | Risk/trade | Notional | % of $1k |
|---------|-----------|----------|---------|
| conservative | 0.5% | $217.78 | 21.8% |
| moderate | 1.0% | $435.57 | 43.6% |
| aggressive | 2.0% | $871.13 | 87.1% |
| maximum | 5.0% | $950.00 | 95.0% |

So the hypothesis is right about the mechanism — on a high-priced ETF,
`conservative` uses about a fifth of the account.

**But it is not what happened last week.** Tuesday 2026-08-25 onward, 15-minute
bars:

| Profile | Trades | Wins | Max deployed | Peak % | Return |
|---------|-------|------|-------------|--------|--------|
| conservative | 2 | 0 | $951.70 | **95.2%** | −0.36% |
| moderate | 2 | 0 | $951.70 | 95.2% | −0.54% |
| aggressive | 2 | 0 | $951.70 | 95.2% | −0.54% |
| maximum | 2 | 0 | $951.70 | 95.2% | −0.54% |

| Symbol | Entry | Notional | Net |
|--------|-------|----------|-----|
| EEM | 08-26 09:30 | $951.70 | −$1.49 |
| SLV | 08-28 09:45 | $949.09 | −$3.95 |

It already committed **95% of the account** — and every profile produced the
identical result, because the 95% notional cap binds long before the risk
setting does. EEM and SLV are cheap ETFs, so risk-based sizing buys a lot of
shares and hits the ceiling immediately.

Both trades still lost. Full deployment on a losing trade loses more, not less:
−$5.45 on the week.

The two things that actually limit profit are unchanged: it is **flat 61% of
the time**, and its per-trade edge over 2017–2023 is negative. Deployment was
never the binding constraint.

Tests 135, all passing.
