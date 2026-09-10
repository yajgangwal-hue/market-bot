# Trading the intraday swings — tested on 192,000 trades, rejected

**9 September 2026.** Asked for directly, with a chart of the open RTX
position: a session of large repeated up-and-down swings, and the observation
that selling near each top and buying near each bottom would have made money
many times over instead of the position sitting at −$91.

The observation is correct. The swings are real and they are large. The
inference — that they can be traded — is what fails.

## What was tested

The most direct reading of the request: a short-horizon RSI on 15-minute bars,
buy when oversold, sell when recovered, repeat, flat by the close. Six
parameter combinations, the whole 230-name universe, regular hours only, from
2024-01-01. Costs 6bps a side, the same model the live bot uses.

| rule | trades | gross/trade | net/trade | 1st half | 2nd half | win% |
|---|---|---|---|---|---|---|
| rsi7 buy 25 sell 65 | 45,435 | +0.0087% | −0.1113% | −0.1444% | −0.0745% | 44% |
| rsi7 buy 30 sell 70 | 64,548 | +0.0086% | −0.1114% | −0.1323% | −0.0886% | 43% |
| rsi14 buy 30 sell 70 | 26,241 | −0.0056% | −0.1256% | −0.1665% | −0.0797% | 41% |
| rsi14 buy 25 sell 60 | 14,753 | −0.0117% | −0.1317% | −0.1873% | −0.0659% | 41% |
| rsi14 buy 35 sell 65 | 41,170 | +0.0007% | −0.1193% | −0.1479% | −0.0879% | 41% |

## Why this is a rejection and not a tuning problem

**The gross edge is zero.** +0.0087%, +0.0086%, −0.0056%, −0.0117%, +0.0007%
across 192,000 trades. Gross is measured before any commission, spread or
slippage, so this is not a cost problem: with perfectly free execution the
rule still captures nothing. No amount of better fills, tighter thresholds or
faster polling can improve on an edge that does not exist.

**The win rate is 41–44%.** The rule is wrong more often than it is right, in
every configuration.

**Both halves are negative** for every variant, so there is not even one
period where it worked.

**Costs then bury it.** Net lands at −0.11% to −0.13%, almost exactly the
0.12% round-trip cost — the strategy captures nothing and pays full freight.
At the 64,548-trade rate that is roughly 38,000 trades a year across the book,
paying about thirteen times more in friction than the signal is worth.

## The mechanism, stated plainly

A swing being visible on a finished chart is not the same as being callable in
advance. Standing at any single candle on the left of that chart, with only
the information available then, the next move was a coin flip — very slightly
worse than one. What makes the pattern look obvious is that it is being read
after it completed.

This is the same result the project's other intraday work reached from
different directions: the opening-range breakout lost money before costs
across 167,594 trades, and the overnight decomposition measured the strategy's
INTRADAY leg at −0.0150% per session against the universe while the OVERNIGHT
leg carried 73.6% of all returns. Three independent tests, one conclusion:
this account's edge lives between the close and the open, not inside the
session.

## Shorting does not rescue it

Equities are shortable on this account — 60 of 60 checked are marked
`shortable` and `easy_to_borrow`, unlike crypto where the number is zero. So
the short side is buildable. It is not worth building: the short side of a
zero-edge swing is the mirror of the same zero edge, and it adds borrow cost
on top. An earlier test of the mean-reversion rule inverted lost 71 points
over 74 trades.

## A real constraint worth recording

The `rsi21` variant produced no trades at all. A 21-period RSI needs 27 bars
and a regular session contains 26 fifteen-minute bars, so it can never form
within a day. That is a hard ceiling on how slow an intraday indicator can be,
and it applies to anything else built on this timescale.

## What the position in the chart was actually doing

RTX at −$91 on 66 shares is −0.7%, against a stop 5.5% below entry. The
strategy holds through exactly these oscillations on purpose, because its
return comes from the close-to-open moves that accumulate over the roughly
fourteen sessions it holds. The swings are noise the rule deliberately sits
through, not opportunities it is failing to take.

Not built.
