# Shorting the volatile open — the gradient runs the other way

**10 September 2026.** From four screenshots of held positions: each session
opens with a violent spike, then the stock slides for the rest of the day, so
shorting into that spike should pay.

Tested directly, because it is a real falsifiable hypothesis and genuinely
distinct from what had been measured before. The opening-range breakout test
measured *breakouts*; the intraday swing test measured *RSI reversals*.
Neither asked whether opening volatility alone carries directional
information.

## Method

Every symbol-session, regular hours, 2024 onward. Opening volatility measured
two ways — the first 30 minutes' high-low range as a share of the open, and
opening volume against that symbol's own 20-session average — then the return
from the 30-minute mark to the close. Bucketed into quintiles by each.

The claim predicts a **gradient**: the most violent opens should give the most
negative forward returns.

## Result: 154,131 sessions

| bucket (opening range) | sessions | forward return | short net |
|---|---|---|---|
| Q1 0.01%–0.61% | 30,826 | +0.0066% | −0.1266% |
| Q2 0.61%–0.99% | 30,826 | +0.0114% | −0.1314% |
| Q3 0.99%–1.43% | 30,826 | +0.0119% | −0.1319% |
| Q4 1.43%–2.27% | 30,826 | +0.0130% | −0.1330% |
| **Q5 2.27%–53.80%** | 30,827 | **+0.0997%** | **−0.2197%** |

**There is a gradient, and it runs the opposite way.** The more violent the
open, the more the stock RISES through the rest of the session — 0.0066 →
0.0114 → 0.0119 → 0.0130 → 0.0997, monotone, fifteen times steeper at the top
than the bottom.

So the instinct that opening volatility carries information was correct. The
direction was backwards. Shorting a violent open is the *worst* version of the
idea: −0.2197% net against −0.1266% for shorting a quiet one.

By opening volume there is no gradient at all: +0.0328%, +0.0055%, +0.0249%,
+0.0312%, +0.0348%. The share of sessions that fall sits at 47–49% in every
bucket, which is a coin flip.

## It cannot be traded long either

The Q5 effect is real and too small to reach. +0.0997% gross against a 0.12%
round trip is **−0.02% net**. Free execution would barely break even, and
there is no version of this that survives a spread.

## The second independent confirmation

The ORB test bucketed 167,594 trades by opening relative volume and found the
same inversion — the highest-volume names performed *worst*, monotonically.
Two measurements, different methods, different samples, same conclusion:
opening volatility does not predict direction on this universe.

## Why the charts look otherwise

Four positions were shown on a day when SPX fell 0.58%, NDQ 1.08% and small
caps 1.07%. Three drifted down and one, TJX, was up $43.79. On a broadly red
day, three of four longs being red is what a long book does.

The spike at the far left of every one of those charts is the 09:30 opening
auction. It appears on every stock, every day, whatever the stock then does —
and the bot's entries were visibly an hour later, so it was not trading that
spike at all.

The deeper issue is that a finished chart reads backwards. Once LIN's path
from 467 to 461 is visible, the open looks like an obvious short. Standing at
09:35 with only what was known then, the question was which of 230 names would
fade and which would run — and the answer, measured across 154,131 sessions,
is that the violent ones ran.

## Where this leaves the intraday question

Five independent measurements now say the same thing:

| test | sample | result |
|---|---|---|
| opening-range breakout | 167,594 trades | −0.18% before costs, inverted gradient |
| intraday swings | 192,000 trades | +0.009% gross — zero |
| entry latency | 3,785 signal days | −0.0012% at +1h — no drift to be late for |
| overnight decomposition | decade | intraday leg −0.0150%/session |
| volatile opens | 154,131 sessions | gradient inverted |

This account's edge is between the close and the open, and 73.6% of its return
comes from there. Inside the session there is nothing to capture.

Not built.
