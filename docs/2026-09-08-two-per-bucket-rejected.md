# Two names per correlation bucket — tested, rejected

**8 September 2026.** Tested because it was the one remaining idea for raising
the number of positions the bot holds at once, and because it had a real
mechanism behind it rather than a hope.

It does not pay. Not marginally, and not for the reason I expected.

## Why it was proposed

The request was 8–10 positions open at once, each about 10% of the account.

Two of those three things were already true. `max_open_positions` is 12 and a
typical position is $9,771 on a $100k account — 9.8%. What is not true is the
count: over the decade the bot holds **3.7 positions on average**, peaking at
9, and sits in cash entirely on 16% of days.

The cap is not what stops it. When the constraints were counted, **36% of
qualifying signals were rejected because another position already occupied
that correlation bucket** — nearly twice as many as the position cap rejected.
So the bucket rule was the binding constraint, and relaxing it was the obvious
lever.

The proposal was two names per bucket at half the risk each. Sector exposure
would then be unchanged in the saturated case while the number of names
roughly doubled, which is exactly the breadth term in Grinold's law:
`IR = TC × IC × √breadth`.

## What was measured

Decade of daily bars, 230 equities, one shared cash balance through
`portfolio.py` — the account simulator, not the per-symbol backtest. Split at
2021-03-01.

| variant | decade | CAGR | maxDD | 1st half | 2nd half | trades | avgPos |
|---|---|---|---|---|---|---|---|
| 1/bucket 0.50% **SHIPPED** | **+127.6%** | 8.02% | −15.0% | +45.5% | +62.4% | 708 | 3.7 |
| 1/bucket 0.25% *size control* | +65.1% | 4.81% | −9.5% | +25.2% | +34.6% | 890 | 4.6 |
| 2/bucket 0.25% **proposal** | +65.7% | 4.85% | −12.2% | +32.0% | +27.7% | 1063 | 5.6 |
| 2/bucket 0.50% | +104.0% | 6.91% | −15.3% | +37.1% | +54.1% | 798 | 4.2 |
| 3/bucket 0.167% | +51.2% | 3.95% | −7.1% | +21.1% | +26.3% | 1108 | 5.8 |
| 3/bucket 0.50% | +105.2% | 6.97% | −15.9% | +37.8% | +53.8% | 819 | 4.3 |

Shuffled sector maps — same bucket sizes, symbols reassigned at random,
2/bucket at 0.25%:

| control | decade | maxDD | 1st half | 2nd half |
|---|---|---|---|---|
| random seed 7 | +76.4% | −10.4% | +27.7% | +40.4% |
| random seed 19 | +84.2% | −9.9% | +27.1% | +47.5% |
| random seed 41 | +83.0% | −11.1% | +27.4% | +45.5% |

## The result

**It did what it was supposed to do mechanically.** Concurrency rose from 3.7
to 5.6 and trades from 890 to 1063. The lever works.

**It bought nothing.** +65.7% against the half-size control's +65.1% — 0.6
points apart over ten years — at a *worse* drawdown, −12.2% against −9.5%. And
it lost to that control on the second half (+27.7% vs +34.6%), so it fails the
both-halves bar outright.

The entire gap between the proposal and the shipped row is **bet size**, not
the bucket rule. That is precisely what the size control existed to separate,
and it is the comparison that would have been missed by testing the proposal
against the shipped config alone.

## Why it is a rejection rather than a tuning problem

**Relaxing the rule at full size is actively worse.** 2/bucket at 0.50%
returns +104.0% against the shipped +127.6%, worse on *both* halves at the
same drawdown. Allowing three per bucket lands in the same place (+105.2%),
because past two names cash binds before the bucket rule does. So the
one-per-bucket rule is doing real work; it is not merely a count that could be
traded for more names.

**The random control removes the theory.** All three shuffled sector maps beat
the real map at 2/bucket, on return and on drawdown. A rule that cannot beat
an arbitrary grouping of the same shape is not delivering the diversification
it is justified by. Whatever the second slot in a bucket is buying, it is not
sector spread.

**The mechanism, stated plainly.** Grinold's breadth term rewards
*independent* bets. A second name in the same correlation bucket is correlated
with the first by construction — that is what the bucket means. Adding it is
not breadth; it is the same bet twice at half size. This is the identical
finding to the universe-expansion test earlier in this project: concentration
wearing breadth's clothes.

## The honest caveats

**Return differences here are noise-dominated and drawdown differences are
not.** This project has measured that before: sweeping `risk_per_trade` across
the decade produced returns of 85 / 112 / 90 / 110 / 90 with no ordering
whatever, while drawdown ran −12 / −15 / −17 / −18 / −20, perfectly ordered.
The mechanism is that a different bet size takes a different *set* of trades
and the sequence diverges chaotically. So the 11–19 point gaps between the
proposal and the random controls should not be read as a precise measurement
of anything. What survives that caveat is the direction — every relaxation
tested is at or below the shipped configuration, and none is above it.

**The earlier concurrency figure of 4.6 was a proxy and overstated it.** It
divided average deployed capital (45%) by an assumed 10% position. Conviction
weighting makes positions range from about 5% to 15%, so the division
overcounts. Counting open positions directly from the trade log gives 3.7.
The number in this document is the counted one.

**One split, not walk-forward.** Both halves are reported, and the proposal
fails on the second, but this is not a rolling out-of-sample test.

## What this means for the original request

8–10 concurrent positions is achievable — 3/bucket at 0.167% reaches 5.8
average and 12 peak — but every configuration that raises the count lowers the
return. The count was never the thing that makes money; it was a symptom of
how often the rule finds a qualifying setup, which is about four at a time.

Not taken. `max_per_bucket` stays at 1, and remains in `RiskPolicy` with this
table beside it so the next person who has this idea can see what happened
when it met the data.
