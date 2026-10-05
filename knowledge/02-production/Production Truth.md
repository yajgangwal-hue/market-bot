---
title: "Production Truth"
authority: "FROZEN"
kind: "production-status"
generated: false
sources:
  - "src/event_aware_trader/broker.py"
  - "src/event_aware_trader/autotrade.py"
  - "src/event_aware_trader/mean_reversion.py"
  - "src/event_aware_trader/live_model.py"
  - "scripts/windows/session-run.ps1"
  - "scripts/windows/crypto-loop-worker.ps1"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
  - "docs/SPEC-0001-decision-boundary.md"
  - "docs/model-lineage.jsonl"
---

# Production Truth — what the bot actually does right now

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

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`. Scheduled-task
facts were read from Windows Task Scheduler, read-only, on the same date.*

This is the only page that describes live behaviour. Research notes never do.

## Active

| topic | what happens | source |
|---|---|---|
| **account** | Alpaca **paper** only; the broker refuses the live endpoint: “Refusing to run against the live trading endpoint. This project is paper-only” — [broker.py](../../src/event_aware_trader/broker.py) | [`broker.py::def _require_paper_endpoint`](../../src/event_aware_trader/broker.py) |
| **equity schedule** | task `EventAwareTrader` runs `session-run.ps1 -Live`, which calls `autotrade --asset-class equity` and appends `--live` | [`session-run.ps1::$TradeArgs = @('autotrade', '--asset-class', 'equity')`](../../scripts/windows/session-run.ps1); task arguments observed read-only |
| **entry** | long-only mean reversion: price ≥ $20, 20-day dollar volume ≥ $50M, close above its 200-day average, RSI(14) ≤ 35, ATR/close ≤ 3.5%; filled at the signal bar's own close in the last 20 minutes of the session | [[Frozen Strategy]], [[Frozen Parameters]], [[SPEC-0001]] §4.1 |
| **model score** | when a usable live model is loaded, candidates that already pass the hand-built gate are ranked by model score. `live_model_floor` defaults to 0.0. The score is not established as a calibrated win probability and does not justify confidence-based sizing | [`autotrade.py::live_model_ranking`](../../src/event_aware_trader/autotrade.py), [[Trading Decision Guardrails]] |
| **exit** | in order: stop; RSI(14) ≥ 60 (`reverted`); 20 sessions held (`time`); then, since 2026-09-28 (EXP-0055), a take profit at k_tp × entry ATR checked against the broker's mark (`take_profit`, [`autotrade.py::def _take_profit_for`](../../src/event_aware_trader/autotrade.py), [adaptive_exits.py](../../src/event_aware_trader/adaptive_exits.py)). Since 2026-10-03 (EXP-0056) the take profit also RESTS AT THE BROKER with the stop as one GTC OCO order (`broker.py::submit_protective_oco`); a refused OCO falls back to the standalone GTC stop in the same cycle. Since 2026-10-04 (EXP-0057) that take profit is the session's BOUNCE PRICE - the close that would put RSI(14) at 60, from the completed sessions ([`indicators.py::def bounce_price`](../../src/event_aware_trader/indicators.py)) - refreshed each session, never rested at or below the broker's mark. No trailing, partial, momentum, regime or limit exit | [`mean_reversion.py::def should_exit`](../../src/event_aware_trader/mean_reversion.py) |
| **stop** | 2.5 × ATR below the entry close, held as a broker-resident GTC order (“broker-resident GTC” — [pre-OOS audit](../../docs/2026-09-22-pre-oos-integrity-audit.md)). Under the frozen rule the stop is **never moved**: it “leaves the stop where it was placed and closes when the oversold” condition resolves — [autotrade.py](../../src/event_aware_trader/autotrade.py) | [`autotrade.py::if config.entry_rule == "mean_reversion":`](../../src/event_aware_trader/autotrade.py) |
| **stop coverage** | reconciled “every cycle, unconditional” — [pre-OOS audit](../../docs/2026-09-22-pre-oos-integrity-audit.md) | [[Operational Safeguards]], [[REM-0007]] |
| **sizing** | 0.5% of equity at risk over the stop distance, scaled 0.5×–1.5× by pullback depth, capped at 20% notional, at most 2% volume participation, whole shares | [[Frozen Strategy]] |
| **portfolio limits** | at most 12 positions, 1 per correlation bucket, 3 new entries per day | [[Frozen Parameters]] |
| **risk limits** | daily loss 1.5%, weekly loss 6%, mark-to-market guard on | [[Frozen Parameters]] |
| **cash** | idle cash above $2,000 parked in SGOV; 5% of equity withheld for the crypto sleeve | [[Frozen Strategy]], [[EXP-0014]], [[EXP-0015]] |
| **crypto** | a separate book. Task `EventAwareTraderCrypto` runs `session-run-crypto.ps1 -IntervalSeconds 30 -Live`, whose worker runs the BTC sleeve — “THE SLEEVE, not autotrade --asset-class crypto.” — [crypto-loop-worker.ps1](../../scripts/windows/crypto-loop-worker.ps1) — holding BTC at 5% of equity while BTC is above its 100-day average | [[Frozen Strategy]] |
| **benchmark** | SPY, total return | [[Benchmark]] |
| **fingerprint** | `da22011e7504759285255c8db0f17365bd8b755822774c9d936145d3537c237b` | [[Frozen Fingerprint]] |

## Explicitly inactive

| component | state | source |
|---|---|---|
| **learned model / ranker** | can reorder candidates when a usable model is loaded; floor 0.0 means the floor does not screen candidates. This rank score is not verified confidence or a calibrated trade probability. Older lineage notes describing the ranker as never consulted are stale relative to the current `autotrade.py` path | [`autotrade.py::live_model_ranking`](../../src/event_aware_trader/autotrade.py), [[Trading Decision Guardrails]] |
| **trade veto model** *(row added 2026-09-24)* | never consulted while `LEARNED_VETO_ENABLED = False`. Its weekly trainer sets `USABLE_AS_VETO` itself, so the flag is the only barrier, and the flag is not in the frozen fingerprint. UNPROVEN and unusable on 2026-09-24 — [learned-state snapshot](../../docs/model-state/pre-clean-oos-2026-09-24.json) | [`trade_learning.py::LEARNED_VETO_ENABLED = False`](../../src/event_aware_trader/trade_learning.py) |
| **news** | collected, not used. The crypto worker runs `record_news.py`, and it is “Print-only, like everything here that is not the sleeve” — [crypto-loop-worker.ps1](../../scripts/windows/crypto-loop-worker.ps1). “News is not in the money path and this specification does not put it there.” — [SPEC-0001](../../docs/SPEC-0001-decision-boundary.md) | [[SPEC-0001]] C-12 |
| **regime** | placeholder, not active: “not in PRODUCTION_CANDIDATE; mr_regime_exit absent” — [pre-OOS audit](../../docs/2026-09-22-pre-oos-integrity-audit.md) | [[SPEC-0001]] C-14 |
| **shorting** | “long-only; no short branch reachable” — [pre-OOS audit](../../docs/2026-09-22-pre-oos-integrity-audit.md) | [[Do Not Re-Research]] |
| **crypto trading rules** | not run; only the sleeve allocation runs | [[EXP-0003]] |
| **the 0.652% haircut** | a research-emulator charge only; the live loop has no such parameter | [[Frozen Strategy]] |

## Clean OOS

**0 sessions recorded; opens 2026-11-02 (projected): EXP-0057 moved the freeze to 2026-10-04 (EXP-0056 had it at 2026-10-03) — 2026-10-27 under EXP-0055, 2026-10-12 before.** Current detail,
including the recorder's scheduled-task state: [[Clean OOS]].

## Known deviations

Every accepted difference between the implementation and [[SPEC-0001]], and why
each was accepted: [[Accepted Non-Conformances]].
