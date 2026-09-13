# An honest emulator, one evaluation, and the exits priced

**13 September 2026.** The owner's specification for the bot was long and
its priorities were right: a realistic emulator first, a proper evaluation
second, and much better exits above everything else. This records what was
built, what was measured, and the one number that changes what the bot can
honestly claim.

Nothing here changes how the bot trades. It changes how truthfully it is
measured — and the measurement is what decides every future change.

---

## The objective, written down as a number

The specification asks for an agent whose survival depends on making money
without blowing up. There is no language model in this bot, so that cannot
be a sentence it believes; it has to be a criterion the evaluation enforces:

> **Maximise geometric growth, subject to the probability of a 25% drawdown.**

`evaluation.py` scores every configuration on exactly that: CAGR as the
objective, and the probability of a 25% drawdown — estimated by
block-bootstrapping the daily equity returns — as the "shut off" risk. A
change that raises CAGR while raising that probability **fails**. The
existing guards (daily and weekly loss limits, position and bucket caps,
whole-share sizing so every position carries a resting stop) are the
enforcement; the evaluation is how the trade-off is seen.

## The emulator was optimistic in two ways

**Stops filled at the stop.** A resting stop becomes a market order when
touched; if the session opened below it, the fill is the open. One in five
stop exits gapped through on the decade, one in six over thirty years, with a
mean shortfall of 1.2% of entry. `realistic_stop_fills` fills at the open.

**Nothing recorded what a trade could have made.** Every `ClosedTrade` now
carries its highest high and lowest low while open, so exit quality is a
number: `captured` (share of the best available profit the exit kept),
`gave_back` (profit that was there and was not taken, as % of entry), `heat`
(worst adverse move). Live exits record the same fields, and `record.py`
reports them on real trades.

### The honest baseline

| | CAGR | maxDD | Sharpe | ruin (25%) | PF | captured | gave back |
|---|---|---|---|---|---|---|---|
| decade, as published | 9.14% | −13.7% | 0.96 | 6.4% | 1.49 | −0.69 | 4.27% |
| **decade, honest** | **8.35%** | −14.3% | 0.88 | **12.0%** | 1.44 | −0.74 | 4.35% |
| 30 years, as published | 5.66% | −14.2% | 0.70 | 17.0% | 1.45 | −0.98 | 4.30% |
| **30 years, honest** | **5.10%** | −15.2% | 0.64 | **26.0%** | 1.39 | −0.94 | 4.38% |

Realistic stop fills cost 0.6–0.8 CAGR points, and — the figure every prior
conversation was missing — **raise the probability of a 25% drawdown from 17%
to 26% over thirty years.**

### Where the money leaks

| 30 years | trades | captured | gave back | P&L |
|---|---|---|---|---|
| `reverted` (RSI recovered) | 451 | **0.92** | 0.65% | +994,227 |
| `stop` | 542 | −3.07 | **8.36%** | −829,266 |
| `time_exit` | 529 | −0.34 | 3.48% | +191,260 |

The owner's instinct was exactly right, and now it is a number. The rule's own
exits keep 92% of available profit. The damage is in the other two: a stopped
trade had on average been *up* and gave back 8.4% of entry before the stop took
it — the "winner became a loser" failure — and a time exit keeps nothing of
what was there because it waits twenty days for a move that decayed.

## The exits the specification asked for, priced

Five variants were built into the simulator, all off by default, each raising
the stop or closing on evidence from bars already printed and never lowering
a stop: a trailing stop under the high through yesterday, partial profit
taking, a momentum-deterioration exit, a regime exit, and a volatility trail
under yesterday's close. The bar: CAGR up, ruin not up, both halves held.

| decade, honest fills | CAGR | maxDD | ruin | trades | win% | captured | 1st | 2nd |
|---|---|---|---|---|---|---|---|---|
| **HONEST BASELINE** | 8.35% | −14.3% | 12.0% | 712 | 55% | −0.74 | 8.69% | 7.97% |
| trail 0.5R, 2.5 ATR | 5.59% | −18.3% | 20.8% | 913 | 43% | −1.15 | 6.01% | 5.11% |
| trail 1.0R, 2.0 ATR | 7.67% | −13.9% | 10.8% | 761 | 58% | −0.76 | 7.25% | 8.14% |
| **trail 1.0R, 3.0 ATR** | 8.59% | −14.6% | 11.6% | 741 | 54% | −0.74 | 8.65% | 8.52% |
| partial 1.0R, half | 7.12% | −15.3% | 13.2% | 1,059 | **69%** | −0.22 | 7.07% | 7.18% |
| partial 1.5R, half | 7.95% | −14.4% | 11.0% | 870 | 63% | −0.45 | 8.38% | 7.47% |
| momentum drop 10 | 7.43% | −15.9% | 14.8% | 737 | 57% | −0.71 | 7.58% | 7.25% |
| momentum drop 15 | 8.20% | −14.3% | 12.0% | 713 | 55% | −0.75 | 8.09% | 8.32% |
| **regime exit** | 8.43% | −14.3% | 11.2% | 713 | 55% | −0.73 | 8.57% | 8.26% |
| vol-trail 2.5 ATR | 8.52% | −15.0% | **7.8%** | 805 | 48% | −0.83 | 9.40% | 7.53% |
| vol-trail 3.0 ATR | 7.91% | −14.4% | 14.4% | 762 | 50% | −0.77 | 8.52% | 7.22% |

Three things this table settles:

* **Taking profit early loses money every time it raises the win rate.** Both
  partial rows and both momentum rows lift the win rate — to 69% in one case
  — and lower CAGR. `gave_back` falls; `captured` collapses. This is the
  rescue-exit finding of 2026-09-11 reproduced four more ways.
* **A tight trail is the worst thing in the table** (5.59%, ruin 20.8%): it
  is shaken out of exactly the recoveries the rule exists to catch.
* **The best ruin probability belongs to a row that fails the second half.**
  `vol-trail 2.5 ATR` nearly halves the shut-off risk and gives up half a
  point of return in the recent half. Not kept, and worth remembering.

Two rows cleared the decade bar, both marginally: `trail 1.0R, 3.0 ATR`
(+0.24 points) and `regime exit` (+0.08, on 713 trades — it barely fires).

### Thirty years decides — and both clear the gate by a rounding margin

| 30 years, honest fills | CAGR | maxDD | Sharpe | ruin | trades | PF | captured | 1st | 2nd |
|---|---|---|---|---|---|---|---|---|---|
| **HONEST BASELINE** | 5.10% | −15.2% | 0.64 | 26.0% | 1,522 | 1.39 | −0.94 | 1.88% | 8.28% |
| trail 1.0R, 3.0 ATR | 5.16% | −14.8% | 0.64 | 25.8% | 1,585 | 1.42 | −0.93 | 1.86% | 8.43% |
| regime exit | 5.13% | −15.2% | 0.64 | 25.6% | 1,523 | 1.40 | −0.94 | 1.88% | 8.33% |

Both pass the mechanical test — CAGR up, ruin not up, halves held. The
decade's +0.24 and +0.08 became **+0.06 and +0.03 CAGR points over thirty
years.** Sharpe is unchanged to two decimals. The regime exit changed one
trade in 1,523.

**Neither is adopted**, and the reason is the specification's own: a more
complicated model is not automatically a better one, and complexity without
measurable justification is a cost. Six hundredths of a point is about $60 a
year on this account. Implementing a trailing stop live means touching the
exit decision, the state file's stop ratchet, and the broker-side GTC stop
reconciler — the path where every serious bug in this project has lived. That
risk is not worth $60.

What is worth keeping from the trail: every column moved the right way by a
hair — drawdown, profit factor, ruin, second half. It is directionally right
and trivially small. Live exits now record `captured` and `gave_back`, so if
real trades show the stop leak the simulator shows (winners giving back 8% of
entry before the stop takes them), that is the moment to revisit it with
evidence from the account rather than the backtest.

The gate itself is worth a note. `passes()` allowed a 0.2-point tolerance on
each half so that noise in one half would not veto a real gain; it also let two
rounding-level gains through. The tolerance was right; the missing condition
was a minimum effect size, and the judgment above is what should have been
written into it.

## Crypto as the training ground

**A trailing stop on the BTC sleeve** — 2/3/4/6 ATR ran 74.7 / 61.0 / 63.0 /
65.2% against 64.0% for the plain 100-day rule, a sawtooth with one good cell
at the tightest setting and double the switches. Not kept.

**Meme coins**, at their measured spreads (DOGE 32 bps, SHIB 38, PEPE 29,
TRUMP 32, BONK 73 — against BTC's 2.6):

| coin | trend CAGR | maxDD | 1st | 2nd | hold CAGR |
|---|---|---|---|---|---|
| DOGE | 2.7% | −95.4% | −13.5% | +22.0% | 5.4% |
| SHIB | 0.8% | −72.1% | +46.3% | −30.4% | −10.4% |
| PEPE | −44.0% | −69.2% | −51.0% | −36.0% | −58.3% |
| TRUMP | −39.8% | −55.0% | −62.4% | −3.8% | −74.3% |

None holds in both halves; most lose outright. They stay tradeable instruments
with measured costs in `MEASURED_ROUND_TRIP`; nothing is allocated to them,
because no edge exists to justify it and the specification says not to force
trades.

## What this leaves

The rule's parameters were all at their optimum yesterday. Today's work found
that the emulator was flattering them, put the real exit-quality numbers on
the table for the first time, and priced every exit idea in the specification.
The learning loop, the live exit record, and the evaluation now all speak the
same language — `captured` and `gave_back` — so the next thing that helps can
be recognised when it appears.

Expected return, honestly: **5.1% a year over thirty years with realistic
fills; 2.2% on the survivorship-free ETF subset; ~8–9% on the decade.** With a
26% chance of a 25% drawdown somewhere in thirty years. That is the product.
