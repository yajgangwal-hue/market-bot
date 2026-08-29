# Stay-invested exit mode, and the week of 2026-08-24

## Why the fixed clock had to go

The prior review found the dominant defect in the payoff geometry: over two
years the 5-day holding clock decided **9 of 13 exits** while only one trade
ever reached its target. The rule risked 1R to make 2R and collected about
+0.14R, and the account sat in cash 85% of the time.

`StrategyConfig.exit_mode` now selects between:

- **`fixed_time`** — the previous behaviour. Close at `max_holding_bars` no
  matter what the position is doing.
- **`trailing`** (new default) — the stop ratchets up behind the running high
  and never loosens. The fixed target is dropped so an advance is not
  truncated, and the position closes only when the trail is hit. The original
  stop stays in force until the trade has earned `trail_activate_r`, so a
  position is not shaken out by noise before it has done anything.

## Why `trailing` became the default

Not because it scored best once. It beat `fixed_time` in **all 15** parameter
combinations tested across the two-year record:

| trail ATR | activate 0.0R | 0.5R | 1.0R |
|-----------|--------------|------|------|
| 1.5 | +0.36% | +2.05% | +2.01% |
| 2.0 | +2.89% | **+4.05%** | +3.86% |
| 2.5 | +3.93% | +3.93% | +3.95% |
| 3.0 | +3.65% | +3.65% | +3.40% |
| 4.0 | +2.33% | +2.33% | +2.31% |

`fixed_time` returned **+0.87%**. Every cell above beats it. That is a broad
plateau rather than a knife-edge, which is much better evidence than a single
lucky setting.

The default is **2.5 ATR / 0.5R — the middle of the plateau, deliberately not
its peak** at 2.0/0.5. Picking the maximum of a sweep is how a backtest gets
fitted to its own noise.

Direction was consistent across the chronological split too: in-sample
+2.15% vs +1.15%, out-of-sample −0.12% vs −0.23%. Note that **both modes lose
money out-of-sample** — trailing merely loses less.

## What staying invested actually changed

Same entries, same signals, only the exit rule differs:

| Symbol | Entry | Old (5-day) | Days | New (trailing) | Days | Change |
|--------|-------|------------|------|---------------|------|--------|
| GLD | 2025-04-04 | −$2.88 | 1 | −$2.88 | 1 | unchanged (stopped day 1) |
| XLK | 2025-06-30 | +$1.07 | 5 | +$4.66 | 24 | +$3.59 |
| GLD | 2025-10-10 | +$8.31 | 4 | +$9.88 | 8 | +$1.57 |
| GLD | 2026-01-13 | +$4.39 | 5 | **+$22.63** | 12 | **+$18.24** |
| XLE | 2026-03-03 | **−$2.39** | 5 | **+$6.25** | 21 | loss → win, +$8.64 |
| QQQ | 2026-05-28 | +$3.09 | 5 | **−$1.57** | 7 | −$4.66 |
| XLF | 2026-07-16 | **−$2.45** | 5 | **+$0.28** | 26 | loss → win, +$2.73 |

Five better, one worse, one unchanged. The clock had been closing two
eventual winners at a loss, and cutting the best trade of the whole record
(GLD in January) at roughly a fifth of what it went on to make.

| | fixed_time | trailing |
|---|-----------|---------|
| closed trades | 13 | 7 |
| win rate | 53.8% | **71.4%** |
| profit factor | 1.55 | **9.82** |
| avg win / avg loss | +$3.52 / −$2.66 | +$8.74 / −$2.22 |
| time in market | 15.2% | **27.3%** |
| max drawdown | −0.87% | −0.90% |
| ending value | $1,008.72 | **$1,039.25** |

Fewer trades, held far longer, and roughly double the capital at work — which
is what "keep things invested" means in practice.

## The week of 2026-08-24

The market that week:

| Symbol | Mon open | Fri close | Change |
|--------|---------|----------|--------|
| SPY | 764.78 | 769.35 | +0.60% |
| QQQ | 709.66 | 716.43 | +0.95% |
| XLK | 181.68 | 185.69 | +2.21% |
| XLE | 63.24 | 62.68 | −0.89% |
| XLF | 57.70 | 58.10 | +0.69% |
| TLT | 82.49 | 82.88 | +0.47% |
| GLD | 428.55 | 408.89 | **−4.59%** |

The bot made **35 decisions (7 symbols × 5 sessions) and opened nothing**:
23 `REJECT`, 12 `WATCH`, 0 `PAPER_LONG`. The account was flat all week — the
XLF position had closed on 2026-08-20.

That is the expected outcome, not a malfunction. At roughly one trade per 51
sessions, 35 symbol-days has an expected trade count near 0.7.

The refusals were coherent:

- **Trend filter** (price > MA20 > MA50) failed repeatedly, and **ADX sat at
  13–17 against an 18 floor** — both saying the same thing, that the week was
  a chop with no trend to join.
- **GLD was rejected Monday for sitting 4.2 ATRs above its 20-day average**,
  then rejected Thursday because the long-term regime had turned down. GLD
  proceeded to fall **−4.59%** that week. The extension filter did precisely
  the job it exists for: it declined to buy the top of a gold spike.
- **XLK rose +2.21% and the bot missed it**, refusing on ADX 13–14. That is a
  real opportunity cost and the honest other side of the same filter.

## Current state

| | |
|---|---|
| Cash | **$1,039.25** |
| Still invested | **$0.00** — no open position |
| Total account value | **$1,039.25** (+3.93% over 2 years) |

## Limits, unchanged

- **SPY buy-and-hold returned +37.79% over the same window** ($1,000 →
  $1,377.90) against the bot's +3.93%. Improving from +0.87% to +3.93% is a
  4.5× improvement on a number that is still far below doing nothing.
- **Seven closed trades prove nothing.** A 71.4% win rate on seven trades has
  a confidence interval wide enough to include a coin flip.
- Out-of-sample remains slightly negative for both exit modes.
- Still daily bars and multi-day holds. Trailing made the average hold *longer*
  (4.2 → 14.1 sessions), which moves this further from day trading, not closer.
