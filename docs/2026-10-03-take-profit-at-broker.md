# The take profit rests at the broker beside the stop (EXP-0056)

*2026-10-03. A live change made on the owner's instruction. Uncommitted.*

> "The bots current trades that it has open doesn't all have stop losses or
> take profits or at least there not viewable on TradingView or the trades
> that were existing before the take profits and stop losses were added
> don't have them so fix that"

## What was actually true before the change

| | Stop loss | Take profit |
|---|---|---|
| Is there one? | **Yes, for all 7 open positions.** Each was covered by a GTC stop order resting at Alpaca, all shares, at the 2026-10-02 close (`stop_coverage`: fully_protected). This includes the older positions. | **Yes, for all 7.** Older positions got theirs on 2026-09-29, from their own entry ATR. |
| Is it a broker order? | Yes | **No.** It lived only in the bot, which checked the broker's price every 15 minutes. |
| Visible on TradingView through the Alpaca connection? | Yes | **No.** TradingView only draws broker orders. |
| Works with the PC off? | Yes | **No** |

So the complaint was half right. Nothing was missing from the bot, but the
take profit was invisible on TradingView and inert whenever the bot was not
running.

## What changed

Every equity position now rests on **one GTC OCO order** (one-cancels-other)
at Alpaca:

- the take profit as a sell **limit**, the parent;
- the stop as a sell **stop**, the child.

When one fills, Alpaca cancels the other. Both appear on any chart connected
to the account.

**Existing positions.** On the first cycle (Monday 2026-10-05, about 06:30
PT), the bot does the following for each one:

1. cancels its standalone stop;
2. submits the OCO with the position's own remembered levels;
3. re-reads the broker to confirm the stop half is resting.

| | Stop | Take profit | Shares |
|---|---:|---:|---:|
| CVS | 81.71 | 93.19 | 124 |
| IWM | 273.20 | 291.01 | 35 |
| MDY | 647.13 | 682.01 | 26 |
| SCHD | 32.49 | 34.15 | 388 |
| SCHW | 92.84 | 103.85 | 142 |
| UNP | 254.77 | 284.97 | 48 |
| VZ | 43.61 | 49.07 | 174 |

The levels do not move. The table shows them rounded to the cent, as
Alpaca will receive them.

**New positions** get their OCO in the same cycle as the entry, where the
standalone stop used to go.

## Safety rules built in

- **Protection comes first.** If Alpaca refuses the OCO, the bot places the
  plain GTC stop in the same cycle, exactly as before. The take profit then
  stays checked by the bot for the rest of that session, and the OCO is
  retried the next session rather than every 15 minutes. A position is never
  left without a stop because of this change. The refusal is logged as
  `protective_oco_FAILED`.
- **Cancel before submit.** The old order reserves the shares, so it has to
  go first. This is the same brief window every stop replacement already
  had.
- **No churn.** A correct OCO already at the broker is left alone. A wrong one
  is replaced whole, never half kept. Keeping one half of an OCO alone is
  never allowed: it protects nothing, it still holds the shares, and
  cancelling its sibling can take it down too.
- **Exits.** RSI, the time limit and the 15-minute take-profit backstop all
  cancel both halves before closing.
- **Reading the orders.** The bot now reads open orders with `nested=true`.
  A GTC stop half sitting in Alpaca's `held` status for weeks is always seen
  under its open parent; it can no longer age out of the order history.
- **Monitoring.** Each cycle's `stop_coverage` row now also reports
  `resting_take_profit_quantity`.
- **Reports.** A position that closes at or above its take profit is
  labelled "closed at or above its take profit (consistent with the resting
  take-profit order)".

## What is verified and what is not

**Verified:**

- All 1,393 tests pass with every network call blocked (0 attempts).
- Fourteen new tests run through the bot's real cycle, `run_once`
  (`tests/test_broker_take_profit.py`). They cover:
  - an old position moved to an OCO, with the cancel before the submit;
  - a correct OCO left alone;
  - a wrong take profit replaced whole;
  - a refused OCO falling back to the plain stop in the same cycle, and not
    retried that session;
  - switched off, and adaptive exits off;
  - an exit cancelling both halves;
  - the coverage check counting the held stop half;
  - the exact request body sent to Alpaca.
- The scheduled `autotrade --asset-class equity` command builds its
  configuration with the setting on.

**Not verified against the live API.** No API calls are allowed while the
Alpaca key is unrotated.

- The request follows Alpaca's documented exit-only OCO and its staff's
  example:
  - `order_class "oco"`, `type "limit"`, `time_in_force "gtc"`;
  - `take_profit.limit_price` and `stop_loss.stop_price`, prices to the cent;
  - no top-level `limit_price`.
- How Alpaca reports the two halves (statuses), and what cancelling one does
  to the other, are not documented. The code assumes the harder case: one
  cancel takes both.
- The first live cycle will settle it. Look in `data/autotrade-audit.jsonl`
  for:
  - `protective_stop_placed` with `"order_class": "oco"`, which means it
    worked;
  - `protective_oco_FAILED`, which means it was refused and the plain stop
    went in instead.

## Governance

- **EXP-0056** in `docs/experiments.jsonl`: accepted, evidence `weak`. The
  only evidence is the simulation bracket. A take profit filled on a touch,
  which is what a resting limit is, gave 5.75% a year. The 15-minute check
  modelled with a 5 bp margin gave 5.53%.
- **New setting:** `AdaptiveExitConfig.take_profit_at_broker = True`.
  `False` restores EXP-0055 exactly.
- **Fingerprint:** `da857ab7…a8c` became
  **`ab33087cf80958d74e3b8d593e454f0dc5200bd98c6c25a32547e4be1d0a0758`**. It
  is re-pinned, with its history, in:
  - `tests/test_phase4_observation.py`;
  - `tests/test_spec0001_exit_boundary.py`;
  - `scripts/phase4_checkpoint.py`;
  - `scripts/preoos_dry_run.py`.
- **Freeze:** 2026-10-03. **The first clean session moves to 2026-11-02**
  (it was 2026-10-27). No clean session had been recorded, so nothing is
  lost but the five sessions.
- **Code changed:**
  - `broker.py`: `submit_protective_oco`; `open_orders` reads nested legs and
    limit prices.
  - `autotrade.py`: the reconciler, `close_out`, the coverage check and the
    external-exit labels.
  - `adaptive_exits.py`: the new setting.
  - `daily_report.py`: the take-profit label.
  - `scripts/tradingview_levels.py`: the chart header now says where the take
    profit rests.
  - `tests/fake_broker.py`: OCO behaviour.

## Seeing it on TradingView

- **The broker panel (Alpaca connected).** After Monday's first cycle each
  held symbol's chart shows two order lines, the take-profit limit above and
  the stop below.
- **The indicator, which shows more.** `tradingview/live-levels.pine` is
  rewritten every 15 minutes. It draws both levels, the dollars at stake and
  the expected result. Paste it again after the bot opens or closes a
  position.
