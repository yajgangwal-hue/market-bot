# Entry latency — measured on 3,785 signal days, costs nothing

**10 September 2026.** The claim: the bot is good at finding the big moves and
bad at acting on them, arriving after the move is done.

There was a concrete mechanism behind it, not a metaphor, which is why it
needed measuring rather than answering. The **backtest** fills every entry at
the OPEN of the next session. The **live bot** fills whenever its cycle
happens to run, and today's entries printed at 14:26 UTC — 10:26 New York,
nearly an hour after the bell. If a signal day's move happens in that first
hour, the backtest banks it and the account pays up for it, and every return
this project has quoted would describe a fill nobody gets.

## Method

Signal days taken from the daily files using the shipped rule; intraday paths
from Alpaca 15-minute bars, regular hours only, 2025 onward. For each session
the return is measured from the 09:30 open to each later checkpoint. A control
runs the same measurement on **all** days, to separate "this is what oversold
stocks do" from "this is what every stock does".

## Result

| point | signal days | n | all days | n |
|---|---|---|---|---|
| +15m | +0.0104% | 3,785 | +0.0183% | 72,756 |
| +30m | +0.0493% | 3,785 | +0.0267% | 72,756 |
| **+1h** | **−0.0012%** | 3,785 | +0.0377% | 72,756 |
| +2h | +0.0005% | 3,785 | +0.0308% | 72,756 |
| +3h | −0.0291% | 3,785 | +0.0282% | 72,756 |
| +4h | +0.0409% | 3,785 | +0.0410% | 72,756 |
| close | +0.0621% | 3,785 | +0.0409% | 72,756 |

**At +1h — when the bot actually enters — the drift on signal days is
−0.0012%.** Zero to three decimal places, very slightly in the account's
favour. Waiting an hour after the open costs nothing measurable.

The signal-day column is also flat and unordered: +0.010, +0.049, −0.001,
+0.001, −0.029, +0.041, +0.062. There is no drift to be late for. The control
column drifts gently upward all session, so a *random* stock does rise after
the open — the bot's own signal days do not.

**Every number in the table is smaller than 0.12%**, the cost of a single
round trip. Intraday entry timing is not where this account's money is won or
lost.

## The side finding, which matters more

The worry that prompted the mechanism — that the backtest flatters itself by
filling at 09:30 while the account fills at 10:26 — is **not** borne out. The
gap is about 0.001% per trade. The backtest's fill assumption is honest, and
every return figure in this project survives the check.

## What was not changed, and why

`max_orders_per_run = 3` spreads a day's entries across several cycles when
the rule finds more than three candidates, so some entries are 15, 30 or 45
minutes later than others. Raising it was the obvious follow-up. It was not
raised: this measurement says the spreading costs nothing, so the change would
be motion without effect, and the setting is a runaway-loop guard worth
keeping for the reason it was added.

## Where the money actually went

On the day this was asked, the account was −$413 (−0.41%), entirely
unrealised, across six positions of which five were opened in the previous two
sessions. The strategy holds about fourteen sessions and earns 73.6% of its
return from overnight moves accumulating across that span; two days is not a
sample.

The genuine change was elsewhere: **cash fell to $703**, so the account is 99%
invested across six positions, against roughly 19% idle before. That followed
directly from removing the 200-day trend filter, which found many more setups.
It is the configuration behaving as chosen rather than a fault — but it means
no buffer, full market exposure, and a rule that now buys stocks in
downtrends. That combination is what the measured −37.9% thirty-year drawdown
looks like from the inside.

Not a latency problem.
