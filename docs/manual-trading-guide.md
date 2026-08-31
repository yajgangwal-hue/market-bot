# Trading the rules by hand through TradingView

This is Option B: TradingView is your chart and order ticket, a broker you
connect inside it holds the money, and you place the trades. Nothing in this
repo contacts a broker or places an order.

The bot's job here is to answer one question each morning: **what, if
anything, do I do today?**

## Why this needs a tool at all

The exit rule is a *trailing* stop. It moves. On the best trade in the two-year
record the stop had to be raised on eight separate sessions:

```
2026-01-14   hold, stop stays 411.20      (trade has not earned 0.5R yet)
2026-01-20   raise stop 411.20 -> 420.25
2026-01-21   raise stop 420.25 -> 429.44
2026-01-22   raise stop 429.44 -> 434.07
2026-01-23   raise stop 434.07 -> 439.94
2026-01-26   raise stop 439.94 -> 449.80
2026-01-27   raise stop 449.80 -> 456.16
2026-01-28   raise stop 456.16 -> 473.47
2026-01-29   SELL - the low traded through the stop
```

That trade returned **+4.16R**. Forget to move the stop for a week and you are
not running the rule that made it worth taking.

## One-time setup

1. **TradingView**: connect a supported broker from the chart's Trading Panel,
   and set the account to **paper** while you are learning. A free plan is
   enough — Option B needs no webhooks and no paid tier.
2. **Optional chart overlay**: paste `tradingview/event_aware_gate.pine` into
   the Pine Editor and add it to the chart, so you can see the gate and the
   trailing stop drawn on the same screen you trade from. Read the header
   first: Pine runs one symbol per chart and does not know about the shared
   account, so treat its Strategy Tester numbers as per-symbol only.

## The daily routine

Once a day, after the close. It takes about a minute.

```bash
cd ~/market-bot
./.venv/bin/event-aware-trader brief --account 1000 --refresh --apply-stops
```

- `--refresh` downloads fresh daily bars first.
- `--apply-stops` writes the new stop levels back to `data/positions.json`, so
  tomorrow's brief knows where the ratchet got to. Leave it off for a
  read-only preview.

The output has two halves.

**`manage_existing`** — one instruction per position you hold:

| action | what to do in TradingView |
|--------|--------------------------|
| `HOLD` | nothing |
| `RAISE_STOP` | move the stop order up to `new_stop` |
| `EXIT` | sell at market; the stop has been traded through |

**`new_candidates`** — anything that cleared the gate, each with the exact
share count for your equity, the stop to place, and the dollar risk if it is
hit. **Review it before you act.** It is a suggestion, not an order.

Most days both halves are empty and the summary reads *"Nothing to do. Hold
everything, place nothing."* That is the normal outcome — the rules average
about **one trade per 51 sessions**. During the week of 2026-08-24 the bot
looked at 35 symbol-sessions and opened nothing.

## After you fill an order

The bot cannot see your broker, so tell it what you actually got — your real
fill price, not the reference close:

```bash
./.venv/bin/event-aware-trader record \
  --symbol GLD --quantity 0.3641 --price 424.84 \
  --stop 411.20 --date 2026-01-13
```

After you sell:

```bash
./.venv/bin/event-aware-trader close --symbol GLD
```

`data/positions.json` is plain JSON. Read it, correct it by hand if you fat-
finger something, and keep it in step with the broker — every stop level the
brief computes is derived from what is in that file.

## Habits that matter more than the code

- **Record your real fill price.** Sizing and every future stop are computed
  from it. A guessed entry price quietly corrupts the whole trade.
- **Place the stop the moment the buy fills**, not later in the day.
- **Never widen a stop.** The ratchet only goes up. Widening one converts a
  planned 0.5% loss into an unplanned one, which is the single most reliable
  way retail accounts are damaged.
- **Skip a signal you do not understand.** A rejected trade is a valid outcome
  and costs you nothing.
- **`data/` is gitignored**, so your position book never lands on GitHub.

## What this does not fix

The strategy still returned **+3.93% over two years** against SPY's **+37.79%**
in the same window, on seven closed trades — a sample far too small to conclude
anything. Doing this by hand does not improve the edge. It just means the exit
rule actually runs, and that you build a real record to judge it by.
