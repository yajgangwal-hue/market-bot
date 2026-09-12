# The owner's three ideas, finally priced as accounts rather than statistics

**11 September 2026, night.** Three ideas have been raised repeatedly across
the week. All three had been *measured*, but two of them only as per-trade
averages across a pile of symbol-days — never run as an account with real
capital, position sizing and a drawdown. Every other idea in this project was
judged that way and these were not, which was the real gap.

Closed now. One works and already shipped. Two do not, and this records exactly
how far each got before it failed.

## 1. Trade the overnight market — **shipped**

Not as a separate book: as a correction to *when the bot buys*. It formed its
signal at Monday's close and bought at Tuesday's open, sitting out the exact
move it had predicted. See `2026-09-11-entry-timing.md`. Thirty years: +440.2%
against +293.9%, with drawdown improving from −16.3% to −14.2%.

Confirmed live the same day. The account made **+$669.91**, of which **+$862.10
came overnight and −$192.19 was lost during the session.**

## 2. Short the violent moves — **rejected, sixth time**

Run as an account for the first time, over thirty years, at two violence
thresholds:

| | CAGR | worst DD | trades |
|---|---|---|---|
| long the violent gaps UP, top 20% | −51.70% | −100.0% | 37,267 |
| **short the violent gaps DOWN, top 20%** | **−64.19%** | −100.0% | 34,986 |
| short, top 5% | −54.32% | −100.0% | 16,905 |
| both together, top 5% | −49.76% | −100.0% | 30,067 |

Total ruin in every variant, and the short side is worse than the long side at
every threshold in both windows.

The per-trade measurement had said the long half earned +0.0800%. That was at a
fill nobody can get: **the signal IS the opening gap**, so it cannot be
transacted at the open that defines it. Charging a realistic fill turns +0.08%
negative, and five trades a day compounding a slightly-negative edge at
meaningful size is ruin rather than underperformance.

## 3. Buy the reliable overnight gappers — **rejected, and this one hurt**

Buy the few names that most reliably gap up, at the close; sell at the open.
Nothing held through a session.

On the shipped 230-name universe it looked like the best thing ever found here:

| thirty years | CAGR | worst DD | 1st half | 2nd half |
|---|---|---|---|---|
| 3 best overnight gappers | **32.59%** | −46.3% | 43.80% | 22.67% |
| 6 best | **23.60%** | −45.9% | 36.59% | 12.32% |
| 12 best | 15.27% | −44.8% | 24.21% | 7.31% |
| 25 best | 4.48% | −66.6% | 10.86% | −1.28% |

### Every control passed

| thirty years, 6 positions | CAGR | worst DD | what it proves |
|---|---|---|---|
| 6 names **at random** | −15.47% | −99.5% | the cost model is right — random loses, as 0.0548% overnight against a 0.12% round trip says it must |
| 6 **worst** overnight gappers | −29.76% | −100.0% | the ranking carries information in both directions |
| 6 best by **intraday** return | −16.44% | −99.9% | same as random, so this is **not** generic momentum |
| 6 **best** overnight gappers | **+23.60%** | −45.9% | |

Monotone in position count, monotone from worst to best, overnight-specific,
positive in both halves. Textbook.

### And then the survivorship test killed it

None of those controls can touch the real problem: the universe is today's 230
names run backwards, so it is already the survivors, and "names that reliably
gap up" is the most survivorship-exposed screen that could possibly be built on
it. The names that gapped up for years and then went to zero are not in the
file.

There is one clean subset available. The 46 broad ETFs — SPY, QQQ, the sector,
bond and commodity funds — do not delist and quietly vanish from a survivor
list. Survivorship bias among them is close to nil.

| ETFs only, 3 positions | decade CAGR | thirty-year CAGR | 30y 1st half | 30y 2nd half |
|---|---|---|---|---|
| at random | −19.84% | −16.86% | −10.31% | −22.68% |
| worst overnight | −24.25% | −22.44% | −17.49% | −26.91% |
| best by intraday | −12.12% | −13.58% | −9.85% | −17.02% |
| **best overnight** | **−9.21%** | **−1.52%** | +6.63% | **−8.74%** |

**On a universe that cannot be survivorship-biased, the strategy loses money.**
+23.60% becomes −1.52%.

The signal itself is real — best still beats worst by 21 points, so overnight
persistence genuinely carries information. It is simply **not large enough to
clear a 0.12% round trip every single night** on instruments whose gaps are not
selected by survival. And the ETF second half is −8.74% against a first half of
+6.63%, so what is left is decaying too.

## Where that leaves the account

| | a year | on $100,000 | worst drawdown |
|---|---|---|---|
| conservative (thirty years) | 6.24% | $6,236 | −14.2% |
| optimistic (decade) | 9.87% | $9,867 | −13.7% |

Both include idle cash earning the actual Treasury rate day by day — worth
$115,260 over thirty years, because the account is 73% in cash on average.

And the comparison that belongs on the same page: buying SPY and never touching
it earned **8.55% a year over thirty years with a −56.5% drawdown**. This bot
earns less and takes a quarter of the pain — 0.40 of CAGR per point of drawdown
against SPY's 0.15.

## The pattern worth keeping

Of everything examined today — four rule parameters, four candidate rankings,
two whole strategies, the idle-cash allocation — **one change shipped**, and it
was not a new idea. It was an hour on a clock.

Five results looked like clear improvements on the decade and did not survive
the thirty-year window or a control. Each time the error ran the same
direction: toward believing the good number.
