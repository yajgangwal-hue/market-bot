# Full automation, intraday support, and a one-month test

## What now runs without you

```bash
event-aware-trader autotrade --interval 1d --live
```

One cycle: fetch bars, read what the broker actually holds, move every
trailing stop, close anything through its stop, open whatever qualifies,
append everything to an audit log. No prompts, no confirmation, no manual
step. `scripts/run-autotrade.sh` wraps it for a scheduler.

Without `--live` it is a dry run — it does everything except send the order.
Run it that way for a few sessions first.

Guards, checked against what the **broker** reports rather than local belief:

| Guard | Behaviour |
|-------|-----------|
| Endpoint | Live Alpaca host refused outright; paper only |
| `max_open_positions` | 3, counted from broker positions |
| Correlation bucket | One position per bucket |
| Daily loss guard | −1.5% from session open suspends new entries |
| `max_orders_per_run` | Bounds a runaway loop |
| Audit | Every decision, order, refusal, and no-op appended to JSONL |

Exits are deliberately *not* gated on the two submission flags. A stop that
fails to fire because a flag was unset is worse than one that fires
unexpectedly.

## Execution venue

**TradingView paper trading cannot receive these orders.** It exposes no
public API and cannot be driven from code — this is TradingView's design, not
a limitation of this project. Orders go to an **Alpaca paper account**: also
free, also fake money, but with a real API. TradingView stays useful as the
chart; `tradingview/event_aware_gate.pine` still draws the same gate.

## Intraday support

Three changes were needed before the strategy could run on anything but daily
bars:

1. **`StrategyConfig.for_interval()`.** The score's magnitude bounds were
   literals tuned to daily bars — a 3% gap between the 20- and 50-bar
   averages, a 4% five-bar move. Fifteen-minute bars are about a seventh that
   size, so every magnitude component scored near zero: 174 candidates cleared
   every blocker and exactly one ever cleared the score. Bounds now scale by
   `1/sqrt(bars per session)`. Only the *scale* changes; which blockers are
   hard, what the score weighs, and how the stop trails are identical.
2. **The portfolio simulator was daily-only by construction.** It keyed bars
   by `.date()`, which collapsed the 26 fifteen-minute bars of a session into
   one and silently discarded 25. It now keys on the full timestamp, while the
   loss guards still bucket by day and ISO week.
3. **Overnight holds.** Positions carry across sessions on every interval —
   nothing force-flattens at the close.

## The one-month test

23 sessions, 2026-07-29 to 2026-08-28, one shared $1,000 account.

| | Trades | Win / loss | Result |
|---|-------|-----------|--------|
| Daily bars | **0** | — | $1,000.00 (nothing qualified) |
| 15-minute, 6bp cost | 16 | 4 / 12 | **$991.20 (−0.88%)** |
| 15-minute, 3bp cost | 17 | 5 / 12 | **$998.19 (−0.18%)** |
| SPY buy-and-hold | — | — | **$1,039.70 (+3.97%)** |

Trading 16 times in a month lost money. Holding one ETF and doing nothing made
+3.97%.

### Why, precisely

| | 6bp | 3bp |
|---|-----|-----|
| Trades | 16 | 17 |
| Gross edge | +$6.19 | +$6.93 |
| Round-trip friction | **−$14.99** | **−$8.74** |
| Net | −$8.80 | −$1.81 |
| Friction as % of account, in one month | **1.50%** | 0.87% |

The gross edge is real but small and roughly **fixed per trade**. Friction is
also per trade. Trading more often multiplies both, and friction is the larger
of the two, so frequency moves the result *down*. At 6bp the friction alone is
about 18%/year on a $1,000 account.

This is arithmetic on your own data, not an opinion about day trading. There
is no setting that reverses it — a faster interval is a bigger denominator on
the same edge. The lever that would matter is a strategy with more edge per
trade, which is a research problem, not a configuration one.

### On the one-month horizon

Planning for one month does not make returns arrive faster; it makes the
sample smaller. Zero daily trades and 16 intraday trades are both too few to
distinguish skill from luck — a 25% win rate on 16 trades and a 71% win rate
on 7 have overlapping confidence intervals. The two-year record exists to give
the numbers something to stand on.

## Recommended setup

```bash
# 1. paper keys in ~/.zprofile so scheduled runs inherit them
export APCA_API_KEY_ID=...
export APCA_API_SECRET_KEY=...

# 2. rehearse — does everything except send the order
event-aware-trader autotrade --interval 1d

# 3. once the dry runs look right, let it trade
scripts/run-autotrade.sh --interval 1d --live
```

Daily is the recommended interval: it is the only one with positive expectancy
in testing. `--interval 15m` works and is fully supported; the table above is
what it did.

Schedule step 3 for 15:45 America/New York on weekdays. With daily bars there
is exactly one decision per session, so running it more often re-reads an
unfinished bar and changes nothing.
