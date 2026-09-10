# The short book — a real per-trade edge that dies in the account

**10 September 2026.** Asked for three times, and the third asking was right
that I had tested the wrong thing. Recorded in full because the failure is
instructive rather than obvious.

## What was wrong with my first two answers

The first test inverted the bot's **own** signal — shorting the *oversold*
names it buys. That lost −0.501% a trade over 25,643 signals, with no gradient
by move violence and a long side earning +0.903%, so the premise failed.

But that is not what was being asked for. The request described a big move
**up** followed by a fall — which is shorting the *overbought*, the true
mirror of a rule that buys weakness expecting a bounce. That had never been
measured at scale here; the only prior attempt was 74 trades on the old
trend-gate configuration.

## The mirror, and it looked genuinely good

| | shipped (long) | tested (short) |
|---|---|---|
| entry | RSI ≤ 35 | RSI ≥ 70 |
| trend | above the 200-day | **below** the 200-day |
| exit | RSI ≥ 60 | RSI ≤ 40 |
| stop | 2.5 ATR below | 2.5 ATR **above** |

Per trade, 1996–2026, net of 6bps a side and 0.5%/yr borrow:

| variant | signals | net/trade | win% | worst year |
|---|---|---|---|---|
| rsi ≥ 65 | 5,895 | +0.171% | 43% | 2012 −3.4% |
| **rsi ≥ 70** | **1,217** | **+1.200%** | **50%** | 2012 −4.4% |
| rsi ≥ 75 | 152 | +2.236% | 62% | 2002 −5.9% |

Everything a real effect should show. The threshold gradient held across
thirty years in the same order as the decade — which is exactly what the
tighter-stop idea failed to do. The trend condition was decisive: shorting
worked **only** below the 200-day (+0.267%) and lost above it (−0.454%), a
coherent mechanism rather than a fitted cell. And it was positive in 21 of 31
years **including bull markets** — 2013 +1.0%, 2015 +2.6%, 2020 +2.6%, 2024
+1.8% — which was the specific test set in advance to distinguish a strategy
from a bear-market hedge.

One caveat was recorded before building anything: the profit concentrates.
2022 alone is 178 trades at +4.9%, about 60% of all profit. Excluding it and
the thin 1996–99 years leaves +0.34% a trade — still nearly three times the
round trip, but thin.

## Then it went through an account simulator

Per-trade statistics are not portfolio returns. This project has already paid
for forgetting that: the crypto mean-reversion family screened at +14.9% and
returned −38.6% through the account engine.

| period | variant | total | CAGR | maxDD | trades | win% |
|---|---|---|---|---|---|---|
| decade | rsi ≥ 65 | −17.0% | −1.73% | −23.1% | 510 | 39% |
| decade | rsi ≥ 70 | −9.0% | −0.88% | −11.3% | 190 | 42% |
| decade | rsi ≥ 75 | +0.7% | +0.06% | −3.1% | 40 | 48% |
| 30 years | rsi ≥ 65 | −19.6% | −0.71% | −27.0% | 980 | 43% |
| 30 years | rsi ≥ 70 | −5.6% | −0.19% | −11.6% | 336 | 43% |

**+1.200% a trade became −0.19% a year.**

## Why, and it is structural

**The book is idle almost all the time.** 336 trades over thirty years is
about eleven a year, held roughly twenty sessions each — under **one position
on average** against twelve slots. Some 89% of the capital earns nothing while
a thin stream of trades bleeds it.

**Risk-based sizing gives the best trades the smallest positions.** Position
size is the risk budget divided by the stop distance, and the stop is 2.5 ATR.
The violent run-ups behind the +9% and +12% per-trade years are high-ATR
names, so they receive the *smallest* allocations. A per-trade average weights
every trade equally; a portfolio weights by capital — and the capital went
where the edge was not.

That is the same structural failure measured on crypto, where SHIB's
volatility earned it 1.5% of the account. Same sizing model, same outcome, a
different asset class.

## What was built and kept

A standalone short-book simulator with its own accounting checks, deliberately
**not** a flag threaded through `portfolio.py`. Shorting inverts nearly every
assumption in the long engine — the stop is above, the exit compares the high,
profit is entry minus exit — and an error there would silently invent or
destroy money every bar rather than crash.

The checks it passes: a flat market causes no equity drift, stops sit above
entry, a continuing rally is closed by the stop, losses stay bounded by the
risk budget, and a declining fixture produces a profitable book.

The live path was **not** built. The most dangerous piece is the reconciler:
shown a short position today it would rest a *sell*-stop, which **doubles the
short instead of closing it** — the worst bug available in this codebase.
There is no reason to accept that risk for a strategy the simulator says loses
money.

## What would change the answer

Not a parameter. The sizing model is what fails here, and the same model fails
on crypto for the same reason. A short book would need volatility-scaled or
equal-weight allocation rather than stop-distance sizing, and its own capital
sleeve — which is the identical conclusion the crypto work reached
independently. If that second sleeve is ever built, both belong in it.

Not built.
