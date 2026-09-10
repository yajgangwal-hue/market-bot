# Shorting the bot's own signals — 25,643 signals, rejected

**10 September 2026.** The hypothesis, as put: the bot waits for a large
violent move, buys into it, and by then the move is finished — so it should be
shorting those setups rather than buying them.

Worth a real test rather than an opinion, because there was already evidence
pointing that way. Since the trend filter came off, the sessions this rule
holds return **less** than the average session of the same universe: −0.0108%
on the overnight leg and −0.0150% intraday. A rule whose picks are worse than
random is a rule whose inverse deserves measuring.

## Method

Every day the shipped rule fires, the forward return is taken from the **next
open** — the price the bot could actually get — through the same exit the bot
uses: RSI recovery, the 2.5-ATR stop, or twenty sessions. The identical trade
is then scored as a short with the stop mirrored above entry.

"A huge volatile move" was made precise as the drop into the signal measured
in ATRs, and results bucketed into quintiles by it. The test is for a
**gradient**: if the mechanism is real, shorts should improve as moves get
more violent.

Costs charged against the short: 6bps a side (same as the long), plus 0.5%/yr
borrow — realistic, since every name is marked `easy_to_borrow` on this
account.

## Result

| bucket | signals | long gross | long net | SHORT net | short 1st | short 2nd | short win% |
|---|---|---|---|---|---|---|---|
| ALL SIGNALS | 25,643 | 1.023% | **+0.903%** | **−0.501%** | +0.580% | −1.175% | 34% |
| Q1 drop 1.6–4.5 ATR | 5,128 | 1.141% | +1.021% | −0.698% | +0.461% | −1.346% | 34% |
| Q2 drop 4.5–5.2 ATR | 5,128 | 1.158% | +1.038% | −0.815% | +0.334% | −1.501% | 33% |
| Q3 drop 5.2–5.8 ATR | 5,128 | 0.831% | +0.711% | −0.252% | +0.861% | −0.940% | 35% |
| Q4 drop 5.8–6.6 ATR | 5,128 | 0.957% | +0.837% | −0.297% | +0.666% | −0.886% | 34% |
| Q5 drop 6.6–12.7 ATR | 5,131 | 1.026% | +0.906% | −0.443% | +0.569% | −1.195% | 35% |

**Shorting loses in every bucket**, −0.50% per trade overall at a 34% win
rate.

**There is no gradient.** The most violent moves (Q5, −0.443%) are not better
for shorts than the calmest (Q1, −0.698%). The proposed mechanism predicts
exactly such a gradient, and it is absent.

**The premise is wrong.** "By then the move is over" predicts the long earns
nothing. It earns **+0.903% net per trade**, positive in all five buckets, on
25,643 signals. The bounce does happen and the rule does capture it.

## The trap in this result

Shorting was **profitable in the first half** (+0.580%) and heavily negative
in the second (−1.175%). Measured on 2016–2021 alone, this idea would have
looked correct and would have shipped. It is the split that rejects it, not
the headline — the same reason every change in this project is reported on
both halves.

This also puts the earlier shorting result in context. A previous test lost 71
points over 74 trades, but that was the *old* configuration shorting overbought
names in uptrends — a different bet. This tests the version actually proposed,
on 346× the sample, and reaches the same verdict by a different route.

## Where the instinct was right

The bot makes money per trade and still underperforms, and both are true at
once:

| | per session held |
|---|---|
| the bot's trades | +0.064% |
| a random stock, same period | +0.0855% |

+0.903% per trade over roughly fourteen sessions is 0.064% a session. Simply
owning any stock in the universe for those same fourteen sessions returns
0.0855%. The trades are genuinely profitable **and** genuinely worse than
doing nothing clever.

So the observation behind the hypothesis — that the bot is not capturing much
— is correct. The diagnosis is not. The bot is not late to the move; its
selection stopped adding value when the trend filter came off, which the
overnight decomposition measured directly (+0.0121% advantage with the filter,
−0.0108% without).

The remedy is therefore either to restore the selection edge, or to accept
that this is an index-tracking strategy with extra steps. Inverting a
positive-expectancy signal into a negative-expectancy one is not a remedy.

Not built.
