# Opening Range Breakout on "Stocks in Play" — tested, rejected

**7 September 2026.** Tested because it is the one day-trading strategy with a
real published backtest behind it, and because it would have been genuinely
uncorrelated with the mean-reversion rule — intraday, flat by the close, beta
near zero, active on the 77% of days the live bot sits idle.

It does not replicate on this universe. Not marginally: it loses before costs.

## What was tested

Zarattini, Barbon & Aziz (2024), *A Profitable Day Trading Strategy For The
U.S. Equity Market* — 7,000+ US stocks, 2016–2023, reported 2.4 Sharpe with
beta near zero. Their central claim is **not** that breakouts work. A plain ORB
was weak. The claim is that the edge lives almost entirely in stocks with
unusually high **opening relative volume** — names with overnight news — and
that the selection does nearly all the work.

So the test was built to measure the selection rather than the breakout.

Rules, per symbol per session:

- opening range = the 09:30–09:35 bar, **regular hours only**. Alpaca serves
  04:00–20:00 by default, so a naive "first bar of the day" is a 4am
  pre-market print — 191 bars a day come back, not 78.
- relative volume = that bar's volume ÷ its own 14-session average
- long on the first 5-minute close above the range high, short below the low
- stop at the opposite end of the range, exit at the 16:00 close
- 6bps one way, the same cost model the live bot uses

**167,594 trades, 230 symbols, 2023-09-22 to 2026-09-04.**

## The result

Overall mean net per trade: **−0.2977%**.

Quintiled by opening relative volume, which is the whole point of the test:

| RVOL bucket | trades | first 2yr | holdout 1yr | win rate |
|---|---|---|---|---|
| 1 lowest (0.0–0.6x) | 33,518 | −0.286% | −0.351% | 29% |
| 2 (0.6–0.7x) | 33,518 | −0.276% | −0.330% | 31% |
| 3 (0.7–0.9x) | 33,518 | −0.276% | −0.357% | 31% |
| 4 (0.9–1.3x) | 33,518 | −0.263% | −0.310% | 32% |
| 5 highest (1.3–44.7x) | 33,518 | −0.289% | −0.339% | 34% |

Flat. Every bucket negative, in both periods.

## Why it is a rejection rather than a tuning problem

**It is not costs.** Gross per trade, before any commission or spread, is
**−0.1777%**. Free execution would not save it.

**It is not one side.** Long −0.158% gross, short −0.199% gross.

**It is not one period.** 2023 −0.167%, 2024 −0.167%, 2025 −0.151%,
2026 −0.238% — all gross.

**The selection is inverted.** Tightening the RVOL filter makes it steadily
worse, which is the exact opposite of the paper's finding:

| filter | trades | gross |
|---|---|---|
| rvol ≥ 1.5x | 24,142 | −0.191% |
| rvol ≥ 2x | 12,945 | −0.214% |
| rvol ≥ 3x | 5,846 | −0.226% |
| rvol ≥ 5x | 2,362 | −0.249% |
| rvol ≥ 10x | 504 | **−0.346%** |

**The mechanism is the payoff ratio.** Win rate 31%, average win +1.215%,
average loss −0.974% — a ratio of **1.25** when breakeven at that win rate
requires **2.24**. The shape is right for a breakout system (few winners, run
them) but the winners are less than half the size they need to be.

## The honest caveats

**This is a reasonable reading of the paper, not a certified replication.**
The stop in particular is a choice: the opposite end of the opening range,
where at least one write-up of the paper mentions an ATR-based stop. Different
stops would change the numbers.

**The universe is the most likely culprit, and it was predicted before the
run.** The paper scanned 7,000+ stocks; these are 230 large caps. "Stocks in
play" are disproportionately small and mid-caps gapping on an FDA decision or
an earnings surprise. A mega-cap rarely goes into play the way a $2bn biotech
does.

But note what that explanation does **not** cover: the inverted gradient. If
the selection carried any signal here it should be flat at worst, not
monotonically worse. A large cap trading 10x its normal opening volume is
having a violent news day with a wide opening range — breaking a wide range
means entering after the move, with a distant stop and more whipsaw. That is a
mechanism, and it points the wrong way.

## What would be needed to pursue it

A different universe: several thousand small and mid-caps, screened
pre-market for gap and relative volume. That is a real project — a new data
pipeline, a new screener, a new execution path with same-day exits — with
uncertain payoff against a published edge that is now two years old and widely
circulated. McLean and Pontiff measured published predictors losing 58% of
their return post-publication.

Not taken. Recorded so the next person who reads the paper knows what happened
when it met this account.
