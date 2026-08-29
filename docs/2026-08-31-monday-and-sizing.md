# Monday's decision, and what larger positions actually do

## Monday 2026-08-31

Monday has not happened yet, so this is the decision the bot will act on at the
open, formed from Friday 2026-08-28's close across all 20 ETFs.

**It trades nothing.** 3 `WATCH`, 17 `REJECT`, 0 `PAPER_LONG`.

| Symbol | Action | Score | Fri close | Reason |
|--------|--------|-------|-----------|--------|
| XLF | WATCH | 50.0 | 58.10 | score below 70 |
| XLE | WATCH | 43.2 | 62.68 | score below 70 |
| XLV | WATCH | 37.8 | 171.16 | score below 70 |
| SPY | REJECT | — | 769.35 | ADX 15.6 below 18 |
| XLK | REJECT | — | 185.69 | ADX 13.4 below 18 |
| QQQ | REJECT | — | 716.43 | trend filter (price > MA20 > MA50) |
| GLD | REJECT | — | 408.89 | long-term regime is a downtrend |
| SLV | REJECT | — | 60.02 | long-term regime is a downtrend |
| DIA, IWM, XLP, XLU, XLI, XLY, VNQ, TLT, EFA | REJECT | — | — | trend filter |
| XLB, USO, EEM | REJECT | — | — | ADX below 18 |

The market is directionless: ADX between 11 and 16 across the large ETFs
against an 18 floor, and most names below their own 20-day average. Standing
aside is the designed response.

## Capital deployment as it stands

Measured, not assumed, over two years on 20 ETFs:

| | |
|---|---|
| Median position | **$164 — 16% of a $1,000 account** |
| Largest position | $217 (22%) |
| Time in market | **38.9%** |
| Idle in cash | 61.1% |

So the account is not tied up in tiny positions. The binding constraint is that
it is **flat 61% of the time**, not that positions are small.

## What larger positions do

Position sizing is now a named choice:

```bash
event-aware-trader autotrade --risk-profile aggressive
```

| Profile | Risk/trade | Daily stop | Weekly stop |
|---------|-----------|-----------|-------------|
| conservative (default) | 0.5% | 1.5% | 6% |
| moderate | 1.0% | 3.0% | 10% |
| aggressive | 2.0% | 5.0% | 15% |
| maximum | 5.0% | 10.0% | 25% |

On the recent two years, bigger looks dramatically better:

| Risk/trade | Equity | Return | Max drawdown |
|-----------|--------|--------|-------------|
| 0.5% | $1,041.96 | +4.20% | −1.44% |
| 2.0% | $1,125.31 | +12.53% | −3.47% |
| 5.0% | $1,226.50 | +22.65% | −5.76% |

Above about 5% nothing changes — the 95% notional cap binds.

### Then it was tested on years it had not been chosen on

Same settings, 2017–2023, seven years excluding the window above:

| Score / risk | Total return | Worst year | Worst drawdown |
|--------------|-------------|-----------|---------------|
| 70 / **0.5%** | **−3.46%** | −2.37% | −4.39% |
| 70 / 1.0% | −10.50% | −4.19% | −8.09% |
| 70 / 2.0% | −16.09% | −5.66% | −15.23% |
| 60 / 0.5% | −0.20% | −4.53% | −7.29% |
| 60 / 1.0% | −1.00% | −5.35% | −10.69% |
| 60 / 2.0% | −7.23% | −8.09% | −17.66% |

**Every configuration loses money, and within every score level, raising risk
loses more.**

Year by year, current settings against the aggressive combination that looked
best on recent data:

| Period | 70 / 0.5% | 60 / 2.0% | SPY |
|--------|----------|----------|-----|
| 2017 calm | −2.13% | −0.61% | +18.58% |
| 2018 selloff | **+1.65%** | **−5.04%** | −6.69% |
| 2019 rally | −0.86% | −0.63% | +30.85% |
| 2020 covid | −0.84% | +7.10% | +15.56% |
| 2021 melt-up | −2.37% | −4.34% | +26.55% |
| 2022 bear | **+0.27%** | **−8.09%** | −19.71% |
| 2023 recovery | +0.81% | +4.37% | +23.66% |
| **2024–26** | +4.83% | **+30.62%** | +37.31% |
| **Sum ex-2024–26** | **−3.46%** | **−7.24%** | |

The aggressive version's entire advantage is 2024–26 — the period it was
compared on. Remove that one window and it is twice as bad as the conservative
default. It also destroys the two years the conservative version earned its
keep: 2018 and 2022, the drawdown years where standing mostly aside was the
whole point, both flip to losses.

### The reason, stated plainly

Position size multiplies whatever edge exists. Over 2017–2023 this strategy's
edge is negative, so multiplying it produces a bigger negative. There is no
sizing setting that converts a losing rule into a winning one — sizing is a
volume knob, not a quality one.

This is why the default stays `conservative`. The other profiles are wired up,
tested, and one flag away, so the choice is yours and reversible; the data
simply does not support making it the default.

## Running it on Monday

The bot places nothing Monday regardless of profile, so nothing will happen.
To have it decide for itself from then on:

```bash
scripts/run-autotrade.sh --interval 1d --live
```

Scheduled for 15:45 America/New_York on weekdays. Run it without `--live`
first for a few sessions.
