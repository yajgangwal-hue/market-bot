# How the bot turns open positions into recognized gains

*2026-10-05, 10:15 pm PT. The owner asked:*

> "ok the keys should be up to date now, also make sure that the bot has a
> solid plan to make recognized gain"

## The answer

**Yes, the plan is in place, with two checks left:**
1. **Restart the PC.**
2. **Tuesday's first cycle at 6:30 am confirms the account.**

| | Status |
|---|---|
| The bot remembers every open position | ✅ restored tonight (REM-0011) |
| Every position has a take profit above its purchase price | ✅ +2.9% to +9.6% (table below) |
| The take profit rests at Alpaca as a real order | ⏳ placed by Tuesday's first cycle, first live test |
| A fill at Alpaca is booked as a realized gain | ✅ from the broker's actual fills; now also after more than 100 fills (REM-0012) |
| The bot's own sales are booked at the confirmed fill price | ✅ (your change of 2026-10-04) |
| The crypto part works | ❌ still running the old, dead key: **restart the PC** |

## What went wrong today

- **The first key you made opened a new, empty paper account.** All of
  Monday's equity cycles ran there.
- **At 6:30 am** the bot couldn't find its 7 positions there, so it deleted
  its records of them.
- **At 12:45 pm** it bought JNJ, SCHD and XLF in that new account.
- **Your 7 positions stayed in the original account.** Their stop orders
  protected them, but nothing managed them: no take-profit orders, no
  exits.
- **Once you regenerated the original account's keys,** the old key stopped
  working: the crypto part now gets "unauthorized". That confirms the
  exposed key is finally dead.

## What I did tonight

1. **Put the bot's records of all 7 positions back** from Saturday's backup:
   original stops, the corrected entry dates, and the entry details the
   learner needs (`scripts/restore_positions.py`, REM-0011).
2. **Set aside the records of JNJ, SCHD and XLF** from the new account, so
   they can't be confused with your original SCHD.
3. **Reset this week's loss-guard starting point.** It had been set from the
   new account's $100,000; it is now your original account's $97,310.39.
4. **Fixed a weak spot in booking gains.** When a take profit fills at
   Alpaca, the bot rebuilds the trade from the broker's fills. It used to
   look only at the account's last 100 fills, so a position held through a
   busy few weeks could have its gain never booked. It now reads further
   back when it needs to (REM-0012, 8 new tests).
5. **Ran all 1,514 tests: all pass.**

## The plan for each position

From Monday's close. The take profit is approximate; the exact level is set
by Tuesday's first cycle.

| Position | Bought at | Monday close | Stop (loss limit) | Take profit | Gain at take profit | Must sell by |
|---|---:|---:|---:|---:|---:|---|
| CVS | 87.45 | 87.01 | 81.71 | ~95.09 | +8.7% | Oct 19 |
| IWM | 282.10 | 283.38 | 273.19 | ~292.75 | +3.8% | Oct 21 |
| MDY | 664.57 | 672.27 | 647.13 | ~686.77 | +3.3% | Oct 22 |
| SCHD | 33.32 | 32.72 | 32.49 | — | — | probably already sold by its stop |
| SCHW | 98.36 | 97.96 | 92.84 | ~107.78 | +9.6% | Oct 29 |
| UNP | 269.87 | 277.06 | 254.77 | ~290.01 | +7.5% | Oct 19 |
| VZ | 46.34 | 45.85 | 43.61 | ~49.52 | +6.9% | Oct 20 |

**SCHD** traded down to $32.36 on Monday, below its $32.49 stop. The stop
was resting at Alpaca, so it most likely sold SCHD for a loss of about
2.5%. Tuesday's first cycle will find it gone and book the loss from the
broker's fills.

The take-profit levels came from Yahoo's daily closes (free, no key).
Alpaca's bars may differ by a few cents.

## How a gain gets recognized

| What happens | Who sells | How it's booked |
|---|---|---|
| Price reaches the take profit | Alpaca, through the resting order, even with the PC off | From Alpaca's actual fills, at the next cycle |
| The bounce completes (RSI ≥ 60) or price is already past the take profit | The bot, at its next check | From the broker-confirmed fill price |
| 20 sessions pass | The bot | Same; this can be a gain or a loss |
| Price falls to the stop | Alpaca, through the resting stop | From the fills; a loss, capped by the stop |

**No plan can promise a gain on every position.** The stop and the
20-session limit exist to end trades that don't work.

## What to check

**Tonight, you:**
- **Restart the PC.** The crypto part is still running the dead key, and I
  wasn't allowed to restart it myself.

**Tuesday, after 6:30 am**, in `data/autotrade-audit.jsonl` (or ask me to
check):
- **The right account.** The first `run_complete` should show account
  equity near $97,000, not $100,000.
- **The orders.** For each position: one `sell_order_canceled`, then one
  `protective_stop_placed` with `order_class: oco` and a `take_profit`.
  `protective_oco_FAILED` would mean Alpaca refused it; the plain stop is
  then restored in the same cycle, and the bot itself sells at the take
  profit.
- **SCHD.** A `learned_from_external_exit` for SCHD means its stop sale was
  booked.

## The other account

The new account still holds JNJ, SCHD, XLF and about $43,000 of SGOV,
under their stops. Nothing manages them now. They are paper: close them in
Alpaca, or delete that paper account.

## Futures and TradingView

**Don't send me TradingView login details.** TradingView has no way for a
program like the bot to place trades in its paper account; that account is
for trading by hand.

The bot can paper trade futures through **Interactive Brokers** instead:
1. Open a full IBKR account. It comes with a $1,000,000 paper account.
2. Install IBKR's "IB Gateway" program on this PC and sign in to it
   yourself. The bot talks to the gateway on this PC, so your password never
   goes to the bot or to me.
3. Then I build the futures side, paper only, as a separate account from
   the Alpaca stock bot. It will run H-0039's trend strategy
   (`docs/2026-10-04-futures-trend-h0039.md`).
