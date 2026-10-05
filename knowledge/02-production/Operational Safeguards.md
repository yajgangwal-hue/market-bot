---
title: "Operational Safeguards"
authority: "FROZEN"
kind: "production-status"
generated: false
sources:
  - "src/event_aware_trader/broker.py"
  - "src/event_aware_trader/autotrade.py"
  - "src/event_aware_trader/research.py"
  - "src/event_aware_trader/forward.py"
  - "scripts/record_clean_session.py"
  - "scripts/windows/stop-everything.ps1"
  - "scripts/windows/record-clean-session.ps1"
  - "docs/remediations.jsonl"
  - "docs/2026-09-22-pre-oos-integrity-audit.md"
---

# Operational Safeguards

> [!note] FROZEN — the frozen strategy as implemented
> Read from the linked sources at build time. If this note and a source differ, **the source governs**.

*Snapshot: built 2026-09-23 against repository HEAD `0d9ce4b`.*

The mechanisms that stop the bot from doing something it should not. Each row
names the code that implements it and, where there is one, the test.

## Broker

| safeguard | implementation |
|---|---|
| paper account only | [`broker.py::def _require_paper_endpoint`](../../src/event_aware_trader/broker.py) |
| two independent switches before any order: “It submits nothing unless the caller passes allow_order_submission=True and the individual call passes dry_run=False.” — [broker.py](../../src/event_aware_trader/broker.py) | `broker.py` |
| credentials only from the environment, never from a file | `broker.py` module docstring |

## Protective stops

| safeguard | implementation | evidence |
|---|---|---|
| a broker-side stop is required | `AutoTradeConfig.require_broker_side_stop = True` — [[Frozen Parameters]] | |
| stops sized from the settled fill, not a stale position read | [`autotrade.py::def _entry_fills_this_cycle`](../../src/event_aware_trader/autotrade.py), [`autotrade.py::STOP_SETTLEMENT_ATTEMPTS`](../../src/event_aware_trader/autotrade.py) | [[REM-0007]]; `tests/test_stop_coverage_race.py` |
| coverage verified after placement | [`autotrade.py::def _verify_stop_coverage`](../../src/event_aware_trader/autotrade.py) | [[REM-0007]] |
| stops reconciled every cycle, unconditionally | [`autotrade.py::def _reconcile_protective_stops`](../../src/event_aware_trader/autotrade.py) | pre-OOS audit §B |
| an exit cancels its stop | | `tests/test_exit_cancels_stop.py` |
| stopping the scheduler leaves stops in place: “This stops the SCHEDULER. It does not close positions, and it does leave them” protected — [stop-everything.ps1](../../scripts/windows/stop-everything.ps1) | `scripts/windows/stop-everything.ps1` | its other comments are partly stale — see [[Conflicts and Ambiguities]] |

## Trading limits

| safeguard | value |
|---|---|
| market must be open | `require_market_open = True` |
| entry window | last 20 minutes of the session |
| new orders per run / entries per day | 3 / 3 |
| daily and weekly loss guards | 1.5% / 6% |
| mark-to-market guard | on |

All values: [[Frozen Parameters]].

## Research and Clean OOS

| safeguard | implementation |
|---|---|
| a historical dataset can only be read for a declared purpose, and every read is recorded | [`research.py::def check_dataset_gate`](../../src/event_aware_trader/research.py); `docs/dataset-uses.jsonl` |
| forward observations cannot reach research code | [`forward.py::def reject_forward_data`](../../src/event_aware_trader/forward.py) |
| the recorder refuses “before the embargo expires, on a session already recorded, on a fingerprint change, or when the loop left no completed run for the day” — [record-clean-session.ps1](../../scripts/windows/record-clean-session.ps1) | `scripts/record_clean_session.py` — [[Clean OOS]] |
| preregistration is hash-chained and sealed before measurement | `docs/preregistrations.jsonl` — [[Governance Ledgers]] |

## What these safeguards do not guarantee

The accepted limits — the cancel-before-submit window, a crash spanning the
close, and the crypto sleeve having no broker stop — are listed with their
exact wording in [[Accepted Non-Conformances]]. None of the rows above should
be read as a claim that protection is continuous in every failure mode.
