# Crypto — every family tested, all rejected, and why it is structural

**8 September 2026.** Crypto was previously paused on a friction argument:
roughly 0.6% round trip against 0.12% for equities. That argument turns out to
be wrong, and the real reason is worse.

## What is actually available

Asked of the broker rather than assumed:

- **73 active crypto assets. `shortable`, `marginable` and `easy_to_borrow`
  are 0 on every one of them.** Alpaca crypto is long-only spot. There is no
  borrow, so there is nothing to sell short. Short crypto is not a coding
  problem on this account; it requires a futures or perpetuals venue, which is
  a different broker and a separate integration.
- **36 USD pairs listed; the bot's universe had 10.** The 23 with usable
  history are now fetched, including four meme coins with real depth — DOGE
  from 2021, SHIB from 2023, PEPE and TRUMP from 2025. BONK and WIF are listed
  but Alpaca only has ~200 bars each, too short to judge.

## Costs were never the problem

Swept rather than assumed. At **zero** cost the shipped rule returns 3.0% over
five years; at 40bps it returns 2.5%. Half a point separates free execution
from expensive execution. The friction objection was real arithmetic pointed
at the wrong target.

## The shipped rule cannot fire on crypto at all

Zero trades, and the reason is countable:

| | share of days |
|---|---|
| RSI ≤ 35 | 10% |
| above the 200-day average | 38% |
| **both at once** | **1%** |
| ATR above the 3.5% ceiling | 95% |

If the two conditions were independent you would get 3.8%. At 1% they actively
exclude each other: in crypto, by the time something is oversold it has already
broken its long-term trend. The volatility ceiling alone rejects 95% of days.

With crypto-appropriate floors the rule fires **8 times in 5 years, and not
once in the last two and a half.**

## Every other family, in the real account simulator

The screening pass — each coin its own slice, no stops, no shared cash — made
two families look viable. The account simulator disagrees with both. That gap
is the whole lesson: this project already learned once that per-symbol
backtests "answer a question nobody has".

**Mean reversion, RSI(2) 10/70:**

| variant | total | maxDD | to 2024-06 | since | win% |
|---|---|---|---|---|---|
| stop 1.5 ATR | −53.4% | −57.1% | −36.5% | −26.3% | 59% |
| stop 2.5 ATR | −38.6% | −43.0% | −29.5% | −12.7% | 61% |
| 1 coin at a time (best) | −13.2% | −14.1% | −9.3% | −4.0% | 59% |
| meme coins only | −7.5% | −9.5% | −1.0% | −6.5% | 56% |

Screened at +14.9%. Simulated at −38.6%. Note the win rates: it wins **more
often than it loses** and still loses money, because crypto gaps through stops
and the losers dwarf the winners.

**Trend following**, the family the screen ranked best (+372.6% above the
20-day):

| variant | total | maxDD | to 2024-06 | since |
|---|---|---|---|---|
| above 50-day average | +8.1% | −41.7% | +9.5% | −19.4% |
| rising average, 10 bars | +16.9% | −37.2% | +15.0% | −8.1% |
| above 20-day average | −9.2% | −38.6% | −2.0% | −17.2% |
| meme coins, above 50-day | −2.4% | −17.9% | +2.9% | −4.6% |

**Equal-weight buy and hold over the same window: +290.8%.** The best rule
returns 16.9% while holding the coins returns 290.8%.

## The structural reason, which no parameter fixes

Position size is the risk budget divided by the distance to the stop. Crypto's
daily range is three to twelve times an equity's, so the stop is that much
further away, so the position is that much smaller:

| asset | ATR/price | stop at 2.5 ATR | position at 0.5% risk |
|---|---|---|---|
| SPY | 1.09% | 2.7% | **18.4%** |
| RTX | 1.90% | 4.8% | 10.5% |
| BTC/USD | 4.06% | 10.1% | **4.9%** |
| ETH/USD | 5.24% | 13.1% | 3.8% |
| DOGE/USD | 7.57% | 18.9% | 2.6% |
| SHIB/USD | 13.27% | 33.2% | **1.5%** |

SHIB gets 1.5% of the account. If SHIB triples, the account gains 3%. **The
risk framework that holds equity drawdown to −15% mathematically prevents
meaningful crypto exposure.** That is not a bug and not a setting; it is what
"risk a fixed fraction, stop at a multiple of volatility" means when it meets
an asset whose volatility is ten times larger.

There are only two ways around it, and they are the same way:

1. Risk far more per crypto trade. The sizing sweep run the same day shows
   what that does to equities: at 10% risk, half the return at nearly double
   the drawdown.
2. Abandon stop-based sizing for crypto and allocate a fixed percentage. That
   is buy-and-hold with extra steps, and buy-and-hold carries an **85%**
   drawdown on this basket.

Either way, crypto exposure is bought by giving up the risk control that makes
the equity book worth running.

## Verdict

Not switched on. Every family tested loses money in a real account, and the
one thing that made money over this window — simply holding the coins — has an
85% drawdown and is not a strategy.

The data is fetched and on disk (23 pairs, meme coins included) so that if a
crypto rule ever earns its way in, the evidence is one run away rather than a
week of plumbing.

## What would actually be needed

A separate risk framework with its own capital allocation, its own drawdown
tolerance, and volatility-scaled position sizing rather than stop-distance
sizing — run as a second book, not bolted onto this one. That is a real
project. Bolting crypto onto the current risk model produces either no
exposure or no risk control, and this document is the measurement showing
which.
