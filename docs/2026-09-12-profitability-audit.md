# Line-by-line audit: seven findings, one that matters

**12 September 2026.** A systematic pass over the money path looking for
anything costing money. Seven findings. Six are small or favourable. One
changes what this bot can honestly claim.

The method throughout: where the LIVE loop and the SIMULATOR disagree, the
simulator's figure is fiction, because the simulator is where every published
number came from and the live loop is what actually trades.

---

## 1. Survivorship — dominant, and not a code bug

The universe is today's 230 names run backwards. A rule that buys names which
fell hard and bets they recover is *directly* exposed to that: in a
survivor-only file every name recovers — that is what made it a survivor. The
ones that fell and kept falling until they delisted are not in the file, so
the rule never has to buy one.

The clean subset is the 46 broad ETFs. An index fund does not go to zero and
vanish from a survivor list; SPY in 1996 is SPY now.

| | decade CAGR | 30-year CAGR | 30y 1st half | 30y 2nd half | trades |
|---|---|---|---|---|---|
| all 230 names (survivor set) | 9.14% | 5.66% | +38.9% | +288.8% | 1,526 |
| **46 ETFs only (clean)** | **3.82%** | **2.24%** | +0.7% | +96.0% | 569 |

The edge is **real** — positive in both halves on the clean set. But ETFs are
also duller: a third the trades, smaller moves, so *some* of the drop is
expected rather than bias. The two cannot be separated without a universe
containing delisted names, which this project does not have.

**Consequence: the 6.24% expected return quoted on 2026-09-11 is too high.**
The honest statement is that the thirty-year figure lies between 2.24% and
5.66% and cannot currently be pinned down further.

This is the same test that killed the overnight book (23.60% → −1.52%). It is
the most valuable test in this project and should be run against anything new
before it ships.

## 2. Stops fill at the stop price in every backtest. Real ones cannot.

```python
exit_raw, exit_reason = position.stop, "stop"
```

A resting stop is not a limit — when touched it becomes a **market** order. If
the session gapped down through the level there was never a trade at that
price, and the fill is the open.

| | decade | thirty years |
|---|---|---|
| stop exits | 250 | 543 |
| of which **gapped through** | 53 (21%) | 93 (17%) |
| shortfall when it gaps | mean 1.19%, worst 5.17% | mean 1.20%, worst 7.29% |
| unmodelled loss | $11,560 | $34,194 |
| **cost** | **−0.48 points** | **−0.23 points** |

First-order — the dollars are not compounded back out of the curve, so the
true cost is somewhat worse.

## 3. Dividends are never credited — and this one is in the owner's favour

Prices are fetched `adjustment=split`, deliberately and correctly: back-
adjusting dividends rewrites history below what actually traded, and this rule
compares against absolute thresholds. But the simulator then never credits the
cash either. The price drops on the ex-date and nothing arrives.

Live, Alpaca pays them. On a large-cap and ETF universe held roughly 45% of the
time, that is **+0.5 to +0.8 points a year the backtest does not show.**

An estimate, not a measurement — there is no dividend data in this project.

## 4. Three live-only constraints — net neutral, and one is an improvement

The live loop obeys three things the simulator never modelled.

| | decade | thirty years |
|---|---|---|
| whole shares (Alpaca refuses fractional stops) | −0.11 | +0.00 |
| 3 entries a day (`max_orders_per_run` × one cycle) | **+0.25** | **+0.07** |
| mark-to-market daily loss guard | −0.37 | −0.26 |
| **all three, as it runs** | **−0.13** | **+0.02** |

And the drawdown *improves*: −14.2% → −12.4% over thirty years.

Two things worth naming:

**The entry cap was expected to be a regression from confining entries to the
close** — `max_orders_per_run` is 3 per *cycle*, and the closing window left
one usable cycle, so it became 3 per *day*. It is not a regression. It is an
improvement, which fits the profit-concentration finding exactly: the top 50
trades of 713 carry 85.9% of all profit, so on a busy day taking only the best
three is better than taking eight.

**The loss guard is the one real cost.** The simulator hands it
`daily_realized`, which sums closed trades only — almost always zero for a rule
that exits rarely, so it never binds. The live loop measures equity against
the session's opening equity *mark to market*, so an unrealised drawdown halts
entries. SPY falls 1.5% or more on 6.4% of sessions, and those are
disproportionately the days a mean-reversion rule wants to buy.

Loosening it is the only tunable improvement this audit found, and it buys
return with safety.

## 5. Market-on-close: supported, and not worth it

Alpaca accepts `time_in_force=cls`, submitted before 15:50 ET — the 15:45
cycle qualifies, so this became newly possible with the entry-window change. It
would fill at the closing auction's single clearing price with no spread to
cross, and would make the live fill match the backtest exactly.

Priced against the measured cost table for this configuration:

| one-way cost | decade CAGR |
|---|---|
| 3 bps | 9.32% |
| 6 bps (live) | 9.14% |
| 9 bps | 8.97% |

Halving cost on *both* legs is worth +0.18 points; an MOC entry touches one
leg, so about **+0.09 points**. Set against an entry that cannot carry a
bracket, leaving the position unprotected until the next morning's cycle
places a stop. Not taken.

The note in `risk.py` claiming "about four points of decade return per basis
point" is **stale** — it was measured under the old entry timing. The table
above replaces it.

## 6. Participation capping: live-only, harmless

`cap_by_participation` runs live and not in the simulator. At 2% of a $50m
dollar-volume floor it permits $1,000,000 per order against a largest live
position of $20,353. It cannot bind below roughly $5m of equity.

## 7. The indicators are correct

Checked against Wilder's own worked example rather than assumed: RSI(14) on
his canonical 15 closes computes 70.46, which is what the arithmetic gives
(gains 3.34/14 = 0.23857, losses 1.40/14 = 0.10, RS 2.3857). RSI is 100 on a
monotone rise and 0 on a monotone fall; ATR(14) on a constant 4.00 true range
returns exactly 4.0000.

---

## What this means for making money

Findings 2 and 3 roughly cancel. Finding 4 is neutral and improves drawdown.
Findings 5, 6 and 7 are clear.

**There is no parameter left to turn.** Position size, stop width, exit level,
holding cap and candidate ranking were all swept on 2026-09-11 and the shipped
setting won every one. This audit adds order type, participation, and the
indicators themselves to that list.

The three things that remain are not parameters:

1. **The universe.** A survivorship-free file with delisted names would not
   raise returns — it would tell us what they actually are, which is currently
   a range spanning a factor of two. Nothing else in this project would improve
   the numbers as much as knowing them.
2. **The mark-to-market loss guard**, worth 0.26 to 0.37 points, tradeable
   against safety. The owner's call.
3. **$5,002 reserved for a crypto sleeve that is not scheduled**, costing about
   $215 a year in foregone interest.

The one change that made money this week was not a parameter and not an idea.
It was an hour on a clock.
