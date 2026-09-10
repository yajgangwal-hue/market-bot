# Volatility targeting and a market regime filter — both rejected

**10 September 2026.** Every parameter *inside* the rule had been swept and
none survived. These two are different in kind: they act on **exposure** —
how much of the account is at risk and when — rather than on stock selection.
That question had never been asked here.

Both failed, and the reasons are worth keeping because they explain something
true about the strategy.

## Volatility targeting

Scale position size by `target_vol / realised_vol`, so the book carries
roughly constant *risk* instead of constant *dollars*. The mechanism is the
best-supported one available: realised volatility is strongly autocorrelated —
a violent week predicts a violent week — while returns are not, so scaling on
volatility uses the part of the market that genuinely is forecastable.

| decade 2016–2026 | total | CAGR | maxDD | 1st half | 2nd half |
|---|---|---|---|---|---|
| **shipped** | **123.1%** | **7.82%** | −14.1% | 43.3% | 61.7% |
| target 10% | 105.1% | 6.97% | −12.3% | 37.5% | 53.0% |
| target 12% | 116.5% | 7.51% | −14.6% | 51.2% | 47.6% |
| target 15% | 117.1% | 7.54% | −14.2% | 52.3% | 47.5% |
| target 20% | 114.1% | 7.40% | −16.5% | 53.9% | 46.0% |
| target 12%, cut only | 106.1% | 7.02% | −12.4% | 38.1% | 53.8% |

| thirty years 1996–2026 | total | CAGR | maxDD | 1st half | 2nd half |
|---|---|---|---|---|---|
| **shipped** | **293.9%** | **4.57%** | −16.3% | 24.3% | 216.8% |
| target 10% | 221.0% | 3.88% | −13.5% | 18.4% | 171.1% |
| target 12% | 245.5% | 4.13% | −14.3% | 22.2% | 182.8% |
| target 15% | 246.6% | 4.14% | −16.2% | 26.6% | 173.8% |
| target 20% | 276.0% | 4.41% | −16.5% | 39.1% | 170.4% |
| target 12%, cut only | 241.6% | 4.09% | −14.8% | 20.1% | 184.3% |

It does what it claims — drawdown falls from −14.1% to −12.3% on the decade —
and it costs proportionally more return than it saves in risk. Return divided
by drawdown, thirty years: **shipped 18.0**, against 16.7, 17.2 and 16.3 for
the variants. Nothing beats the baseline on both halves on either window.

**Why it fails here.** The bot is *already* a variable-exposure strategy. It
holds about 3.7 positions and sits roughly half in cash, and that cash
fraction rises on its own when setups dry up — which is precisely when
volatility is high. Layering a second exposure scalar on top of one that
already exists mostly just reduces participation.

## The market regime filter

Refuse new entries while SPY is below its own 200-day average. Not the
per-stock filter that already ships — that asks whether each *stock* is in an
uptrend, this asks whether the *market* is. It is also the shape that worked
on crypto, where holding the basket only while BTC was above its average cut
2018 from −74% to −40%.

| | total | CAGR | maxDD |
|---|---|---|---|
| shipped (30yr) | **293.9%** | **4.57%** | **−16.3%** |
| no entries while SPY below 200d | 211.8% | 3.78% | −16.4% |
| market gate + vol target 12% | 184.2% | 3.46% | −14.8% |

**−16.4% against −16.3%.** No risk reduction at all, for 82 points less
return. That is the clearest single result in the file.

**Why**, and it is the useful finding: the per-stock 200-day filter already
does the regime job. In a market decline individual stocks fall below their
*own* 200-day and the rule stops buying by itself — which is exactly why 2008
cost this strategy only −8.7% against the market's −38.3%. A market-level gate
removes trades the per-stock filter would have allowed **without removing
losses**, because the losses were already being avoided.

The crypto analogy did not transfer for the same reason: the crypto basket had
no per-coin trend filter, so the regime overlay was supplying protection that
did not otherwise exist. Here it already exists.

## The wider point

This is roughly the thirty-fifth distinct idea tested across the week. Two
shipped: restoring the trend filter, and parking idle cash. Everything else
measured worse, or measured better on one window and failed on another.

That is not a failure to search. It is the answer. The strategy's edge is
small, lives almost entirely in the 200-day trend filter, and is already being
harvested at close to its measured optimum — about 9.3% a year at a −16% worst
case with cash parking included.

The one avenue still untried is a **second book with fixed-fraction sizing in
its own capital sleeve**. Both the crypto work and the short-book work arrived
at it independently: stop-distance sizing starves exactly the positions that
carry a diversifying edge. The crypto regime overlay is the concrete
candidate, with two-cycle evidence behind it. That is a build, not a tune.
