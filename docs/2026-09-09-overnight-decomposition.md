# Where the money actually comes from: overnight, not the trading day

**9 September 2026.** Prompted by a question about holding positions overnight.
The answer turned out to be more interesting than the question.

A daily bar contains two different markets:

- **overnight** — yesterday's close to today's open. Nobody trades through it;
  you are either holding or you are not.
- **intraday** — today's open to today's close. The session itself.

Every trade the strategy takes over the decade was decomposed across its
holding period, and compared against the average session of the same universe
over the same decade — so the comparison controls for the market itself.

## The headline

**73.6% of the strategy's entire return comes from the overnight gap.**

| leg | total over the decade | share |
|---|---|---|
| overnight (close → open) | +710.7% | **73.6%** |
| intraday (open → close) | +254.3% | 26.4% |

This is the documented overnight anomaly showing up in this account's own
trades: essentially the whole US equity risk premium has historically accrued
between the close and the open, while the session itself contributed little.
The universe control here splits 64.1% / 35.9% the same way.

So holding overnight is not a risk this bot tolerates. It is the entire
business. Anything that shortens holding periods, or moves toward being flat
into the close, is destroying the thing that works.

## The finding that mattered more

Per **session held**, against the average session of the same universe:

| config | decade | trades | overnight | intraday | overnight adv | intraday adv |
|---|---|---|---|---|---|---|
| filter OFF (shipped 2026-09-09) | 157.4% | 1117 | 0.0440% | 0.0157% | **−0.0108%** | −0.0150% |
| filter ON (200-day) | 123.1% | 710 | 0.0670% | 0.0139% | **+0.0121%** | −0.0168% |
| the universe (control) | — | 582,094 | 0.0548% | 0.0307% | — | — |

**With the 200-day trend filter on, the rule had genuine selection skill, and
all of it lived in the overnight leg** — the stocks it chose gapped up
+0.0121% per session more than the average stock in the same universe.

**With the filter off, that edge is gone and inverted** to −0.0108%. The
stocks it now picks gap up *less* than average.

The higher headline return with the filter off — 157.4% against 123.1% — is
therefore not better stock-picking. It is more capital exposed to the market's
own drift. Return and drawdown tables cannot see this distinction; both
configurations look like improvements on one and trade-offs on the other, and
only the per-session decomposition separates skill from exposure.

The uncomfortable implication, stated plainly: a strategy with no selection
edge that makes money by being more invested is doing a job an index fund does
better — higher return, no trading costs, no 1,117 round trips a year, and it
does not need a machine to stay awake.

The account owner was shown this and chose to keep the filter off, for
position count and headline return, with the trade understood. Recorded here
so the reasoning is not mistaken later for an oversight. One line restores it:
`trend_ma_days: int = 200`.

## Why "hold only overnight" does not work

The obvious trade suggests itself: if the overnight leg earns +0.0670% per
session and the intraday leg is a drag against the universe in *both*
configurations, why not buy at the close and sell at the open?

Costs. A round trip is 12bps at the modelled 6bps a side. One night earns
6.7bps. Holding a single night therefore pays 12bps to earn 6.7 and loses
money on every trade; it takes roughly two nights just to break even before
any edge at all.

The current design already handles this correctly by accident: it holds about
14 sessions per trade, capturing fourteen overnight legs for one round trip.
The intraday drag is the price of admission to the overnight gains, and it
cannot be avoided without paying more in commission than it saves.

## What this does not say

The comparison is against *all* universe sessions, while the rule conditions
on recent weakness. A dip-buying rule holding below-average sessions is not
automatically evidence of no skill — it may be evidence that dips are
genuinely worse days, which is the premise the rule is betting against. The
right reading is narrower and still damning enough: **whatever skill the rule
had came from the trend filter, and it was all in the overnight leg.**
