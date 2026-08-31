# Going live on Monday

## Read this first

These instructions make the bot **safe to run**. They do not make it
profitable, and the measured history says it is not:

| Rule | 2017–2023, held out | Profitable years |
|------|--------------------|-----------------|
| Trend gate | **−3.46%** | 3 of 8 |
| Mean reversion | **+2.28%** | 5 of 8 |
| SPY buy-and-hold | far higher | — |

Every intraday week tested lost money. The best result found anywhere in this
project is about **0.3% a year**, against a buy-and-hold that returned many
times that. Run it on the paper account. Do not fund it with money you cannot
lose, and understand that the evidence here points to losing slowly.

## 1. Create the paper account

At <https://alpaca.markets>, open an account and generate **paper** API keys.
I cannot create accounts or handle credentials — this step is yours.

Put the keys in `~/.zprofile` so scheduled runs inherit them, never in a file
inside the repo:

```bash
export APCA_API_KEY_ID=...
export APCA_API_SECRET_KEY=...
```

Open a new terminal, then confirm:

```bash
event-aware-trader account
```

## 2. Refresh data

```bash
cd ~/market-bot
for s in SPY QQQ XLK XLE XLF TLT GLD DIA IWM XLV XLP XLU XLI XLB XLY VNQ EFA EEM SLV USO; do
  ./.venv/bin/event-aware-trader fetch --symbol $s --period 2y --out data/$s.csv
done
```

## 3. Preflight

```bash
event-aware-trader preflight
```

Exit code 0 means safe to run. It verifies credentials, that the endpoint is
the **paper** host and not the live one, that all 20 price files exist and are
fresh, that no setting implies leverage, that the loss guards are set, that
sizing respects the risk cap, and that the strategy produces no malformed
plans. **Do not start anything if this fails.**

## 4. Rehearse

```bash
event-aware-trader autotrade --interval 1d
```

Without `--live` this does everything except send the order. Run it for
several sessions and read `data/autotrade-audit.jsonl`. You should see
`run_complete` entries and, most days, no entries at all — the rules average
about one trade per 51 sessions, so *nothing happening is the normal case.*

## 5. Go live on paper

```bash
scripts/run-autotrade.sh --interval 1d --live
```

Schedule it for 15:45 America/New_York on weekdays. With daily bars there is
exactly one decision per session, so running it more often re-reads an
unfinished bar.

## 6. Watch it in TradingView

Chart → Trading Panel → **Alpaca** → connect → choose the paper account.
Positions and fills placed by the bot appear on the chart. TradingView is the
window; it does not execute the orders.

## What protects you while it runs

| Guard | Behaviour |
|-------|-----------|
| Endpoint | Live Alpaca host refused outright — a typo cannot route to real money |
| Credentials | Environment only, never a file, never committed |
| Order submission | Two independent flags required; dry run is the default |
| Leverage | None. 95% of equity per position is the ceiling |
| Risk per trade | 0.5% of equity, enforced by rounding down |
| Daily guard | −1.5% from session open suspends new entries |
| Position cap | 3 open, one per correlation bucket |
| Per-run cap | Bounds a runaway loop |
| Exits | Deliberately *not* gated on the submission flags — a stop that cannot fire is worse than one that fires unexpectedly |
| Audit | Every decision, order, refusal and no-op appended to JSONL |

## Killing it

```bash
launchctl unload ~/Library/LaunchAgents/com.eventawaretrader.autotrade.plist
```

To flatten positions, do it from TradingView or the Alpaca dashboard directly.

## What to expect in week one

Most likely: **no trades at all.** As of Friday 2026-08-28 all 20 instruments
were `REJECT` or `WATCH` — ADX 11–16 against an 18 floor, most names below
their 20-day average. Two of the last three weeks produced zero trades.

That is the system working. A long-only trend rule that stands aside in a
directionless market is doing its job; the failure mode you should worry about
is it suddenly trading a lot.

## Verified state

- 168 tests passing
- No look-ahead: swing structure carries confirmation lag, signals are
  reproducible when future bars are replaced with extreme values
- Edge cases return REJECT rather than crashing: empty, flat, zero-volume,
  gapped, penny-priced, and monotonically collapsing series all handled
- NaN, infinite, and non-positive prices screened at the data boundary
- Positions can no longer be entered beyond their own stop after a gap
