# The bot was buying the day after the move it predicted

**11 September 2026.** The account owner has said the same thing four
different ways over three days:

> "it sees those big swings... but by then the volatility is over"
>
> "it's good at finding the big moves but not good on acting on them"
>
> "it hops on it too late"

Every previous answer treated that as a request for an intraday strategy, and
every intraday test came back empty — five of them, on 167,594 opening-range
trades, 192,000 swing trades, 3,785 days of entry latency, a full
overnight/intraday decomposition, and 154,131 volatile opens.

All five were answering the wrong question. He was not describing a missing
strategy. He was describing a **bug in the order clock**, and he was right.

## What was actually happening

The rule forms its signal from a **completed** daily bar. The order then fills
at the **next session's open**.

So on the evening a name closes oversold, the bot decides to buy it — and then
stands aside for the entire close-to-open move before transacting. That is not
a rounding error in this strategy. It is the strategy:

* 73.6% of this rule's return is close-to-open, measured in the decomposition
  on 2026-09-09;
* the universe averages +0.0548% overnight against +0.0307% intraday.

The one move that pays was the one move the bot was never present for at
entry.

## What the gap was worth

Measured directly, trade by trade, across the decade's 710 trades — the
close-to-open return on the bar each signal was computed from:

| | n | mean | median | 1st half | 2nd half | worst | up% |
|---|---|---|---|---|---|---|---|
| **entry** → signal close | 710 | **+0.1292%** | +0.0615% | +0.0782% | +0.1766% | −4.09% | 54% |
| exit → next open (all) | 464 | +0.0180% | +0.0979% | +0.0112% | +0.0244% | −10.98% | 57% |
|   of which `reverted` | 225 | +0.0578% | +0.0930% | +0.0193% | +0.0920% | −3.46% | 57% |
|   of which `time_exit` | 239 | −0.0195% | +0.1010% | +0.0040% | −0.0432% | −10.98% | 57% |

The entry side is worth +0.1292% a trade, positive in both halves and **larger
in the recent half**. The median is positive too, so it is not a handful of fat
tails.

The exit side is worth nothing — +0.018% overall, and negative on the time
exits, which are the larger half. **Only the entry moves.** Holding a recovered
position one extra night to catch its gap is not paid for, and it adds a night
of risk, so the exit stays where it is.

## Re-run end to end, at four levels of friction

The per-trade figure is first-order: it multiplies gaps by position sizes. It
cannot see compounding, cannot see that a different fill price changes what the
next trade can afford, and cannot see that entering *before* the night means a
gap can now run through the stop while the position is live rather than before
it exists — and that last one can only hurt.

Full account simulation, same rule, same universe, same sizing, both
configurations charged the **same** friction at each level:

| one-way | next open (shipped) | signal close | advantage | maxDD |
|---|---|---|---|---|
| 3 bps | 8.81% | 9.32% | **+0.51** | −14.3% → −13.2% |
| 6 bps | 7.83% | 9.14% | **+1.32** | −14.1% → −13.7% |
| 9 bps | 7.67% | 8.97% | **+1.30** | −14.1% → −13.7% |
| 12 bps | 6.42% | 7.31% | **+0.89** | −14.1% → −14.7% |

Positive at every friction level, in both halves at every level, with drawdown
*improving* in three of four. Win rate goes 53% → 55%, and the 20 entries a
decade that were skipped because the overnight gap ran through the stop before
the position existed go to **zero**, because there is no longer a gap between
the signal and the fill.

This is the only change found in this project that raises return without
buying it with drawdown — because it is not taking more risk. It is the same
trade, at a different hour.

## Thirty years, which is what decides it here

The decade contains no sustained bear market, so nothing ships on it alone.

| 30 years, 6bps | total | CAGR | maxDD | 1st half | 2nd half | trades | win% |
|---|---|---|---|---|---|---|---|
| next open (old) | +293.9% | 4.58% | −16.3% | +24.3% | +216.8% | 1,516 | 53% |
| **signal close** | **+440.4%** | **5.66%** | **−14.2%** | **+39.0%** | **+288.8%** | 1,526 | 54% |

| crisis year | 2000 | 2001 | 2002 | 2008 | 2020 | 2022 |
|---|---|---|---|---|---|---|
| next open | −1.8% | +1.7% | −2.2% | −8.7% | +3.4% | −8.7% |
| signal close | −1.7% | +2.1% | −1.9% | **−7.8%** | +3.6% | **−10.1%** |

+1.08 CAGR points over thirty years, better in both halves, better through the
dot-com bust and better through 2008, with the maximum drawdown improving from
−16.3% to −14.2%.

**2022 is the exception and it is the honest caveat.** −8.7% becomes −10.1%. A
grinding decline is the one regime where being in before the gap is a
liability rather than an asset, because in that regime the gaps are down. One
year out of thirty went the wrong way, and it is the kind of year that is
worth naming rather than averaging away.

### One row that was wrong and should not be quoted

The first version of this comparison charged **double** friction to the close
fill and single friction to the shipped one, and reported −0.51 CAGR points. It
compared a cheap version of one idea against an expensive version of the other,
and it doubled the cost of the *exits* too, which this change does not touch.
The cost-matched table above is the answer.

## The obvious objection, measured rather than assumed

At 16:00:00 there is no session left to trade in. Filling at close[T] on a
signal computed from close[T] cannot literally be done.

The honest version is to make 15:45 the decision point for **both** halves —
compute the signal from prices through 15:45 and buy at 15:45 — which removes
the look-ahead entirely and turns the objection into a measurable question: is
15:45 → next open worth as much as close → next open?

On 19,348 symbol-sessions of real 15-minute bars across 40 names:

| | n | mean | median | up% |
|---|---|---|---|---|
| last 15 min, every session | 19,348 | +0.0030% | +0.0015% | 50% |
| last 15 min, **oversold** sessions | 1,421 | +0.0118% | −0.0118% | 48% |
| **15:45 → next open** | 1,421 | **+0.0240%** | +0.0520% | 54% |
| close → next open | 1,421 | +0.0111% | +0.0531% | 53% |

Trading at 15:45 reaches the next open **better** than trading at the close
does, not worse. And the signal is the same signal: the RSI verdict at 15:45
differs from the verdict at the close on **125 of 19,348 sessions — 0.65%**,
and a disagreement there is a marginal name either side of 35, not a different
trade in kind.

(These gap figures are much smaller than the +0.1292% above because they cover
*every* oversold session over two years, not the trades this rule actually
takes, which must also clear the 200-day trend filter, the liquidity floors and
the ATR limit. The table settles the approximation, not the size of the edge.)

Alpaca serves a partial daily bar during the session, and it aggregates the
regular session rather than pre-market — checked again live on 2026-09-11 at
10:46 ET, where the in-progress close tracked the last trade to within 0.06%.

## What shipped

`AutoTradeConfig.entry_window_minutes`. When set, entries are attempted only in
the last N minutes of the session, and the signal is computed with the session
in progress appended to the daily history.

Four things it deliberately will not do:

* **It never gates protection.** Exits, stops and the stop reconciler run every
  cycle, all day, exactly as before. A window on entries that became a window
  on selling would be far more expensive than the gap is worth, and
  `test_entry_timing.py` pins it.
* **It uses the broker's clock, not this machine's,** so half-days and holidays
  are handled by the venue that decides them.
* **It refuses to act blind.** A clock it cannot parse, or a failure to fetch
  same-day bars, means no entries that cycle. Filling at today's close on
  yesterday's information would pay the gap's price without reading the day
  that set it — worse than either design.
* **It is not the loss guard.** `halted` still means the daily loss guard closed
  the book; an ordinary 10am cycle does not report itself as halted.

## What this does and does not answer

It answers "it hops on too late" exactly. From here the bot acts on the same
session it sees the move in, rather than the morning after.

It does **not** make the bot a day trader, and the same simulator says why. The
identical rule, flat every night — in at the open, out at the close, zero
overnight exposure — over the same decade:

| holding period | total | CAGR | maxDD | 1st half | 2nd half | trades | nights held |
|---|---|---|---|---|---|---|---|
| **1 day — flat every night** | **−39.3%** | −4.57% | −40.5% | −17.6% | −26.3% | 3,093 | **0** |
| 3 days | +5.2% | +0.48% | −11.7% | +7.9% | −2.5% | 1,499 | 2,928 |
| 20 days (shipped) | +123.1% | +7.83% | −14.1% | +66.1% | +34.3% | 710 | 9,159 |
| 20 days + close entry | **+153.9%** | **+9.14%** | −13.7% | +68.3% | +50.8% | 713 | 9,841 |

Same signals, same universe, same costs — only the holding period changes, and
it is monotone. Going flat every night turns +123% into −39% and triples the
drawdown, because it forfeits the 73.6% of the return that happens while the
market is shut and pays 3,093 round trips for the 26% that is left. Even three
days is barely break-even.

What the bot now does instead is the day trader's *reflex* without the day
trader's *exit*: it reacts within the session it sees the move in, and then
holds through the part of the move that actually pays.
