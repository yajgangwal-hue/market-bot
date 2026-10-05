---
title: "Frozen Strategy"
authority: "FROZEN"
kind: "strategy"
generated: false
sources:
  - "src/event_aware_trader/mean_reversion.py"
  - "src/event_aware_trader/autotrade.py"
  - "src/event_aware_trader/research.py"
  - "src/event_aware_trader/risk.py"
  - "src/event_aware_trader/crypto_sleeve.py"
  - "src/event_aware_trader/live_model.py"
  - "scripts/windows/crypto-loop-worker.ps1"
  - "docs/experiments.jsonl"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/remediations.jsonl"
---

# Frozen Strategy

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

> [!warning] Updated 2026-09-28 — EXP-0055 changed the strategy
> The owner's adaptive volatility exits are live from the session of 2026-09-29.
> - **Take profit:** every position also has one. Since 2026-10-04 (EXP-0057)
>   it is the session's bounce price - the close that would put RSI(14) at 60 -
>   refreshed each session; before that, k_tp × its entry ATR (2.5). It is
>   checked against the broker's mark after the stop, the bounce exit and the
>   20-session cap, and rests at the broker (EXP-0056).
> - **Learning:** a slow rule may move the stop multiple one step at a time
>   (and k_tp too, in the take-profit mode "atr" that EXP-0057 replaced).
> - **Freeze:** moved to 2026-09-28, to 2026-10-03 by EXP-0056 (the take profit
>   rests at the broker with the stop as one OCO order), then to 2026-10-04 by
>   EXP-0057 (the take profit is the bounce price).
> - **Fingerprint:** now `448170c3364935560663048c59647dfb5b204c6e6c724ce603f0d61c476e0f29`
>   (EXP-0057; `ab33087c…758` under EXP-0056, `da857ab7…a8c` under EXP-0055)
>   (was `da22011e…c237b`).
> - **First clean session:** still 2026-11-02 under EXP-0057 (2026-10-27 under EXP-0055; was 2026-10-12).
>
> Where this note says otherwise below, [the change record](../../docs/2026-09-28-adaptive-exits.md)
> and EXP-0055, EXP-0056 and EXP-0057 in `docs/experiments.jsonl` govern;
> the take-profit change is recorded in [its implementation note](../../docs/2026-10-04-bounce-take-profit-live.md).

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

The strategy frozen for Clean OOS, as the code implements it. Exact values are
in [[Frozen Parameters]], which is generated from the configuration objects;
decision timing is governed by [[SPEC-0001]]; what runs day to day, including
safeguards, is [[Production Truth]].

## Identity

- Fingerprint `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` — [[Frozen Fingerprint]].
- Research freeze **2026-09-11**, set by the last config-changing ledger entry, [[EXP-0017]] — [[Clean OOS]].
- Frozen baseline **+58.5889000000% / 698 trades** — [[Frozen Baseline]].

## The equity rule

Long-only mean reversion over the 230 equity and ETF symbols of
`strategy.DEFAULT_UNIVERSE`.

### Entry

[`mean_reversion.py::def evaluate`](../../src/event_aware_trader/mean_reversion.py)
returns BUY only when **every** check passes on bars up to and including the
decision bar:

| check | frozen value | `MeanReversionConfig` field |
|---|---|---|
| close at or above the minimum price | $20 | `min_price` |
| 20-day average dollar volume at or above the floor | $50,000,000 | `min_average_dollar_volume` |
| close strictly above its 200-day simple average | 200 days | `trend_ma_days` |
| RSI(14) at or below the entry level | 35 | `rsi_entry`, `rsi_period` |
| ATR(14) / close at or below the ceiling | 3.5% | `max_atr_fraction`, `atr_days` |
| stop = close − 2.5 × ATR is positive | 2.5 | `stop_atr_multiple` |

### Exit

[`mean_reversion.py::def should_exit`](../../src/event_aware_trader/mean_reversion.py)
checks, in this order:

1. **stop** — the bar's low at or below the stop, on a session strictly after the entry;
2. **`reverted`** — RSI(14) at or above 60 (`rsi_exit`);
3. **`time`** — `bars_held` at or above 20 (`max_holding_bars`).

In live trading the stop is also a broker-resident order — see
[[Production Truth]]. `research.PRODUCTION_CANDIDATE` has exactly six keys and
no take-profit, trailing, partial, momentum, regime or limit-exit key:
“PRODUCTION_CANDIDATE has exactly 6 keys” —
[pre-OOS integrity audit](../../docs/2026-09-22-pre-oos-integrity-audit.md);
the keys themselves are listed in [[Frozen Parameters]].

### Entry timing

Orders fill at the signal bar's own close (`entry_fill = "signal_close"`),
entering during the last 20 minutes of the session (`entry_window_minutes = 20`).

- Adopted by [[EXP-0016]]: “SHIPPED as the 15:45 window” —
  [experiments.jsonl](../../docs/experiments.jsonl).
- The 20-minute length comes from [[EXP-0017]], recorded as `reverted`:
  “entries fire on the first cycle so 30 made 15:30 the default; corrected to
  20” — [experiments.jsonl](../../docs/experiments.jsonl).

### Sizing and limits

| rule | frozen value | source field |
|---|---|---|
| risk per trade, over the stop distance | 0.5% of equity | `RiskPolicy.risk_per_trade` |
| conviction multiplier on that size | 0.5× – 1.5×, from the depth of the pullback below the 20-day high | [`mean_reversion.py::def conviction`](../../src/event_aware_trader/mean_reversion.py) |
| notional cap per name, applied after conviction | 20% of equity | `RiskPolicy.max_notional_fraction` |
| volume participation cap | 2% | `RiskPolicy.max_volume_participation` |
| whole shares only | yes | `production_policy()` |
| open positions | at most 12 | `RiskPolicy.max_open_positions` |
| names per correlation bucket (30 buckets) | at most 1 | `RiskPolicy.max_per_bucket` |
| new entries per day | at most 3 | `max_entries_per_day`, `max_orders_per_run` |
| daily / weekly loss guard | 1.5% / 6% | `RiskPolicy.max_daily_loss`, `max_weekly_loss` |

Conviction is applied in the live loop only under the mean-reversion rule —
[`autotrade.py::scale = conviction(daily_bars(candidate.symbol))`](../../src/event_aware_trader/autotrade.py)
— and the 20% cap is re-applied after it.

### Cash

- Idle cash above a $2,000 floor is parked in SGOV — [[EXP-0014]].
- 5% of equity is withheld from equity sizing for the crypto sleeve:
  “SET TO 0.05 on 2026-09-10 for the crypto sleeve, which holds BTC at 5%” —
  [autotrade.py](../../src/event_aware_trader/autotrade.py)
  (`reserved_fraction`).

### What the emulator charges

Half-spread 2 bps and slippage 4 bps (`CostModel`), and a **0.652%
exit-timing haircut** on rule exits (`rule_exit_timing_haircut`). The haircut
is a modelling charge applied only inside the research emulator, which
`research.py` describes as an uncertainty adjustment rather than an observed
price; the live loop has no such parameter. Its history: [[H-0008]],
[[H-0012]], [[H-0013]].

## The crypto sleeve — a separate book

Not part of the equity rule. Clean OOS records it separately, and
“equity_sleeve_return is the HEADLINE candidate metric” —
[remediations.jsonl](../../docs/remediations.jsonl) ([[REM-0005]]).
It is an allocation, held or not held: “BTC above its own 100-day average ->
hold the sleeve in BTC” —
[crypto_sleeve.py](../../src/event_aware_trader/crypto_sleeve.py). It runs from
the crypto task, and the worker states: “THE SLEEVE, not autotrade
--asset-class crypto.” —
[crypto-loop-worker.ps1](../../scripts/windows/crypto-loop-worker.ps1).
Accepted as [[EXP-0015]]. It has no broker-resident stop — item 5 of
[[Accepted Non-Conformances]].

## How it came to be frozen

The core rule and its parameters — RSI 35/60, the 2.5-ATR stop, the 20-bar
cap, the 3.5% ATR ceiling — **predate the experiment ledger**, whose first row
is dated 2026-09-08. Their rationale is recorded in the comments of
`mean_reversion.py` and in early reports ([[Reports Catalogue]]).

Since the ledger began, exactly five rows changed the shipped configuration —
the only rows whose decision is config-changing (`accepted` or `reverted`):

| ledger row | decision | effect on the frozen strategy |
|---|---|---|
| [[EXP-0004]] | reverted | the 200-day trend filter stays on: “shipped, then reverted by the owner after one red day; the drawdown is the filter's purpose” — [experiments.jsonl](../../docs/experiments.jsonl) |
| [[EXP-0014]] | accepted | idle cash parked in a T-bill ETF |
| [[EXP-0015]] | accepted | the 5% BTC sleeve |
| [[EXP-0016]] | accepted | fill at the signal bar's own close |
| [[EXP-0017]] | reverted | entry window at 20 minutes; its date is the research freeze |

## Not part of the frozen strategy

| branch | state | source |
|---|---|---|
| news | not in the money path | [[SPEC-0001]] C-12 |
| regime | placeholder, not active | [[SPEC-0001]] C-14 |
| learned ranking / veto | `LEARNED_RANKING_ENABLED = False`; `LEARNED_VETO_ENABLED = False` (`trade_learning.py`; neither switch is in the frozen fingerprint); `live_model_floor = 0.0` | [[Frozen Parameters]], [[Clean OOS]] |
| shorting | long-only | [[Production Truth]] |
| crypto *trading* | rejected; the sleeve is an allocation | [[EXP-0003]] |

Every other idea tested is in [[Do Not Re-Research]]; none of it is part of
this strategy.
